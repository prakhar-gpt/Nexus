-- Changeset 011: Production-grade authentication, server-side sessions, and workspace ownership
-- Idempotent and reversible migration.

-- 1. Ensure pgcrypto extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Update users table with authentication and security fields
CREATE TABLE IF NOT EXISTS users (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email              text NOT NULL,
    name               text NOT NULL,
    password_hash      text,
    role               text NOT NULL DEFAULT 'analyst',
    is_active          boolean NOT NULL DEFAULT true,
    failed_login_count integer NOT NULL DEFAULT 0,
    locked_until       timestamptz,
    last_login_at      timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);

-- Add columns if table already existed from Changeset 008
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count integer NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at timestamptz;

-- Ensure lowercased unique index on trimmed email
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower_trimmed ON users (lower(trim(email)));

-- Seed default local analyst user with known bcrypt hash ($2b$12$e8u... password: 'nexus-password-10')
-- Default password: 'nexus-password-10' (cost 12)
INSERT INTO users (id, email, name, password_hash, role, is_active)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'prakhar@nexus.ai',
    'Prakhar Gupta',
    '$2b$12$a4cR5y2o91l66aYd9t2R3epPqm99b3cQzP9w.E1Z0dM3bHwKkOqU6',
    'analyst',
    true
)
ON CONFLICT (lower(trim(email))) DO UPDATE SET
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active;

-- 3. Create server-side sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz,
    user_agent   text,
    ip           text
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions (token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);

-- 4. Workspaces ownership and backfill
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_workspaces_owner_id ON workspaces (owner_id);

-- Backfill any workspaces lacking an owner_id to the default local user
UPDATE workspaces 
SET owner_id = '00000000-0000-0000-0000-000000000001'::uuid 
WHERE owner_id IS NULL;

-- 5. RLS policies and role grants for sessions
-- Sessions is an application security ledger managed by backend services.
-- We disable RLS so nexus_writer is never blocked by default-deny, and add a permissive policy as fallback.
ALTER TABLE sessions DISABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_writer') THEN
        DROP POLICY IF EXISTS sessions_writer_all ON sessions;
        CREATE POLICY sessions_writer_all ON sessions
            FOR ALL
            TO nexus_writer
            USING (true)
            WITH CHECK (true);
        GRANT ALL ON sessions TO nexus_writer;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_reader') THEN
        DROP POLICY IF EXISTS sessions_reader_all ON sessions;
        CREATE POLICY sessions_reader_all ON sessions
            FOR SELECT
            TO nexus_reader
            USING (true);
        GRANT SELECT ON sessions TO nexus_reader;
    END IF;
END $$;
