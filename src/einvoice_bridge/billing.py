"""Plans, monthly limits and the Paddle Billing integration.

Paddle is the merchant of record: it runs the checkout (Paddle.js overlay),
charges the customer, issues the invoice and handles VAT. We only learn about
subscriptions through signed webhooks and send customers to Paddle's portal
to change or cancel.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from .store import Account, Store

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_eur: int
    monthly_limit: int  # generated e-invoices per calendar month
    customer_delivery: bool  # may e-mail e-invoices straight to the seller's customers


PLANS = {
    "free": Plan("free", "Kostenlos", 0, 3, False),
    "starter": Plan("starter", "Starter", 9, 30, False),
    "business": Plan("business", "Business", 29, 300, True),
}
PAID_PLANS = ("starter", "business")
# past_due keeps access while Paddle retries the payment (dunning).
ENTITLED_STATUSES = {"active", "trialing", "past_due"}


def effective_plan(account: Account) -> Plan:
    """The plan the account may use right now."""
    if account.paddle_subscription_id:
        if account.subscription_status in ENTITLED_STATUSES:
            return PLANS.get(account.plan, PLANS["free"])
        return PLANS["free"]
    # No subscription: the operator-assigned plan (beta accounts via CLI), default free.
    return PLANS.get(account.plan, PLANS["free"])


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@dataclass
class Usage:
    plan: Plan
    used: int

    @property
    def remaining(self) -> int:
        return max(0, self.plan.monthly_limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.plan.monthly_limit


def usage(store: Store, account: Account) -> Usage:
    return Usage(effective_plan(account), store.billable_count(account.id, current_month()))


# Paddle ---------------------------------------------------------------------


@dataclass
class PaddleConfig:
    client_token: str  # public, for Paddle.js
    api_key: str  # secret, for the customer-portal API
    webhook_secret: str
    sandbox: bool = True
    prices: dict[str, list[str]] = field(default_factory=dict)  # plan -> price IDs (first = checkout)

    @property
    def api_base(self) -> str:
        return "https://sandbox-api.paddle.com" if self.sandbox else "https://api.paddle.com"

    def plan_for_price(self, price_id: str) -> str | None:
        return next((plan for plan, ids in self.prices.items() if price_id in ids), None)

    def checkout_price(self, plan: str) -> str | None:
        ids = self.prices.get(plan) or []
        return ids[0] if ids else None

    @classmethod
    def from_env(cls) -> PaddleConfig | None:
        token, key, secret = (os.environ.get(v) for v in ("PADDLE_CLIENT_TOKEN", "PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET"))
        if not (token and key and secret):
            return None
        prices = {
            plan: [p.strip() for p in os.environ.get(f"PADDLE_PRICES_{plan.upper()}", "").split(",") if p.strip()]
            for plan in PAID_PLANS
        }
        return cls(token, key, secret, os.environ.get("PADDLE_ENVIRONMENT", "sandbox") != "production", prices)


def verify_paddle_signature(raw_body: bytes, header: str, secret: str, tolerance: int = 300, now: float | None = None) -> bool:
    """Check ``Paddle-Signature: ts=...;h1=...`` (HMAC-SHA256 of ``ts:body``)."""
    parts = dict(p.split("=", 1) for p in header.split(";") if "=" in p)
    ts, signature = parts.get("ts"), parts.get("h1")
    if not ts or not signature or not ts.isdigit():
        return False
    if abs((now or time.time()) - int(ts)) > tolerance:
        return False  # replayed or badly delayed
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def sign_account(account_id: str, secret: str) -> str:
    """Tag the account ID we put into checkout custom data, which the browser could alter."""
    return hmac.new(secret.encode(), f"paddle-checkout:{account_id}".encode(), hashlib.sha256).hexdigest()


def account_from_custom_data(custom_data: dict | None, secret: str) -> str | None:
    custom_data = custom_data or {}
    account_id, tag = custom_data.get("account_id"), custom_data.get("account_sig")
    if account_id and tag and hmac.compare_digest(sign_account(account_id, secret), tag):
        return account_id
    return None


class PaddleClient:
    def __init__(self, config: PaddleConfig, http: httpx.Client | None = None):
        self.config = config
        self.http = http or httpx.Client(timeout=20)

    def portal_url(self, customer_id: str, subscription_id: str | None = None) -> str:
        """A short-lived, signed-in link to Paddle's customer portal (never cache it)."""
        body = {"subscription_ids": [subscription_id]} if subscription_id else {}
        response = self.http.post(
            f"{self.config.api_base}/customers/{customer_id}/portal-sessions",
            json=body,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
        )
        response.raise_for_status()
        return response.json()["data"]["urls"]["general"]["overview"]

    def change_plan(self, subscription_id: str, price_id: str) -> None:
        """Switch the subscription to another price; the difference is prorated now.

        The resulting ``subscription.updated`` webhook updates the account.
        """
        response = self.http.patch(
            f"{self.config.api_base}/subscriptions/{subscription_id}",
            json={"items": [{"price_id": price_id, "quantity": 1}], "proration_billing_mode": "prorated_immediately"},
            headers={"Authorization": f"Bearer {self.config.api_key}"},
        )
        response.raise_for_status()


@dataclass
class SubscriptionChange:
    account_id: str
    plan: str
    became_paid: bool


def apply_subscription_event(store: Store, config: PaddleConfig, signing_secret: str, event: dict) -> SubscriptionChange | None:
    """Update an account from a ``subscription.*`` webhook event."""
    if not str(event.get("event_type", "")).startswith("subscription."):
        return None
    sub = event.get("data") or {}
    account_id = account_from_custom_data(sub.get("custom_data"), signing_secret)
    account = store.account(account_id) if account_id else store.account_by_paddle(sub.get("id"), sub.get("customer_id"))
    if account is None:
        return None
    status = sub.get("status", "")
    if (
        account.paddle_subscription_id
        and sub.get("id") != account.paddle_subscription_id
        and account.subscription_status in ENTITLED_STATUSES
        and status not in ENTITLED_STATUSES
    ):
        # A late event about an old subscription must not end the current one.
        return None
    before = effective_plan(account)

    prices = [(item.get("price") or {}).get("id") for item in sub.get("items") or []]
    plan = next((p for p in (config.plan_for_price(pid) for pid in prices if pid) if p), None)
    if plan is None:
        log.error("Paddle price(s) %s are not mapped to a plan (PADDLE_PRICES_*); account %s stays free", prices, account.id)
        plan = "free"
    scheduled = sub.get("scheduled_change") or {}
    applied = store.apply_subscription(
        account.id,
        event.get("occurred_at") or datetime.now(timezone.utc).isoformat(),
        plan=plan,
        status=status,
        customer_id=sub.get("customer_id"),
        subscription_id=sub.get("id"),
        period_ends_at=(sub.get("current_billing_period") or {}).get("ends_at"),
        cancel_at=scheduled.get("effective_at") if scheduled.get("action") == "cancel" else None,
    )
    if not applied:
        return None
    after = effective_plan(store.account(account.id))
    return SubscriptionChange(account.id, after.key, after.monthly_limit > before.monthly_limit)
