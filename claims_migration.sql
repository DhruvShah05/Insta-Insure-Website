-- Migration to create claims tables
-- Run this SQL script in your Supabase SQL editor

-- Create claims table
CREATE TABLE IF NOT EXISTS public.claims (
    claim_id SERIAL PRIMARY KEY,
    policy_id INTEGER REFERENCES policies(policy_id) ON DELETE CASCADE,
    member_name VARCHAR(255) NOT NULL,
    claim_type VARCHAR(20) NOT NULL CHECK (claim_type IN ('CASHLESS', 'REIMBURSEMENT')),
    diagnosis TEXT,
    hospital_name VARCHAR(255),
    admission_date DATE,
    discharge_date DATE,
    claimed_amount NUMERIC(12,2),
    settled_amount NUMERIC(12,2),
    settlement_date DATE,
    utr_no VARCHAR(100),
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'APPROVED', 'REJECTED', 'SETTLED')),
    remarks TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create claim documents table
CREATE TABLE IF NOT EXISTS public.claim_documents (
    document_id SERIAL PRIMARY KEY,
    claim_id INTEGER REFERENCES claims(claim_id) ON DELETE CASCADE,
    document_name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL, -- 'MEDICAL_BILL', 'DISCHARGE_SUMMARY', 'PRESCRIPTION', 'LAB_REPORT', 'OTHER'
    drive_file_id VARCHAR(255),
    drive_url TEXT,
    drive_path TEXT,
    file_size INTEGER,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_claims_policy_id ON public.claims (policy_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON public.claims (status);
CREATE INDEX IF NOT EXISTS idx_claims_created_at ON public.claims (created_at);
CREATE INDEX IF NOT EXISTS idx_claims_settlement_date ON public.claims (settlement_date);
CREATE INDEX IF NOT EXISTS idx_claim_documents_claim_id ON public.claim_documents (claim_id);

-- Add comments to document the tables
COMMENT ON TABLE public.claims IS 'Insurance claims submitted by policyholders';
COMMENT ON TABLE public.claim_documents IS 'Documents uploaded for insurance claims';

COMMENT ON COLUMN public.claims.claim_type IS 'Type of claim: CASHLESS or REIMBURSEMENT';
COMMENT ON COLUMN public.claims.status IS 'Current status of the claim';
COMMENT ON COLUMN public.claim_documents.document_type IS 'Category of the uploaded document';

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_claims_updated_at 
    BEFORE UPDATE ON public.claims 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Verify the changes
SELECT table_name, column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name IN ('claims', 'claim_documents') 
ORDER BY table_name, ordinal_position;
