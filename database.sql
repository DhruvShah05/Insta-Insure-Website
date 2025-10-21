-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.claim_documents (
  document_id integer NOT NULL DEFAULT nextval('claim_documents_document_id_seq'::regclass),
  claim_id integer,
  document_name character varying NOT NULL,
  document_type character varying NOT NULL,
  drive_file_id character varying,
  drive_url text,
  drive_path text,
  file_size integer,
  uploaded_at timestamp without time zone DEFAULT now(),
  CONSTRAINT claim_documents_pkey PRIMARY KEY (document_id),
  CONSTRAINT claim_documents_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.claims(claim_id)
);
CREATE TABLE public.claims (
  claim_id integer NOT NULL DEFAULT nextval('claims_claim_id_seq'::regclass),
  policy_id integer,
  member_name character varying NOT NULL,
  claim_type character varying NOT NULL CHECK (claim_type::text = ANY (ARRAY['CASHLESS'::character varying, 'REIMBURSEMENT'::character varying, 'PRE-POST'::character varying]::text[])),
  diagnosis text,
  hospital_name character varying,
  admission_date date,
  discharge_date date,
  claimed_amount numeric,
  settled_amount numeric,
  settlement_date date,
  utr_no character varying,
  status character varying DEFAULT 'PENDING'::character varying CHECK (status::text = ANY (ARRAY['PENDING'::character varying, 'PROCESSING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'SETTLED'::character varying]::text[])),
  remarks text,
  created_at timestamp without time zone DEFAULT now(),
  updated_at timestamp without time zone DEFAULT now(),
  approved_amount numeric,
  claim_number character varying UNIQUE,
  CONSTRAINT claims_pkey PRIMARY KEY (claim_id),
  CONSTRAINT claims_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policies(policy_id)
);
CREATE TABLE public.clients (
  client_id text NOT NULL,
  prefix text NOT NULL,
  name text NOT NULL,
  phone text,
  email text,
  CONSTRAINT clients_pkey PRIMARY KEY (client_id)
);
CREATE TABLE public.custom_document_types (
  id integer NOT NULL DEFAULT nextval('custom_document_types_id_seq'::regclass),
  type_name character varying NOT NULL UNIQUE,
  created_at timestamp without time zone DEFAULT now(),
  is_active boolean DEFAULT true,
  CONSTRAINT custom_document_types_pkey PRIMARY KEY (id)
);
CREATE TABLE public.factory_insurance_details (
  factory_id bigint NOT NULL DEFAULT nextval('factory_insurance_details_factory_id_seq'::regclass),
  policy_id bigint NOT NULL,
  building numeric,
  plant_machinery numeric,
  furniture_fittings numeric,
  stocks numeric,
  electrical_installations numeric,
  CONSTRAINT factory_insurance_details_pkey PRIMARY KEY (factory_id),
  CONSTRAINT factory_insurance_details_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policies(policy_id)
);
CREATE TABLE public.health_insurance_details (
  health_id bigint NOT NULL DEFAULT nextval('health_insurance_details_health_id_seq'::regclass),
  policy_id bigint NOT NULL,
  plan_type text CHECK (plan_type = ANY (ARRAY['FLOATER'::text, 'INDIVIDUAL'::text, 'TOPUP_FLOATER'::text, 'TOPUP_INDIVIDUAL'::text])),
  floater_sum_insured numeric,
  floater_bonus numeric,
  floater_deductible numeric,
  CONSTRAINT health_insurance_details_pkey PRIMARY KEY (health_id),
  CONSTRAINT health_insurance_details_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policies(policy_id)
);
CREATE TABLE public.health_insured_members (
  member_id bigint NOT NULL DEFAULT nextval('health_insured_members_member_id_seq'::regclass),
  health_id bigint NOT NULL,
  member_name text NOT NULL,
  sum_insured numeric,
  bonus numeric,
  deductible numeric,
  CONSTRAINT health_insured_members_pkey PRIMARY KEY (member_id),
  CONSTRAINT health_insured_members_health_id_fkey FOREIGN KEY (health_id) REFERENCES public.health_insurance_details(health_id)
);
CREATE TABLE public.members (
  member_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  client_id text NOT NULL,
  member_name text NOT NULL,
  CONSTRAINT members_pkey PRIMARY KEY (member_id),
  CONSTRAINT members_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id)
);
CREATE TABLE public.pending_factory_insurance_details (
  pending_id bigint NOT NULL,
  building numeric,
  plant_machinery numeric,
  furniture_fittings numeric,
  stocks numeric,
  electrical_installations numeric,
  CONSTRAINT pending_factory_insurance_details_pkey PRIMARY KEY (pending_id),
  CONSTRAINT pending_factory_insurance_details_pending_id_fkey FOREIGN KEY (pending_id) REFERENCES public.pending_policies(pending_id)
);
CREATE TABLE public.pending_health_insurance_details (
  pending_health_id bigint NOT NULL DEFAULT nextval('pending_health_insurance_details_pending_health_id_seq'::regclass),
  pending_id bigint NOT NULL,
  plan_type text CHECK (plan_type = ANY (ARRAY['FLOATER'::text, 'INDIVIDUAL'::text, 'TOPUP_FLOATER'::text, 'TOPUP_INDIVIDUAL'::text])),
  floater_sum_insured numeric,
  floater_bonus numeric,
  floater_deductible numeric,
  CONSTRAINT pending_health_insurance_details_pkey PRIMARY KEY (pending_health_id),
  CONSTRAINT pending_health_insurance_details_pending_id_fkey FOREIGN KEY (pending_id) REFERENCES public.pending_policies(pending_id)
);
CREATE TABLE public.pending_health_insured_members (
  member_id bigint NOT NULL DEFAULT nextval('pending_health_insured_members_member_id_seq'::regclass),
  pending_health_id bigint NOT NULL,
  member_name text NOT NULL,
  sum_insured numeric,
  bonus numeric,
  deductible numeric,
  CONSTRAINT pending_health_insured_members_pkey PRIMARY KEY (member_id),
  CONSTRAINT pending_health_insured_members_pending_health_id_fkey FOREIGN KEY (pending_health_id) REFERENCES public.pending_health_insurance_details(pending_health_id)
);
CREATE TABLE public.pending_policies (
  pending_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  client_id text NOT NULL,
  member_id bigint NOT NULL,
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
  commission numeric DEFAULT (gross_premium * (commission_percentage / (100)::numeric)),
  commission_received boolean NOT NULL DEFAULT false,
  remarks text,
  business_type text CHECK (business_type = ANY (ARRAY['NEW'::text, 'RENEWAL'::text, 'ROLL OVER'::text])),
  group_name text,
  subgroup_name text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  tp_tr_premium numeric,
  sum_insured numeric,
  addon_premium numeric,
  gst_percentage numeric DEFAULT 18.00,
  commission_amount numeric,
  CONSTRAINT pending_policies_pkey PRIMARY KEY (pending_id),
  CONSTRAINT pending_policies_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id),
  CONSTRAINT pending_policies_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.members(member_id)
);
CREATE TABLE public.policies (
  policy_id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  client_id text NOT NULL,
  member_id bigint NOT NULL,
  policy_number text NOT NULL,
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
  commission numeric DEFAULT (gross_premium * (commission_percentage / (100)::numeric)),
  commission_received boolean NOT NULL DEFAULT false,
  remarks text,
  business_type text CHECK (business_type = ANY (ARRAY['NEW'::text, 'RENEWAL'::text, 'ROLL OVER'::text])),
  group_name text,
  subgroup_name text,
  file_path text,
  drive_file_id text,
  drive_path text,
  drive_url text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  renewed_at timestamp with time zone,
  last_reminder_sent timestamp with time zone,
  tp_tr_premium numeric,
  sum_insured numeric,
  addon_premium numeric,
  gst_percentage numeric DEFAULT 18.00,
  commission_amount numeric,
  CONSTRAINT policies_pkey PRIMARY KEY (policy_id),
  CONSTRAINT policies_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id),
  CONSTRAINT policies_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.members(member_id)
);
CREATE TABLE public.policy_history (
  history_id integer NOT NULL DEFAULT nextval('policy_history_history_id_seq'::regclass),
  original_policy_id integer NOT NULL,
  client_id text NOT NULL,
  member_id integer NOT NULL,
  insurance_company text,
  product_name text,
  policy_number text,
  one_time_insurance boolean DEFAULT false,
  commission_received boolean DEFAULT false,
  file_path text,
  drive_file_id text,
  drive_path text,
  drive_url text,
  payment_date date,
  agent_name text,
  policy_from date,
  policy_to date,
  payment_details text,
  net_premium numeric,
  addon_premium numeric,
  tp_tr_premium numeric,
  gst_percentage numeric,
  gross_premium numeric,
  commission_percentage numeric,
  commission_amount numeric,
  business_type text,
  group_name text,
  subgroup_name text,
  remarks text,
  sum_insured numeric,
  last_reminder_sent timestamp with time zone,
  renewed_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  archived_at timestamp with time zone DEFAULT now(),
  archived_reason text DEFAULT 'renewal'::text,
  archived_by text,
  CONSTRAINT policy_history_pkey PRIMARY KEY (history_id),
  CONSTRAINT fk_policy_history_original_policy FOREIGN KEY (original_policy_id) REFERENCES public.policies(policy_id)
);
CREATE TABLE public.users (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email text NOT NULL UNIQUE,
  name text NOT NULL,
  picture text,
  is_admin boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  last_login timestamp with time zone DEFAULT now(),
  is_active boolean NOT NULL DEFAULT true,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);