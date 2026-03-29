# CONVENTIONS.md — Coding Standards & Patterns

## Project: VoiceBooks v1

---

## 1. Python Version & Style

- Python 3.11+
- All functions that do I/O (DB, API calls, file ops) MUST be `async`
- Type hints on ALL function signatures — no exceptions
- f-strings for string formatting, never `.format()` or `%`
- No wildcard imports (`from x import *`)

## 2. Import Order

```python
# 1. Standard library
import asyncio
import uuid
from datetime import datetime, timezone

# 2. Third party
from fastapi import FastAPI, Request
from pydantic import BaseModel
from aiogram import Bot, Dispatcher

# 3. Local
from config import settings
from db.models import Merchant, Transaction
from db.queries import get_merchant_by_telegram_id
```

## 3. Environment Variables

All env vars loaded through a single `config.py` using Pydantic Settings.

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str

    # Groq
    GROQ_API_KEY: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # App
    ENVIRONMENT: str = "development"  # "development" | "production"
    RATE_LIMIT_PER_DAY: int = 50
    AUTO_CONFIRM_DELAY_SECONDS: int = 120
    BATCH_WAIT_SECONDS: int = 30
    DAILY_SUMMARY_HOUR_IST: int = 21  # 9 PM IST

    class Config:
        env_file = ".env"

settings = Settings()
```

**Rule:** NEVER read `os.environ` directly anywhere. Always use `from config import settings`.

## 4. Pydantic Models (db/models.py)

All shared data structures live in `db/models.py`. This is the single source of truth for data shapes across all modules.

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

# --- DB Row Models ---

class Merchant(BaseModel):
    id: str
    telegram_id: int
    telegram_username: str | None = None
    shop_name: str | None = None
    language: str = "hi"
    is_onboarding: bool = True
    created_at: datetime

class Entity(BaseModel):
    id: str
    merchant_id: str
    name: str
    phone: str | None = None
    contact_type: str | None = None
    created_at: datetime

class Transaction(BaseModel):
    id: str
    merchant_id: str
    entity_id: str
    amount: float
    direction: str          # "incoming" | "outgoing"
    transaction_type: str   # "payment" | "credit_given" | "credit_recovery" | "expense"
    item: str | None = None
    audio_url: str | None = None
    raw_transcript: str | None = None
    status: str = "pending" # "pending" | "confirmed" | "rejected"
    message_id: int | None = None
    batch_id: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None

# --- LLM Extraction Models ---

class TransactionData(BaseModel):
    person_name: str
    amount: float
    direction: str          # "incoming" | "outgoing"
    transaction_type: str   # "payment" | "credit_given" | "credit_recovery" | "expense"
    item: str | None = None

class ExtractionResult(BaseModel):
    intent: str             # "new_transaction" | "correction" | "balance_query" | "report_request" | "greeting" | "unknown"
    confidence: float
    transactions: list[TransactionData] | None = None
    query_person: str | None = None
    correction_data: dict | None = None
    raw_llm_response: str = ""

# --- Transcription Models ---

class TranscriptionResult(BaseModel):
    text: str
    language: str
    duration_seconds: float
    success: bool
    error: str | None = None

# --- Handler Response Models ---

class DocumentResponse(BaseModel):
    file_bytes: bytes
    filename: str
    caption: str

class HandlerResponse(BaseModel):
    messages: list[str]
    documents: list[DocumentResponse] | None = None

# --- DB Input Models ---

class CreateTransactionInput(BaseModel):
    merchant_id: str
    entity_id: str
    amount: float
    direction: str
    transaction_type: str
    item: str | None = None
    audio_url: str | None = None
    raw_transcript: str | None = None
    message_id: int | None = None
    batch_id: str | None = None

# --- Report Models ---

class EntityBalance(BaseModel):
    entity_name: str
    total_incoming: float
    total_outgoing: float
    net_balance: float  # positive = they owe merchant, negative = merchant owes them

class ReportData(BaseModel):
    shop_name: str
    period_days: int
    total_inflow: float
    total_outflow: float
    net_position: float
    entity_balances: list[EntityBalance]
    transaction_count: int
    generated_at: datetime
```

## 5. Supabase Client Usage

```python
# db/connection.py
from supabase import create_client, Client
from config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
```

**Query patterns:**

```python
# ALWAYS filter by merchant_id — NO EXCEPTIONS
from db.connection import supabase

# SELECT
result = supabase.table("transactions") \
    .select("*") \
    .eq("merchant_id", merchant_id) \
    .eq("status", "confirmed") \
    .execute()
rows = result.data  # list[dict]

# INSERT
result = supabase.table("merchants") \
    .insert({"telegram_id": telegram_id, "shop_name": shop_name}) \
    .execute()
new_row = result.data[0]  # dict

# UPDATE
result = supabase.table("transactions") \
    .update({"status": "confirmed", "confirmed_at": datetime.now(timezone.utc).isoformat()}) \
    .eq("id", transaction_id) \
    .eq("merchant_id", merchant_id) \  # ALWAYS include merchant_id even on updates
    .execute()

# IMPORTANT: supabase-py is synchronous. Wrap in asyncio if needed:
import asyncio
from functools import partial

async def async_query():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants").select("*").eq("telegram_id", tid).execute()
    )
    return result.data
```

**CRITICAL:** `supabase-py` is NOT async. All Supabase calls are blocking. Wrap them in `run_in_executor` to avoid blocking the FastAPI event loop. Every function in `db/queries.py` must use this pattern.

## 6. Groq API Usage

```python
# Whisper (transcription.py)
from groq import Groq
from config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

transcription = client.audio.transcriptions.create(
    model="whisper-large-v3",
    file=("voice.oga", audio_bytes),
    language="hi",
    response_format="verbose_json"
)

# Llama (extraction.py)
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript}
    ],
    temperature=0.1,  # Low temperature for structured extraction
    max_tokens=1024,
    response_format={"type": "json_object"}
)
result = response.choices[0].message.content  # JSON string
```

**CRITICAL:** Groq client is also synchronous. Wrap in `run_in_executor` same as Supabase.

## 7. Error Handling Pattern

Every service function returns a result, never raises exceptions to the caller. Use try/except internally.

```python
# GOOD — handle errors internally, return result
async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.oga") -> TranscriptionResult:
    try:
        # ... groq call ...
        return TranscriptionResult(text=text, language=lang, duration_seconds=dur, success=True)
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return TranscriptionResult(text="", language="", duration_seconds=0, success=False, error=str(e))

# BAD — raising exceptions to caller
async def transcribe_audio(audio_bytes: bytes) -> str:
    result = groq.transcribe(audio_bytes)  # might raise!
    return result.text
```

## 8. Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use structured messages
logger.info(f"Transaction created: merchant={merchant_id} entity={entity_name} amount={amount}")
logger.error(f"Groq API failed: {error}")
logger.warning(f"Duplicate detected: merchant={merchant_id} entity={entity_id} amount={amount}")
```

Levels:
- `INFO` — successful operations (transaction created, message sent, report generated)
- `WARNING` — non-fatal issues (duplicate detected, rate limit approaching, low confidence extraction)
- `ERROR` — failures (API down, invalid audio, DB error)

## 9. Hindi Response Messages

All user-facing messages are in Hindi (Devanagari). Store them as constants:

```python
# In the file that uses them, or a shared constants file

MESSAGES = {
    "welcome": "🙏 नमस्ते! VoiceBooks में आपका स्वागत है। अपनी दुकान का नाम बताइए।",
    "registered": "✅ धन्यवाद! {shop_name} रजिस्टर हो गया। अब आप अपने लेनदेन voice note में भेज सकते हैं।",
    "transaction_confirm": "📝 {index}. {person} — ₹{amount} {direction_hindi}\n",
    "confirm_ask": "\nक्या यह सही है? (हाँ/नहीं)",
    "confirmed": "✅ सभी लेनदेन सेव हो गए।",
    "auto_confirmed": "✅ लेनदेन ऑटो-कन्फर्म हो गए।",
    "not_understood": "🤔 माफ़ कीजिए, समझ नहीं आया। कृपया दोबारा बोलिए।",
    "error": "⚠️ अभी थोड़ी दिक्कत है, थोड़ी देर में दोबारा भेजिए।",
    "balance_response": "💰 {person} का हिसाब: ₹{balance} {status}",
    "balance_clear": "बराबर है",
    "balance_owes": "उधार बाकी है",
    "balance_owed": "आपको देना है",
    "no_entity_found": "❓ '{name}' नाम से कोई नहीं मिला। नाम दोबारा बताइए।",
    "name_ask": "❓ किसका नाम बताएं?",
    "duplicate_warning": "⚠️ यह पहले भी लॉग हो चुका है — दोबारा सेव करें? (हाँ/नहीं)",
    "daily_summary": "📊 आज का हिसाब ({date}):\n💰 बिक्री: ₹{sales}\n📤 उधार दिया: ₹{credit_given}\n📥 उधार वापस: ₹{credit_recovered}\n📈 कुल: ₹{net}",
    "report_sent": "📄 आपकी {days} दिन की रिपोर्ट तैयार है।",
    "rate_limited": "⚠️ आज की लिमिट पूरी हो गई। कल दोबारा भेजिए।",
    "greeting": "🙏 नमस्ते! Voice note भेजकर लेनदेन रिकॉर्ड करें।",
}
```

Direction translations:
- "incoming" + "payment" → "मिले" (received)
- "incoming" + "credit_recovery" → "उधार वापस मिले" (udhaar recovered)
- "outgoing" + "credit_given" → "उधार दिया" (credit given)
- "outgoing" + "expense" → "खर्च" (expense)

## 10. UUID Generation

Use Python's `uuid4()` for all IDs. Supabase can also auto-generate UUIDs if column default is set — prefer DB-generated UUIDs via `gen_random_uuid()` in SQL.

## 11. Timezone Handling

```python
# utils/timezone.py
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def now_ist() -> datetime:
    return datetime.now(IST)

def today_start_ist() -> datetime:
    """Returns start of today in IST as UTC datetime (for DB queries)."""
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)

def today_end_ist() -> datetime:
    """Returns end of today in IST as UTC datetime."""
    now = datetime.now(IST)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return end.astimezone(timezone.utc)

def format_date_hindi(dt: datetime) -> str:
    """Returns date in DD/MM/YYYY format."""
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%d/%m/%Y")
```

**Rule:** Store everything in UTC. Convert to IST only at display time or for IST-scoped queries.

## 12. File Naming

- All Python files: `snake_case.py`
- All folders: `snake_case/`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Pydantic models: `PascalCase` ending with purpose (`TransactionData`, `HandlerResponse`, `CreateTransactionInput`)

## 13. Prompt Engineering Rules (Dev 2)

- The extraction prompt lives in `prompts/extraction_prompt.py` as a function that returns a string
- The function accepts `existing_entities: list[str]` to inject known entity names for better resolution
- Temperature MUST be 0.1 for extraction — we want deterministic, not creative
- Response format MUST be `{"type": "json_object"}` — Groq supports this for structured output
- The prompt MUST instruct the model to return ONLY valid JSON, no markdown, no preamble
- Test cases (sample transcript → expected JSON) should be documented as comments in the prompt file

## 14. Supabase Storage Pattern

```python
# Uploading audio
from db.connection import supabase

bucket = "voice-receipts"
path = f"{merchant_id}/{transaction_id}.oga"
supabase.storage.from_(bucket).upload(path, audio_bytes)

# Getting public URL
url = supabase.storage.from_(bucket).get_public_url(path)
```

**Rule:** Always scope storage paths by `merchant_id/` prefix.

## 15. What NOT To Do

- NEVER query without `merchant_id` filter
- NEVER raise raw exceptions — always catch and return structured results
- NEVER hardcode API keys — always use `config.settings`
- NEVER use `time.sleep()` — use `asyncio.sleep()` in async code
- NEVER import from another dev's owned files during Days 1-2 (use mocks)
- NEVER modify `db/models.py` without telling other devs — it's a shared contract
- NEVER send more than 3 messages in rapid succession to Telegram (rate limits)
