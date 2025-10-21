-- Migration to create policy_history table for preserving historical policy data
-- Run this SQL script in your Supabase SQL editor

-- Create policy_history table with all fields from policies table
CREATE TABLE IF NOT EXISTS public.policy_history (
    history_id SERIAL PRIMARY KEY,
    original_policy_id INTEGER NOT NULL,
    client_id TEXT NOT NULL,
    member_id INTEGER NOT NULL,
    insurance_company TEXT,
    product_name TEXT,
    policy_number TEXT,
    one_time_insurance BOOLEAN DEFAULT false,
    commission_received BOOLEAN DEFAULT false,
    file_path TEXT,
    drive_file_id TEXT,
    drive_path TEXT,
    drive_url TEXT,
    payment_date DATE,
    agent_name TEXT,
    policy_from DATE,
    policy_to DATE,
    payment_details TEXT,
    net_premium NUMERIC(10,2),
    addon_premium NUMERIC(10,2),
    tp_tr_premium NUMERIC(10,2),
    gst_percentage NUMERIC(5,2),
    gross_premium NUMERIC(10,2),
    commission_percentage NUMERIC(5,2),
    commission_amount NUMERIC(10,2),
    business_type TEXT,
    group_name TEXT,
    subgroup_name TEXT,
    remarks TEXT,
    sum_insured NUMERIC(12,2),
    last_reminder_sent TIMESTAMP WITH TIME ZONE,
    renewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Historical metadata
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    archived_reason TEXT DEFAULT 'renewal',
    archived_by TEXT,
    
    -- Foreign key reference to original policy
    CONSTRAINT fk_policy_history_original_policy 
        FOREIGN KEY (original_policy_id) 
        REFERENCES public.policies(policy_id) 
        ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_policy_history_original_policy_id ON public.policy_history (original_policy_id);
CREATE INDEX IF NOT EXISTS idx_policy_history_client_id ON public.policy_history (client_id);
CREATE INDEX IF NOT EXISTS idx_policy_history_archived_at ON public.policy_history (archived_at);
CREATE INDEX IF NOT EXISTS idx_policy_history_policy_to ON public.policy_history (policy_to);

-- Add comments to document the table
COMMENT ON TABLE public.policy_history IS 'Historical records of policies before renewal or updates';
COMMENT ON COLUMN public.policy_history.original_policy_id IS 'Reference to the current policy record';
COMMENT ON COLUMN public.policy_history.archived_at IS 'When this historical record was created';
COMMENT ON COLUMN public.policy_history.archived_reason IS 'Reason for archiving (renewal, update, etc.)';
COMMENT ON COLUMN public.policy_history.archived_by IS 'User who performed the action that created this historical record';

-- Create a function to automatically copy policy data to history
CREATE OR REPLACE FUNCTION public.archive_policy_data(
    p_policy_id INTEGER,
    p_reason TEXT DEFAULT 'renewal',
    p_archived_by TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_history_id INTEGER;
BEGIN
    -- Insert current policy data into history table
    INSERT INTO public.policy_history (
        original_policy_id, client_id, member_id, insurance_company, product_name,
        policy_number, one_time_insurance, commission_received, file_path,
        drive_file_id, drive_path, drive_url, payment_date, agent_name,
        policy_from, policy_to, payment_details, net_premium, addon_premium,
        tp_tr_premium, gst_percentage, gross_premium, commission_percentage,
        commission_amount, business_type, group_name, subgroup_name, remarks,
        sum_insured, last_reminder_sent, renewed_at, created_at,
        archived_reason, archived_by
    )
    SELECT 
        policy_id, client_id, member_id, insurance_company, product_name,
        policy_number, one_time_insurance, commission_received, file_path,
        drive_file_id, drive_path, drive_url, payment_date, agent_name,
        policy_from, policy_to, payment_details, net_premium, addon_premium,
        tp_tr_premium, gst_percentage, gross_premium, commission_percentage,
        commission_amount, business_type, group_name, subgroup_name, remarks,
        sum_insured, last_reminder_sent, renewed_at, created_at,
        p_reason, p_archived_by
    FROM public.policies 
    WHERE policy_id = p_policy_id
    RETURNING history_id INTO v_history_id;
    
    RETURN v_history_id;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
GRANT SELECT, INSERT ON public.policy_history TO authenticated;
GRANT USAGE ON SEQUENCE public.policy_history_history_id_seq TO authenticated;
GRANT EXECUTE ON FUNCTION public.archive_policy_data(INTEGER, TEXT, TEXT) TO authenticated;

-- Verify the table was created successfully
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name = 'policy_history' 
ORDER BY ordinal_position;
