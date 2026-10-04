"""Seller master data that Stripe does not hold (VAT ID, IBAN, contact...)."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .model import Address, Contact, Party


@dataclass
class SellerProfile:
    name: str
    email: str  # used as electronic address (BT-34) and contact e-mail
    address: Address
    contact: Contact
    vat_id: str | None = None
    tax_number: str | None = None
    legal_registration_id: str | None = None
    trading_name: str | None = None
    kleinunternehmer: bool = False  # § 19 UStG: no VAT charged
    iban: str | None = None
    bic: str | None = None
    account_name: str | None = None
    creditor_id: str | None = None  # SEPA Gläubiger-ID, for direct debit
    timezone: str = "Europe/Berlin"

    def party(self) -> Party:
        return Party(
            name=self.name,
            address=self.address,
            electronic_address=self.email,
            vat_id=self.vat_id,
            tax_number=self.tax_number,
            legal_registration_id=self.legal_registration_id,
            trading_name=self.trading_name,
            contact=self.contact,
            creditor_id=self.creditor_id,
        )

    def problems(self) -> list[str]:
        missing = []
        if not (self.vat_id or self.tax_number):
            missing.append("USt-IdNr. oder Steuernummer des Verkäufers fehlt.")
        if not self.address.city or not self.address.postcode:
            missing.append("Ort und Postleitzahl des Verkäufers fehlen.")
        if not (self.contact.phone and self.contact.email and self.contact.name):
            missing.append("Kontakt des Verkäufers (Name, Telefon, E-Mail) ist unvollständig.")
        return missing

    @classmethod
    def from_dict(cls, data: dict) -> SellerProfile:
        data = dict(data)
        address = Address(**data.pop("address"))
        contact = Contact(**data.pop("contact"))
        bank = data.pop("bank", {}) or {}
        return cls(address=address, contact=contact, **bank, **data)

    @classmethod
    def load(cls, path: Path) -> SellerProfile:
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "address": vars(self.address),
            "contact": vars(self.contact),
            "vat_id": self.vat_id,
            "tax_number": self.tax_number,
            "legal_registration_id": self.legal_registration_id,
            "trading_name": self.trading_name,
            "kleinunternehmer": self.kleinunternehmer,
            "bank": {"iban": self.iban, "bic": self.bic, "account_name": self.account_name},
            "creditor_id": self.creditor_id,
            "timezone": self.timezone,
        }
