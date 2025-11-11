-- Migration script for pending renewals feature
-- This allows users to start renewal process without PDF and complete it later

-- Create pending_renewals table (mirrors policies table but without Drive fields)
CREATE TABLE IF NOT EXISTS public.pending_renewals (
  pending_renewal_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  policy_id bigint NOT NULL, -- Reference to the policy being renewed
  client_id text NOT NULL,
  member_id bigint NOT NULL,
  policy_number text,
  payment_date date,
  insurance_company text NOT NULL,
  agent_name text,
  policy_from date,
  policy_to date,
  one_time_insurance boolean NOT NULL DEFAULT false,
  product_name text,
  payment_details text,
  net_premium numeric,
  gross_premium numeric,
  commission_percentage numeric,
  commission_received boolean NOT NULL DEFAULT false,
  remarks text,
  business_type text CHECK (business_type = ANY (ARRAY['NEW'::text, 'RENEWAL'::text, 'ROLL OVER'::text])),
  group_name text,
  subgroup_name text,
  tp_tr_premium numeric,
  sum_insured numeric,
  addon_premium numeric,
  gst_percentage numeric DEFAULT 18.00,
  commission_amount numeric,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  created_by text, -- User who created the pending renewal
  CONSTRAINT pending_renewals_pkey PRIMARY KEY (pending_renewal_id),
  CONSTRAINT pending_renewals_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policies(policy_id),
  CONSTRAINT pending_renewals_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id),
  CONSTRAINT pending_renewals_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.members(member_id)
);

-- Create pending_renewal_health_insurance_details table
CREATE TABLE IF NOT EXISTS public.pending_renewal_health_insurance_details (
  pending_renewal_health_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  pending_renewal_id bigint NOT NULL,
  plan_type text CHECK (plan_type = ANY (ARRAY['FLOATER'::text, 'INDIVIDUAL'::text, 'TOPUP_FLOATER'::text, 'TOPUP_INDIVIDUAL'::text])),
  floater_sum_insured numeric,
  floater_bonus numeric,
  floater_deductible numeric,
  CONSTRAINT pending_renewal_health_insurance_details_pkey PRIMARY KEY (pending_renewal_health_id),
  CONSTRAINT pending_renewal_health_insurance_details_pending_renewal_id_fkey FOREIGN KEY (pending_renewal_id) REFERENCES public.pending_renewals(pending_renewal_id) ON DELETE CASCADE
);

-- Create pending_renewal_health_insured_members table
CREATE TABLE IF NOT EXISTS public.pending_renewal_health_insured_members (
  member_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  pending_renewal_health_id bigint NOT NULL,
  member_name text NOT NULL,
  sum_insured numeric,
  bonus numeric,
  deductible numeric,
  CONSTRAINT pending_renewal_health_insured_members_pkey PRIMARY KEY (member_id),
  CONSTRAINT pending_renewal_health_insured_members_health_id_fkey FOREIGN KEY (pending_renewal_health_id) REFERENCES public.pending_renewal_health_insurance_details(pending_renewal_health_id) ON DELETE CASCADE
);

-- Create pending_renewal_factory_insurance_details table
CREATE TABLE IF NOT EXISTS public.pending_renewal_factory_insurance_details (
  pending_renewal_factory_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  pending_renewal_id bigint NOT NULL,
  building numeric,
  plant_machinery numeric,
  furniture_fittings numeric,
  stocks numeric,
  electrical_installations numeric,
  CONSTRAINT pending_renewal_factory_insurance_details_pkey PRIMARY KEY (pending_renewal_factory_id),
  CONSTRAINT pending_renewal_factory_insurance_details_pending_renewal_id_fkey FOREIGN KEY (pending_renewal_id) REFERENCES public.pending_renewals(pending_renewal_id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_pending_renewals_policy_id ON public.pending_renewals(policy_id);
CREATE INDEX IF NOT EXISTS idx_pending_renewals_client_id ON public.pending_renewals(client_id);
CREATE INDEX IF NOT EXISTS idx_pending_renewals_created_at ON public.pending_renewals(created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE public.pending_renewals IS 'Stores renewal data before PDF is uploaded - allows editing details before completing renewal';
COMMENT ON COLUMN public.pending_renewals.policy_id IS 'Reference to the original policy being renewed';
COMMENT ON COLUMN public.pending_renewals.created_by IS 'Email of user who created the pending renewal';
