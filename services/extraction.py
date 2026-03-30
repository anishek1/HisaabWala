import asyncio
import json
import logging

from groq import Groq

from config import settings
from db.models import ExtractionResult
from prompts.extraction_prompt import get_extraction_prompt

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)


async def extract_from_transcript(
    transcript: str,
    existing_entities: list[str],
) -> ExtractionResult:
    """
    Send transcript to Groq Llama 3.3 70B for intent classification + extraction.

    Args:
        transcript: Hindi/Hinglish transcript from Whisper
        existing_entities: Known entity names for this merchant

    Returns:
        ExtractionResult with intent, confidence, and extracted data.
        On failure, returns intent="unknown" with confidence=0.0.
        NEVER raises exceptions to the caller.
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
                    {"role": "user", "content": transcript},
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            ),
        )

        raw = response.choices[0].message.content
        if not raw:
            logger.warning("LLM returned empty response")
            return ExtractionResult(intent="unknown", confidence=0.0, raw_llm_response="")

        # Clean response — strip markdown backticks if LLM adds them despite instructions
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)

        intent = parsed.get("intent", "unknown")
        confidence = float(parsed.get("confidence", 0.0))

        # Validate transactions if present
        transactions = parsed.get("transactions")
        if transactions is not None:
            validated = []
            for tx in transactions:
                if "amount" not in tx or "direction" not in tx:
                    logger.warning(f"Skipping malformed transaction: {tx}")
                    continue
                amount = float(tx["amount"])
                if amount <= 0:
                    logger.warning(f"Skipping non-positive amount: {amount}")
                    continue
                validated.append(tx)
            transactions = validated if validated else None

        return ExtractionResult(
            intent=intent,
            confidence=confidence,
            transactions=transactions,
            query_person=parsed.get("query_person"),
            correction_data=parsed.get("correction_data"),
            raw_llm_response=raw,
        )

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error from LLM: {e}")
        return ExtractionResult(intent="unknown", confidence=0.0, raw_llm_response=str(e))
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractionResult(intent="unknown", confidence=0.0, raw_llm_response=str(e))
