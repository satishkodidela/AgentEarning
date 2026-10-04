"""The seller-profile form shown after installing the Stripe App."""

from __future__ import annotations

import re

from ..model import Address, Contact
from ..profile import SellerProfile

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VAT_ID = re.compile(r"^[A-Z]{2}[0-9A-Z+*.]{2,13}$")
DE_VAT_ID = re.compile(r"^DE[0-9]{9}$")
BIC = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")
CREDITOR_ID = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{3}[A-Z0-9]{1,28}$")

FIELDS = (
    "name", "line1", "postcode", "city", "country_code", "vat_id", "tax_number", "legal_registration_id",
    "contact_name", "contact_phone", "contact_email", "invoice_email", "iban", "bic", "creditor_id",
)


def iban_valid(iban: str) -> bool:
    """ISO 13616 check digits (mod 97)."""
    iban = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", iban):
        return False
    digits = "".join(str(int(ch, 36)) for ch in iban[4:] + iban[:4])
    return int(digits) % 97 == 1


def values_from_profile(profile: SellerProfile | None, send_to_customer: bool) -> dict:
    if profile is None:
        return {"country_code": "DE", "send_to_customer": False}
    return {
        "name": profile.name,
        "line1": profile.address.line1 or "",
        "postcode": profile.address.postcode,
        "city": profile.address.city,
        "country_code": profile.address.country_code,
        "vat_id": profile.vat_id or "",
        "tax_number": profile.tax_number or "",
        "legal_registration_id": profile.legal_registration_id or "",
        "contact_name": profile.contact.name,
        "contact_phone": profile.contact.phone,
        "contact_email": profile.contact.email,
        "invoice_email": profile.email,
        "iban": profile.iban or "",
        "bic": profile.bic or "",
        "creditor_id": profile.creditor_id or "",
        "kleinunternehmer": profile.kleinunternehmer,
        "send_to_customer": send_to_customer,
    }


def parse_profile(form: dict) -> tuple[SellerProfile | None, dict[str, str], dict]:
    """Return (profile or None, errors by field, cleaned values to re-render)."""
    v = {key: (form.get(key) or "").strip() for key in FIELDS}
    v["country_code"] = (v["country_code"] or "DE").upper()
    v["vat_id"] = v["vat_id"].replace(" ", "").upper()
    v["iban"] = v["iban"].replace(" ", "").upper()
    v["bic"] = v["bic"].replace(" ", "").upper()
    v["creditor_id"] = v["creditor_id"].replace(" ", "").upper()
    v["kleinunternehmer"] = bool(form.get("kleinunternehmer"))
    v["send_to_customer"] = bool(form.get("send_to_customer"))
    v["invoice_email"] = v["invoice_email"] or v["contact_email"]

    errors: dict[str, str] = {}
    required = {
        "name": "Firmenname", "line1": "Straße und Hausnummer", "postcode": "Postleitzahl", "city": "Ort",
        "contact_name": "Ansprechpartner", "contact_phone": "Telefon", "contact_email": "E-Mail",
    }
    for key, label in required.items():
        if not v[key]:
            errors[key] = f"{label} fehlt."
    if not re.fullmatch(r"[A-Z]{2}", v["country_code"]):
        errors["country_code"] = "Ländercode mit zwei Buchstaben, z. B. DE."
    if v["country_code"] == "DE" and v["postcode"] and not re.fullmatch(r"[0-9]{5}", v["postcode"]):
        errors["postcode"] = "Deutsche Postleitzahlen haben fünf Ziffern."
    for key in ("contact_email", "invoice_email"):
        if v[key] and not EMAIL.match(v[key]):
            errors[key] = "Keine gültige E-Mail-Adresse."
    if len(re.sub(r"\D", "", v["contact_phone"])) < 3 and "contact_phone" not in errors:
        errors["contact_phone"] = "Mindestens drei Ziffern (Pflicht in XRechnung)."
    if not (v["vat_id"] or v["tax_number"]):
        errors["vat_id"] = "USt-IdNr. oder Steuernummer angeben."
    elif v["vat_id"] and not (DE_VAT_ID if v["vat_id"].startswith("DE") else VAT_ID).match(v["vat_id"]):
        errors["vat_id"] = "Format prüfen, z. B. DE123456789."
    if v["kleinunternehmer"] and v["vat_id"] and not v["tax_number"]:
        errors["tax_number"] = "Als Kleinunternehmer bitte auch die Steuernummer angeben."
    if v["iban"] and not iban_valid(v["iban"]):
        errors["iban"] = "Die IBAN ist ungültig (Prüfziffer)."
    if v["bic"] and not BIC.match(v["bic"]):
        errors["bic"] = "Der BIC hat 8 oder 11 Zeichen."
    if v["creditor_id"] and not CREDITOR_ID.match(v["creditor_id"]):
        errors["creditor_id"] = "Format der Gläubiger-ID prüfen, z. B. DE98ZZZ09999999999."

    if errors:
        return None, errors, v
    profile = SellerProfile(
        name=v["name"],
        email=v["invoice_email"],
        address=Address(city=v["city"], postcode=v["postcode"], country_code=v["country_code"], line1=v["line1"]),
        contact=Contact(name=v["contact_name"], phone=v["contact_phone"], email=v["contact_email"]),
        vat_id=v["vat_id"] or None,
        tax_number=v["tax_number"] or None,
        legal_registration_id=v["legal_registration_id"] or None,
        kleinunternehmer=v["kleinunternehmer"],
        iban=v["iban"] or None,
        bic=v["bic"] or None,
        account_name=v["name"],
        creditor_id=v["creditor_id"] or None,
    )
    return profile, {}, v
