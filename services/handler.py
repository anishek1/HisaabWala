"""
HisaabWala - Main Orchestrator
Owner: Dev 3

Routes every incoming message through the full pipeline:
Telegram → Transcription → Extraction → DB → Response

Every public function returns HandlerResponse, never raises exceptions.
"""

import asyncio
import logging
import uuid

from db.models import (
    CreateTransactionInput,
    DocumentResponse,
    HandlerResponse,
)
from db.queries import (
    complete_onboarding,
    confirm_transaction,
    create_merchant,
    create_transaction,
    find_entity_by_name,
    get_entity_balance,
    get_merchant_by_telegram_id,
    get_merchant_entities,
    get_pending_transactions,
    get_recent_duplicate,
    get_report_data,
    log_message,
    reject_transaction,
    update_merchant_shop_name,
    update_transaction_amount,
)
from services.entity_resolver import normalize_name, resolve_entity
from services.extraction import extract_from_transcript
from services.transcription import transcribe_audio

logger = logging.getLogger(__name__)


# ==========================================
# HINDI MESSAGE TEMPLATES
# ==========================================

MESSAGES = {
    "welcome": "🙏 नमस्ते! HisaabWala में आपका स्वागत है। अपनी दुकान का नाम बताइए।",
    "registered": "✅ धन्यवाद! {shop_name} रजिस्टर हो गया। अब आप अपने लेनदेन voice note में भेज सकते हैं।",
    "not_understood": "🤔 माफ़ कीजिए, समझ नहीं आया। कृपया दोबारा बोलिए।",
    "error": "⚠️ अभी थोड़ी दिक्कत है, थोड़ी देर में दोबारा भेजिए।",
    "transcription_failed": "🤔 आवाज़ साफ़ नहीं आई। कृपया दोबारा बोलिए।",
    "low_confidence": "🤔 पूरा समझ नहीं आया। कृपया दोबारा बताइए।",
    "name_ask": "❓ किसका नाम बताएं?",
    "duplicate_warning": "⚠️ यह पहले भी लॉग हो चुका है ({person} ₹{amount}) — दोबारा सेव करें? 'haan' या 'nahi' बोलें।",
    "confirm_ask": "\nक्या यह सही है? 'haan' या 'nahi' बोलें।",
    "confirmed": "✅ सभी लेनदेन सेव हो गए।",
    "auto_confirmed": "✅ लेनदेन ऑटो-कन्फर्म हो गए।",
    "rejected": "❌ लेनदेन रद्द कर दिए गए। दोबारा बोलिए।",
    "balance_response": "💰 {person} का हिसाब: ₹{balance} {status}",
    "no_entity_found": "❓ '{name}' नाम से कोई नहीं मिला।",
    "report_sent": "📄 आपकी रिपोर्ट तैयार है।",
    "report_empty": "📄 अभी कोई लेनदेन नहीं है रिपोर्ट बनाने के लिए।",
    "greeting": "🙏 नमस्ते! Voice note भेजकर लेनदेन रिकॉर्ड करें, या 'hisaab bhejo' बोलें रिपोर्ट के लिए।",
    "correction_applied": "✅ सुधार हो गया। ₹{old} → ₹{new}",
    "correction_no_pending": "❓ कोई pending लेनदेन नहीं है जो सुधारा जा सके।",
    "no_transactions_today": "📊 आज कोई लेनदेन नहीं हुआ।",
    "help": (
        "🎙️ HisaabWala — कैसे इस्तेमाल करें:\n\n"
        "📝 लेनदेन रिकॉर्ड करने के लिए:\n"
        "Voice note भेजें, जैसे: \"Ramesh ne 500 diye\"\n\n"
        "💰 किसी का हिसाब जानने के लिए:\n"
        "\"Ramesh ka kitna baaki hai\"\n\n"
        "📊 रिपोर्ट के लिए:\n"
        "\"Mera hisaab bhejo\"\n\n"
        "✅ कन्फर्म करने के लिए: \"haan\"\n"
        "❌ रद्द करने के लिए: \"nahi\""
    ),
}

# Direction + type → Hindi translation
DIRECTION_HINDI = {
    ("incoming", "payment"): "मिले",
    ("incoming", "credit_recovery"): "उधार वापस मिले",
    ("outgoing", "credit_given"): "उधार दिया",
    ("outgoing", "expense"): "खर्च",
}


# ==========================================
# MAIN ENTRY POINT
# ==========================================

async def process_message(
    telegram_id: int,
    telegram_username: str | None,
    audio_bytes: bytes | None,
    text: str | None,
    message_id: int,
) -> HandlerResponse:
    """
    Main orchestrator. Routes every incoming message.

    Flow:
    1. Get or create merchant
    2. Check onboarding state
    3. If voice: transcribe → extract
    4. If text: check for confirmations, then extract
    5. Route by intent

    NEVER raises exceptions — always returns HandlerResponse.
    """
    try:
        # Step 1: Get or create merchant
        merchant = await get_merchant_by_telegram_id(telegram_id)
        if not merchant:
            merchant = await create_merchant(telegram_id, telegram_username)
            if not merchant:
                return HandlerResponse(messages=[MESSAGES["error"]])
            return HandlerResponse(messages=[MESSAGES["welcome"]])

        # Step 2: Onboarding — if merchant hasn't set shop name yet
        if merchant.is_onboarding:
            return await _handle_onboarding(merchant, audio_bytes, text, message_id)

        # Step 3: Check for simple text commands and confirmations BEFORE extraction
        if text and not audio_bytes:
            lower = text.strip().lower()

            # Commands
            if lower in ["/start"]:
                return HandlerResponse(messages=[MESSAGES["greeting"]])
            if lower in ["/help", "help"]:
                return HandlerResponse(messages=[MESSAGES["help"]])

            # Confirmation replies
            if lower in ["haan", "ha", "हाँ", "हां", "yes", "y", "sahi", "ok"]:
                return await _handle_confirm_all(merchant)
            if lower in ["nahi", "nhi", "नहीं", "no", "n", "galat", "cancel"]:
                return await _handle_reject_pending(merchant)

        # Step 4: Transcribe if voice note
        transcript = text
        audio_url = None
        if audio_bytes:
            tr_result = await transcribe_audio(audio_bytes)
            if not tr_result.success:
                return HandlerResponse(messages=[MESSAGES["transcription_failed"]])
            transcript = tr_result.text

            # Upload audio to Supabase storage (non-critical)
            audio_url = await _upload_audio(merchant.id, message_id, audio_bytes)

        if not transcript or not transcript.strip():
            return HandlerResponse(messages=[MESSAGES["not_understood"]])

        # Log inbound message
        msg_type = "voice" if audio_bytes else "text"
        await log_message(merchant.id, "inbound", msg_type, message_id, transcript)

        # Step 5: Extract intent + data via LLM
        entities = await get_merchant_entities(merchant.id)
        entity_names = [e.name for e in entities]
        extraction = await extract_from_transcript(transcript, entity_names)

        # Step 6: Check confidence
        if extraction.confidence < 0.6:
            return HandlerResponse(messages=[MESSAGES["low_confidence"]])

        # Step 7: Route by intent
        match extraction.intent:
            case "new_transaction":
                return await _handle_new_transactions(
                    merchant, extraction, transcript, audio_url, message_id
                )
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
        logger.error(f"Handler error for telegram_id={telegram_id}: {e}", exc_info=True)
        return HandlerResponse(messages=[MESSAGES["error"]])


# ==========================================
# INTENT HANDLERS
# ==========================================

async def _handle_onboarding(merchant, audio_bytes, text, message_id) -> HandlerResponse:
    """Handle onboarding: extract shop name from voice or text."""
    shop_name = text

    if audio_bytes:
        result = await transcribe_audio(audio_bytes)
        if result.success and result.text.strip():
            shop_name = result.text.strip()

    if not shop_name or not shop_name.strip():
        return HandlerResponse(messages=[MESSAGES["welcome"]])

    shop_name = shop_name.strip()

    # Ignore system commands masquerading as shop name
    if shop_name.lower() in ["/start", "/help"]:
        return HandlerResponse(messages=[MESSAGES["welcome"]])

    updated = await update_merchant_shop_name(merchant.id, shop_name)
    if not updated:
        return HandlerResponse(messages=[MESSAGES["error"]])

    completed = await complete_onboarding(merchant.id)
    if not completed:
        return HandlerResponse(messages=[MESSAGES["error"]])

    return HandlerResponse(
        messages=[MESSAGES["registered"].format(shop_name=shop_name)]
    )


async def _handle_new_transactions(
    merchant, extraction, transcript: str, audio_url: str | None, message_id: int
) -> HandlerResponse:
    """Handle one or more new transactions from a single voice note."""
    if not extraction.transactions:
        return HandlerResponse(messages=[MESSAGES["not_understood"]])

    batch_id = str(uuid.uuid4())
    created: list[tuple] = []
    messages: list[str] = []

    for tx_data in extraction.transactions:
        # Support both Pydantic model and plain dict from LLM
        if isinstance(tx_data, dict):
            person_name = tx_data.get("person_name", "")
            amount = float(tx_data.get("amount", 0))
            direction = tx_data.get("direction", "")
            transaction_type = tx_data.get("transaction_type", "")
            item = tx_data.get("item")
        else:
            person_name = tx_data.person_name
            amount = float(tx_data.amount)
            direction = tx_data.direction
            transaction_type = tx_data.transaction_type
            item = tx_data.item

        # Validate amount
        if amount <= 0:
            logger.warning(f"Skipping non-positive amount: {amount}")
            continue

        # Check if person name is missing
        if not person_name or not person_name.strip():
            messages.append(MESSAGES["name_ask"])
            continue

        # Resolve entity (normalize name, find or create)
        entity_id, entity_name = await resolve_entity(merchant.id, person_name)
        if not entity_id:
            messages.append(MESSAGES["name_ask"])
            continue

        # Duplicate check (within 10 minutes)
        dup = await get_recent_duplicate(merchant.id, entity_id, amount, direction)
        if dup:
            messages.append(
                MESSAGES["duplicate_warning"].format(person=entity_name, amount=int(amount))
            )
            continue

        # Create transaction in pending state
        tx = await create_transaction(CreateTransactionInput(
            merchant_id=merchant.id,
            entity_id=entity_id,
            amount=amount,
            direction=direction,
            transaction_type=transaction_type,
            item=item,
            audio_url=audio_url,
            raw_transcript=transcript,
            message_id=message_id,
            batch_id=batch_id,
        ))

        if tx:
            created.append((tx, entity_name, direction, transaction_type, amount, item))

    # Build confirmation message
    if created:
        confirm_msg = "📝 लेनदेन:\n"
        for i, (tx, name, direction, tx_type, amount, item) in enumerate(created, 1):
            direction_hindi = DIRECTION_HINDI.get((direction, tx_type), direction)
            item_str = f" ({item})" if item else ""
            confirm_msg += f"{i}. {name} — ₹{amount:,.0f} {direction_hindi}{item_str}\n"
        confirm_msg += MESSAGES["confirm_ask"]
        messages.insert(0, confirm_msg)

    if not messages:
        messages = [MESSAGES["not_understood"]]

    return HandlerResponse(messages=messages)


async def _handle_confirm_all(merchant) -> HandlerResponse:
    """Confirm all pending transactions for this merchant."""
    pending = await get_pending_transactions(merchant.id)

    if not pending:
        return HandlerResponse(messages=[MESSAGES["greeting"]])

    confirmed_count = 0
    for tx in pending:
        result = await confirm_transaction(tx.id)
        if result:
            confirmed_count += 1

    if confirmed_count > 0:
        return HandlerResponse(messages=[MESSAGES["confirmed"]])
    return HandlerResponse(messages=[MESSAGES["error"]])


async def _handle_reject_pending(merchant) -> HandlerResponse:
    """Reject all pending transactions for this merchant."""
    pending = await get_pending_transactions(merchant.id)

    if not pending:
        return HandlerResponse(messages=[MESSAGES["greeting"]])

    for tx in pending:
        await reject_transaction(tx.id)

    return HandlerResponse(messages=[MESSAGES["rejected"]])


async def _handle_correction(merchant, extraction) -> HandlerResponse:
    """Handle correction of the most recent pending transaction."""
    pending = await get_pending_transactions(merchant.id)

    if not pending:
        return HandlerResponse(messages=[MESSAGES["correction_no_pending"]])

    correction = extraction.correction_data
    if not correction:
        return HandlerResponse(messages=[MESSAGES["not_understood"]])

    # Default to the most recent pending transaction
    target = pending[0]

    # If original_amount is specified, try to find the matching transaction
    original_amount = correction.get("original_amount")
    if original_amount:
        for tx in pending:
            if tx.amount == float(original_amount):
                target = tx
                break

    # Apply the corrected amount
    new_amount = correction.get("new_amount")
    if new_amount:
        new_amount = float(new_amount)
        old_amount = target.amount
        updated = await update_transaction_amount(target.id, new_amount)
        if updated:
            return HandlerResponse(messages=[
                MESSAGES["correction_applied"].format(old=int(old_amount), new=int(new_amount))
            ])
        return HandlerResponse(messages=[MESSAGES["error"]])

    return HandlerResponse(messages=[MESSAGES["not_understood"]])


async def _handle_balance_query(merchant, extraction) -> HandlerResponse:
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
        status = "उधार बाकी है (आपको मिलने हैं)"
        display_balance = balance
    elif balance < 0:
        status = "आपको देना है"
        display_balance = abs(balance)
    else:
        status = "बराबर है ✅"
        display_balance = 0.0

    return HandlerResponse(messages=[
        MESSAGES["balance_response"].format(
            person=normalized,
            balance=f"{display_balance:,.0f}",
            status=status,
        )
    ])


async def _handle_report_request(merchant) -> HandlerResponse:
    """Generate and return a text summary report (PDF on Day 4)."""
    try:
        report_data = await get_report_data(merchant.id)

        if not report_data or report_data.transaction_count == 0:
            return HandlerResponse(messages=[MESSAGES["report_empty"]])

        summary = _generate_text_report(report_data)
        return HandlerResponse(messages=[summary])

    except Exception as e:
        logger.error(f"Report generation failed for merchant={merchant.id}: {e}", exc_info=True)
        return HandlerResponse(messages=[MESSAGES["error"]])


def _generate_text_report(report_data) -> str:
    """
    Generate a plain-text report summary.
    Temporary solution until the PDF generator is built on Day 4.
    """
    from utils.timezone import format_date_hindi, now_utc

    lines = [
        f"📊 HisaabWala रिपोर्ट — {report_data.shop_name}",
        f"📅 पिछले {report_data.period_days} दिन | {format_date_hindi(now_utc())}",
        f"📋 कुल लेनदेन: {report_data.transaction_count}",
        "",
        f"💰 कुल आमदनी: ₹{report_data.total_inflow:,.0f}",
        f"📤 कुल खर्च/उधार: ₹{report_data.total_outflow:,.0f}",
        f"📈 शुद्ध स्थिति: ₹{report_data.net_position:,.0f}",
    ]

    if report_data.entity_balances:
        lines.append("")
        lines.append("👥 बकाया हिसाब:")
        for eb in report_data.entity_balances:
            if eb.net_balance > 0:
                lines.append(f"  • {eb.entity_name}: ₹{eb.net_balance:,.0f} उधार बाकी")
            elif eb.net_balance < 0:
                lines.append(f"  • {eb.entity_name}: ₹{abs(eb.net_balance):,.0f} आपको देना है")
            else:
                lines.append(f"  • {eb.entity_name}: बराबर ✅")

    return "\n".join(lines)


# ==========================================
# HELPERS
# ==========================================

async def _upload_audio(merchant_id: str, message_id: int, audio_bytes: bytes) -> str | None:
    """Upload audio bytes to Supabase Storage. Returns public URL or None on failure."""
    try:
        from db.connection import supabase

        path = f"{merchant_id}/{message_id}.oga"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: supabase.storage.from_("voice-receipts").upload(
                path, audio_bytes, {"content-type": "audio/ogg"}
            ),
        )
        url = supabase.storage.from_("voice-receipts").get_public_url(path)
        logger.info(f"Audio uploaded: {path}")
        return url
    except Exception as e:
        logger.warning(f"Audio upload failed (non-critical): {e}")
        return None
