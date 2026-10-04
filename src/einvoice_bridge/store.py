"""SQLite store for accounts, processed invoices and the waitlist.

Generated files are archived write-once under ``<data>/archive``; the
database keeps their SHA-256 so later tampering is detectable (GoBD).
Stripe API keys, OAuth tokens and webhook secrets are encrypted at rest
with Fernet.

Accounts come in two kinds: ``manual`` (restricted key and per-account
webhook, set up with the CLI) and ``oauth`` (installed as a Stripe App; one
Connect webhook for everyone, short-lived access tokens refreshed on demand).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from .profile import SellerProfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    dashboard_token TEXT UNIQUE NOT NULL,
    stripe_api_key TEXT NOT NULL,
    webhook_secret TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    send_to_customer INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    stripe_invoice_id TEXT NOT NULL,
    number TEXT,
    status TEXT NOT NULL,           -- generated | blocked | failed | voided
    problems_json TEXT NOT NULL DEFAULT '[]',
    files_json TEXT NOT NULL DEFAULT '{}',
    delivered_to TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (account_id, stripe_invoice_id)
);
CREATE TABLE IF NOT EXISTS waitlist (
    email TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL,
    confirmed_at TEXT
);
"""


# Columns added after the first release; applied with ALTER TABLE on start.
ACCOUNT_COLUMNS = {
    "access_mode": "TEXT NOT NULL DEFAULT 'manual'",  # manual | oauth
    "status": "TEXT NOT NULL DEFAULT 'active'",  # onboarding | active | uninstalled
    "stripe_account_id": "TEXT",
    "livemode": "INTEGER NOT NULL DEFAULT 1",
    "access_token": "TEXT",
    "refresh_token": "TEXT",
    "token_expires_at": "INTEGER NOT NULL DEFAULT 0",
    # billing (Paddle)
    "plan": "TEXT NOT NULL DEFAULT 'free'",
    "paddle_customer_id": "TEXT",
    "paddle_subscription_id": "TEXT",
    "subscription_status": "TEXT",
    "period_ends_at": "TEXT",
    "cancel_at": "TEXT",
    "billing_event_at": "TEXT",  # occurred_at of the last applied Paddle event
    "limit_notice_month": "TEXT",  # YYYY-MM when the seller was told about the limit
}
DOCUMENT_COLUMNS = {
    "billable": "INTEGER NOT NULL DEFAULT 1",  # counts towards the monthly plan limit
    "kind": "TEXT NOT NULL DEFAULT 'invoice'",  # invoice | credit_note
    "related_number": "TEXT",  # for credit notes: the invoice they correct
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class Account:
    id: str
    dashboard_token: str
    stripe_api_key: str
    webhook_secret: str
    profile: SellerProfile | None  # None until onboarding is finished
    send_to_customer: bool
    access_mode: str = "manual"
    status: str = "active"
    stripe_account_id: str | None = None
    livemode: bool = True
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: int = 0
    plan: str = "free"
    paddle_customer_id: str | None = None
    paddle_subscription_id: str | None = None
    subscription_status: str | None = None
    period_ends_at: str | None = None
    cancel_at: str | None = None
    billing_event_at: str | None = None
    limit_notice_month: str | None = None

    @property
    def is_oauth(self) -> bool:
        return self.access_mode == "oauth"

    @property
    def is_active(self) -> bool:
        return self.status == "active" and self.profile is not None


@dataclass
class Document:
    id: int
    account_id: str
    stripe_invoice_id: str
    number: str | None
    status: str
    problems: list[dict]
    files: dict[str, str]  # name -> sha256
    delivered_to: str | None
    created_at: str
    kind: str = "invoice"
    related_number: str | None = None

    @property
    def is_credit_note(self) -> bool:
        return self.kind == "credit_note"


class Store:
    def __init__(self, data_dir: Path, secret_key: str):
        self.data_dir = data_dir
        self.archive = data_dir / "archive"
        self.archive.mkdir(parents=True, exist_ok=True)
        self.secret = secret_key if isinstance(secret_key, str) else secret_key.decode()
        self.fernet = Fernet(self.secret.encode())
        self.path = data_dir / "einvoice.sqlite3"
        # One connection per thread: webhooks and the first-run backfill run in
        # background threads, and a sqlite3 connection must not be shared.
        self._local = threading.local()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self._migrate()

    @property
    def db(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _migrate(self) -> None:
        with self.db:
            for table, columns in (("accounts", ACCOUNT_COLUMNS), ("documents", DOCUMENT_COLUMNS)):
                existing = {row["name"] for row in self.db.execute(f"PRAGMA table_info({table})")}
                for column, ddl in columns.items():
                    if column not in existing:
                        self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            self.db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS accounts_stripe_account"
                " ON accounts (stripe_account_id, livemode) WHERE stripe_account_id IS NOT NULL"
            )

    # accounts -------------------------------------------------------------

    def create_account(
        self,
        profile: SellerProfile,
        stripe_api_key: str,
        webhook_secret: str,
        send_to_customer: bool = False,
        plan: str = "free",
    ) -> Account:
        account = Account(
            id=secrets.token_urlsafe(12),
            dashboard_token=secrets.token_urlsafe(24),
            stripe_api_key=stripe_api_key,
            webhook_secret=webhook_secret,
            profile=profile,
            send_to_customer=send_to_customer,
            plan=plan,
        )
        with self.db:
            self.db.execute(
                "INSERT INTO accounts (id, dashboard_token, stripe_api_key, webhook_secret, profile_json,"
                " send_to_customer, created_at, plan) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account.id,
                    account.dashboard_token,
                    self._encrypt(stripe_api_key),
                    self._encrypt(webhook_secret),
                    json.dumps(profile.to_dict(), ensure_ascii=False),
                    int(send_to_customer),
                    now(),
                    plan,
                ),
            )
        return account

    def install(
        self,
        stripe_account_id: str,
        livemode: bool,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> tuple[Account, bool]:
        """Record a Stripe App installation (or re-authorisation).

        Returns the account and whether it is new. Re-installing an account
        that was uninstalled keeps its profile and archive.
        """
        existing = self.account_by_stripe_id(stripe_account_id, livemode)
        expires_at = int(time.time()) + expires_in
        if existing:
            status = "active" if existing.profile else "onboarding"
            with self.db:
                self.db.execute(
                    "UPDATE accounts SET access_token = ?, refresh_token = ?, token_expires_at = ?, status = ?"
                    " WHERE id = ?",
                    (self._encrypt(access_token), self._encrypt(refresh_token), expires_at, status, existing.id),
                )
            return self.account(existing.id), False
        account_id = secrets.token_urlsafe(12)
        with self.db:
            self.db.execute(
                "INSERT INTO accounts (id, dashboard_token, stripe_api_key, webhook_secret, profile_json,"
                " send_to_customer, created_at, access_mode, status, stripe_account_id, livemode,"
                " access_token, refresh_token, token_expires_at)"
                " VALUES (?, ?, ?, ?, '{}', 0, ?, 'oauth', 'onboarding', ?, ?, ?, ?, ?)",
                (
                    account_id,
                    secrets.token_urlsafe(24),
                    self._encrypt(""),
                    self._encrypt(""),
                    now(),
                    stripe_account_id,
                    int(livemode),
                    self._encrypt(access_token),
                    self._encrypt(refresh_token),
                    expires_at,
                ),
            )
        return self.account(account_id), True

    def update_tokens(self, account_id: str, access_token: str, refresh_token: str, expires_in: int) -> None:
        with self.db:
            self.db.execute(
                "UPDATE accounts SET access_token = ?, refresh_token = ?, token_expires_at = ? WHERE id = ?",
                (self._encrypt(access_token), self._encrypt(refresh_token), int(time.time()) + expires_in, account_id),
            )

    def uninstall(self, account_id: str) -> None:
        """Forget the tokens; keep profile and archive (retention duties)."""
        with self.db:
            self.db.execute(
                "UPDATE accounts SET status = 'uninstalled', access_token = NULL, refresh_token = NULL,"
                " token_expires_at = 0 WHERE id = ?",
                (account_id,),
            )

    def save_profile(self, account_id: str, profile: SellerProfile, send_to_customer: bool) -> None:
        with self.db:
            self.db.execute(
                "UPDATE accounts SET profile_json = ?, send_to_customer = ?,"
                " status = CASE WHEN status = 'onboarding' THEN 'active' ELSE status END WHERE id = ?",
                (json.dumps(profile.to_dict(), ensure_ascii=False), int(send_to_customer), account_id),
            )

    def account_by_paddle(self, subscription_id: str | None, customer_id: str | None) -> Account | None:
        for column, value in (("paddle_subscription_id", subscription_id), ("paddle_customer_id", customer_id)):
            if value:
                row = self.db.execute(f"SELECT * FROM accounts WHERE {column} = ?", (value,)).fetchone()
                if row:
                    return self._account(row)
        return None

    def apply_subscription(
        self,
        account_id: str,
        occurred_at: str,
        *,
        plan: str,
        status: str,
        customer_id: str | None,
        subscription_id: str,
        period_ends_at: str | None,
        cancel_at: str | None,
    ) -> bool:
        """Store a Paddle subscription state unless a newer event was applied already.

        Paddle does not guarantee delivery order, so each event carries its
        occurred_at and older ones are ignored. Returns whether it was applied.
        """
        row = self.db.execute("SELECT billing_event_at FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row and row["billing_event_at"] and _parse_time(row["billing_event_at"]) > _parse_time(occurred_at):
            return False
        with self.db:
            self.db.execute(
                "UPDATE accounts SET plan = ?, subscription_status = ?, paddle_customer_id = COALESCE(?, paddle_customer_id),"
                " paddle_subscription_id = ?, period_ends_at = ?, cancel_at = ?, billing_event_at = ? WHERE id = ?",
                (plan, status, customer_id, subscription_id, period_ends_at, cancel_at, occurred_at, account_id),
            )
        return True

    def set_limit_notice(self, account_id: str, month: str) -> None:
        with self.db:
            self.db.execute("UPDATE accounts SET limit_notice_month = ? WHERE id = ?", (month, account_id))

    def billable_count(self, account_id: str, month: str) -> int:
        """Generated, billable e-invoices in a month ("YYYY-MM", UTC)."""
        return self.db.execute(
            "SELECT COUNT(*) FROM documents WHERE account_id = ? AND status = 'generated' AND billable = 1"
            " AND substr(created_at, 1, 7) = ?",
            (account_id, month),
        ).fetchone()[0]

    def account_by_stripe_id(self, stripe_account_id: str, livemode: bool) -> Account | None:
        row = self.db.execute(
            "SELECT * FROM accounts WHERE stripe_account_id = ? AND livemode = ?",
            (stripe_account_id, int(livemode)),
        ).fetchone()
        return self._account(row) if row else None

    def account(self, account_id: str) -> Account | None:
        row = self.db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return self._account(row) if row else None

    def account_by_token(self, token: str) -> Account | None:
        row = self.db.execute("SELECT * FROM accounts WHERE dashboard_token = ?", (token,)).fetchone()
        return self._account(row) if row else None

    def _account(self, row: sqlite3.Row) -> Account:
        profile = json.loads(row["profile_json"])
        return Account(
            id=row["id"],
            dashboard_token=row["dashboard_token"],
            stripe_api_key=self._decrypt(row["stripe_api_key"]),
            webhook_secret=self._decrypt(row["webhook_secret"]),
            profile=SellerProfile.from_dict(profile) if profile else None,
            send_to_customer=bool(row["send_to_customer"]),
            access_mode=row["access_mode"],
            status=row["status"],
            stripe_account_id=row["stripe_account_id"],
            livemode=bool(row["livemode"]),
            access_token=self._decrypt(row["access_token"]) if row["access_token"] else None,
            refresh_token=self._decrypt(row["refresh_token"]) if row["refresh_token"] else None,
            token_expires_at=row["token_expires_at"],
            plan=row["plan"],
            paddle_customer_id=row["paddle_customer_id"],
            paddle_subscription_id=row["paddle_subscription_id"],
            subscription_status=row["subscription_status"],
            period_ends_at=row["period_ends_at"],
            cancel_at=row["cancel_at"],
            billing_event_at=row["billing_event_at"],
            limit_notice_month=row["limit_notice_month"],
        )

    def _encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        return self.fernet.decrypt(value.encode()).decode()

    # documents ------------------------------------------------------------

    def document(self, account_id: str, stripe_invoice_id: str) -> Document | None:
        row = self.db.execute(
            "SELECT * FROM documents WHERE account_id = ? AND stripe_invoice_id = ?",
            (account_id, stripe_invoice_id),
        ).fetchone()
        return self._document(row) if row else None

    def documents(self, account_id: str, limit: int = 200) -> list[Document]:
        rows = self.db.execute(
            "SELECT * FROM documents WHERE account_id = ? ORDER BY id DESC LIMIT ?", (account_id, limit)
        ).fetchall()
        return [self._document(r) for r in rows]

    def save_document(
        self,
        account_id: str,
        stripe_invoice_id: str,
        number: str | None,
        status: str,
        problems: list[dict],
        files: dict[str, bytes] | None = None,
        billable: bool = True,
        kind: str = "invoice",
        related_number: str | None = None,
    ) -> Document:
        hashes = {}
        if files:
            folder = self.document_dir(account_id, stripe_invoice_id)
            folder.mkdir(parents=True, exist_ok=True)
            for name, content in files.items():
                path = folder / name
                if path.exists():
                    raise FileExistsError(f"{path} is archived and must not be overwritten")
                path.write_bytes(content)
                path.chmod(0o444)
                hashes[name] = hashlib.sha256(content).hexdigest()
        with self.db:
            # A blocked invoice can be retried once the seller fixed the data;
            # a generated one is final.
            self.db.execute(
                "DELETE FROM documents WHERE account_id = ? AND stripe_invoice_id = ? AND status != 'generated'",
                (account_id, stripe_invoice_id),
            )
            self.db.execute(
                "INSERT INTO documents (account_id, stripe_invoice_id, number, status, problems_json, files_json,"
                " created_at, billable, kind, related_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id, stripe_invoice_id, number, status, json.dumps(problems, ensure_ascii=False),
                    json.dumps(hashes), now(), int(billable), kind, related_number,
                ),
            )
        return self.document(account_id, stripe_invoice_id)

    def mark_voided(self, account_id: str, stripe_id: str, message: str) -> Document | None:
        """Flag a document whose Stripe object was voided; archived files stay untouched."""
        doc = self.document(account_id, stripe_id)
        if doc is None:
            return None
        problems = doc.problems + [{"field": "status", "message": message, "severity": "warning"}]
        with self.db:
            self.db.execute(
                "UPDATE documents SET status = 'voided', problems_json = ? WHERE id = ?",
                (json.dumps(problems, ensure_ascii=False), doc.id),
            )
        return self.document(account_id, stripe_id)

    def mark_delivered(self, document_id: int, recipients: str) -> None:
        with self.db:
            self.db.execute("UPDATE documents SET delivered_to = ? WHERE id = ?", (recipients, document_id))

    def document_dir(self, account_id: str, stripe_invoice_id: str) -> Path:
        safe = "".join(c for c in stripe_invoice_id if c.isalnum() or c in "_-")
        return self.archive / account_id / safe

    def read_file(self, doc: Document, name: str) -> bytes | None:
        if name not in doc.files:
            return None
        content = (self.document_dir(doc.account_id, doc.stripe_invoice_id) / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != doc.files[name]:
            raise RuntimeError(f"Archived file {name} of {doc.stripe_invoice_id} was modified")
        return content

    def _document(self, row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            account_id=row["account_id"],
            stripe_invoice_id=row["stripe_invoice_id"],
            number=row["number"],
            status=row["status"],
            problems=json.loads(row["problems_json"]),
            files=json.loads(row["files_json"]),
            delivered_to=row["delivered_to"],
            created_at=row["created_at"],
            kind=row["kind"],
            related_number=row["related_number"],
        )

    # waitlist (double opt-in) ------------------------------------------------

    def add_to_waitlist(self, email: str, source: str | None) -> str | None:
        """Return a confirmation token, or None if the address is already confirmed."""
        email = email.strip().lower()
        row = self.db.execute("SELECT token, confirmed_at FROM waitlist WHERE email = ?", (email,)).fetchone()
        if row and row["confirmed_at"]:
            return None
        if row:
            return row["token"]
        token = secrets.token_urlsafe(24)
        with self.db:
            self.db.execute("INSERT INTO waitlist VALUES (?, ?, ?, ?, NULL)", (email, token, source, now()))
        return token

    def confirm_waitlist(self, token: str) -> bool:
        with self.db:
            cur = self.db.execute(
                "UPDATE waitlist SET confirmed_at = ? WHERE token = ? AND confirmed_at IS NULL", (now(), token)
            )
        return cur.rowcount == 1
