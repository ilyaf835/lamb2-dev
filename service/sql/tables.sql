CREATE TABLE IF NOT EXISTS users (
    id bigserial PRIMARY KEY,
    name text NOT NULL,
    tripcode text NOT NULL,
    passcode text NOT NULL,
    salt text NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bots (
    id bigserial PRIMARY KEY,
    name text NOT NULL DEFAULT '',
    tripcode text NOT NULL DEFAULT '',
    passcode text NOT NULL DEFAULT '',
    icon text NOT NULL DEFAULT '',
    language text NOT NULL DEFAULT 'EN',
    command_prefix text NOT NULL DEFAULT '-',
    whitelist jsonb NOT NULL DEFAULT '{}'::jsonb,
    blacklist jsonb NOT NULL DEFAULT '{}'::jsonb,
    groups jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id bigserial UNIQUE REFERENCES users(id) ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = now();
        RETURN NEW;
    END;
$$ language 'plpgsql';

CREATE TRIGGER update_timestamp
    BEFORE UPDATE ON bots
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();
