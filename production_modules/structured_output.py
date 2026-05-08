"""
Structured output from LLM — the single place in the codebase that makes
classification LLM calls. Both approaches accept a system_prompt argument
so the caller (graph node or retry wrapper) controls prompt content without
touching LLM wiring.

# PRODUCTION NOTE: In a real system, prefer function-calling (approach 1) as
# it is more reliable and model-native. Fall back to JSON mode only for models
# that don't support tool/function calling. Always validate the output with
# Pydantic regardless of which approach you use.
"""

# Standard library imports for JSON parsing, file system operations, and Python path manipulation
import json      # Used to serialize/deserialize Pydantic schemas and parse LLM responses in JSON mode
import os        # Required to read environment variables (OPENAI_API_KEY, DEFAULT_MODEL)
import sys       # Used to modify Python's module search path for importing from parent directory

# Add parent directory to sys.path so we can import schema.py from the parent folder
# This allows the relative import to work when running from different locations
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Third-party imports for environment configuration and LLM integration
from dotenv import load_dotenv              # Load API keys and config from .env file for secure credential management
from langchain_openai import ChatOpenAI      # OpenAI LLM wrapper from LangChain for easy API integration
from langchain_core.prompts import ChatPromptTemplate  # Template system for building prompts with variables
from pydantic import ValidationError         # Exception handler for schema validation failures
from schema import TicketClassification      # Import Pydantic model defining the expected classification output structure

# Load environment variables from .env file (OPENAI_API_KEY, etc.) into os.environ
# This must be called before ChatOpenAI() to ensure API credentials are available
load_dotenv()

# Read DEFAULT_MODEL from environment, fall back to gpt-4o-mini if not set
# Using a smaller model (gpt-4o-mini) reduces API costs while maintaining classification quality
# The underscore prefix indicates this is an internal/private variable
_DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

# High-level system prompt for the primary classification attempt
# Tells the LLM it should act as an expert classifier to encourage quality output
DEFAULT_SYSTEM_PROMPT = "You are an expert customer support ticket classifier."

# Fallback system prompt used on retry attempts after initial classification fails
# Simpler and more conservative: explicitly lists categories to guide the model
# Encourages lower confidence scores and human review when uncertain, reducing misclassifications
# Used by the fallback_retry module to recover from failed or ambiguous classifications
SIMPLE_SYSTEM_PROMPT = (
    "You are a support ticket classifier. Classify into one of: "
    "order_issue, payment_issue, delivery_issue, product_issue, account_issue, refund_request, other. "
    "Keep confidence low and set requires_human_review=True if unsure."
)


# ---------------------------------------------------------------------------
# Approach 1: Function-calling (recommended)
# Use when: the model supports tool/function calling (GPT-4, GPT-3.5-turbo-1106+)
# Pros: Model is explicitly told the schema; more reliable JSON adherence.
# Cons: Slightly higher token overhead for the schema definition.
# ---------------------------------------------------------------------------

# Approach 1: Function-calling method for structured output from LLM
# This is the RECOMMENDED approach for modern OpenAI models
# Parameters:
#   ticket_text: The customer support ticket content to classify
#   system_prompt: Custom system prompt (allows retry logic to use different prompts without code changes)
#   model: Which LLM to use (allows A/B testing or fallback to other models)
#   seed: Ensures deterministic output across multiple runs (important for testing and reproducibility)
# Returns: TicketClassification object with category, confidence, and reasoning
def classify_with_function_calling(
    ticket_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    model: str = _DEFAULT_MODEL,
    seed: int = 42,
) -> TicketClassification:
    # Initialize the LLM with temperature=0 for deterministic outputs (no randomness)
    # Using seed=42 ensures reproducible results across API calls
    llm = ChatOpenAI(model=model, temperature=0, seed=seed)
    
    # Attach the TicketClassification schema to the LLM using function calling
    # This tells OpenAI to use tool_choice='required' and return structured JSON matching our schema
    # This is more reliable than JSON mode because the model is explicitly bound to our schema
    structured_llm = llm.with_structured_output(TicketClassification)

    # Create a prompt template with two parts:
    # - system: Defines the LLM's role and behavior (configurable for retry attempts)
    # - human: Contains the actual ticket to classify with a placeholder for the ticket text
    # LangChain will replace {ticket_text} with the actual content during invocation
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Classify this support ticket:\n\n{ticket_text}"),
    ])

    # Create a processing chain: prompt template → LLM → structured output
    # The pipe operator (|) chains components together in LangChain
    # This ensures the prompt is formatted before being sent to the LLM
    chain = prompt | structured_llm
    
    # Execute the chain with the actual ticket text
    # Returns a TicketClassification object automatically parsed and validated by Pydantic
    return chain.invoke({"ticket_text": ticket_text})


# ---------------------------------------------------------------------------
# Approach 2: JSON mode
# Use when: you need the model to freely structure its output as JSON but
# don't want to pin to a specific schema via tool calling, or when using
# older models that lack function-calling support.
# Pros: Simpler setup; works across more models.
# Cons: Must parse + validate manually; model may deviate from expected fields.
# ---------------------------------------------------------------------------

# Approach 2: JSON mode method for structured output from LLM
# Use this when the model doesn't support function calling or you need more flexibility
# Parameters:
#   ticket_text: The customer support ticket content to classify
#   system_prompt: Custom system prompt (allows retry logic to adjust prompts)
#   model: Which LLM to use (supports older models that lack tool calling)
#   seed: Ensures deterministic output for testing and reproducibility
# Returns: TicketClassification object with category, confidence, and reasoning
def classify_with_json_mode(
    ticket_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    model: str = _DEFAULT_MODEL,
    seed: int = 42,
) -> TicketClassification:
    # Convert the Pydantic schema to JSON representation
    # This creates a human-readable description of what fields and types the LLM should output
    schema_json = json.dumps(TicketClassification.model_json_schema(), indent=2)
    
    # IMPORTANT: Escape curly braces in the schema for LangChain's template engine
    # LangChain uses {variable} syntax for template placeholders
    # If we pass {"type": "string"}, LangChain will try to find a variable named 'type'
    # Escaping to {{"type": "string"}} prevents this and sends literal braces to the LLM
    schema_escaped = schema_json.replace("{", "{{").replace("}", "}}")
    # Combine the base system prompt with detailed schema instructions
    # Tells the LLM: 'Do X, and your output must be JSON matching this exact structure'
    # The explicit schema instruction reduces the chance of malformed or unexpected JSON
    full_system = f"{system_prompt}\n\nReturn ONLY valid JSON matching this schema:\n{schema_escaped}"

    # Initialize ChatOpenAI with JSON mode enabled
    # temperature=0 ensures deterministic output (no randomness)
    # seed=42 makes results reproducible across multiple API calls
    # model_kwargs passes OpenAI-specific parameters:
    #   - response_format={"type": "json_object"} activates JSON mode
    #   - This tells OpenAI to guarantee the response is valid JSON (prevents parsing errors)
    llm = ChatOpenAI(
        model=model,
        temperature=0,
        seed=seed,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    # Create prompt template with system instructions (including schema) and the ticket to classify
    # The system prompt now includes both role definition AND the expected JSON schema
    # This redundancy helps ensure the LLM understands the exact output format required
    prompt = ChatPromptTemplate.from_messages([
        ("system", full_system),
        ("human", "Classify this support ticket:\n\n{ticket_text}"),
    ])

    # Create processing chain: prompt template → LLM (with JSON mode)
    chain = prompt | llm
    
    # Execute the chain with the actual ticket text
    # response is a LangChain Message object containing the LLM's output
    response = chain.invoke({"ticket_text": ticket_text})
    
    # Extract the JSON string from the response and parse it into a Python dictionary
    # Even with JSON mode enabled, we must manually parse and validate the output
    raw = json.loads(response.content)
    
    # Debug print: Display the raw JSON output for inspection
    # In production, replace with logging instead of print()
    print(json.dumps(raw, indent=4))
    
    # Validate the raw dictionary against TicketClassification schema
    # This ensures all required fields are present and have correct types
    # Raises ValidationError if the response doesn't match the schema
    return TicketClassification.model_validate(raw)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
# Demo / Test section: Only runs when this file is executed directly
if __name__ == "__main__":
    # Sample support ticket to classify
    # This is a clear payment_issue that should be confidently classified
    ticket = "I was charged twice for order #9981. Please refund immediately!"

    # Test Approach 1: Function calling (recommended for modern models)
    # This should be faster and more reliable than JSON mode
    print("=== Approach 1: Function-calling ===")
    result1 = classify_with_function_calling(ticket)
    # Convert the TicketClassification object to formatted JSON for display
    print(result1.model_dump_json(indent=2))

    # Test Approach 2: JSON mode (fallback for older models)
    # This demonstrates the alternative method if function calling isn't available
    print("\n=== Approach 2: JSON mode ===")
    result2 = classify_with_json_mode(ticket)
    # Convert the TicketClassification object to formatted JSON for display
    print(result2.model_dump_json(indent=2))
