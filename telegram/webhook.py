import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message

from db.models import HandlerResponse
from services.rate_limiter import RateLimiter
from services.stats import stats_tracker
from telegram.audio import download_with_retry
from telegram.sender import send_document, send_text

logger = logging.getLogger(__name__)

processed_message_ids: set[int] = set()
rate_limiter: RateLimiter | None = None


def register_handlers(dp: Dispatcher, limiter: RateLimiter) -> None:
    global rate_limiter
    rate_limiter = limiter
    dp.message.register(handle_message)


async def is_duplicate(message_id: int) -> bool:
    if message_id in processed_message_ids:
        return True
    processed_message_ids.add(message_id)
    return False


async def _stub_handler(
    telegram_id: int,
    telegram_username: str | None,
    audio_bytes: bytes | None,
    text: str | None,
    message_id: int,
) -> HandlerResponse:
    # TEMPORARY - replaced on Day 3
    if text == "/start":
        return HandlerResponse(
            messages=[
                "नमस्ते! मैं हिसाबवाला हूँ। आप अपना टेक्स्ट या वॉइस नोट भेजें, मैं मदद करूँगा।"
            ]
        )

    if text == "/help":
        return HandlerResponse(
            messages=[
                "उपयोग: टेक्स्ट या 1 मिनट से छोटा वॉइस नोट भेजें। "
                "मैं उसे पढ़कर पुष्टि संदेश भेजूँगा।"
            ]
        )

    if audio_bytes is not None:
        return HandlerResponse(
            messages=[f"वॉइस नोट प्राप्त हुआ। आकार: {len(audio_bytes)} बाइट्स।"]
        )

    if text:
        return HandlerResponse(messages=[f"टेक्स्ट प्राप्त हुआ: {text}"])

    return HandlerResponse(messages=["माफ़ कीजिए, मैं संदेश समझ नहीं पाया।"])


async def handle_message(message: Message, bot: Bot) -> None:
    from_user = message.from_user
    if from_user is None:
        logger.warning("Message ignored because from_user is missing.")
        stats_tracker.mark_failed()
        return

    telegram_id = from_user.id
    username = from_user.username
    message_id = message.message_id
    message_type = "unknown"

    logger.info(
        "Processing incoming message.",
        extra={"telegram_id": telegram_id, "message_id": message_id},
    )

    try:
        if rate_limiter is None:
            logger.error("Rate limiter is not initialized.")
        else:
            allowed = await rate_limiter.check_and_increment(telegram_id)
            if not allowed:
                await send_text(
                    bot,
                    telegram_id,
                    "आपने दैनिक सीमा पार कर ली है। कल पुनः प्रयास करें।",
                )
                stats_tracker.mark_processed(telegram_id)
                return

        audio_bytes: bytes | None = None
        text: str | None = None

        if message.voice:
            message_type = "voice"
            if message.voice.duration > 60:
                await send_text(
                    bot, telegram_id, "कृपया छोटा voice note भेजिए (1 मिनट से कम)।"
                )
                stats_tracker.mark_processed(telegram_id)
                return
            try:
                audio_bytes = await download_with_retry(bot, message.voice.file_id)
            except ValueError:
                await send_text(
                    bot,
                    telegram_id,
                    "फाइल बहुत बड़ी है। कृपया छोटा voice note भेजिए।",
                )
                stats_tracker.mark_processed(telegram_id)
                return
            except Exception:
                logger.exception(
                    "Voice note download failed.",
                    extra={"telegram_id": telegram_id, "message_id": message_id},
                )
                await send_text(
                    bot,
                    telegram_id,
                    "वॉइस नोट डाउनलोड नहीं हो पाया। कृपया दोबारा कोशिश करें।",
                )
                stats_tracker.mark_processed(telegram_id)
                return
        elif message.text:
            message_type = "text"
            text = message.text
        else:
            message_type = "unsupported"
            await send_text(bot, telegram_id, "सिर्फ़ voice note या text भेजिए।")
            stats_tracker.mark_processed(telegram_id)
            return

        response = await _stub_handler(
            telegram_id=telegram_id,
            telegram_username=username,
            audio_bytes=audio_bytes,
            text=text,
            message_id=message_id,
        )

        for msg in response.messages:
            await send_text(bot, telegram_id, msg)

        for doc in response.documents or []:
            await send_document(
                bot=bot,
                chat_id=telegram_id,
                file_bytes=doc.file_bytes,
                filename=doc.filename,
                caption=doc.caption,
            )

        stats_tracker.mark_processed(telegram_id)
        logger.info(
            "Message processed successfully.",
            extra={
                "telegram_id": telegram_id,
                "message_id": message_id,
                "message_type": message_type,
            },
        )
    except Exception:
        stats_tracker.mark_failed(telegram_id)
        logger.exception(
            "Unhandled error while processing message.",
            extra={
                "telegram_id": telegram_id,
                "message_id": message_id,
                "message_type": message_type,
            },
        )
