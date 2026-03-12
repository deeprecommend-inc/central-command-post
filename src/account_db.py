"""
Account DB - SQLite state management for account lifecycle.

Control Layer: tracks account status, proxy/profile assignments,
and enables resume after interruption.

Statuses: pending -> warmup -> creating -> sms_wait -> sns_expand -> active | banned
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from loguru import logger


class AccountStatus(str, Enum):
    PENDING = "pending"
    WARMUP = "warmup"
    CREATING = "creating"
    SMS_WAIT = "sms_wait"
    SNS_EXPAND = "sns_expand"
    ACTIVE = "active"
    BANNED = "banned"
    FAILED = "failed"


@dataclass
class AccountRecord:
    """Single account record"""
    id: int
    email: str
    status: AccountStatus
    area: str
    proxy_session: str
    profile_id: str
    warmup_days: int
    warmup_started: Optional[float]
    phone_number: str
    sns_accounts: dict[str, str]  # platform -> username
    metadata: dict[str, Any]
    created_at: float
    updated_at: float
    error: str

    @property
    def warmup_elapsed_days(self) -> float:
        if not self.warmup_started:
            return 0.0
        return (time.time() - self.warmup_started) / 86400.0


_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    area TEXT NOT NULL DEFAULT 'us',
    proxy_session TEXT NOT NULL DEFAULT '',
    profile_id TEXT NOT NULL DEFAULT '',
    warmup_days INTEGER NOT NULL DEFAULT 3,
    warmup_started REAL,
    phone_number TEXT NOT NULL DEFAULT '',
    sns_accounts TEXT NOT NULL DEFAULT '{}',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
"""


class AccountDB:
    """
    SQLite-backed account state store.

    Usage:
        db = AccountDB("accounts.db")
        db.create_account(area="jp")
        account = db.next_pending()
        db.update_status(account.id, AccountStatus.WARMUP)
    """

    def __init__(self, db_path: str = "accounts.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
        logger.debug(f"AccountDB initialized: {self._db_path}")

    def _row_to_record(self, row: sqlite3.Row) -> AccountRecord:
        return AccountRecord(
            id=row["id"],
            email=row["email"],
            status=AccountStatus(row["status"]),
            area=row["area"],
            proxy_session=row["proxy_session"],
            profile_id=row["profile_id"],
            warmup_days=row["warmup_days"],
            warmup_started=row["warmup_started"],
            phone_number=row["phone_number"],
            sns_accounts=json.loads(row["sns_accounts"]),
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=row["error"],
        )

    def create_account(
        self,
        area: str = "us",
        warmup_days: int = 3,
        metadata: Optional[dict] = None,
    ) -> AccountRecord:
        """Create a new account in pending state"""
        now = time.time()
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO accounts (area, warmup_days, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (area, warmup_days, json.dumps(metadata or {}), now, now),
            )
            row = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        record = self._row_to_record(row)
        logger.info(f"Account created: id={record.id} area={area}")
        return record

    def create_batch(
        self,
        count: int,
        area: str = "us",
        warmup_days: int = 3,
    ) -> list[AccountRecord]:
        """Create multiple accounts at once"""
        records = []
        for _ in range(count):
            records.append(self.create_account(area=area, warmup_days=warmup_days))
        logger.info(f"Batch created: {count} accounts, area={area}")
        return records

    def get(self, account_id: int) -> Optional[AccountRecord]:
        """Get account by ID"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_all(self) -> list[AccountRecord]:
        """List all accounts"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts ORDER BY id"
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_by_status(self, status: AccountStatus) -> list[AccountRecord]:
        """List accounts by status"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE status = ? ORDER BY id",
                (status.value,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def next_by_status(self, status: AccountStatus) -> Optional[AccountRecord]:
        """Get the next account with given status (oldest first)"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE status = ? ORDER BY id LIMIT 1",
                (status.value,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def update_status(
        self,
        account_id: int,
        status: AccountStatus,
        error: str = "",
    ) -> None:
        """Update account status"""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "UPDATE accounts SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status.value, error, now, account_id),
            )
        logger.info(f"Account {account_id}: status -> {status.value}")

    def update_fields(self, account_id: int, **fields) -> None:
        """Update arbitrary fields on an account"""
        if not fields:
            return
        now = time.time()
        fields["updated_at"] = now

        # Serialize dict fields
        for key in ("sns_accounts", "metadata"):
            if key in fields and isinstance(fields[key], dict):
                fields[key] = json.dumps(fields[key])

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [account_id]

        with self._conn() as conn:
            conn.execute(
                f"UPDATE accounts SET {set_clause} WHERE id = ?",
                values,
            )

    def start_warmup(self, account_id: int, profile_id: str, proxy_session: str) -> None:
        """Mark account as warming up with environment info"""
        now = time.time()
        self.update_fields(
            account_id,
            status=AccountStatus.WARMUP.value,
            profile_id=profile_id,
            proxy_session=proxy_session,
            warmup_started=now,
        )
        logger.info(f"Account {account_id}: warmup started, profile={profile_id}")

    def warmup_ready(self, account_id: int) -> bool:
        """Check if warmup period has elapsed"""
        account = self.get(account_id)
        if not account or account.status != AccountStatus.WARMUP:
            return False
        return account.warmup_elapsed_days >= account.warmup_days

    def set_email(self, account_id: int, email: str) -> None:
        """Set the created email address"""
        self.update_fields(account_id, email=email)

    def set_phone(self, account_id: int, phone: str) -> None:
        """Set the phone number used for verification"""
        self.update_fields(account_id, phone_number=phone)

    def add_sns_account(self, account_id: int, platform: str, username: str) -> None:
        """Add an SNS account to this email"""
        account = self.get(account_id)
        if not account:
            return
        sns = account.sns_accounts.copy()
        sns[platform] = username
        self.update_fields(account_id, sns_accounts=sns)
        logger.info(f"Account {account_id}: SNS added {platform}={username}")

    def summary(self) -> dict[str, int]:
        """Get status counts"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM accounts GROUP BY status"
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    def delete(self, account_id: int) -> bool:
        """Delete an account"""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM accounts WHERE id = ?", (account_id,)
            )
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Account {account_id}: deleted")
        return deleted

    def reset(self, account_id: int) -> None:
        """Reset account to pending state"""
        self.update_fields(
            account_id,
            status=AccountStatus.PENDING.value,
            error="",
            warmup_started=None,
        )
        logger.info(f"Account {account_id}: reset to pending")
