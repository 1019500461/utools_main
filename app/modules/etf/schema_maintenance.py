from __future__ import annotations

from loguru import logger
from tortoise import connections


async def ensure_etf_schema() -> None:
    connection = connections.get("default")
    if connection.capabilities.dialect != "postgres":
        return

    await connection.execute_script(
        """
        ALTER TABLE etf_monitor
            ADD COLUMN IF NOT EXISTS user_id INTEGER;

        ALTER TABLE etf_monitor
            ADD COLUMN IF NOT EXISTS holding_cost DOUBLE PRECISION NULL,
            ADD COLUMN IF NOT EXISTS holding_shares DOUBLE PRECISION NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS take_profit_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS take_profit_first_rise DOUBLE PRECISION NOT NULL DEFAULT 0.15,
            ADD COLUMN IF NOT EXISTS take_profit_step DOUBLE PRECISION NOT NULL DEFAULT 0.05,
            ADD COLUMN IF NOT EXISTS take_profit_stage INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS take_profit_last_alert_at TIMESTAMP NULL;

        UPDATE etf_monitor
        SET user_id = (
            SELECT id
            FROM admin_user
            WHERE is_active = TRUE
            ORDER BY is_superuser DESC, id ASC
            LIMIT 1
        )
        WHERE user_id IS NULL;

        DO $$
        DECLARE
            old_constraint_name text;
        BEGIN
            FOR old_constraint_name IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'etf_monitor'
                  AND c.contype = 'u'
                  AND pg_get_constraintdef(c.oid) = 'UNIQUE (code)'
            LOOP
                EXECUTE format('ALTER TABLE etf_monitor DROP CONSTRAINT %I', old_constraint_name);
            END LOOP;
        END $$;

        DO $$
        DECLARE
            old_index_name text;
        BEGIN
            FOR old_index_name IN
                SELECT i.relname
                FROM pg_class t
                JOIN pg_index ix ON ix.indrelid = t.oid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ix.indkey[0]
                LEFT JOIN pg_constraint c ON c.conindid = ix.indexrelid
                WHERE t.relname = 'etf_monitor'
                  AND ix.indisunique
                  AND ix.indnatts = 1
                  AND a.attname = 'code'
                  AND c.oid IS NULL
            LOOP
                EXECUTE format('DROP INDEX IF EXISTS %I', old_index_name);
            END LOOP;
        END $$;

        ALTER TABLE etf_monitor
            ALTER COLUMN user_id SET NOT NULL;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = c.conkey[1]
                WHERE t.relname = 'etf_monitor'
                  AND c.contype = 'f'
                  AND a.attname = 'user_id'
                  AND c.confrelid = 'admin_user'::regclass
            ) THEN
                ALTER TABLE etf_monitor
                    ADD CONSTRAINT fk_etf_monitor_user
                    FOREIGN KEY (user_id) REFERENCES admin_user(id)
                    ON DELETE CASCADE;
            END IF;
        END $$;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_etf_monitor_user_code
            ON etf_monitor(user_id, code);

        CREATE INDEX IF NOT EXISTS idx_etf_monitor_take_profit_enabled
            ON etf_monitor(take_profit_enabled);

        CREATE TABLE IF NOT EXISTS etf_alert_log (
            id SERIAL PRIMARY KEY,
            monitor_id INTEGER NOT NULL REFERENCES etf_monitor(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES admin_user(id) ON DELETE CASCADE,
            code VARCHAR(20) NOT NULL,
            recipient VARCHAR(255) NOT NULL DEFAULT '',
            stage INTEGER NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            retract DOUBLE PRECISION NOT NULL,
            status VARCHAR(20) NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            sent_at TIMESTAMP NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_user_id ON etf_alert_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_monitor_id ON etf_alert_log(monitor_id);
        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_code ON etf_alert_log(code);
        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_status ON etf_alert_log(status);
        """
    )
    logger.info("ETF schema maintenance finished")
