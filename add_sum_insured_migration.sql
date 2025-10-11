-- Migration to add sum_insured field to policies and pending_policies tables
-- Run this SQL script in your Supabase SQL editor

-- Add sum_insured column to policies table
ALTER TABLE public.policies 
ADD COLUMN IF NOT EXISTS sum_insured NUMERIC(12,2) NULL;

-- Add sum_insured column to pending_policies table  
ALTER TABLE public.pending_policies 
ADD COLUMN IF NOT EXISTS sum_insured NUMERIC(12,2) NULL;

-- Add comments to document the new columns
COMMENT ON COLUMN public.policies.sum_insured IS 'General sum insured amount for non-health policies';
COMMENT ON COLUMN public.pending_policies.sum_insured IS 'General sum insured amount for non-health policies';

-- Create index on sum_insured for better query performance (optional)
CREATE INDEX IF NOT EXISTS idx_policies_sum_insured ON public.policies (sum_insured);
CREATE INDEX IF NOT EXISTS idx_pending_policies_sum_insured ON public.pending_policies (sum_insured);

-- Verify the changes
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name IN ('policies', 'pending_policies') 
AND column_name = 'sum_insured';
