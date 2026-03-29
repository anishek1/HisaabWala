# SPRINT.md — Day-by-Day Build Plan

## Project: VoiceBooks v1
## Team: Dev 1 (Free tier), Dev 2 (Free tier), Dev 3 (Claude Pro)

---

# DAY 1

---

## Day 1 — Dev 1: Telegram Bot + FastAPI Skeleton

### Task 1.1: Create project skeleton

**Create file:** `requirements.txt`
```
fastapi==0.115.0
uvicorn==0.30.0
aiogram==3.13.0
pydantic==2.9.0
pydantic-settings==2.5.0
supabase==2.9.0
groq==0.11.0
fpdf2==2.8.1
httpx==0.27.0
apscheduler==3.10.4
python-dotenv==1.0.1
```

**Create file:** `.env.example`
```
TELEGRAM_BOT_TOKEN=
GROQ_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
ENVIRONMENT=development
```

**Create file:** `Procfile`
```
web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Create file:** `config.py`
Implement exactly as shown in CONVENTIONS.md Section 3. Pydantic Settings with all env vars.

**Create file:** `telegram/__init__.py` (empty)

**Verify:** `python -c "from config import settings"` should not error (with .env populated).

---

### Task 1.2: Create FastAPI app + Telegram webhook

**Create file:** `main.py`

```python
# Structure:
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from config import settings

# Initialize bot and dispatcher at module level
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: set webhook URL (in production) or skip (in dev)
    # Register aiogram router/handlers
    from telegram.webhook import register_handlers
    register_handlers(dp)
    yield
    # On shutdown: close bot session
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Verify:** Run `uvicorn main:app --reload`, hit `/health`, get `{"status": "ok"}`.

---

### Task 1.3: Telegram webhook handler (voice + text)

**Create file:** `telegram/webhook.py`

```python
# Structure:
from aiogram import Dispatcher, Bot
from aiogram.types import Message
from telegram.audio import download_voice_note
from telegram.sender import send_text, send_document
# from services.handler import process_message  # Day 3 integration
from db.models import HandlerResponse

def register_handlers(dp: Dispatcher):
    dp.message.register(handle_message)

async def handle_message(message: Message, bot: Bot):
    telegram_id = message.from_user.id
    telegram_username = message.from_user.username
    message_id = message.message_id
    
    audio_bytes = None
    text = None
    
    if message.voice:
        # Download voice note
        audio_bytes = await download_voice_note(bot, message.voice.file_id)
    elif message.text:
        text = message.text
    else:
        await send_text(bot, telegram_id, "🤔 माफ़ कीजिए, सिर्फ़ voice note या text भेजिए।")
        return
    
    # DAY 1: Stub response for testing
    # DAY 3: Replace with actual handler call
    # response = await process_message(telegram_id, telegram_username, audio_bytes, text, message_id)
    
    if audio_bytes:
        await send_text(bot, telegram_id, f"✅ Voice note received ({len(audio_bytes)} bytes)")
    else:
        await send_text(bot, telegram_id, f"✅ Text received: {text}")
```

**Important:** On Day 1, use stub responses. Do NOT import from `services/handler.py` yet. Comment out the real handler call.

---

### Task 1.4: Audio download utility

**Create file:** `telegram/audio.py`

```python
from aiogram import Bot
import asyncio

async def download_voice_note(bot: Bot, file_id: str) -> bytes:
    """
    Downloads voice note from Telegram servers.
    Telegram voice notes are .oga (Opus in OGG container).
    
    Args:
        bot: aiogram Bot instance
        file_id: Telegram file_id from message.voice.file_id
    
    Returns:
        Raw audio bytes
    
    Raises:
        Exception if download fails (caller should handle)
    """
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    from io import BytesIO
    buffer = BytesIO()
    await bot.download_file(file_path, buffer)
    return buffer.getvalue()
```

**Verify:** Send a voice note to bot → get back "Voice note received (XXXX bytes)" with a non-zero byte count.

---

### Task 1.5: Telegram sender utility

**Create file:** `telegram/sender.py`

```python
from aiogram import Bot
from aiogram.types import BufferedInputFile
import logging

logger = logging.getLogger(__name__)

async def send_text(bot: Bot, telegram_id: int, text: str) -> None:
    """
    Send a text message to a Telegram user.
    Splits into multiple messages if text exceeds 4096 chars (Telegram limit).
    """
    try:
        if len(text) <= 4096:
            await bot.send_message(chat_id=telegram_id, text=text)
        else:
            # Split at newlines to avoid breaking mid-sentence
            chunks = []
            current = ""
            for line in text.split("\n"):
                if len(current) + len(line) + 1 > 4096:
                    chunks.append(current)
                    current = line
                else:
                    current += "\n" + line if current else line
            if current:
                chunks.append(current)
            for chunk in chunks:
                await bot.send_message(chat_id=telegram_id, text=chunk)
    except Exception as e:
        logger.error(f"Failed to send text to {telegram_id}: {e}")

async def send_document(bot: Bot, telegram_id: int, file_bytes: bytes, filename: str, caption: str = "") -> None:
    """
    Send a document (PDF) to a Telegram user.
    """
    try:
        doc = BufferedInputFile(file=file_bytes, filename=filename)
        await bot.send_document(chat_id=telegram_id, document=doc, caption=caption)
    except Exception as e:
        logger.error(f"Failed to send document to {telegram_id}: {e}")
```

**Verify:** Bot can send text responses and can receive voice notes.

---

### Task 1.6: Test with real phone

1. Create bot via @BotFather on Telegram
2. Set bot token in `.env`
3. Run locally with `uvicorn main:app --reload --port 8000`
4. Use ngrok to expose: `ngrok http 8000`
5. Set webhook: `curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<NGROK_URL>/webhook"`
6. Send a text message → get confirmation
7. Send a voice note → get "Voice note received (XXXX bytes)"

**Day 1 Done Criteria for Dev 1:**
- [ ] FastAPI server running
- [ ] Telegram bot receiving text messages
- [ ] Telegram bot receiving voice notes and downloading audio bytes
- [ ] Bot responding with stub messages
- [ ] ngrok tunnel working for local dev

---

## Day 1 — Dev 2: Groq Whisper + Llama Extraction

### Task 2.1: Transcription service

**Create file:** `services/__init__.py` (empty)

**Create file:** `services/transcription.py`

```python
from groq import Groq
from config import settings
from db.models import TranscriptionResult
import asyncio
import logging

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)

async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.oga") -> TranscriptionResult:
    """
    Transcribe audio using Groq Whisper.
    
    Args:
        audio_bytes: Raw audio bytes (.oga format from Telegram)
        filename: Filename hint for Whisper (include extension)
    
    Returns:
        TranscriptionResult with text, language, duration, success flag
    """
    try:
        loop = asyncio.get_event_loop()
        transcription = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=(filename, audio_bytes),
                language="hi",
                response_format="verbose_json"
            )
        )
        return TranscriptionResult(
            text=transcription.text,
            language=transcription.language or "hi",
            duration_seconds=transcription.duration or 0.0,
            success=True
        )
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return TranscriptionResult(
            text="",
            language="",
            duration_seconds=0.0,
            success=False,
            error=str(e)
        )
```

**Verify with test script:**
```python
# test_transcription.py (temporary, not committed)
import asyncio
from services.transcription import transcribe_audio

async def test():
    with open("test_voice.oga", "rb") as f:
        audio = f.read()
    result = await transcribe_audio(audio)
    print(f"Success: {result.success}")
    print(f"Text: {result.text}")
    print(f"Language: {result.language}")

asyncio.run(test())
```

**Test with:** Record a Hindi voice note on your phone saying "Ramesh ne paanch sau rupaye diye". Save it, send to yourself, download as .oga, run the test.

**Day 1 Verify for Task 2.1:**
- [ ] .oga file from Telegram transcribes successfully
- [ ] Hindi text comes back correctly
- [ ] Hindi numbers are transcribed (may be in words like "पांच सौ" — this is fine, LLM will normalize)

---

### Task 2.2: Extraction prompt (START — continue on Day 2)

**Create file:** `prompts/__init__.py` (empty)

**Create file:** `prompts/extraction_prompt.py`

```python
def get_extraction_prompt(existing_entities: list[str]) -> str:
    """
    Returns the system prompt for Groq Llama 3.3 70B.
    Handles intent classification + entity extraction in one call.
    
    Args:
        existing_entities: List of known entity names for this merchant.
                          Used to help LLM match to existing contacts.
    """
    entities_str = ", ".join(existing_entities) if existing_entities else "कोई नहीं"
    
    return f"""You are a Hindi/Hinglish transaction extraction AI for a small Indian shopkeeper's voice-based accounting system.

TASK: Analyze the shopkeeper's transcribed speech. Classify the intent AND extract structured data.

KNOWN CONTACTS for this shopkeeper: [{entities_str}]
If a name is similar to a known contact (e.g., "Ramesh bhai" matches "Ramesh"), use the known contact's exact name.

INTENTS:
1. "new_transaction" — shopkeeper is logging one or more financial transactions
2. "correction" — shopkeeper is correcting a previous entry (mentions "galat", "nahi", "change", "sahi karo", number reference)
3. "balance_query" — shopkeeper is asking about someone's outstanding balance ("kitna baaki hai", "hisaab batao", "udhaar kitna hai")
4. "report_request" — shopkeeper wants a summary/report ("hisaab bhejo", "report", "mahina ka hisaab")
5. "greeting" — simple greeting or hello
6. "unknown" — cannot determine intent

TRANSACTION EXTRACTION RULES:
- "diye" / "diya" / "mila" / "aaya" / "wapas" → incoming (money came to shopkeeper)
- "udhaar" / "le gaya" / "udhar" / "khata" → outgoing + credit_given (shopkeeper gave credit)
- "udhaar chukaya" / "wapas diya" / "udhaar wapas" → incoming + credit_recovery
- "kharcha" / "khareed" / "wholesale" / "cost" → outgoing + expense
- Convert Hindi numbers to digits: paanch sau = 500, hazaar = 1000, do hazaar = 2000, etc.
- "dhai sau" = 250, "saadhe teen sau" = 350, "dedh sau" = 150
- Extract item names if mentioned ("cement", "saamaan", "chai", etc.)

MULTIPLE TRANSACTIONS: A single message may contain multiple transactions. Extract ALL of them.

RESPOND WITH ONLY VALID JSON. No markdown, no explanation, no preamble.

JSON SCHEMA:
{{
    "intent": "new_transaction" | "correction" | "balance_query" | "report_request" | "greeting" | "unknown",
    "confidence": 0.0 to 1.0,
    "transactions": [  // only for intent "new_transaction"
        {{
            "person_name": "string",
            "amount": number,
            "direction": "incoming" | "outgoing",
            "transaction_type": "payment" | "credit_given" | "credit_recovery" | "expense",
            "item": "string or null"
        }}
    ],
    "query_person": "string or null",  // only for intent "balance_query"
    "correction_data": {{  // only for intent "correction"
        "original_amount": number or null,
        "new_amount": number or null,
        "person_name": "string or null",
        "field": "amount" or "person" or "direction"
    }}
}}

EXAMPLES:

Input: "Ramesh ne aaj paanch sau rupaye diye"
Output: {{"intent": "new_transaction", "confidence": 0.95, "transactions": [{{"person_name": "Ramesh", "amount": 500, "direction": "incoming", "transaction_type": "payment", "item": null}}], "query_person": null, "correction_data": null}}

Input: "Suresh do hazaar ka saamaan le gaya udhaar"
Output: {{"intent": "new_transaction", "confidence": 0.95, "transactions": [{{"person_name": "Suresh", "amount": 2000, "direction": "outgoing", "transaction_type": "credit_given", "item": "saamaan"}}], "query_person": null, "correction_data": null}}

Input: "Ramesh ne paanch sau diye aur Mohan ne hazaar wapas kiya"
Output: {{"intent": "new_transaction", "confidence": 0.92, "transactions": [{{"person_name": "Ramesh", "amount": 500, "direction": "incoming", "transaction_type": "payment", "item": null}}, {{"person_name": "Mohan", "amount": 1000, "direction": "incoming", "transaction_type": "credit_recovery", "item": null}}], "query_person": null, "correction_data": null}}

Input: "Ramesh ka kitna baaki hai"
Output: {{"intent": "balance_query", "confidence": 0.95, "transactions": null, "query_person": "Ramesh", "correction_data": null}}

Input: "woh paanch sau nahi tha teen sau tha"
Output: {{"intent": "correction", "confidence": 0.88, "transactions": null, "query_person": null, "correction_data": {{"original_amount": 500, "new_amount": 300, "person_name": null, "field": "amount"}}}}

Input: "mera hisaab bhejo"
Output: {{"intent": "report_request", "confidence": 0.95, "transactions": null, "query_person": null, "correction_data": null}}

Input: "namaste"
Output: {{"intent": "greeting", "confidence": 0.99, "transactions": null, "query_person": null, "correction_data": null}}
"""
```

**Day 1 Done Criteria for Dev 2:**
- [ ] Transcription service working with real .oga files
- [ ] Hindi transcription verified with 5+ test voice notes
- [ ] Extraction prompt drafted with examples
- [ ] Prompt file created and importable

---

## Day 1 — Dev 3: Supabase Setup + DB Layer + Models

### Task 3.1: Create all Pydantic models

**Create file:** `db/__init__.py` (empty)

**Create file:** `db/models.py`

Implement ALL models exactly as defined in CONVENTIONS.md Section 4. This file is the shared contract — Dev 1 and Dev 2 will import from it.

Models to create:
- Merchant
- Entity
- Transaction
- TransactionData
- ExtractionResult
- TranscriptionResult
- DocumentResponse
- HandlerResponse
- CreateTransactionInput
- EntityBalance
- ReportData

**Verify:** `python -c "from db.models import Merchant, Transaction, ExtractionResult, HandlerResponse"` works.

---

### Task 3.2: Supabase setup

1. Create Supabase project at supabase.com
2. Go to SQL Editor
3. Run `sql/init.sql` (the full file)
4. Verify all 4 tables created in Table Editor
5. Create storage bucket "voice-receipts" (public, for v1)
6. Copy Supabase URL and service key to `.env`

**Create file:** `db/connection.py`

```python
from supabase import create_client, Client
from config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
```

**Verify:** `python -c "from db.connection import supabase; print(supabase.table('merchants').select('*').execute())"` returns empty data with no error.

---

### Task 3.3: DB query functions

**Create file:** `db/queries.py`

Implement ALL functions listed in AGENTS.md Contract 4. Every function:
- Is `async`
- Wraps supabase call in `run_in_executor`
- Filters by `merchant_id` where applicable
- Returns Pydantic models (not raw dicts)
- Has try/except with logging

**Full function list with exact signatures and behavior:**

```python
import asyncio
import logging
from datetime import datetime, timezone
from db.connection import supabase
from db.models import (
    Merchant, Entity, Transaction, CreateTransactionInput,
    ReportData, EntityBalance
)
from utils.timezone import today_start_ist, today_end_ist

logger = logging.getLogger(__name__)

# --- Merchants ---

async def get_merchant_by_telegram_id(telegram_id: int) -> Merchant | None:
    """Query merchants table by telegram_id. Return Merchant or None."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants")
            .select("*")
            .eq("telegram_id", telegram_id)
            .execute()
    )
    if result.data:
        return Merchant(**result.data[0])
    return None

async def create_merchant(telegram_id: int, telegram_username: str | None) -> Merchant:
    """Insert new merchant row. Return created Merchant."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants")
            .insert({
                "telegram_id": telegram_id,
                "telegram_username": telegram_username,
                "is_onboarding": True
            })
            .execute()
    )
    return Merchant(**result.data[0])

async def update_merchant_shop_name(merchant_id: str, shop_name: str) -> Merchant:
    """Update shop_name for merchant."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants")
            .update({"shop_name": shop_name})
            .eq("id", merchant_id)
            .execute()
    )
    return Merchant(**result.data[0])

async def complete_onboarding(merchant_id: str) -> Merchant:
    """Set is_onboarding=False."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants")
            .update({"is_onboarding": False})
            .eq("id", merchant_id)
            .execute()
    )
    return Merchant(**result.data[0])

# --- Entities ---

async def find_entity_by_name(merchant_id: str, name: str) -> Entity | None:
    """Find entity by exact normalized name within merchant scope."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("entities")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("name", name)
            .execute()
    )
    if result.data:
        return Entity(**result.data[0])
    return None

async def create_entity(merchant_id: str, name: str) -> Entity:
    """Create new entity for merchant."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("entities")
            .insert({
                "merchant_id": merchant_id,
                "name": name
            })
            .execute()
    )
    return Entity(**result.data[0])

async def get_merchant_entities(merchant_id: str) -> list[Entity]:
    """Get all entities for a merchant. Used to pass existing names to LLM."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("entities")
            .select("*")
            .eq("merchant_id", merchant_id)
            .execute()
    )
    return [Entity(**row) for row in result.data]

# --- Transactions ---

async def create_transaction(data: CreateTransactionInput) -> Transaction:
    """Insert new transaction with status='pending'."""
    loop = asyncio.get_event_loop()
    insert_data = data.model_dump()
    insert_data["status"] = "pending"
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .insert(insert_data)
            .execute()
    )
    return Transaction(**result.data[0])

async def confirm_transaction(transaction_id: str) -> Transaction:
    """Set status='confirmed' and confirmed_at=now()."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .update({
                "status": "confirmed",
                "confirmed_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", transaction_id)
            .execute()
    )
    return Transaction(**result.data[0])

async def reject_transaction(transaction_id: str) -> Transaction:
    """Set status='rejected'."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .update({"status": "rejected"})
            .eq("id", transaction_id)
            .execute()
    )
    return Transaction(**result.data[0])

async def update_transaction_amount(transaction_id: str, new_amount: float) -> Transaction:
    """Update amount on a pending transaction."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .update({"amount": new_amount})
            .eq("id", transaction_id)
            .eq("status", "pending")
            .execute()
    )
    return Transaction(**result.data[0])

async def get_pending_transactions(merchant_id: str) -> list[Transaction]:
    """Get all pending transactions for merchant, ordered by created_at DESC."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
    )
    return [Transaction(**row) for row in result.data]

async def get_recent_duplicate(
    merchant_id: str,
    entity_id: str,
    amount: float,
    direction: str,
    minutes: int = 10
) -> Transaction | None:
    """Check for duplicate: same entity + amount + direction within X minutes."""
    from utils.timezone import now_ist
    from datetime import timedelta
    
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("entity_id", entity_id)
            .eq("amount", amount)
            .eq("direction", direction)
            .gte("created_at", cutoff)
            .neq("status", "rejected")
            .execute()
    )
    if result.data:
        return Transaction(**result.data[0])
    return None

async def get_entity_balance(merchant_id: str, entity_id: str) -> float:
    """
    Calculate net balance for an entity.
    Positive = entity owes merchant. Negative = merchant owes entity.
    incoming transactions add to balance (entity paid or returned money).
    outgoing transactions subtract (merchant gave credit/goods).
    Wait — actually:
    - incoming (entity paid merchant) → reduces what entity owes
    - outgoing credit_given (merchant gave credit) → increases what entity owes
    So: balance = SUM(outgoing amounts) - SUM(incoming amounts)
    Positive balance = entity owes merchant.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .select("amount, direction")
            .eq("merchant_id", merchant_id)
            .eq("entity_id", entity_id)
            .eq("status", "confirmed")
            .execute()
    )
    balance = 0.0
    for row in result.data:
        if row["direction"] == "outgoing":
            balance += float(row["amount"])
        else:
            balance -= float(row["amount"])
    return balance

async def get_daily_transactions(merchant_id: str) -> list[Transaction]:
    """Get today's confirmed transactions for merchant (IST timezone)."""
    start = today_start_ist().isoformat()
    end = today_end_ist().isoformat()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("status", "confirmed")
            .gte("created_at", start)
            .lte("created_at", end)
            .execute()
    )
    return [Transaction(**row) for row in result.data]

async def get_report_data(merchant_id: str, days: int = 30) -> ReportData:
    """Aggregate transaction data for report generation."""
    from datetime import timedelta
    
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    loop = asyncio.get_event_loop()
    
    # Get all confirmed transactions in period
    tx_result = await loop.run_in_executor(
        None,
        lambda: supabase.table("transactions")
            .select("*, entities(name)")
            .eq("merchant_id", merchant_id)
            .eq("status", "confirmed")
            .gte("created_at", cutoff)
            .execute()
    )
    
    transactions = tx_result.data
    total_inflow = sum(float(t["amount"]) for t in transactions if t["direction"] == "incoming")
    total_outflow = sum(float(t["amount"]) for t in transactions if t["direction"] == "outgoing")
    
    # Group by entity for balances
    entity_map = {}
    for t in transactions:
        eid = t["entity_id"]
        if eid not in entity_map:
            entity_name = t.get("entities", {}).get("name", "Unknown") if t.get("entities") else "Unknown"
            entity_map[eid] = {"name": entity_name, "incoming": 0.0, "outgoing": 0.0}
        if t["direction"] == "incoming":
            entity_map[eid]["incoming"] += float(t["amount"])
        else:
            entity_map[eid]["outgoing"] += float(t["amount"])
    
    entity_balances = [
        EntityBalance(
            entity_name=v["name"],
            total_incoming=v["incoming"],
            total_outgoing=v["outgoing"],
            net_balance=v["outgoing"] - v["incoming"]
        )
        for v in entity_map.values()
    ]
    
    # Get merchant shop name
    merchant_result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants")
            .select("shop_name")
            .eq("id", merchant_id)
            .execute()
    )
    shop_name = merchant_result.data[0]["shop_name"] if merchant_result.data else "Unknown Shop"
    
    return ReportData(
        shop_name=shop_name,
        period_days=days,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        net_position=total_inflow - total_outflow,
        entity_balances=entity_balances,
        transaction_count=len(transactions),
        generated_at=datetime.now(timezone.utc)
    )

async def log_message(
    merchant_id: str,
    direction: str,
    message_type: str,
    telegram_message_id: int,
    raw_content: str
) -> None:
    """Log inbound/outbound message for debugging."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: supabase.table("message_log")
            .insert({
                "merchant_id": merchant_id,
                "direction": direction,
                "message_type": message_type,
                "telegram_message_id": telegram_message_id,
                "raw_content": raw_content
            })
            .execute()
    )

async def get_all_active_merchants() -> list[Merchant]:
    """Get all merchants who have completed onboarding. For daily summary."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: supabase.table("merchants")
            .select("*")
            .eq("is_onboarding", False)
            .execute()
    )
    return [Merchant(**row) for row in result.data]
```

**Verify:** Write a quick test script that creates a merchant, creates an entity, creates a transaction, queries it back. Then delete test data.

---

### Task 3.4: Utility files

**Create file:** `utils/__init__.py` (empty)

**Create file:** `utils/timezone.py`
Implement exactly as shown in CONVENTIONS.md Section 11.

**Create file:** `utils/rate_limiter.py`

```python
from collections import defaultdict
from datetime import date

# In-memory rate limiter. Resets on process restart and daily.
# Acceptable for single-instance deployment.

_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Structure: {merchant_id: {date_string: count}}

def check_rate_limit(merchant_id: str, max_per_day: int = 50) -> bool:
    """Returns True if under limit, False if rate limited."""
    today = date.today().isoformat()
    
    # Clean old dates (simple garbage collection)
    if merchant_id in _counts:
        old_dates = [d for d in _counts[merchant_id] if d != today]
        for d in old_dates:
            del _counts[merchant_id][d]
    
    current = _counts[merchant_id][today]
    return current < max_per_day

def increment_rate_limit(merchant_id: str) -> None:
    """Increment message count for today."""
    today = date.today().isoformat()
    _counts[merchant_id][today] += 1

def get_remaining(merchant_id: str, max_per_day: int = 50) -> int:
    """Get remaining messages for today."""
    today = date.today().isoformat()
    return max_per_day - _counts[merchant_id][today]
```

**Day 1 Done Criteria for Dev 3:**
- [ ] All Pydantic models created and importable
- [ ] Supabase project created, all tables created
- [ ] Storage bucket "voice-receipts" created
- [ ] All DB query functions implemented
- [ ] Timezone utils working
- [ ] Rate limiter working
- [ ] Test script verifying CRUD operations on Supabase

---

# DAY 2

---

## Day 2 — Dev 1: Sender Refinements + Webhook Hardening

### Task 1.7: Add message logging to webhook

Update `telegram/webhook.py`:
- After receiving any message, call `log_message()` from `db/queries.py` to log it
- For Day 2, use a mock/pass since handler isn't connected yet — just add the structure
- Add try/except around the entire handler with fallback error message
- Add support for `/start` command detection (text == "/start" → treat as first message)

### Task 1.8: Handle edge cases in webhook

Update `telegram/webhook.py` to handle:
- Photo messages → respond "सिर्फ़ voice note या text भेजिए"
- Sticker/GIF → same response
- Video → same response
- Location → same response
- Empty text messages → ignore
- Very long voice notes (>60 seconds via `message.voice.duration`) → respond "कृपया छोटा voice note भेजिए (1 मिनट से कम)"

### Task 1.9: Test audio format compatibility

Critical test: Record 10 different voice notes on Telegram (different lengths, background noise, Hindi + Hinglish, numbers spoken in Hindi). Save them. These become the shared test corpus for Dev 2.

**Share test files with Dev 2** via shared drive or git (put in `tests/audio/` folder, gitignore in production).

**Day 2 Done Criteria for Dev 1:**
- [ ] Webhook handles all message types gracefully
- [ ] /start command detected
- [ ] 10 test audio files recorded and shared with Dev 2
- [ ] Error handling on all paths

---

## Day 2 — Dev 2: Extraction Service + Prompt Testing

### Task 2.3: Extraction service

**Create file:** `services/extraction.py`

```python
from groq import Groq
from config import settings
from db.models import ExtractionResult
from prompts.extraction_prompt import get_extraction_prompt
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)

async def extract_from_transcript(
    transcript: str,
    existing_entities: list[str]
) -> ExtractionResult:
    """
    Send transcript to Groq Llama 3.3 70B for intent classification + extraction.
    
    Args:
        transcript: Hindi/Hinglish transcript from Whisper
        existing_entities: Known entity names for this merchant
    
    Returns:
        ExtractionResult with intent, confidence, and extracted data
    """
    try:
        system_prompt = get_extraction_prompt(existing_entities)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript}
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
        )
        
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        
        return ExtractionResult(
            intent=parsed.get("intent", "unknown"),
            confidence=parsed.get("confidence", 0.0),
            transactions=parsed.get("transactions"),
            query_person=parsed.get("query_person"),
            correction_data=parsed.get("correction_data"),
            raw_llm_response=raw
        )
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error from LLM: {e}")
        return ExtractionResult(
            intent="unknown",
            confidence=0.0,
            raw_llm_response=str(e)
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractionResult(
            intent="unknown",
            confidence=0.0,
            raw_llm_response=str(e)
        )
```

---

### Task 2.4: Test extraction with 20+ samples

Test the FULL pipeline: audio file → transcribe → extract. Use the 10 audio files from Dev 1 plus create 10 more covering:

**Test cases (minimum):**
1. Simple payment: "Ramesh ne 500 diye" → incoming, payment, 500
2. Credit given: "Suresh 2000 ka saamaan le gaya udhaar" → outgoing, credit_given, 2000
3. Credit recovery: "Mohan ne udhaar ke 1000 wapas diye" → incoming, credit_recovery, 1000
4. Expense: "Wholesale se 5000 ka maal aaya" → outgoing, expense, 5000
5. Multi-transaction: "Ramesh 500, Suresh 300, Mohan 1000 — sab ne diye" → 3 incoming payments
6. Hindi numbers: "paanch sau" → 500
7. Mixed Hindi/English: "Ramesh ne 500 rupees diye for cement order" → incoming, payment, item=cement
8. Balance query: "Ramesh ka kitna baaki hai" → balance_query
9. Report request: "mera hisaab bhejo" → report_request
10. Correction: "woh 500 nahi 300 tha" → correction
11. Greeting: "namaste" → greeting
12. Ambiguous: "Ramesh 500" (direction unclear) → should still extract with lower confidence
13. No name: "500 rupaye aaye" → should flag missing name
14. Honorifics: "Ramesh bhai ne diye 200" → person_name should be "Ramesh" (stripped)
15. Large amount: "Ramesh ne ek lakh diya" → 100000
16. Decimal-ish: "dhai sau" → 250
17. With item: "Suresh ne 3 bag cement liya udhaar" → outgoing, credit_given, item=cement
18. Colloquial: "Ramu ka 500 aa gaya" → incoming, credit_recovery or payment
19. Multiple corrections: "number 2 galat hai, 300 hona chahiye" → correction with index reference
20. Random noise / unclear speech → unknown intent

**Create file:** `tests/test_extraction.py` — log results of all 20 tests with pass/fail.

**Day 2 Done Criteria for Dev 2:**
- [ ] Extraction service working end-to-end
- [ ] 20+ test cases run
- [ ] At least 85% accuracy on test cases
- [ ] Edge cases documented (which ones fail and why)
- [ ] Prompt refined based on failures

---

## Day 2 — Dev 3: Handler Orchestration + Entity Resolution

### Task 3.5: Entity resolver

**Create file:** `services/entity_resolver.py`

```python
from db.queries import find_entity_by_name, create_entity, get_merchant_entities
import logging
import re

logger = logging.getLogger(__name__)

# Honorifics to strip during normalization
HONORIFICS = ["ji", "bhai", "bhaiya", "didi", "amma", "chacha", "mama", "sahab", "seth", "madam"]

def normalize_name(name: str) -> str:
    """
    Normalize entity name:
    1. Strip leading/trailing whitespace
    2. Remove common honorifics
    3. Title case
    
    Examples:
        "Ramesh bhai" → "Ramesh"
        "  suresh JI " → "Suresh"
        "MOHAN" → "Mohan"
    """
    name = name.strip()
    words = name.split()
    filtered = [w for w in words if w.lower() not in HONORIFICS]
    if not filtered:
        # All words were honorifics, keep original
        filtered = words
    return " ".join(w.capitalize() for w in filtered)

async def resolve_entity(merchant_id: str, raw_name: str) -> tuple[str | None, str | None]:
    """
    Resolve a raw name to an entity ID.
    
    Returns:
        (entity_id, normalized_name) if resolved or created
        (None, None) if name is empty/invalid
    """
    if not raw_name or not raw_name.strip():
        return None, None
    
    normalized = normalize_name(raw_name)
    
    if not normalized:
        return None, None
    
    # Try exact match
    entity = await find_entity_by_name(merchant_id, normalized)
    if entity:
        logger.info(f"Entity resolved: '{raw_name}' → '{normalized}' (existing: {entity.id})")
        return entity.id, normalized
    
    # No match — create new entity
    entity = await create_entity(merchant_id, normalized)
    logger.info(f"Entity created: '{raw_name}' → '{normalized}' (new: {entity.id})")
    return entity.id, normalized
```

---

### Task 3.6: Main handler (the orchestrator)

**Create file:** `services/handler.py`

This is the most complex file. It handles ALL intents and orchestrates the full flow.

```python
import asyncio
import uuid
import logging
from db.models import (
    HandlerResponse, ExtractionResult, CreateTransactionInput,
    DocumentResponse
)
from db.queries import (
    get_merchant_by_telegram_id, create_merchant, update_merchant_shop_name,
    complete_onboarding, get_merchant_entities, create_transaction,
    get_pending_transactions, get_recent_duplicate, confirm_transaction,
    reject_transaction, update_transaction_amount, get_entity_balance,
    find_entity_by_name, get_report_data, log_message
)
from services.transcription import transcribe_audio
from services.extraction import extract_from_transcript
from services.entity_resolver import resolve_entity, normalize_name
from services.report_generator import generate_report
from services.scheduler import schedule_auto_confirm, cancel_auto_confirm
from utils.rate_limiter import check_rate_limit, increment_rate_limit
from config import settings

logger = logging.getLogger(__name__)

# Hindi messages
MESSAGES = {
    "welcome": "🙏 नमस्ते! VoiceBooks में आपका स्वागत है। अपनी दुकान का नाम बताइए।",
    "registered": "✅ धन्यवाद! {shop_name} रजिस्टर हो गया। अब आप अपने लेनदेन voice note में भेज सकते हैं।",
    "not_understood": "🤔 माफ़ कीजिए, समझ नहीं आया। कृपया दोबारा बोलिए।",
    "error": "⚠️ अभी थोड़ी दिक्कत है, थोड़ी देर में दोबारा भेजिए।",
    "transcription_failed": "🤔 आवाज़ साफ़ नहीं आई। कृपया दोबारा बोलिए।",
    "low_confidence": "🤔 पूरा समझ नहीं आया। कृपया दोबारा बताइए।",
    "name_ask": "❓ किसका नाम बताएं?",
    "duplicate_warning": "⚠️ यह पहले भी लॉग हो चुका है ({person} ₹{amount}) — दोबारा सेव करें? (हाँ/नहीं)",
    "confirm_ask": "\nक्या यह सही है? (हाँ/नहीं)",
    "confirmed": "✅ सभी लेनदेन सेव हो गए।",
    "balance_response": "💰 {person} का हिसाब: ₹{balance} {status}",
    "no_entity_found": "❓ '{name}' नाम से कोई नहीं मिला।",
    "report_sent": "📄 आपकी रिपोर्ट तैयार है।",
    "rate_limited": "⚠️ आज की लिमिट पूरी हो गई। कल दोबारा भेजिए।",
    "greeting": "🙏 नमस्ते! Voice note भेजकर लेनदेन रिकॉर्ड करें, या 'hisaab bhejo' बोलें रिपोर्ट के लिए।",
    "correction_applied": "✅ सुधार हो गया। ₹{old} → ₹{new}",
    "correction_no_pending": "❓ कोई pending लेनदेन नहीं है जो सुधारा जा सके।",
}

DIRECTION_HINDI = {
    ("incoming", "payment"): "मिले",
    ("incoming", "credit_recovery"): "उधार वापस मिले",
    ("outgoing", "credit_given"): "उधार दिया",
    ("outgoing", "expense"): "खर्च",
}

async def process_message(
    telegram_id: int,
    telegram_username: str | None,
    audio_bytes: bytes | None,
    text: str | None,
    message_id: int
) -> HandlerResponse:
    """
    Main orchestrator. Routes every incoming message.
    
    Flow:
    1. Get or create merchant
    2. Check onboarding state
    3. Rate limit check
    4. If voice: transcribe → extract
    5. If text: extract directly (or handle confirmation replies)
    6. Route by intent
    """
    try:
        # Step 1: Get or create merchant
        merchant = await get_merchant_by_telegram_id(telegram_id)
        if not merchant:
            merchant = await create_merchant(telegram_id, telegram_username)
            return HandlerResponse(messages=[MESSAGES["welcome"]])
        
        # Step 2: Onboarding
        if merchant.is_onboarding:
            return await _handle_onboarding(merchant, audio_bytes, text, message_id)
        
        # Step 3: Rate limit
        if not check_rate_limit(merchant.id):
            return HandlerResponse(messages=[MESSAGES["rate_limited"]])
        increment_rate_limit(merchant.id)
        
        # Step 4: Check for simple text confirmations (haan/nahi)
        if text and not audio_bytes:
            lower = text.strip().lower()
            if lower in ["haan", "ha", "हाँ", "हां", "yes", "y", "sahi"]:
                return await _handle_confirm_all(merchant)
            elif lower in ["nahi", "nhi", "नहीं", "no", "n", "galat"]:
                return await _handle_reject_pending(merchant)
        
        # Step 5: Transcribe if voice
        transcript = text
        audio_url = None
        if audio_bytes:
            result = await transcribe_audio(audio_bytes)
            if not result.success:
                return HandlerResponse(messages=[MESSAGES["transcription_failed"]])
            transcript = result.text
            
            # Upload audio to Supabase storage
            # (implement in _upload_audio helper)
            audio_url = await _upload_audio(merchant.id, message_id, audio_bytes)
        
        if not transcript or not transcript.strip():
            return HandlerResponse(messages=[MESSAGES["not_understood"]])
        
        # Step 6: Extract intent + data
        entities = await get_merchant_entities(merchant.id)
        entity_names = [e.name for e in entities]
        extraction = await extract_from_transcript(transcript, entity_names)
        
        # Step 7: Route by intent
        if extraction.confidence < 0.7:
            return HandlerResponse(messages=[MESSAGES["low_confidence"]])
        
        match extraction.intent:
            case "new_transaction":
                return await _handle_new_transactions(merchant, extraction, transcript, audio_url, message_id)
            case "correction":
                return await _handle_correction(merchant, extraction)
            case "balance_query":
                return await _handle_balance_query(merchant, extraction)
            case "report_request":
                return await _handle_report_request(merchant)
            case "greeting":
                return HandlerResponse(messages=[MESSAGES["greeting"]])
            case _:
                return HandlerResponse(messages=[MESSAGES["not_understood"]])
    
    except Exception as e:
        logger.error(f"Handler error for telegram_id={telegram_id}: {e}")
        return HandlerResponse(messages=[MESSAGES["error"]])


async def _handle_onboarding(merchant, audio_bytes, text, message_id):
    """Handle onboarding: extract shop name from voice or text."""
    shop_name = text
    if audio_bytes:
        result = await transcribe_audio(audio_bytes)
        if result.success:
            shop_name = result.text
    
    if not shop_name or not shop_name.strip():
        return HandlerResponse(messages=[MESSAGES["welcome"]])
    
    shop_name = shop_name.strip()
    await update_merchant_shop_name(merchant.id, shop_name)
    await complete_onboarding(merchant.id)
    
    return HandlerResponse(
        messages=[MESSAGES["registered"].format(shop_name=shop_name)]
    )


async def _handle_new_transactions(merchant, extraction, transcript, audio_url, message_id):
    """Handle one or more new transactions."""
    if not extraction.transactions:
        return HandlerResponse(messages=[MESSAGES["not_understood"]])
    
    batch_id = str(uuid.uuid4())
    created = []
    messages = []
    
    for i, tx_data in enumerate(extraction.transactions):
        # Resolve entity
        entity_id, entity_name = await resolve_entity(merchant.id, tx_data.person_name)
        if not entity_id:
            messages.append(MESSAGES["name_ask"])
            continue
        
        # Duplicate check
        dup = await get_recent_duplicate(
            merchant.id, entity_id, tx_data.amount, tx_data.direction
        )
        if dup:
            messages.append(MESSAGES["duplicate_warning"].format(
                person=entity_name, amount=tx_data.amount
            ))
            continue
        
        # Create transaction
        tx = await create_transaction(CreateTransactionInput(
            merchant_id=merchant.id,
            entity_id=entity_id,
            amount=tx_data.amount,
            direction=tx_data.direction,
            transaction_type=tx_data.transaction_type,
            item=tx_data.item,
            audio_url=audio_url,
            raw_transcript=transcript,
            message_id=message_id,
            batch_id=batch_id
        ))
        created.append((tx, entity_name, tx_data))
    
    # Build confirmation message
    if created:
        confirm_msg = "📝 लेनदेन:\n"
        tx_ids = []
        for i, (tx, name, data) in enumerate(created, 1):
            direction_hindi = DIRECTION_HINDI.get(
                (data.direction, data.transaction_type), data.direction
            )
            item_str = f" ({data.item})" if data.item else ""
            confirm_msg += f"{i}. {name} — ₹{data.amount} {direction_hindi}{item_str}\n"
            tx_ids.append(tx.id)
        
        confirm_msg += MESSAGES["confirm_ask"]
        messages.insert(0, confirm_msg)
        
        # Schedule auto-confirm after 2 minutes
        schedule_auto_confirm(tx_ids, settings.AUTO_CONFIRM_DELAY_SECONDS)
    
    if not messages:
        messages = [MESSAGES["not_understood"]]
    
    return HandlerResponse(messages=messages)


async def _handle_confirm_all(merchant):
    """Confirm all pending transactions for merchant."""
    pending = await get_pending_transactions(merchant.id)
    if not pending:
        return HandlerResponse(messages=[MESSAGES["greeting"]])
    
    for tx in pending:
        await confirm_transaction(tx.id)
        cancel_auto_confirm([tx.id])
    
    return HandlerResponse(messages=[MESSAGES["confirmed"]])


async def _handle_reject_pending(merchant):
    """Reject all pending transactions (merchant said no)."""
    pending = await get_pending_transactions(merchant.id)
    if not pending:
        return HandlerResponse(messages=[MESSAGES["greeting"]])
    
    for tx in pending:
        await reject_transaction(tx.id)
        cancel_auto_confirm([tx.id])
    
    return HandlerResponse(messages=["❌ लेनदेन रद्द कर दिए गए। दोबारा बोलिए।"])


async def _handle_correction(merchant, extraction):
    """Handle correction of most recent pending transaction."""
    pending = await get_pending_transactions(merchant.id)
    if not pending:
        return HandlerResponse(messages=[MESSAGES["correction_no_pending"]])
    
    correction = extraction.correction_data
    if not correction:
        return HandlerResponse(messages=[MESSAGES["not_understood"]])
    
    # Match: find pending tx with original_amount or just use most recent
    target = pending[0]  # most recent pending
    if correction.get("original_amount"):
        for tx in pending:
            if tx.amount == correction["original_amount"]:
                target = tx
                break
    
    new_amount = correction.get("new_amount")
    if new_amount:
        old_amount = target.amount
        await update_transaction_amount(target.id, new_amount)
        return HandlerResponse(messages=[
            MESSAGES["correction_applied"].format(old=old_amount, new=new_amount)
        ])
    
    return HandlerResponse(messages=[MESSAGES["not_understood"]])


async def _handle_balance_query(merchant, extraction):
    """Handle balance query for an entity."""
    person = extraction.query_person
    if not person:
        return HandlerResponse(messages=[MESSAGES["name_ask"]])
    
    normalized = normalize_name(person)
    entity = await find_entity_by_name(merchant.id, normalized)
    if not entity:
        return HandlerResponse(messages=[
            MESSAGES["no_entity_found"].format(name=person)
        ])
    
    balance = await get_entity_balance(merchant.id, entity.id)
    
    if balance > 0:
        status = f"उधार बाकी है (आपको मिलने हैं)"
    elif balance < 0:
        status = f"आपको देना है"
        balance = abs(balance)
    else:
        status = "बराबर है ✅"
    
    return HandlerResponse(messages=[
        MESSAGES["balance_response"].format(
            person=normalized, balance=balance, status=status
        )
    ])


async def _handle_report_request(merchant):
    """Generate and return PDF report."""
    try:
        report_data = await get_report_data(merchant.id)
        pdf_bytes = await generate_report(
            merchant.id, report_data.shop_name
        )
        
        return HandlerResponse(
            messages=[MESSAGES["report_sent"]],
            documents=[DocumentResponse(
                file_bytes=pdf_bytes,
                filename=f"VoiceBooks_Report_{report_data.shop_name}.pdf",
                caption=MESSAGES["report_sent"]
            )]
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return HandlerResponse(messages=[MESSAGES["error"]])


async def _upload_audio(merchant_id: str, message_id: int, audio_bytes: bytes) -> str | None:
    """Upload audio to Supabase Storage, return public URL."""
    try:
        from db.connection import supabase
        path = f"{merchant_id}/{message_id}.oga"
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: supabase.storage.from_("voice-receipts").upload(path, audio_bytes)
        )
        
        url = supabase.storage.from_("voice-receipts").get_public_url(path)
        return url
    except Exception as e:
        logger.warning(f"Audio upload failed: {e}")
        return None
```

**Day 2 Verify for Dev 3 Task 3.6:**
- [ ] Handler can process a mock extraction result and create transactions
- [ ] Onboarding flow works end-to-end with Supabase
- [ ] Confirmation / rejection flow works
- [ ] Balance query works with test data
- [ ] Entity resolution creates and matches correctly

**Day 2 Done Criteria for Dev 3:**
- [ ] Entity resolver working with normalization
- [ ] Handler orchestration complete for all intents
- [ ] Handler tested with mock data (no Telegram/Groq dependency)

---

# DAY 3 — INTEGRATION DAY

---

## Day 3 — All Devs: Connect Everything

### Morning: Dev 1 + Dev 3 — Telegram → Handler

**Task 3.7:** Dev 1 updates `telegram/webhook.py`:
- Remove stub responses
- Uncomment `from services.handler import process_message`
- Call `process_message()` with real data
- Iterate over `response.messages` and send each via `send_text()`
- If `response.documents` exists, send each via `send_document()`

```python
# Updated handle_message in webhook.py:
async def handle_message(message: Message, bot: Bot):
    telegram_id = message.from_user.id
    telegram_username = message.from_user.username
    message_id = message.message_id
    
    audio_bytes = None
    text = None
    
    if message.voice:
        try:
            audio_bytes = await download_voice_note(bot, message.voice.file_id)
        except Exception as e:
            await send_text(bot, telegram_id, "⚠️ अभी थोड़ी दिक्कत है, थोड़ी देर में दोबारा भेजिए।")
            return
    elif message.text:
        text = message.text
    else:
        await send_text(bot, telegram_id, "🤔 सिर्फ़ voice note या text भेजिए।")
        return
    
    response = await process_message(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        audio_bytes=audio_bytes,
        text=text,
        message_id=message_id
    )
    
    for msg in response.messages:
        await send_text(bot, telegram_id, msg)
    
    if response.documents:
        for doc in response.documents:
            await send_document(bot, telegram_id, doc.file_bytes, doc.filename, doc.caption)
```

**Verify:** Send a voice note → get a transaction confirmation back.

### Afternoon: Dev 2 + Dev 3 — Fix Extraction Issues

Any extraction failures found during integration testing → Dev 2 fixes the prompt, Dev 3 adjusts handler logic if needed.

Common Day 3 issues:
- LLM returns unexpected JSON structure → add validation in extraction.py
- Hindi number conversion wrong → fix prompt examples
- Entity names coming through with extra whitespace → fix normalizer
- Supabase type mismatches → fix model fields

### Evening: First End-to-End Test

All 3 devs test together:
1. Fresh Telegram account sends /start → gets welcome message
2. Says shop name → gets registered
3. Sends voice note "Ramesh ne 500 diye" → gets confirmation
4. Replies "haan" → gets confirmed message
5. Sends "Ramesh ka kitna baaki hai" → gets balance
6. Sends voice note with two transactions → gets numbered confirmation
7. Waits 2 minutes → gets auto-confirm
8. Sends correction → gets correction applied

**Day 3 Done Criteria (ALL DEVS):**
- [ ] End-to-end flow working: voice → transcription → extraction → DB → confirmation
- [ ] Onboarding working
- [ ] Text confirmations (haan/nahi) working
- [ ] Balance queries working
- [ ] No crashes on any path

---

# DAY 4

---

## Day 4 — Dev 1: Polish + Edge Cases

### Task 1.10: Handle all remaining edge cases

- Voice note too short (<1 second) → "कृपया थोड़ा और बोलिए"
- Multiple rapid messages → ensure each gets processed (no drops)
- Bot restart resilience → pending transactions should survive restart (they're in DB)

### Task 1.11: Add /help command

When user sends "/help" → respond with usage instructions in Hindi:
```
🎙️ VoiceBooks — कैसे इस्तेमाल करें:

📝 लेनदेन रिकॉर्ड करने के लिए:
Voice note भेजें, जैसे: "Ramesh ne 500 diye"

💰 किसी का हिसाब जानने के लिए:
"Ramesh ka kitna baaki hai"

📊 रिपोर्ट के लिए:
"Mera hisaab bhejo"

✅ कन्फर्म करने के लिए: "haan"
❌ रद्द करने के लिए: "nahi"
```

---

## Day 4 — Dev 2: Prompt Refinement Based on Day 3 Failures

### Task 2.5: Fix any extraction failures from Day 3

Review all failed cases from integration testing. Update prompt with:
- Additional examples for cases that failed
- Better Hindi number handling if needed
- Better handling of ambiguous direction

### Task 2.6: Add text-based extraction support

Some shopkeepers might type instead of sending voice. Ensure extraction works on typed Hindi/Hinglish text too. Test with:
- "Ramesh 500" (minimal text)
- "Ramesh ne diya 500" (typed Hindi)
- "ramesh 500 udhaar" (lowercase Hinglish)

---

## Day 4 — Dev 3: Reports + Daily Summary + Scheduler

### Task 3.8: PDF Report Generator

**Create file:** `services/report_generator.py`

```python
from fpdf import FPDF
from db.queries import get_report_data
from db.models import ReportData
from utils.timezone import now_ist, format_date_hindi
import asyncio
import logging

logger = logging.getLogger(__name__)

async def generate_report(merchant_id: str, shop_name: str, days: int = 30) -> bytes:
    """
    Generate a credit-ready PDF report.
    Bilingual: Hindi + English.
    
    Returns: PDF as bytes
    """
    report = await get_report_data(merchant_id, days)
    
    pdf = FPDF()
    pdf.add_page()
    
    # Note: fpdf2 supports Unicode with add_font()
    # For Hindi text, you need a Unicode font like NotoSansDevanagari
    # Download and add: pdf.add_font("Noto", "", "NotoSansDevanagari-Regular.ttf", uni=True)
    # For v1, use English-only report if Hindi font setup is too complex
    # TODO: Add Hindi font support
    
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"VoiceBooks - Financial Report", new_x="LMARGIN", new_y="NEXT", align="C")
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Shop: {shop_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Period: Last {days} days", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Generated: {format_date_hindi(report.generated_at)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Total Transactions: {report.transaction_count}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Summary
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Summary", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Total Inflow: Rs. {report.total_inflow:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Total Outflow: Rs. {report.total_outflow:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Net Position: Rs. {report.net_position:,.2f}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Receivables / Payables
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Outstanding Balances", new_x="LMARGIN", new_y="NEXT")
    
    # Table header
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 8, "Person", border=1)
    pdf.cell(40, 8, "They Paid (In)", border=1, align="R")
    pdf.cell(40, 8, "Credit Given (Out)", border=1, align="R")
    pdf.cell(40, 8, "Net Balance", border=1, align="R")
    pdf.ln()
    
    pdf.set_font("Helvetica", "", 10)
    for eb in report.entity_balances:
        status = ""
        if eb.net_balance > 0:
            status = " (owes you)"
        elif eb.net_balance < 0:
            status = " (you owe)"
        
        pdf.cell(60, 8, eb.entity_name, border=1)
        pdf.cell(40, 8, f"Rs. {eb.total_incoming:,.2f}", border=1, align="R")
        pdf.cell(40, 8, f"Rs. {eb.total_outgoing:,.2f}", border=1, align="R")
        pdf.cell(40, 8, f"Rs. {abs(eb.net_balance):,.2f}{status}", border=1, align="R")
        pdf.ln()
    
    return bytes(pdf.output())
```

**Verify:** Generate a test report with mock data, open the PDF, verify it looks clean.

---

### Task 3.9: Daily Summary Scheduler

**Create file:** `services/scheduler.py`

```python
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db.queries import get_all_active_merchants, get_daily_transactions, confirm_transaction
from utils.timezone import format_date_hindi, now_ist

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Store pending auto-confirm tasks so we can cancel them
_pending_confirms: dict[str, asyncio.Task] = {}

def init_scheduler(bot):
    """Initialize scheduler with daily summary job. Call during app lifespan startup."""
    scheduler.add_job(
        daily_summary_job,
        CronTrigger(hour=15, minute=30),  # 9 PM IST = 3:30 PM UTC
        args=[bot],
        id="daily_summary",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started — daily summary at 9 PM IST")

def shutdown_scheduler():
    """Shutdown scheduler. Call during app lifespan shutdown."""
    scheduler.shutdown()

async def daily_summary_job(bot):
    """Send daily summary to all active merchants."""
    from telegram.sender import send_text
    
    merchants = await get_all_active_merchants()
    today_str = format_date_hindi(now_ist())
    
    for merchant in merchants:
        try:
            transactions = await get_daily_transactions(merchant.id)
            
            if not transactions:
                continue  # Skip merchants with no transactions today
            
            sales = sum(t.amount for t in transactions if t.direction == "incoming")
            credit_given = sum(
                t.amount for t in transactions 
                if t.direction == "outgoing" and t.transaction_type == "credit_given"
            )
            credit_recovered = sum(
                t.amount for t in transactions
                if t.direction == "incoming" and t.transaction_type == "credit_recovery"
            )
            net = sales - credit_given
            
            summary = (
                f"📊 आज का हिसाब ({today_str}):\n"
                f"💰 बिक्री: ₹{sales:,.0f}\n"
                f"📤 उधार दिया: ₹{credit_given:,.0f}\n"
                f"📥 उधार वापस: ₹{credit_recovered:,.0f}\n"
                f"📈 कुल: ₹{net:,.0f}"
            )
            
            await send_text(bot, merchant.telegram_id, summary)
        except Exception as e:
            logger.error(f"Daily summary failed for merchant {merchant.id}: {e}")


# --- Auto-Confirm Timer ---

def schedule_auto_confirm(transaction_ids: list[str], delay_seconds: int = 120):
    """Schedule auto-confirmation after delay."""
    for tx_id in transaction_ids:
        if tx_id in _pending_confirms:
            # Already scheduled, skip
            continue
        
        task = asyncio.get_event_loop().call_later(
            delay_seconds,
            lambda tid=tx_id: asyncio.ensure_future(_auto_confirm(tid))
        )
        _pending_confirms[tx_id] = task
        logger.info(f"Auto-confirm scheduled: {tx_id} in {delay_seconds}s")

def cancel_auto_confirm(transaction_ids: list[str]):
    """Cancel pending auto-confirm tasks."""
    for tx_id in transaction_ids:
        if tx_id in _pending_confirms:
            task = _pending_confirms.pop(tx_id)
            if hasattr(task, 'cancel'):
                task.cancel()
            logger.info(f"Auto-confirm cancelled: {tx_id}")

async def _auto_confirm(transaction_id: str):
    """Auto-confirm a single transaction if still pending."""
    try:
        from db.queries import get_pending_transactions
        # Verify still pending before confirming
        tx = await confirm_transaction(transaction_id)
        logger.info(f"Auto-confirmed: {transaction_id}")
    except Exception as e:
        logger.error(f"Auto-confirm failed for {transaction_id}: {e}")
    finally:
        _pending_confirms.pop(transaction_id, None)
```

**Update `main.py`** (Dev 1 does this with Dev 3's guidance):
```python
# In lifespan:
from services.scheduler import init_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    from telegram.webhook import register_handlers
    register_handlers(dp)
    init_scheduler(bot)
    yield
    shutdown_scheduler()
    await bot.session.close()
```

**Day 4 Done Criteria:**
- [ ] Dev 1: Edge cases handled, /help command working
- [ ] Dev 2: Prompt refined, text extraction verified
- [ ] Dev 3: PDF report generating correctly, daily summary scheduler running, auto-confirm timer working
- [ ] All features integrated and testable

---

# DAY 5 — DEPLOYMENT + TESTING

---

## Day 5 — All Devs: Test + Deploy

### Morning: End-to-End Test Checklist

Test EVERY flow with real phones. All 3 devs testing simultaneously.

**Test Script:**

| # | Action | Expected Result | Pass? |
|---|--------|----------------|-------|
| 1 | New user sends /start | Welcome message asking for shop name | |
| 2 | User sends shop name (voice) | Registration confirmation | |
| 3 | Send "Ramesh ne 500 diye" (voice) | Transaction confirmation with Ramesh, ₹500, incoming | |
| 4 | Reply "haan" | "सभी लेनदेन सेव हो गए" | |
| 5 | Send "Suresh 2000 udhaar" (voice) | Confirmation: Suresh, ₹2000, outgoing credit | |
| 6 | Wait 2 minutes, don't reply | Auto-confirm message | |
| 7 | Send "Ramesh ka kitna baaki hai" (voice) | Balance: ₹500 (or correct amount) | |
| 8 | Send "mera hisaab bhejo" (voice) | PDF report delivered | |
| 9 | Send multi-transaction voice note | Numbered confirmation | |
| 10 | Reply "nahi" | Transactions rejected | |
| 11 | Send same transaction twice within 10 min | Duplicate warning | |
| 12 | Send "woh 500 nahi 300 tha" after a pending tx | Correction applied | |
| 13 | Send random noise audio | "समझ नहीं आया" message | |
| 14 | Send photo/sticker | "सिर्फ़ voice note या text" message | |
| 15 | Send /help | Help message with instructions | |
| 16 | Wait until 9 PM IST | Daily summary arrives (if transactions today) | |
| 17 | Send 51+ messages in a day | Rate limit message | |

### Afternoon: Deployment to Railway

**Dev 1 handles deployment:**

1. Push all code to GitHub repo
2. Connect Railway to GitHub
3. Set all environment variables in Railway dashboard:
   - TELEGRAM_BOT_TOKEN
   - GROQ_API_KEY
   - SUPABASE_URL
   - SUPABASE_KEY
   - ENVIRONMENT=production
4. Railway auto-detects Python from requirements.txt
5. If ffmpeg needed: add nixpacks config or Dockerfile
6. Deploy and verify `/health` endpoint responds
7. Set Telegram webhook to Railway URL:
   ```
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<RAILWAY_URL>/webhook"
   ```
8. Verify webhook is set:
   ```
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```
9. Test with real phone on production URL

### Evening: Final Verification

Run the full test script (above) on the deployed version. Fix any production-only issues (usually environment variables, URL configs, or CORS).

**Day 5 Done Criteria:**
- [ ] All 17 test cases passing
- [ ] Deployed on Railway
- [ ] Webhook configured and responding
- [ ] PDF reports generating and downloadable
- [ ] Daily summary scheduled
- [ ] No crashes after 30 minutes of continuous testing
- [ ] README.md created with setup instructions

---

# PROJECT COMPLETE FILE TREE

```
voicebooks/
├── main.py                          # FastAPI app + webhook endpoint
├── config.py                        # Pydantic Settings (all env vars)
├── requirements.txt                 # Python dependencies
├── Procfile                         # Railway deployment
├── .env                             # Local env (not committed)
├── .env.example                     # Template
├── .gitignore                       # Standard Python + .env
│
├── telegram/
│   ├── __init__.py
│   ├── webhook.py                   # Telegram update handler
│   ├── sender.py                    # Send text/documents to Telegram
│   └── audio.py                     # Download voice notes
│
├── services/
│   ├── __init__.py
│   ├── transcription.py             # Groq Whisper ASR
│   ├── extraction.py                # Groq Llama intent + entity extraction
│   ├── handler.py                   # Main orchestrator (routes all intents)
│   ├── entity_resolver.py           # Name normalization + entity matching
│   ├── report_generator.py          # fpdf2 PDF report generation
│   └── scheduler.py                 # APScheduler + auto-confirm timers
│
├── db/
│   ├── __init__.py
│   ├── connection.py                # Supabase client init
│   ├── models.py                    # ALL Pydantic models (shared contract)
│   └── queries.py                   # ALL database operations
│
├── prompts/
│   ├── __init__.py
│   └── extraction_prompt.py         # Llama 3.3 system prompt
│
├── utils/
│   ├── __init__.py
│   ├── rate_limiter.py              # In-memory rate limiting
│   └── timezone.py                  # IST helpers
│
├── sql/
│   └── init.sql                     # Supabase table creation
│
├── docs/
│   ├── PRD.md                       # Product requirements
│   ├── AGENTS.md                    # Module ownership + contracts
│   ├── CONVENTIONS.md               # Coding standards
│   └── SPRINT.md                    # This file
│
└── tests/
    └── audio/                       # Test voice note files (gitignored)
```
