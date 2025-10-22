-- Migration to add password field to users table
-- Run this in your Supabase SQL editor

ALTER TABLE public.users 
ADD COLUMN password_hash text;

-- Add index for better performance on email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);

-- Update existing admin users with a default password (change this immediately after running)
-- Default password will be "admin123" - CHANGE THIS IMMEDIATELY
UPDATE public.users 
SET password_hash = '$2b$12$LQv3c1yqBwEHFww.vHAuCOmqvWiZr4u5rFd8mPA.rV0pyFZ8Qo/Sq'
WHERE email IN (
    SELECT unnest(string_to_array('dhruv@instainsure.co.in,admin@instainsure.co.in', ','))
);

-- Note: The above hash is for password "admin123"
-- You should change this immediately after testing
