import asyncio
import logging

from groq import Groq

from config import settings
from db.models import TranscriptionResult

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)


async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.oga") -> TranscriptionResult:
    """
    Transcribe audio using Groq Whisper.

    Args:
        audio_bytes: Raw audio bytes (.oga format from Telegram)
        filename: Filename hint for Whisper (include extension)

    Returns:
        TranscriptionResult with text, language, duration, success flag.
        On failure, success=False and error contains the error message.
        NEVER raises exceptions to the caller.
    """
    try:
        loop = asyncio.get_event_loop()
        transcription = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=(filename, audio_bytes),
                language="hi",
                response_format="verbose_json",
            ),
        )

        text = transcription.text.strip() if transcription.text else ""
        language = getattr(transcription, "language", "hi") or "hi"
        duration = getattr(transcription, "duration", 0.0) or 0.0

        if not text:
            logger.warning("Whisper returned empty transcription")
            return TranscriptionResult(
                text="",
                language=language,
                duration_seconds=duration,
                success=False,
                error="Empty transcription returned",
            )

        logger.info(f"Transcription successful: '{text[:80]}...' lang={language} dur={duration}s")
        return TranscriptionResult(
            text=text,
            language=language,
            duration_seconds=duration,
            success=True,
        )

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return TranscriptionResult(
            text="",
            language="",
            duration_seconds=0.0,
            success=False,
            error=str(e),
        )
