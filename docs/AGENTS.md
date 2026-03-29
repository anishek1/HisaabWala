# AGENTS.md — Module Ownership & Interface Contracts

## Project: VoiceBooks v1
## Team: 3 developers, 5 days

---

## Dev 1 — Telegram + Audio Pipeline (Free tier)

**Owns:**
```
main.py
config.py
telegram/
  __init__.py
  webhook.py
  sender.py
  audio.py
requirements.txt
Procfile
.env.example
```

**Responsibility:** Everything that touches Telegram API. Receiving updates, downloading voice notes, sending messages/documents back, FastAPI app setup, deployment config.

**Does NOT touch:** `services/`, `db/`, `prompts/`, `utils/`

---

## Dev 2 — AI/LLM Pipeline (Free tier)

**Owns:**
```
services/
  __init__.py
  transcription.py
  extraction.py
prompts/
  __init__.py
  extraction_prompt.py
```

**Responsibility:** Everything that touches Groq APIs (Whisper + Llama). Transcription, intent classification, entity extraction, Hindi number normalization. Prompt engineering.

**Does NOT touch:** `telegram/`, `db/`, `main.py`

---

## Dev 3 — Database + Business Logic + Orchestration (Claude Pro)

**Owns:**
```
db/
  __init__.py
  connection.py
  models.py
  queries.py
services/
  handler.py
  entity_resolver.py
  report_generator.py
  scheduler.py
utils/
  __init__.py
  rate_limiter.py
  timezone.py
sql/
  init.sql
```

**Responsibility:** Supabase setup, all DB operations, orchestration handler, entity resolution, PDF reports, daily summary scheduler, auto-confirm timer, rate limiting.

**Does NOT touch:** `telegram/`, `services/transcription.py`, `services/extraction.py`, `prompts/`

---

## Interface Contracts

These are the EXACT function signatures at module boundaries. Every dev must implement their side of these contracts exactly as defined. Do not change signatures without agreement from all devs.

### Contract 1: Telegram → Handler

**File:** `telegram/webhook.py` calls `services/handler.py`

```python
# Dev 1 calls this, Dev 3 implements this
async def process_message(
    telegram_id: int,
    telegram_username: str | None,
    audio_bytes: bytes | None,
    text: str | None,
    message_id: int
) -> HandlerResponse:
    ...
```

```python
# Defined in db/models.py (Dev 3 creates, everyone uses)
class HandlerResponse(BaseModel):
    messages: list[str]           # Text messages to send back (in order)
    documents: list[DocumentResponse] | None = None  # PDFs to send

class DocumentResponse(BaseModel):
    file_bytes: bytes
    filename: str
    caption: str
```

**Rule:** `webhook.py` calls `process_message()`, iterates over `response.messages` and sends each via `sender.send_text()`. If `response.documents` exists, sends each via `sender.send_document()`. That's it — webhook has ZERO business logic.

### Contract 2: Handler → Extraction

**File:** `services/handler.py` calls `services/extraction.py`

```python
# Dev 3 calls this, Dev 2 implements this
async def extract_from_transcript(
    transcript: str,
    existing_entities: list[str]  # names of known entities for this merchant
) -> ExtractionResult:
    ...
```

```python
# Defined in db/models.py (Dev 3 creates, everyone uses)
class TransactionData(BaseModel):
    person_name: str
    amount: float
    direction: str          # "incoming" | "outgoing"
    transaction_type: str   # "payment" | "credit_given" | "credit_recovery" | "expense"
    item: str | None = None

class ExtractionResult(BaseModel):
    intent: str             # "new_transaction" | "correction" | "balance_query" | "report_request" | "greeting" | "unknown"
    confidence: float       # 0.0 to 1.0
    transactions: list[TransactionData] | None = None    # for new_transaction intent
    query_person: str | None = None                      # for balance_query intent
    correction_data: dict | None = None                  # for correction intent
    raw_llm_response: str = ""                           # for debugging
```

### Contract 3: Handler → Transcription

**File:** `services/handler.py` calls `services/transcription.py`

```python
# Dev 3 calls this, Dev 2 implements this
async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "voice.oga"
) -> TranscriptionResult:
    ...
```

```python
# Defined in db/models.py
class TranscriptionResult(BaseModel):
    text: str
    language: str           # detected language code
    duration_seconds: float
    success: bool
    error: str | None = None
```

### Contract 4: Handler → DB Queries

**File:** `services/handler.py` calls `db/queries.py`

```python
# All DB functions follow this pattern (Dev 3 implements all):
async def get_merchant_by_telegram_id(telegram_id: int) -> Merchant | None
async def create_merchant(telegram_id: int, telegram_username: str | None) -> Merchant
async def update_merchant_shop_name(merchant_id: str, shop_name: str) -> Merchant
async def complete_onboarding(merchant_id: str) -> Merchant

async def find_entity_by_name(merchant_id: str, name: str) -> Entity | None
async def create_entity(merchant_id: str, name: str) -> Entity

async def create_transaction(data: CreateTransactionInput) -> Transaction
async def confirm_transaction(transaction_id: str) -> Transaction
async def reject_transaction(transaction_id: str) -> Transaction
async def update_transaction_amount(transaction_id: str, new_amount: float) -> Transaction
async def get_pending_transactions(merchant_id: str) -> list[Transaction]
async def get_recent_duplicate(merchant_id: str, entity_id: str, amount: float, direction: str, minutes: int = 10) -> Transaction | None
async def get_entity_balance(merchant_id: str, entity_id: str) -> float
async def get_daily_transactions(merchant_id: str) -> list[Transaction]
async def get_report_data(merchant_id: str, days: int = 30) -> ReportData

async def log_message(merchant_id: str, direction: str, message_type: str, telegram_message_id: int, raw_content: str) -> None
```

### Contract 5: Telegram Audio Download

**File:** `telegram/audio.py` (Dev 1 implements)

```python
# Dev 1 implements, called by webhook.py before passing to handler
async def download_voice_note(file_id: str) -> bytes:
    """Downloads voice note from Telegram servers, returns raw audio bytes."""
    ...
```

### Contract 6: Handler → Report Generator

```python
# Dev 3 implements both sides
async def generate_report(merchant_id: str, shop_name: str, days: int = 30) -> bytes:
    """Returns PDF file as bytes."""
    ...
```

### Contract 7: Handler → Scheduler

```python
# Dev 3 implements both sides
def schedule_auto_confirm(transaction_ids: list[str], delay_seconds: int = 120) -> None:
    """Schedules auto-confirmation of pending transactions after delay."""
    ...

def cancel_auto_confirm(transaction_ids: list[str]) -> None:
    """Cancels pending auto-confirm if merchant sends correction."""
    ...
```

---

## Shared Files (Dev 3 creates, everyone imports from)

- `config.py` — Dev 1 creates this, everyone imports from it
- `db/models.py` — Dev 3 creates ALL Pydantic models here, Dev 1 and Dev 2 import from it

## Integration Order

1. Day 1-2: All devs work independently
2. Day 3 morning: Dev 1 + Dev 3 integrate (Telegram → Handler)
3. Day 3 afternoon: Dev 2 + Dev 3 integrate (Extraction → Handler)
4. Day 3 evening: First end-to-end test
5. Day 4-5: Feature completion + testing

## Git Workflow

- `main` branch — production, never push directly
- `dev/telegram` — Dev 1's branch
- `dev/ai-pipeline` — Dev 2's branch
- `dev/backend` — Dev 3's branch
- Merge to `main` via PR after Day 3 integration
- If merge conflicts arise, the dev who owns the file resolves it
