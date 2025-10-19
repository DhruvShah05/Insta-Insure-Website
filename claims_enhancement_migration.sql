-- Enhancement migration for claims table
-- Add approved_amount and claim_number fields (manual input)
-- Run this SQL script in your Supabase SQL editor

-- Add the new columns to the claims table
ALTER TABLE public.claims 
ADD COLUMN IF NOT EXISTS approved_amount NUMERIC(12,2),
ADD COLUMN IF NOT EXISTS claim_number VARCHAR(50) UNIQUE;

-- Add index for better performance on claim_number lookups
CREATE INDEX IF NOT EXISTS idx_claims_claim_number ON public.claims (claim_number);

-- Add comments to document the new fields
COMMENT ON COLUMN public.claims.approved_amount IS 'Amount approved by insurance company for the claim';
COMMENT ON COLUMN public.claims.claim_number IS 'Claim number provided by insurance company (manual input)';

-- Verify the changes
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'claims' 
AND column_name IN ('approved_amount', 'claim_number')
ORDER BY ordinal_position;
