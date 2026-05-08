"""
Versioned prompt registry for the ticket classifier.

# PRODUCTION NOTE: In a real system, store prompts in a database (Postgres,
# DynamoDB) with full version history, author metadata, A/B test assignments,
# and rollback capability. Use a feature flag service to control active version
# per environment/customer segment.
"""

# Standard library imports for configuration management and type hints
import os                          # Access environment variables (e.g., PROMPT_VERSION)
from datetime import datetime      # Used for timestamp metadata in prompt version history
from typing import Optional        # Type hint for optional parameters and return values

# Third-party imports for environment configuration
from dotenv import load_dotenv     # Load configuration from .env file (e.g., PROMPT_VERSION=v2)

# Load environment variables from .env into os.environ
# This allows us to read PROMPT_VERSION from the environment to control which prompt to use
load_dotenv()

# Central registry storing all versioned prompts
# Maps version ID (e.g., "v1", "v2") to prompt configuration dictionaries
# In production, this should be replaced with a database (PostgreSQL, DynamoDB) for:
#   - Version history and rollback capability
#   - Author attribution and change tracking
#   - A/B test assignment logic
#   - Feature flag integration for per-environment/customer control
PROMPT_REGISTRY: dict[str, dict] = {
    # Version 1: Baseline simple prompt
    # This serves as the control/baseline for A/B testing against newer versions
    "v1": {
        "version_id": "v1",                          # Unique identifier for this prompt version
        "model": "gpt-4o-mini",                      # The LLM this prompt is optimized for
        "created_at": "2024-01-01",                 # When this version was created (audit trail)
        "description": "Basic classification prompt", # Human-readable description for UI/logs
        # IMPORTANT: Only system instructions go here. The actual ticket text and JSON schema
        # are injected by the structured_output.py module, not here.
        # This separation allows changing prompts without modifying the LLM wiring.
        "template": "You are a customer support ticket classifier.",
    },
    # Version 2: Enhanced prompt with chain-of-thought reasoning
    # This version is expected to produce better classifications through explicit reasoning steps
    # Metrics tracked: accuracy improvement over v1, confidence distribution, human review rate
    "v2": {
        "version_id": "v2",                                    # Unique identifier for this improved version
        "model": "gpt-4o-mini",                                # Same LLM, but with better instructions
        "created_at": "2024-03-01",                           # When this improved version was released
        "description": "Adds chain-of-thought reasoning instruction", # Describes the improvement
        # IMPORTANT: Only system instructions go here. Ticket text and JSON schema
        # are injected separately by structured_output.py for modularity.
        # This allows A/B testing prompts without changing LLM integration code.
        "template": """You are an expert customer support ticket classifier.

Think step by step before classifying:
1. Identify the core problem the customer is facing.
2. Assess the emotional tone and urgency.
3. Determine which team is best equipped to resolve this.
4. Assign a priority based on business impact and customer sentiment.
5. Flag for human review if ambiguous or high-stakes.""",
    },
}


# Retrieve a specific versioned prompt by its version ID
# Parameters:
#   version: The version identifier (e.g., "v1", "v2")
# Returns: Dictionary containing version metadata and template
# Raises: ValueError if the version doesn't exist (prevents silent failures)
def get_prompt(version: str) -> dict:
    # Check if the requested version exists in the registry
    # Fail explicitly with a helpful error message if not found
    if version not in PROMPT_REGISTRY:
        raise ValueError(f"Unknown prompt version: {version}. Available: {list(PROMPT_REGISTRY)}")
    # Return the prompt configuration for the requested version
    return PROMPT_REGISTRY[version]


# Retrieve the most recently created prompt version
# Assumes version keys are sortable strings (e.g., "v1", "v2", "v10")
# Returns: Dictionary containing the latest version's metadata and template
# Used for: Quick access to the newest prompt without needing to know its exact ID
def get_latest() -> dict:
    # Sort version keys alphabetically to find the "latest" version
    # Note: This assumes naming convention like v1, v2, v10 (lexicographic sorting)
    # For true chronological sorting, should use created_at field instead
    latest_key = sorted(PROMPT_REGISTRY.keys())[-1]
    # Return the prompt configuration of the latest version
    return PROMPT_REGISTRY[latest_key]


# Get the currently active prompt version from environment configuration
# Returns: Version ID string (e.g., "v1", "v2")
# Default: "v2" if PROMPT_VERSION environment variable is not set
# Purpose: Allows changing the active prompt without code changes (environment-based feature flag)
# In production: Should integrate with a feature flag service for dynamic version switching
def get_active_version() -> str:
    # Read PROMPT_VERSION from environment; defaults to v2 if not specified
    # This enables quick rollback: just change the env var and restart the service
    # No code deployment required for prompt version switches
    return os.getenv("PROMPT_VERSION", "v2")


# Retrieve the full configuration of the currently active prompt
# Returns: Dictionary containing metadata and template of the active version
# Combines two operations: find active version, then fetch its configuration
# Used by: Classification graph and retry logic to get the current prompt
def get_active_prompt() -> dict:
    # Get the currently active version ID and retrieve its full configuration
    # This is the main entry point for the classifier to get the right prompt
    return get_prompt(get_active_version())


# Return a list of all available prompt versions with their metadata
# Returns: List of dictionaries, each containing essential version information
# Purpose: Used for UI display, API endpoints, and version selection interfaces
# Note: Excludes the full template to keep the response lightweight
def list_versions() -> list[dict]:
    # Extract a subset of metadata from each prompt version in the registry
    # Includes only essential info: ID, description, model, and creation date
    # This is useful for UI displays without exposing full template details
    return [
        {
            "version_id": v["version_id"],        # Unique identifier for the version
            "description": v["description"],      # Human-readable description of changes
            "model": v["model"],                  # LLM model this version targets
            "created_at": v["created_at"],        # Timestamp when version was created
        }
        for v in PROMPT_REGISTRY.values()         # Iterate through all registered versions
    ]


# ============================================================================
# Demo / Test Section: Only runs when this file is executed directly
# ============================================================================
if __name__ == "__main__":
    # Display header
    print("Available versions:")
    # Retrieve and display all available prompt versions with their metadata
    # This shows the version registry state for debugging/inspection
    for v in list_versions():
        print(f"  {v['version_id']}: {v['description']}")
    
    # Display which version is currently active
    # This confirms the active version set by the PROMPT_VERSION environment variable
    print(f"\nActive version: {get_active_version()}")
    
    # Retrieve the active prompt configuration
    prompt = get_active_prompt()
    
    # Display the full template of the active prompt
    # Shows the exact system instructions being used for classification
    print(f"\nActive prompt template:\n{prompt['template']}")
