-- Enhanced Policy History Migration
-- This migration adds missing fields and creates tables for storing additional policy details (factory, health insurance)
-- Run this SQL script in your Supabase SQL editor

-- Step 1: Add missing updated_at field to policy_history table
ALTER TABLE public.policy_history 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;

-- Step 2: Create table for factory insurance history
CREATE TABLE IF NOT EXISTS public.policy_history_factory_details (
    history_factory_id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL,
    building NUMERIC,
    plant_machinery NUMERIC,
    furniture_fittings NUMERIC,
    stocks NUMERIC,
    electrical_installations NUMERIC,
    
    CONSTRAINT fk_history_factory_history_id 
        FOREIGN KEY (history_id) 
        REFERENCES public.policy_history(history_id) 
        ON DELETE CASCADE
);

-- Step 3: Create table for health insurance history
CREATE TABLE IF NOT EXISTS public.policy_history_health_details (
    history_health_id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL,
    plan_type TEXT CHECK (plan_type = ANY (ARRAY['FLOATER'::text, 'INDIVIDUAL'::text, 'TOPUP_FLOATER'::text, 'TOPUP_INDIVIDUAL'::text])),
    floater_sum_insured NUMERIC,
    floater_bonus NUMERIC,
    floater_deductible NUMERIC,
    
    CONSTRAINT fk_history_health_history_id 
        FOREIGN KEY (history_id) 
        REFERENCES public.policy_history(history_id) 
        ON DELETE CASCADE
);

-- Step 4: Create table for health insurance members history
CREATE TABLE IF NOT EXISTS public.policy_history_health_members (
    history_member_id SERIAL PRIMARY KEY,
    history_health_id INTEGER NOT NULL,
    member_name TEXT NOT NULL,
    sum_insured NUMERIC,
    bonus NUMERIC,
    deductible NUMERIC,
    
    CONSTRAINT fk_history_health_member_health_id 
        FOREIGN KEY (history_health_id) 
        REFERENCES public.policy_history_health_details(history_health_id) 
        ON DELETE CASCADE
);

-- Step 5: Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_history_factory_history_id ON public.policy_history_factory_details (history_id);
CREATE INDEX IF NOT EXISTS idx_history_health_history_id ON public.policy_history_health_details (history_id);
CREATE INDEX IF NOT EXISTS idx_history_health_members_health_id ON public.policy_history_health_members (history_health_id);

-- Step 6: Add comments to document the tables
COMMENT ON TABLE public.policy_history_factory_details IS 'Historical factory insurance details for archived policies';
COMMENT ON TABLE public.policy_history_health_details IS 'Historical health insurance details for archived policies';
COMMENT ON TABLE public.policy_history_health_members IS 'Historical health insurance member details for archived policies';

-- Step 7: Update the archive_policy_data function to include all fields and additional details
CREATE OR REPLACE FUNCTION public.archive_policy_data(
    p_policy_id INTEGER,
    p_reason TEXT DEFAULT 'renewal',
    p_archived_by TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_history_id INTEGER;
    v_factory_id BIGINT;
    v_health_id BIGINT;
BEGIN
    -- Insert current policy data into history table (including updated_at)
    INSERT INTO public.policy_history (
        original_policy_id, client_id, member_id, insurance_company, product_name,
        policy_number, one_time_insurance, commission_received, file_path,
        drive_file_id, drive_path, drive_url, payment_date, agent_name,
        policy_from, policy_to, payment_details, net_premium, addon_premium,
        tp_tr_premium, gst_percentage, gross_premium, commission_percentage,
        commission_amount, business_type, group_name, subgroup_name, remarks,
        sum_insured, last_reminder_sent, renewed_at, created_at, updated_at,
        archived_reason, archived_by
    )
    SELECT 
        policy_id, client_id, member_id, insurance_company, product_name,
        policy_number, one_time_insurance, commission_received, file_path,
        drive_file_id, drive_path, drive_url, payment_date, agent_name,
        policy_from, policy_to, payment_details, net_premium, addon_premium,
        tp_tr_premium, gst_percentage, gross_premium, commission_percentage,
        commission_amount, business_type, group_name, subgroup_name, remarks,
        sum_insured, last_reminder_sent, renewed_at, created_at, updated_at,
        p_reason, p_archived_by
    FROM public.policies 
    WHERE policy_id = p_policy_id
    RETURNING history_id INTO v_history_id;
    
    -- Archive factory insurance details if they exist
    SELECT factory_id INTO v_factory_id
    FROM public.factory_insurance_details
    WHERE policy_id = p_policy_id;
    
    IF v_factory_id IS NOT NULL THEN
        INSERT INTO public.policy_history_factory_details (
            history_id, building, plant_machinery, furniture_fittings, 
            stocks, electrical_installations
        )
        SELECT 
            v_history_id, building, plant_machinery, furniture_fittings,
            stocks, electrical_installations
        FROM public.factory_insurance_details
        WHERE policy_id = p_policy_id;
    END IF;
    
    -- Archive health insurance details if they exist
    SELECT health_id INTO v_health_id
    FROM public.health_insurance_details
    WHERE policy_id = p_policy_id;
    
    IF v_health_id IS NOT NULL THEN
        -- Archive health insurance main details
        INSERT INTO public.policy_history_health_details (
            history_id, plan_type, floater_sum_insured, 
            floater_bonus, floater_deductible
        )
        SELECT 
            v_history_id, plan_type, floater_sum_insured,
            floater_bonus, floater_deductible
        FROM public.health_insurance_details
        WHERE policy_id = p_policy_id
        RETURNING history_health_id INTO v_health_id;
        
        -- Archive health insurance members
        INSERT INTO public.policy_history_health_members (
            history_health_id, member_name, sum_insured, bonus, deductible
        )
        SELECT 
            v_health_id, member_name, sum_insured, bonus, deductible
        FROM public.health_insured_members
        WHERE health_id = (
            SELECT health_id 
            FROM public.health_insurance_details 
            WHERE policy_id = p_policy_id
        );
    END IF;
    
    RETURN v_history_id;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Grant necessary permissions
GRANT SELECT, INSERT ON public.policy_history TO authenticated;
GRANT SELECT, INSERT ON public.policy_history_factory_details TO authenticated;
GRANT SELECT, INSERT ON public.policy_history_health_details TO authenticated;
GRANT SELECT, INSERT ON public.policy_history_health_members TO authenticated;

GRANT USAGE ON SEQUENCE public.policy_history_history_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.policy_history_factory_details_history_factory_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.policy_history_health_details_history_health_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE public.policy_history_health_members_history_member_id_seq TO authenticated;

GRANT EXECUTE ON FUNCTION public.archive_policy_data(INTEGER, TEXT, TEXT) TO authenticated;

-- Step 9: Verify the tables were created successfully
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name IN ('policy_history', 'policy_history_factory_details', 'policy_history_health_details', 'policy_history_health_members')
ORDER BY table_name, ordinal_position;
