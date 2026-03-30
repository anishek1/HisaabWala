import asyncio
import logging
from io import BytesIO

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError

MAX_VOICE_NOTE_SIZE_BYTES = 20 * 1024 * 1024

logger = logging.getLogger(__name__)


async def download_voice_note(bot: Bot, file_id: str) -> bytes:
    logger.info("Starting voice note download.", extra={"file_id": file_id})

    file = await bot.get_file(file_id)
    if file.file_size is not None and file.file_size > MAX_VOICE_NOTE_SIZE_BYTES:
        raise ValueError("File too large")

    buffer = BytesIO()
    await bot.download_file(file.file_path, destination=buffer)
    data = buffer.getvalue()

    logger.info(
        "Voice note downloaded successfully.",
        extra={"file_id": file_id, "size_bytes": len(data)},
    )
    return data


async def download_with_retry(bot: Bot, file_id: str, max_retries: int = 3) -> bytes:
    transient_errors = (TelegramNetworkError, TimeoutError, asyncio.TimeoutError, OSError)
    delays = [1, 2, 4]

    for attempt in range(max_retries):
        try:
            return await download_voice_note(bot, file_id)
        except ValueError:
            logger.exception(
                "Voice note download failed due to validation issue.",
                extra={"file_id": file_id},
            )
            raise
        except transient_errors:
            if attempt >= max_retries - 1:
                logger.exception(
                    "Voice note download failed after retries.",
                    extra={"file_id": file_id, "attempts": max_retries},
                )
                raise
            delay = delays[min(attempt, len(delays) - 1)]
            logger.warning(
                "Transient error during voice note download. Retrying.",
                extra={
                    "file_id": file_id,
                    "attempt": attempt + 1,
                    "next_retry_in_seconds": delay,
                },
            )
            await asyncio.sleep(delay)
        except Exception:
            logger.exception(
                "Non-transient error during voice note download.",
                extra={"file_id": file_id},
            )
            raise

    raise RuntimeError("Retry loop exited unexpectedly.")
