"""
HisaabWala - Database Operations
Owner: Dev 3

CRITICAL RULES:
- EVERY query that touches merchants/entities/transactions MUST filter by merchant_id
- All functions are async and wrap synchronous supabase calls in run_in_executor
- Never raise exceptions — return None or empty list on failure
- Return Pydantic models, not raw dicts
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from db.connection import supabase
from db.models import (
    Merchant,
    Entity,
    Transaction,
    CreateTransactionInput,
    ReportData,
    EntityBalance,
)
from utils.timezone import today_start_ist, today_end_ist

logger = logging.getLogger(__name__)


def _run_sync(func):
    """Helper to run synchronous supabase calls in executor."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, func)


# ==========================================
# MERCHANTS
# ==========================================

async def get_merchant_by_telegram_id(telegram_id: int) -> Merchant | None:
    """Query merchants table by telegram_id. Return Merchant or None."""
    try:
        result = await _run_sync(
            lambda: supabase.table("merchants")
            .select("*")
            .eq("telegram_id", telegram_id)
            .execute()
        )
        if result.data:
            return Merchant(**result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to get merchant by telegram_id={telegram_id}: {e}")
        return None


async def create_merchant(telegram_id: int, telegram_username: str | None) -> Merchant | None:
    """Insert new merchant row. Return created Merchant."""
    try:
        result = await _run_sync(
            lambda: supabase.table("merchants")
            .insert({
                "telegram_id": telegram_id,
                "telegram_username": telegram_username,
                "is_onboarding": True,
            })
            .execute()
        )
        return Merchant(**result.data[0])
    except Exception as e:
        logger.error(f"Failed to create merchant telegram_id={telegram_id}: {e}")
        return None


async def update_merchant_shop_name(merchant_id: str, shop_name: str) -> Merchant | None:
    """Update shop_name for merchant."""
    try:
        result = await _run_sync(
            lambda: supabase.table("merchants")
            .update({"shop_name": shop_name})
            .eq("id", merchant_id)
            .execute()
        )
        return Merchant(**result.data[0])
    except Exception as e:
        logger.error(f"Failed to update shop name for merchant={merchant_id}: {e}")
        return None


async def complete_onboarding(merchant_id: str) -> Merchant | None:
    """Set is_onboarding=False."""
    try:
        result = await _run_sync(
            lambda: supabase.table("merchants")
            .update({"is_onboarding": False})
            .eq("id", merchant_id)
            .execute()
        )
        return Merchant(**result.data[0])
    except Exception as e:
        logger.error(f"Failed to complete onboarding for merchant={merchant_id}: {e}")
        return None


async def get_all_active_merchants() -> list[Merchant]:
    """Get all merchants who have completed onboarding. For daily summary."""
    try:
        result = await _run_sync(
            lambda: supabase.table("merchants")
            .select("*")
            .eq("is_onboarding", False)
            .execute()
        )
        return [Merchant(**row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get active merchants: {e}")
        return []


# ==========================================
# ENTITIES
# ==========================================

async def find_entity_by_name(merchant_id: str, name: str) -> Entity | None:
    """Find entity by exact normalized name within merchant scope."""
    try:
        result = await _run_sync(
            lambda: supabase.table("entities")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("name", name)
            .execute()
        )
        if result.data:
            return Entity(**result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to find entity name='{name}' merchant={merchant_id}: {e}")
        return None


async def create_entity(merchant_id: str, name: str) -> Entity | None:
    """Create new entity for merchant."""
    try:
        result = await _run_sync(
            lambda: supabase.table("entities")
            .insert({
                "merchant_id": merchant_id,
                "name": name,
            })
            .execute()
        )
        return Entity(**result.data[0])
    except Exception as e:
        logger.error(f"Failed to create entity name='{name}' merchant={merchant_id}: {e}")
        return None


async def get_merchant_entities(merchant_id: str) -> list[Entity]:
    """Get all entities for a merchant. Used to pass existing names to LLM."""
    try:
        result = await _run_sync(
            lambda: supabase.table("entities")
            .select("*")
            .eq("merchant_id", merchant_id)
            .execute()
        )
        return [Entity(**row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get entities for merchant={merchant_id}: {e}")
        return []


# ==========================================
# TRANSACTIONS
# ==========================================

async def create_transaction(data: CreateTransactionInput) -> Transaction | None:
    """Insert new transaction with status='pending'."""
    try:
        insert_data = data.model_dump()
        insert_data["status"] = "pending"
        result = await _run_sync(
            lambda: supabase.table("transactions")
            .insert(insert_data)
            .execute()
        )
        return Transaction(**result.data[0])
    except Exception as e:
        logger.error(f"Failed to create transaction merchant={data.merchant_id}: {e}")
        return None


async def confirm_transaction(transaction_id: str) -> Transaction | None:
    """Set status='confirmed' and confirmed_at=now()."""
    try:
        result = await _run_sync(
            lambda: supabase.table("transactions")
            .update({
                "status": "confirmed",
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", transaction_id)
            .execute()
        )
        if result.data:
            return Transaction(**result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to confirm transaction={transaction_id}: {e}")
        return None


async def reject_transaction(transaction_id: str) -> Transaction | None:
    """Set status='rejected'."""
    try:
        result = await _run_sync(
            lambda: supabase.table("transactions")
            .update({"status": "rejected"})
            .eq("id", transaction_id)
            .execute()
        )
        if result.data:
            return Transaction(**result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to reject transaction={transaction_id}: {e}")
        return None


async def update_transaction_amount(transaction_id: str, new_amount: float) -> Transaction | None:
    """Update amount on a pending transaction."""
    try:
        result = await _run_sync(
            lambda: supabase.table("transactions")
            .update({"amount": new_amount})
            .eq("id", transaction_id)
            .eq("status", "pending")
            .execute()
        )
        if result.data:
            return Transaction(**result.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to update amount on transaction={transaction_id}: {e}")
        return None


async def get_pending_transactions(merchant_id: str) -> list[Transaction]:
    """Get all pending transactions for merchant, ordered by created_at DESC."""
    try:
        result = await _run_sync(
            lambda: supabase.table("transactions")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
        return [Transaction(**row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get pending transactions merchant={merchant_id}: {e}")
        return []


async def get_recent_duplicate(
    merchant_id: str,
    entity_id: str,
    amount: float,
    direction: str,
    minutes: int = 10,
) -> Transaction | None:
    """Check for duplicate: same entity + amount + direction within X minutes."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        result = await _run_sync(
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
    except Exception as e:
        logger.error(f"Failed to check duplicate merchant={merchant_id}: {e}")
        return None


async def get_entity_balance(merchant_id: str, entity_id: str) -> float:
    """
    Calculate net balance for an entity.
    Positive = entity owes merchant (merchant gave more credit than received back).
    Negative = merchant owes entity.

    Logic:
    - outgoing (credit_given/expense to entity) → increases what entity owes → ADD to balance
    - incoming (payment/credit_recovery from entity) → reduces what entity owes → SUBTRACT from balance
    """
    try:
        result = await _run_sync(
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
    except Exception as e:
        logger.error(f"Failed to get balance merchant={merchant_id} entity={entity_id}: {e}")
        return 0.0


async def get_daily_transactions(merchant_id: str) -> list[Transaction]:
    """Get today's confirmed transactions for merchant (IST timezone)."""
    try:
        start = today_start_ist().isoformat()
        end = today_end_ist().isoformat()
        result = await _run_sync(
            lambda: supabase.table("transactions")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("status", "confirmed")
            .gte("created_at", start)
            .lte("created_at", end)
            .execute()
        )
        return [Transaction(**row) for row in result.data]
    except Exception as e:
        logger.error(f"Failed to get daily transactions merchant={merchant_id}: {e}")
        return []


async def get_report_data(merchant_id: str, days: int = 30) -> ReportData | None:
    """Aggregate transaction data for report generation."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get all confirmed transactions in period
        tx_result = await _run_sync(
            lambda: supabase.table("transactions")
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("status", "confirmed")
            .gte("created_at", cutoff)
            .execute()
        )
        transactions = tx_result.data

        total_inflow = sum(float(t["amount"]) for t in transactions if t["direction"] == "incoming")
        total_outflow = sum(float(t["amount"]) for t in transactions if t["direction"] == "outgoing")

        # Get entity names for balance breakdown
        entities = await get_merchant_entities(merchant_id)
        entity_name_map = {e.id: e.name for e in entities}

        # Group by entity for balances
        entity_map: dict[str, dict] = {}
        for t in transactions:
            eid = t["entity_id"]
            if eid not in entity_map:
                entity_map[eid] = {
                    "name": entity_name_map.get(eid, "Unknown"),
                    "incoming": 0.0,
                    "outgoing": 0.0,
                }
            if t["direction"] == "incoming":
                entity_map[eid]["incoming"] += float(t["amount"])
            else:
                entity_map[eid]["outgoing"] += float(t["amount"])

        entity_balances = [
            EntityBalance(
                entity_name=v["name"],
                total_incoming=v["incoming"],
                total_outgoing=v["outgoing"],
                net_balance=v["outgoing"] - v["incoming"],
            )
            for v in entity_map.values()
        ]

        # Get merchant shop name
        merchant_result = await _run_sync(
            lambda: supabase.table("merchants")
            .select("shop_name")
            .eq("id", merchant_id)
            .execute()
        )
        shop_name = (
            merchant_result.data[0]["shop_name"]
            if merchant_result.data and merchant_result.data[0]["shop_name"]
            else "Unknown Shop"
        )

        return ReportData(
            shop_name=shop_name,
            period_days=days,
            total_inflow=total_inflow,
            total_outflow=total_outflow,
            net_position=total_inflow - total_outflow,
            entity_balances=entity_balances,
            transaction_count=len(transactions),
            generated_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"Failed to get report data merchant={merchant_id}: {e}")
        return None


# ==========================================
# MESSAGE LOG
# ==========================================

async def log_message(
    merchant_id: str,
    direction: str,
    message_type: str,
    telegram_message_id: int,
    raw_content: str,
) -> None:
    """Log inbound/outbound message for debugging. Fire-and-forget, never fails loudly."""
    try:
        await _run_sync(
            lambda: supabase.table("message_log")
            .insert({
                "merchant_id": merchant_id,
                "direction": direction,
                "message_type": message_type,
                "telegram_message_id": telegram_message_id,
                "raw_content": raw_content,
            })
            .execute()
        )
    except Exception as e:
        logger.warning(f"Failed to log message (non-critical): {e}")
