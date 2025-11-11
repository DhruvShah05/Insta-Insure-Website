-- Migration to add is_pending_renewal flag to policies table
-- This flag indicates policies where payment is received but company hasn't issued new policy details yet

-- Add the boolean flag column
ALTER TABLE policies ADD COLUMN IF NOT EXISTS is_pending_renewal BOOLEAN DEFAULT FALSE;

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_policies_pending_renewal ON policies(is_pending_renewal);

-- Add comment for documentation
COMMENT ON COLUMN policies.is_pending_renewal IS 'TRUE when payment received but waiting for insurance company to issue new policy details and PDF';
