-- WhatsApp Message Logs Migration
-- This table will store all WhatsApp messages sent through the system

CREATE TABLE IF NOT EXISTS whatsapp_logs (
    log_id SERIAL PRIMARY KEY,
    message_sid VARCHAR(100) UNIQUE NOT NULL, -- Twilio Message SID
    policy_id BIGINT REFERENCES policies(policy_id) ON DELETE SET NULL,
    client_id TEXT REFERENCES clients(client_id) ON DELETE SET NULL,
    phone_number VARCHAR(20) NOT NULL,
    message_type VARCHAR(50) NOT NULL, -- 'policy_document', 'renewal_reminder', 'general'
    message_content TEXT,
    media_url TEXT,
    status VARCHAR(50) DEFAULT 'queued', -- Twilio status: queued, sending, sent, delivered, undelivered, failed, read
    error_code VARCHAR(20),
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_status_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_policy_id ON whatsapp_logs(policy_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_client_id ON whatsapp_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_phone ON whatsapp_logs(phone_number);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_status ON whatsapp_logs(status);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_sent_at ON whatsapp_logs(sent_at);
CREATE INDEX IF NOT EXISTS idx_whatsapp_logs_message_type ON whatsapp_logs(message_type);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_whatsapp_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_whatsapp_logs_updated_at
    BEFORE UPDATE ON whatsapp_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_whatsapp_logs_updated_at();
