-- Migration to create custom document types table
-- Run this SQL script in your Supabase SQL editor

-- Create custom document types table
CREATE TABLE IF NOT EXISTS public.custom_document_types (
    id SERIAL PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Insert default document types
INSERT INTO public.custom_document_types (type_name) VALUES 
('MEDICAL_BILL'),
('DISCHARGE_SUMMARY'),
('PRESCRIPTION'),
('LAB_REPORT'),
('INVESTIGATION_REPORT'),
('DOCTOR_CERTIFICATE'),
('HOSPITAL_BILL'),
('PHARMACY_BILL')
ON CONFLICT (type_name) DO NOTHING;

-- Add index for better performance
CREATE INDEX IF NOT EXISTS idx_custom_document_types_active ON public.custom_document_types (is_active);

-- Add comment
COMMENT ON TABLE public.custom_document_types IS 'Stores custom document types that users can add for claims';
