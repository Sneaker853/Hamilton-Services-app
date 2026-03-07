ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP NULL;
UPDATE user_sessions SET expires_at = created_at + INTERVAL '24 hours' WHERE expires_at IS NULL;
ALTER TABLE user_sessions ALTER COLUMN expires_at SET NOT NULL;
