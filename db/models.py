"""
HisaabWala - Pydantic Models (Shared Contract)
Owner: Dev 3
Status: COMPLETE

This file defines ALL shared data structures. Dev 1 and Dev 2 import from here.
Do NOT remove any existing models — only add new ones.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# --- Handler Response Models (Dev 1 uses these) ---

class DocumentResponse(BaseModel):
    file_bytes: bytes
    filename: str
    caption: str = ""


class HandlerResponse(BaseModel):
    messages: list[str] = Field(default_factory=list)
    documents: list[DocumentResponse] | None = None


# --- AI Pipeline Models (Dev 2 uses these) ---

class TransactionData(BaseModel):
    person_name: str
    amount: float
    direction: str          # "incoming" | "outgoing"
    transaction_type: str   # "payment" | "credit_given" | "credit_recovery" | "expense"
    item: str | None = None


class ExtractionResult(BaseModel):
    intent: str             # "new_transaction" | "correction" | "balance_query" | "report_request" | "greeting" | "unknown"
    confidence: float       # 0.0 to 1.0
    transactions: list[TransactionData] | None = None
    query_person: str | None = None
    correction_data: dict | None = None
    raw_llm_response: str = ""


class TranscriptionResult(BaseModel):
    text: str
    language: str
    duration_seconds: float
    success: bool
    error: str | None = None


# --- Database Row Models (Dev 3) ---

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
    status: str = "pending"  # "pending" | "confirmed" | "rejected"
    message_id: int | None = None
    batch_id: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None


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
