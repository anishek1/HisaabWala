-- VoiceBooks v1 — Supabase PostgreSQL Schema
-- Run this in Supabase SQL Editor before starting development

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Table: merchants
-- ============================================
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(255),
    shop_name VARCHAR(255),
    language VARCHAR(10) DEFAULT 'hi',
    is_onboarding BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_merchants_telegram_id ON merchants(telegram_id);

-- ============================================
-- Table: entities
-- ============================================
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    contact_type VARCHAR(20),  -- 'smartphone' | 'keypad' | NULL
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate entity names per merchant
    UNIQUE(merchant_id, name)
);

CREATE INDEX idx_entities_merchant_id ON entities(merchant_id);
CREATE INDEX idx_entities_merchant_name ON entities(merchant_id, name);

-- ============================================
-- Table: transactions
-- ============================================
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    amount DECIMAL(12, 2) NOT NULL,
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    transaction_type VARCHAR(30) NOT NULL CHECK (transaction_type IN ('payment', 'credit_given', 'credit_recovery', 'expense')),
    item VARCHAR(255),
    audio_url VARCHAR(500),
    raw_transcript TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')),
    message_id BIGINT,
    batch_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

CREATE INDEX idx_transactions_merchant_id ON transactions(merchant_id);
CREATE INDEX idx_transactions_merchant_status ON transactions(merchant_id, status);
CREATE INDEX idx_transactions_merchant_entity ON transactions(merchant_id, entity_id);
CREATE INDEX idx_transactions_batch ON transactions(batch_id);
CREATE INDEX idx_transactions_created ON transactions(merchant_id, created_at DESC);

-- ============================================
-- Table: message_log
-- ============================================
CREATE TABLE message_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('voice', 'text')),
    telegram_message_id BIGINT,
    raw_content TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_message_log_merchant ON message_log(merchant_id, created_at DESC);

-- ============================================
-- Supabase Storage Bucket (run separately or via dashboard)
-- ============================================
-- Create a bucket named "voice-receipts" in Supabase Dashboard > Storage
-- Set it to public (for audio URL access) or private (with signed URLs)
-- Recommended: public for v1 simplicity

-- ============================================
-- Row Level Security (RLS) — optional for v1
-- ============================================
-- For v1, RLS is not strictly needed since all access is server-side via service key.
-- If you enable RLS later, add policies scoped by merchant_id.
-- ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE message_log ENABLE ROW LEVEL SECURITY;
