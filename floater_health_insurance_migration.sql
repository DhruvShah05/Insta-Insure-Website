-- Migration to add floater-specific fields to health insurance tables
-- Run this SQL script in your Supabase SQL editor

-- Add floater_sum_insured and floater_bonus columns to health_insurance_details table
ALTER TABLE public.health_insurance_details 
ADD COLUMN IF NOT EXISTS floater_sum_insured NUMERIC(12,2) NULL,
ADD COLUMN IF NOT EXISTS floater_bonus NUMERIC(12,2) NULL;

-- Add floater_sum_insured and floater_bonus columns to pending_health_insurance_details table  
ALTER TABLE public.pending_health_insurance_details 
ADD COLUMN IF NOT EXISTS floater_sum_insured NUMERIC(12,2) NULL,
ADD COLUMN IF NOT EXISTS floater_bonus NUMERIC(12,2) NULL;

-- Add comments to document the new columns
COMMENT ON COLUMN public.health_insurance_details.floater_sum_insured IS 'Sum insured amount for floater health insurance plans (shared across all members)';
COMMENT ON COLUMN public.health_insurance_details.floater_bonus IS 'Bonus amount for floater health insurance plans (shared across all members)';
COMMENT ON COLUMN public.pending_health_insurance_details.floater_sum_insured IS 'Sum insured amount for floater health insurance plans (shared across all members)';
COMMENT ON COLUMN public.pending_health_insurance_details.floater_bonus IS 'Bonus amount for floater health insurance plans (shared across all members)';

-- Create indexes for better query performance (optional)
CREATE INDEX IF NOT EXISTS idx_health_insurance_details_floater_sum_insured ON public.health_insurance_details (floater_sum_insured);
CREATE INDEX IF NOT EXISTS idx_health_insurance_details_floater_bonus ON public.health_insurance_details (floater_bonus);
CREATE INDEX IF NOT EXISTS idx_pending_health_insurance_details_floater_sum_insured ON public.pending_health_insurance_details (floater_sum_insured);
CREATE INDEX IF NOT EXISTS idx_pending_health_insurance_details_floater_bonus ON public.pending_health_insurance_details (floater_bonus);

-- Verify the changes
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name IN ('health_insurance_details', 'pending_health_insurance_details') 
AND column_name IN ('floater_sum_insured', 'floater_bonus')
ORDER BY table_name, column_name;
