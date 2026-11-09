"""Make a backup now:  python -m loomtrack.backup

The app also does this by itself about once a day. Run it by hand before an upgrade, or from a scheduled task, to copy to
another place:  python -m loomtrack.backup  and then copy the backups folder. Safe while the app is running."""

from __future__ import annotations

import sqlite3

from . import config
from .services import backup


def main() -> None:
    db = sqlite3.connect(config.DB_FILE)
    try:
        target = backup.backup_database(db, config.BACKUP_DIR, config.backup_keep())
    finally:
        db.close()
    copied = backup.mirror_uploads(config.UPLOAD_DIR, config.BACKUP_DIR)
    print(f"Database copied to {target}")
    print(f"{copied} new uploaded file(s) copied to {config.BACKUP_DIR / 'uploads'}")


if __name__ == "__main__":
    main()
