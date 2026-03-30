import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

MAX_TELEGRAM_TEXT_LENGTH = 4096
logger = logging.getLogger(__name__)


def _chunk_text(text: str, max_len: int = MAX_TELEGRAM_TEXT_LENGTH) -> list[str]:
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(line) > max_len:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(line):
                chunks.append(line[start : start + max_len])
                start += max_len
            continue

        if len(current) + len(line) <= max_len:
            current += line
            continue

        if current:
            chunks.append(current)
        current = line

    if current:
        chunks.append(current)

    return chunks


async def send_text(bot: Bot, chat_id: int, text: str) -> None:
    chunks = _chunk_text(text)
    for index, chunk in enumerate(chunks, start=1):
        try:
            await bot.send_message(chat_id, chunk)
            logger.info(
                "Text message sent.",
                extra={
                    "chat_id": chat_id,
                    "chunk_index": index,
                    "total_chunks": len(chunks),
                    "preview": chunk[:80],
                },
            )
        except Exception:
            logger.exception(
                "Failed to send text message chunk.",
                extra={"chat_id": chat_id, "chunk_index": index},
            )


async def send_document(
    bot: Bot,
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    caption: str = "",
) -> None:
    try:
        input_file = BufferedInputFile(file_bytes, filename=filename)
        await bot.send_document(chat_id, input_file, caption=caption)
        logger.info(
            "Document sent.",
            extra={
                "chat_id": chat_id,
                "filename": filename,
                "caption_preview": caption[:80],
            },
        )
    except Exception:
        logger.exception(
            "Failed to send document.",
            extra={"chat_id": chat_id, "filename": filename},
        )
