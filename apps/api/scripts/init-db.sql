-- PostgreSQL initialization script for Crypto Signal Aggregator
-- This runs when the PostgreSQL container is first created

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for common queries (tables created by SQLAlchemy)
-- These will be applied after initial table creation

-- Note: The actual tables are created by SQLAlchemy on app startup
-- This script is for additional database setup

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE crypto_signals TO crypto;

-- Performance settings notification
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully';
    RAISE NOTICE 'Tables will be created by SQLAlchemy on first app startup';
END $$;
