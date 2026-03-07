ALTER TABLE user_sessions
ADD COLUMN IF NOT EXISTS csrf_token TEXT;

UPDATE user_sessions
SET csrf_token = token
WHERE csrf_token IS NULL;

ALTER TABLE user_sessions
ALTER COLUMN csrf_token SET NOT NULL;