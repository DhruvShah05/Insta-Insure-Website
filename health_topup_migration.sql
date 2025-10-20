-- Migration to add health topup support with deductible functionality
-- Run this SQL script in your Supabase SQL editor

-- 1. Add deductible column to health_insured_members table
ALTER TABLE public.health_insured_members 
ADD COLUMN IF NOT EXISTS deductible NUMERIC(12,2) NULL;

-- 2. Add deductible column to pending_health_insured_members table
ALTER TABLE public.pending_health_insured_members 
ADD COLUMN IF NOT EXISTS deductible NUMERIC(12,2) NULL;

-- 3. Add floater_deductible columns to health_insurance_details table
ALTER TABLE public.health_insurance_details 
ADD COLUMN IF NOT EXISTS floater_deductible NUMERIC(12,2) NULL;

-- 4. Add floater_deductible columns to pending_health_insurance_details table
ALTER TABLE public.pending_health_insurance_details 
ADD COLUMN IF NOT EXISTS floater_deductible NUMERIC(12,2) NULL;

-- 5. Update plan_type constraints to include TOPUP options
ALTER TABLE public.health_insurance_details 
DROP CONSTRAINT IF EXISTS health_insurance_details_plan_type_check;

ALTER TABLE public.health_insurance_details 
ADD CONSTRAINT health_insurance_details_plan_type_check 
CHECK (plan_type = ANY (ARRAY['FLOATER'::text, 'INDIVIDUAL'::text, 'TOPUP_FLOATER'::text, 'TOPUP_INDIVIDUAL'::text]));

ALTER TABLE public.pending_health_insurance_details 
DROP CONSTRAINT IF EXISTS pending_health_insurance_details_plan_type_check;

ALTER TABLE public.pending_health_insurance_details 
ADD CONSTRAINT pending_health_insurance_details_plan_type_check 
CHECK (plan_type = ANY (ARRAY['FLOATER'::text, 'INDIVIDUAL'::text, 'TOPUP_FLOATER'::text, 'TOPUP_INDIVIDUAL'::text]));

-- 6. Add comments to document the new columns
COMMENT ON COLUMN public.health_insured_members.deductible IS 'Deductible amount for individual health insurance/topup plans';
COMMENT ON COLUMN public.pending_health_insured_members.deductible IS 'Deductible amount for individual health insurance/topup plans';
COMMENT ON COLUMN public.health_insurance_details.floater_deductible IS 'Deductible amount for floater health insurance/topup plans (shared across all members)';
COMMENT ON COLUMN public.pending_health_insurance_details.floater_deductible IS 'Deductible amount for floater health insurance/topup plans (shared across all members)';

-- 7. Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_health_insured_members_deductible ON public.health_insured_members (deductible);
CREATE INDEX IF NOT EXISTS idx_pending_health_insured_members_deductible ON public.pending_health_insured_members (deductible);
CREATE INDEX IF NOT EXISTS idx_health_insurance_details_floater_deductible ON public.health_insurance_details (floater_deductible);
CREATE INDEX IF NOT EXISTS idx_pending_health_insurance_details_floater_deductible ON public.pending_health_insurance_details (floater_deductible);

-- 8. Verify the changes
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name IN ('health_insurance_details', 'pending_health_insurance_details', 'health_insured_members', 'pending_health_insured_members') 
AND column_name IN ('deductible', 'floater_deductible')
ORDER BY table_name, column_name;

-- 9. Check updated constraints
SELECT 
    tc.table_name, 
    tc.constraint_name, 
    cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc ON tc.constraint_name = cc.constraint_name
WHERE tc.table_name IN ('health_insurance_details', 'pending_health_insurance_details')
AND tc.constraint_type = 'CHECK'
AND cc.check_clause LIKE '%plan_type%';
