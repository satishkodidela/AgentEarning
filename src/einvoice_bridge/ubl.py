"""Render an Invoice as XRechnung 3.0 UBL 2.1 (Invoice or CreditNote).

Element order follows the UBL 2.1 XSD sequences; the validators reject
documents with elements out of order.
"""

from __future__ import annotations

from datetime import date

from lxml import etree

from .model import (
    PEPPOL_PROFILE_ID,
    XRECHNUNG_CUSTOMIZATION_ID,
    Address,
    Invoice,
    Line,
    Party,
    VatCategory,
    fmt_amount,
    fmt_decimal,
)

NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


def _cac(parent: etree._Element, tag: str) -> etree._Element:
    return etree.SubElement(parent, f"{{{CAC}}}{tag}")


def _cbc(parent: etree._Element, tag: str, text: str | None, **attrs: str) -> etree._Element | None:
    if not text:  # empty elements are invalid (PEPPOL-EN16931-R008)
        return None
    el = etree.SubElement(parent, f"{{{CBC}}}{tag}", **attrs)
    el.text = text
    return el


def _date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _address(parent: etree._Element, tag: str, address: Address) -> None:
    el = _cac(parent, tag)
    _cbc(el, "StreetName", address.line1)
    _cbc(el, "AdditionalStreetName", address.line2)
    _cbc(el, "CityName", address.city)
    _cbc(el, "PostalZone", address.postcode)
    _cbc(el, "CountrySubentity", address.state)
    _cbc(_cac(el, "Country"), "IdentificationCode", address.country_code)


def _party(parent: etree._Element, tag: str, party: Party, creditor_id: str | None = None) -> None:
    p = _cac(_cac(parent, tag), "Party")
    if party.electronic_address:
        _cbc(p, "EndpointID", party.electronic_address, schemeID=party.electronic_address_scheme)
    if party.effective_identifier:
        _cbc(_cac(p, "PartyIdentification"), "ID", party.effective_identifier)
    if creditor_id:
        _cbc(_cac(p, "PartyIdentification"), "ID", creditor_id, schemeID="SEPA")
    if party.trading_name:
        _cbc(_cac(p, "PartyName"), "Name", party.trading_name)
    _address(p, "PostalAddress", party.address)
    if party.vat_id:
        scheme = _cac(p, "PartyTaxScheme")
        _cbc(scheme, "CompanyID", party.vat_id)
        _cbc(_cac(scheme, "TaxScheme"), "ID", "VAT")
    if party.tax_number:
        scheme = _cac(p, "PartyTaxScheme")
        _cbc(scheme, "CompanyID", party.tax_number)
        _cbc(_cac(scheme, "TaxScheme"), "ID", "FC")
    legal = _cac(p, "PartyLegalEntity")
    _cbc(legal, "RegistrationName", party.name)
    _cbc(legal, "CompanyID", party.legal_registration_id)
    if party.contact:
        contact = _cac(p, "Contact")
        _cbc(contact, "Name", party.contact.name)
        _cbc(contact, "Telephone", party.contact.phone)
        _cbc(contact, "ElectronicMail", party.contact.email)


def _line(parent: etree._Element, invoice: Invoice, line: Line) -> None:
    credit = invoice.is_credit_note
    cur = {"currencyID": invoice.currency}
    el = _cac(parent, "CreditNoteLine" if credit else "InvoiceLine")
    _cbc(el, "ID", line.id)
    _cbc(el, "CreditedQuantity" if credit else "InvoicedQuantity", fmt_decimal(line.quantity), unitCode=line.unit_code)
    _cbc(el, "LineExtensionAmount", fmt_amount(line.net_amount), **cur)
    if line.period_start or line.period_end:
        period = _cac(el, "InvoicePeriod")
        _cbc(period, "StartDate", _date(line.period_start))
        _cbc(period, "EndDate", _date(line.period_end))
    for allowance in line.allowances:
        ac = _cac(el, "AllowanceCharge")
        _cbc(ac, "ChargeIndicator", "false")
        _cbc(ac, "AllowanceChargeReason", allowance.reason)
        _cbc(ac, "Amount", fmt_amount(allowance.amount), **cur)
    item = _cac(el, "Item")
    _cbc(item, "Description", line.description)
    _cbc(item, "Name", line.name)
    tax = _cac(item, "ClassifiedTaxCategory")
    _cbc(tax, "ID", line.vat_category.value)
    if line.vat_category != VatCategory.NOT_SUBJECT:  # BR-O-05: no rate outside the scope of VAT
        _cbc(tax, "Percent", fmt_decimal(line.vat_rate))
    _cbc(_cac(tax, "TaxScheme"), "ID", "VAT")
    _cbc(_cac(el, "Price"), "PriceAmount", fmt_decimal(line.net_price), **cur)


def to_ubl(invoice: Invoice) -> bytes:
    credit = invoice.is_credit_note
    root_ns = NS_CREDIT_NOTE if credit else NS_INVOICE
    root = etree.Element(
        f"{{{root_ns}}}{'CreditNote' if credit else 'Invoice'}",
        nsmap={None: root_ns, "cac": CAC, "cbc": CBC},
    )
    cur = {"currencyID": invoice.currency}

    _cbc(root, "CustomizationID", XRECHNUNG_CUSTOMIZATION_ID)
    _cbc(root, "ProfileID", PEPPOL_PROFILE_ID)
    _cbc(root, "ID", invoice.number)
    _cbc(root, "IssueDate", _date(invoice.issue_date))
    if not credit:
        _cbc(root, "DueDate", _date(invoice.due_date))
    _cbc(root, "CreditNoteTypeCode" if credit else "InvoiceTypeCode", invoice.type_code)
    for note in invoice.notes:
        _cbc(root, "Note", note)
    _cbc(root, "DocumentCurrencyCode", invoice.currency)
    _cbc(root, "BuyerReference", invoice.buyer_reference)
    if invoice.period_start or invoice.period_end:
        period = _cac(root, "InvoicePeriod")
        _cbc(period, "StartDate", _date(invoice.period_start))
        _cbc(period, "EndDate", _date(invoice.period_end))
    if invoice.order_reference:
        _cbc(_cac(root, "OrderReference"), "ID", invoice.order_reference)
    if invoice.preceding_invoice:
        ref = _cac(_cac(root, "BillingReference"), "InvoiceDocumentReference")
        _cbc(ref, "ID", invoice.preceding_invoice)
        _cbc(ref, "IssueDate", _date(invoice.preceding_invoice_date))

    creditor_id = invoice.seller.creditor_id if invoice.is_direct_debit else None
    _party(root, "AccountingSupplierParty", invoice.seller, creditor_id)
    _party(root, "AccountingCustomerParty", invoice.buyer)

    if invoice.delivery_date:
        _cbc(_cac(root, "Delivery"), "ActualDeliveryDate", _date(invoice.delivery_date))

    pay = invoice.payment
    means = _cac(root, "PaymentMeans")
    attrs = {"name": pay.means_text} if pay.means_text else {}
    _cbc(means, "PaymentMeansCode", pay.means_code, **attrs)
    if credit:
        _cbc(means, "PaymentDueDate", _date(invoice.due_date))
    _cbc(means, "PaymentID", pay.remittance_info)
    if pay.card_last_digits:
        card = _cac(means, "CardAccount")
        _cbc(card, "PrimaryAccountNumberID", pay.card_last_digits)
        _cbc(card, "NetworkID", pay.card_network or "mapped-from-cii")
        _cbc(card, "HolderName", pay.card_holder)
    if pay.iban:
        account = _cac(means, "PayeeFinancialAccount")
        _cbc(account, "ID", pay.iban)
        _cbc(account, "Name", pay.account_name)
        if pay.bic:
            _cbc(_cac(account, "FinancialInstitutionBranch"), "ID", pay.bic)
    if pay.mandate_reference:
        mandate = _cac(means, "PaymentMandate")
        _cbc(mandate, "ID", pay.mandate_reference)
        if pay.debited_iban:
            _cbc(_cac(mandate, "PayerFinancialAccount"), "ID", pay.debited_iban)

    if invoice.payment_terms:
        _cbc(_cac(root, "PaymentTerms"), "Note", invoice.payment_terms)

    tax_total = _cac(root, "TaxTotal")
    _cbc(tax_total, "TaxAmount", fmt_amount(invoice.tax_total), **cur)
    for b in invoice.vat_breakdown():
        sub = _cac(tax_total, "TaxSubtotal")
        _cbc(sub, "TaxableAmount", fmt_amount(b.taxable_amount), **cur)
        _cbc(sub, "TaxAmount", fmt_amount(b.tax_amount), **cur)
        cat = _cac(sub, "TaxCategory")
        _cbc(cat, "ID", b.category.value)
        _cbc(cat, "Percent", fmt_decimal(b.rate))  # XRechnung needs it even for O (BR-DE-14)
        _cbc(cat, "TaxExemptionReasonCode", b.exemption_code)
        _cbc(cat, "TaxExemptionReason", b.exemption_reason)
        _cbc(_cac(cat, "TaxScheme"), "ID", "VAT")

    totals = _cac(root, "LegalMonetaryTotal")
    _cbc(totals, "LineExtensionAmount", fmt_amount(invoice.line_total), **cur)
    _cbc(totals, "TaxExclusiveAmount", fmt_amount(invoice.tax_exclusive_total), **cur)
    _cbc(totals, "TaxInclusiveAmount", fmt_amount(invoice.tax_inclusive_total), **cur)
    if invoice.paid_amount:
        _cbc(totals, "PrepaidAmount", fmt_amount(invoice.paid_amount), **cur)
    _cbc(totals, "PayableAmount", fmt_amount(invoice.amount_due), **cur)

    for line in invoice.lines:
        _line(root, invoice, line)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
