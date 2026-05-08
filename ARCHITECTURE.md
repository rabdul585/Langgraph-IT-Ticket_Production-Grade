# Support Ticket Classifier - Architecture Documentation

## 📋 Project Overview

This project is an **AI-powered support ticket classification system** built with LangGraph, FastAPI, and OpenAI's GPT models. It intelligently categorizes customer support tickets, assigns them to the appropriate team, determines priority, and detects sentiment — all while handling security concerns, cost tracking, and production-grade reliability.

**Key Capabilities:**
- ✅ Automatic ticket classification into 7 categories
- ✅ Team assignment and priority determination
- ✅ Sentiment analysis
- ✅ PII (Personally Identifiable Information) redaction
- ✅ Prompt injection detection and blocking
- ✅ Real-time cost tracking per LLM call
- ✅ Response validation with structured output
- ✅ Automatic retry with fallback prompts
- ✅ Prompt versioning for A/B testing
- ✅ REST API with FastAPI

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          FastAPI Server                          │
│                    (main.py - REST Endpoints)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  POST /classify                                                  │
│  ├─ Validate request                                             │
│  ├─ Call LangGraph Pipeline                                      │
│  └─ Return structured response with cost metadata                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Pipeline                           │
│                      (graph.py - Nodes)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  START ─► PII Redact ─► Injection Check ─► Classify ─► Validate │
│                                               ▲        │         │
│                                               │        ▼         │
│                                          Fallback    Cost Log ───┤
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Production Modules (production_modules/)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  • pii_redaction.py ............ Redact sensitive data           │
│  • prompt_injection.py ......... Detect malicious prompts        │
│  • structured_output.py ........ LLM calls (function calling)    │
│  • validate_response.py ........ Schema validation              │
│  • fallback_retry.py ........... Retry with safe prompts         │
│  • prompt_versioning.py ........ Version control for prompts     │
│  • cost_calculator.py .......... Token counting & cost tracking  │
│  • non_determinism.py .......... Handling randomness             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer (schema.py)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  • TicketClassification (Pydantic Model)                         │
│  • TicketState (LangGraph State)                                 │
│  • IssueCategory, TeamOwner, Priority, Sentiment Enums           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  • OpenAI API (GPT-4o-mini, GPT-4o, GPT-4-turbo)                 │
│  • Environment Variables (.env file)                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
Project3_support-ticket-classifier/
│
├── 📄 main.py                  # FastAPI server & REST endpoints
├── 📄 graph.py                 # LangGraph pipeline orchestration
├── 📄 schema.py                # Pydantic models & enums
├── 📄 requirements.txt          # Python dependencies
├── 📄 .env                      # Environment variables (secrets)
├── 📄 .env.example             # Template for .env
├── 📄 documentation.md         # User-facing documentation
│
├── 📁 production_modules/      # Core business logic (modular, reusable)
│   ├── __init__.py
│   ├── pii_redaction.py        # Redact emails, phone numbers, names
│   ├── prompt_injection.py     # Detect prompt injection attacks
│   ├── structured_output.py    # LLM integration (function calling & JSON mode)
│   ├── validate_response.py    # Pydantic validation
│   ├── fallback_retry.py       # Retry logic with fallback prompts
│   ├── prompt_versioning.py    # Version control for system prompts
│   ├── cost_calculator.py      # Token counting & cost tracking
│   └── non_determinism.py      # Handle randomness & reproducibility
│
├── 📁 demo_ui/                 # Web UI for testing
│   └── index.html              # Simple HTML interface
│
└── 📁 tests/                   # Unit tests
    ├── __init__.py
    └── test_classifier.py      # Test cases for pipeline
```

---

## 🔄 Data Flow

### Request Flow (End-to-End)

```
1. CLIENT SENDS REQUEST
   ┌─────────────────────────────────────┐
   │ POST /classify                      │
   │ {                                   │
   │   "ticket_text": "I was charged..." │
   │   "channel": "web_form"             │
   │ }                                   │
   └─────────────────────────────────────┘
                    │
                    ▼
2. REQUEST VALIDATION (main.py)
   ├─ Check min/max length (5-4000 chars)
   ├─ Validate channel (web_form|email)
   └─ Convert to TicketState
                    │
                    ▼
3. LANGRAPH PIPELINE EXECUTION (graph.py)
   
   ┌─────────────────────────────────────────────────────────┐
   │ Node 1: pii_redact_node                                 │
   │ ├─ Input: raw_ticket                                    │
   │ ├─ Action: Redact emails, phone numbers, names          │
   │ └─ Output: redacted_ticket, pii_detected                │
   └─────────────────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────┐
   │ Node 2: injection_check_node                            │
   │ ├─ Input: raw_ticket                                    │
   │ ├─ Action: Detect prompt injection patterns             │
   │ ├─ Decision: Is safe?                                   │
   │ │  ├─ NO → Set injection_blocked=True, return default   │
   │ │  └─ YES → Continue to classify                        │
   │ └─ Output: injection_blocked flag                       │
   └─────────────────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────┐
   │ Node 3: classify_node (MAIN LLM CALL)                   │
   │ ├─ Input: redacted_ticket, active_prompt               │
   │ ├─ Action:                                              │
   │ │  ├─ Get active prompt version                         │
   │ │  ├─ Call OpenAI with JSON mode                        │
   │ │  ├─ Parse response to TicketClassification            │
   │ │  └─ Catch exceptions for fallback                     │
   │ ├─ On Success: classification object                    │
   │ └─ On Failure: Trigger fallback_node                    │
   └─────────────────────────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼ (Success)           ▼ (Failure)
         
   ┌─────────────────────────────────────────────────────────┐
   │ Node 4: validate_node                                   │
   │ ├─ Input: classification                                │
   │ ├─ Action: Validate against schema                      │
   │ │  ├─ Check all fields present                          │
   │ │  ├─ Check confidence is 0.0-1.0                       │
   │ │  └─ Raise ValidationError if invalid                  │
   │ └─ Output: validation_status                            │
   └─────────────────────────────────────────────────────────┘
              │                    ┌─────────────────────┐
              │                    │ Fallback node       │
              │                    ├─────────────────────┤
              │                    │ Retry with:         │
              │                    │ • Simpler prompt    │
              │                    │ • Lower confidence  │
              │                    │ • human_review=True │
              │                    └─────────────────────┘
              │                           │
              └───────────────┬───────────┘
                              ▼
   ┌─────────────────────────────────────────────────────────┐
   │ Node 5: cost_log_node                                   │
   │ ├─ Input: classification, token counts                  │
   │ ├─ Action:                                              │
   │ │  ├─ Count tokens in prompt & response                 │
   │ │  ├─ Calculate USD cost                                │
   │ │  ├─ Record to session tracker                         │
   │ │  └─ Log cost metadata                                 │
   │ └─ Output: cost_info dictionary                         │
   └─────────────────────────────────────────────────────────┘
                    │
                    ▼
4. RESPONSE ASSEMBLY (main.py)
   ┌─────────────────────────────────────────────────────────┐
   │ ClassifyResponse object with:                           │
   │ ├─ issue_category                                       │
   │ ├─ assigned_team                                        │
   │ ├─ priority                                             │
   │ ├─ user_sentiment                                       │
   │ ├─ confidence_score                                     │
   │ ├─ reasoning                                            │
   │ ├─ requires_human_review                                │
   │ ├─ pii_detected (from redaction)                        │
   │ ├─ prompt_version (A/B testing)                         │
   │ ├─ cost_info (token count & USD)                        │
   │ └─ injection_blocked                                    │
   └─────────────────────────────────────────────────────────┘
                    │
                    ▼
5. RESPONSE SENT TO CLIENT
   ┌─────────────────────────────────────────────────────────┐
   │ HTTP 200 OK                                             │
   │ Content-Type: application/json                          │
   │ {                                                       │
   │   "issue_category": "delivery_issue",                   │
   │   "assigned_team": "logistics_team",                    │
   │   "priority": "high",                                   │
   │   "user_sentiment": "angry",                            │
   │   "confidence_score": 0.92,                             │
   │   "reasoning": "Clear delivery failure...",             │
   │   "requires_human_review": false,                       │
   │   "pii_detected": false,                                │
   │   "prompt_version": "v2",                               │
   │   "cost_info": {                                        │
   │     "input_cost_usd": 0.000045,                         │
   │     "output_cost_usd": 0.00012,                         │
   │     "total_cost_usd": 0.000165                          │
   │   },                                                    │
   │   "injection_blocked": false                            │
   │ }                                                       │
   └─────────────────────────────────────────────────────────┘
```

---

## 🧩 Core Components

### 1. **FastAPI Server** (`main.py`)
**Purpose:** HTTP REST API layer for receiving and responding to classification requests

**Key Responsibilities:**
- Request validation using Pydantic models
- Routing to the LangGraph pipeline
- Response formatting and serialization
- CORS middleware setup
- Startup/shutdown hooks
- Health check endpoints

**Endpoints:**
- `POST /classify` - Classify a single ticket
- `GET /prompt-versions` - List available prompt versions
- `GET /session-cost` - Get cumulative session costs

---

### 2. **LangGraph Pipeline** (`graph.py`)
**Purpose:** Orchestrates the multi-step classification workflow using LangGraph

**Design Pattern:** Each node is independent, delegating to production modules
- **No LLM wiring in graph.py** — purely orchestration
- **State-based flow** — uses TicketState to pass data between nodes
- **Conditional routing** — decisions based on state flags

**Nodes:**
1. `pii_redact_node` — Remove sensitive data
2. `injection_check_node` — Block malicious inputs
3. `classify_node` — Call LLM for classification
4. `validate_node` — Ensure response validity
5. `cost_log_node` — Track API costs
6. `fallback_node` (if classify fails) — Retry with simpler prompt

---

### 3. **Data Models** (`schema.py`)
**Purpose:** Define the shape of data flowing through the system using Pydantic

**Key Models:**
- `TicketClassification` — Output of classifier (7 fields + validation)
- `TicketState` — LangGraph state object
- `IssueCategory` — Enum of 7 ticket types
- `TeamOwner` — Enum of 5 teams
- `Priority` — Enum: low, medium, high, critical
- `Sentiment` — Enum: positive, neutral, negative, angry

**Why Pydantic?**
- Automatic validation with clear error messages
- JSON serialization/deserialization
- Type hints for IDE autocomplete
- Schema generation for OpenAPI docs

---

### 4. **Production Modules** (`production_modules/`)

#### **pii_redaction.py**
- **What it does:** Detects and redacts PII (emails, phone numbers, names, SSN)
- **Why:** Protect customer privacy before sending to LLM
- **Output:** Redacted text + list of detected PII types
- **Pattern:** Uses regex patterns and named entity recognition

#### **prompt_injection.py**
- **What it does:** Detects prompt injection attacks (e.g., "Ignore previous instructions...")
- **Why:** Prevent users from manipulating the LLM to change behavior
- **Output:** Boolean `is_safe` flag + detected pattern description
- **Pattern:** Regex matching for common injection patterns

#### **structured_output.py**
- **What it does:** Makes the actual LLM API calls with structured output
- **Approach 1:** Function calling (recommended) — LLM is bound to schema
- **Approach 2:** JSON mode — LLM outputs free-form JSON, then validated
- **Why:** Ensures LLM output matches expected structure
- **Returns:** TicketClassification object

#### **validate_response.py**
- **What it does:** Validates LLM response against Pydantic schema
- **Why:** Catch LLM hallucinations or malformed responses before downstream use
- **Output:** Validation status + error details
- **Pattern:** Uses Pydantic's built-in validation

#### **fallback_retry.py**
- **What it does:** Retry failed classifications with a simpler prompt
- **Why:** Recover from transient LLM errors or ambiguous cases
- **Strategy:** Use SIMPLE_SYSTEM_PROMPT + lower confidence + human review flag
- **Returns:** Safe default classification if all retries fail

#### **prompt_versioning.py**
- **What it does:** Version control for system prompts
- **Why:** A/B test different prompts without code changes
- **Features:** Environment-based version switching, version metadata
- **Usage:** Active version loaded from `PROMPT_VERSION` env var
- **Production:** Should integrate with feature flag service

#### **cost_calculator.py**
- **What it does:** Counts tokens and calculates USD cost per LLM call
- **Why:** Monitor API spend, enforce budgets, bill users
- **Components:**
  - `count_tokens()` — Uses tiktoken for accurate counting
  - `calculate_cost()` — Converts tokens to USD based on pricing table
  - `SessionCostTracker` — Accumulates costs across multiple calls
- **Output:** CostInfo object with breakdown

#### **non_determinism.py**
- **What it does:** Manages randomness in LLM outputs
- **Why:** Some use cases need reproducible results (testing), others benefit from variance
- **Approach:** Use `seed` parameter to control determinism
- **Usage:** Production classifier uses `seed=42` for reproducibility

---

## 🔌 Integration Points

### Environment Configuration (`.env`)
```ini
OPENAI_API_KEY=sk-...          # OpenAI API credentials
DEFAULT_MODEL=gpt-4o-mini      # Default LLM model
PROMPT_VERSION=v2              # Active prompt version
LOG_LEVEL=INFO                 # Logging verbosity
```

### External Dependencies
```
FastAPI        → Web server framework
LangGraph      → Pipeline orchestration
LangChain      → LLM integration
OpenAI         → GPT models (API)
Pydantic       → Data validation
Tiktoken       → Token counting
```

---

## 🛠️ Key Design Patterns

### 1. **Separation of Concerns**
- **graph.py:** Orchestration only (no business logic)
- **production_modules:** Each module handles one responsibility
- **main.py:** HTTP layer (no LLM logic)

### 2. **Delegated Nodes**
Each LangGraph node delegates to a production module:
```python
def classify_node(state):
    # Delegate to structured_output.py
    return classify_with_json_mode(...)
```
**Benefit:** Easy testing, swappable implementations, clear ownership

### 3. **State-Based Data Flow**
LangGraph state carries data between nodes:
```python
TicketState {
    raw_ticket: str
    redacted_ticket: str
    pii_detected: bool
    injection_blocked: bool
    classification: TicketClassification
    validation_status: str
    cost_info: dict
}
```
**Benefit:** Immutable data passing, clear dependencies, easy debugging

### 4. **Fallback Strategy**
- Primary attempt with high-quality prompt
- If fails → Retry with simpler prompt + human review flag
- If all fail → Return safe default
**Benefit:** Resilience, user satisfaction, clear escalation path

### 5. **Cost Tracking**
Session-level accumulation without database:
```python
session_tracker = SessionCostTracker()
session_tracker.record(cost_info)
print(session_tracker.summary)
```
**Benefit:** Per-session monitoring, easy to extend to database

### 6. **Prompt Versioning**
- Prompts in registry (not code)
- Version ID set via environment variable
- Easy A/B testing without redeployment
**Benefit:** Rapid iteration, feature flag compatibility, audit trail

---

## 📊 Sequence Diagram

```
Client          FastAPI          LangGraph        Production Modules     OpenAI
  │                │                 │                    │                │
  ├─POST /classify─→                 │                    │                │
  │                 │                 │                    │                │
  │                 ├─validate request│                    │                │
  │                 ├─run_pipeline()──→                    │                │
  │                 │                 ├─pii_redact()──────→                │
  │                 │                 │← redacted_text    │                │
  │                 │                 │                    │                │
  │                 │                 ├─injection_check()─→                │
  │                 │                 │← is_safe flag     │                │
  │                 │                 │                    │                │
  │                 │                 ├─classify_node()───┤                │
  │                 │                 │                    ├─classify()────→
  │                 │                 │                    │                │
  │                 │                 │                    │←─response JSON─┤
  │                 │                 │                    ├─validate()────→
  │                 │                 │                    │← validation OK │
  │                 │                 │← classification    │                │
  │                 │                 │                    │                │
  │                 │                 ├─cost_log_node()───→                │
  │                 │                 │                    ├─count_tokens()│
  │                 │                 │                    ├─calculate_cost→
  │                 │                 │← cost_info        │                │
  │                 │← final state    │                    │                │
  │                 │                 │                    │                │
  │←─200 OK─────────┤                 │                    │                │
  │ (with response) │                 │                    │                │
  │                 │                 │                    │                │
```

---

## 🧪 Testing Strategy

### Unit Tests (`tests/test_classifier.py`)
- Test individual production modules in isolation
- Mock OpenAI API calls
- Verify edge cases (PII redaction, injection patterns)
- Validate cost calculations

### Integration Tests
- Test full graph pipeline with mock LLM
- Verify node ordering and state transitions
- Check error handling and fallback logic

### E2E Tests
- Deploy to staging
- Send real tickets through the system
- Monitor costs and token usage
- Verify classification accuracy

---

## 🚀 Extension Points

### Adding a New Classification Category
1. Add enum value to `IssueCategory` in `schema.py`
2. Update `SIMPLE_SYSTEM_PROMPT` in `structured_output.py`
3. Update prompt templates in `prompt_versioning.py` (v1, v2)
4. No code changes needed in `graph.py`

### Switching to a Different LLM
1. Update `DEFAULT_MODEL` in `.env`
2. Update `PRICING` dict in `cost_calculator.py`
3. Update `structured_output.py` if using non-OpenAI model
4. No changes to pipeline logic needed

### Persisting Cost Data
1. Add database integration to `cost_calculator.py`
2. Modify `SessionCostTracker.record()` to also write to DB
3. Add new endpoint in `main.py` for cost reports
4. No changes to pipeline logic needed

### Adding New Production Modules
1. Create `production_modules/new_module.py` with business logic
2. Create corresponding node in `graph.py`
3. Add node to StateGraph with conditional routing if needed
4. Update `TicketState` schema if new fields are needed

---

## 📈 Performance Considerations

| Metric | Value | Notes |
|--------|-------|-------|
| LLM Response Time | ~1-3s | Depends on OpenAI API latency |
| PII Redaction | <10ms | Regex-based, very fast |
| Injection Check | <5ms | Pattern matching |
| Validation | <1ms | Pydantic validation |
| **Total E2E Time** | ~1-3s | Dominated by LLM call |
| **Cost per Call** | $0.0002-$0.0005 | Using gpt-4o-mini |
| **Throughput** | ~330 req/min | Single process, async |

**Optimization Opportunities:**
- Batch requests to OpenAI
- Cache classification results for identical tickets
- Use gpt-3.5-turbo for cost reduction (with accuracy trade-off)
- Implement response caching

---

## 🔒 Security Considerations

1. **PII Protection** — Automatically redact before LLM
2. **Prompt Injection Detection** — Block malicious inputs
3. **API Key Management** — Use `.env` (never commit secrets)
4. **Input Validation** — Pydantic validates all inputs
5. **CORS Configuration** — Restrict origins in `main.py`
6. **Rate Limiting** — Implement in FastAPI middleware
7. **Audit Trail** — Log all classifications with timestamps

---

## 📚 How to Use This Architecture

### For Developers
1. Read `schema.py` first to understand the data models
2. Examine `graph.py` to see the pipeline structure
3. Study individual production modules for implementation details
4. Run tests in `tests/` to understand expected behavior

### For DevOps
1. Review environment variables in `.env.example`
2. Set up monitoring for cost_tracker.summary
3. Configure alerting for `requires_human_review=True`
4. Plan capacity based on LLM API rate limits

### For Product Managers
1. Check `prompt_versioning.py` for A/B testing capabilities
2. Review `cost_calculator.py` for budgeting
3. Monitor `confidence_score` distribution
4. Use `requires_human_review` for escalation workflows

---

## 🎯 Next Steps

- [ ] Add database persistence for costs
- [ ] Implement batch classification endpoint
- [ ] Set up monitoring dashboard
- [ ] Add cache layer for duplicate tickets
- [ ] Integrate with ticketing system (Jira, ServiceNow)
- [ ] Implement analytics endpoint
- [ ] Add multi-language support
- [ ] Implement async batch processing

---

**Last Updated:** May 2024
**Version:** 1.0
**Maintainers:** AI Engineering Team
