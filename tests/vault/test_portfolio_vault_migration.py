from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/alembic/versions/018_portfolio_vault.py"


def test_migration_018_defines_portfolio_vault_without_auth_fk():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "018_portfolio_vault"' in text
    assert 'down_revision = "017_stock_tech_calc_version"' in text
    assert "CREATE TABLE IF NOT EXISTS public.portfolio_vault" in text
    assert "ciphertext text NOT NULL" in text
    # upgrade() DDL must not reference auth.users (FK added only via supabase SQL)
    upgrade_start = text.index("def upgrade()")
    downgrade_start = text.index("def downgrade()")
    upgrade_body = text[upgrade_start:downgrade_start]
    assert "REFERENCES auth.users" not in upgrade_body
    assert "auth.users" not in upgrade_body
