import tempfile

from alembic import command
from alembic.config import Config


def test_alembic_migration_lifecycle() -> None:
    """Verify that migrations can upgrade to head, downgrade to base, and re-upgrade cleanly."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        sqlite_url = f"sqlite:///{tmp.name}"
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)

        # 1. Upgrade to head
        command.upgrade(alembic_cfg, "head")

        # 2. Downgrade to base
        command.downgrade(alembic_cfg, "base")

        # 3. Re-upgrade to head
        command.upgrade(alembic_cfg, "head")
