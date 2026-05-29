-- =============================================================================
-- Bitenex API - Database Initialization Script
-- This script runs when the PostgreSQL container is first created
-- =============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Grant privileges (if needed for specific users)
-- GRANT ALL PRIVILEGES ON DATABASE bitenex TO bitenex_user;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Bitenex database initialized successfully at %', NOW();
END $$;
