"""
HisaabWala - Entity Name Resolution
Owner: Dev 3

Normalizes Hindi names by stripping honorifics and matching to existing entities.
Creates new entities when no match found.
"""

import logging

from db.queries import find_entity_by_name, create_entity

logger = logging.getLogger(__name__)

# Common Hindi/Hinglish honorifics to strip
HONORIFICS = [
    "ji", "bhai", "bhaiya", "didi", "amma", "chacha",
    "mama", "sahab", "seth", "madam", "sir", "uncle",
    "aunty", "auntie", "beta", "beti",
]


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
        "chhotu bhaiya" → "Chhotu"
    """
    if not name:
        return ""

    name = name.strip()
    words = name.split()
    filtered = [w for w in words if w.lower() not in HONORIFICS]

    if not filtered:
        # All words were honorifics — keep original words
        filtered = words

    return " ".join(w.capitalize() for w in filtered)


async def resolve_entity(merchant_id: str, raw_name: str) -> tuple[str | None, str | None]:
    """
    Resolve a raw name to an entity ID.

    Steps:
    1. Normalize the name (strip honorifics, title case)
    2. Search for exact match in merchant's entities
    3. If found → return existing entity ID
    4. If not found → create new entity, return new ID

    Args:
        merchant_id: The merchant who owns this entity
        raw_name: Raw name from LLM extraction (may include honorifics)

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
    if entity:
        logger.info(f"Entity created: '{raw_name}' → '{normalized}' (new: {entity.id})")
        return entity.id, normalized

    logger.error(f"Failed to create entity: '{raw_name}' → '{normalized}' for merchant={merchant_id}")
    return None, None
