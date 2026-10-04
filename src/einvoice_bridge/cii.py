"""Render an Invoice as UN/CEFACT CII D16B.

Used two ways: with the XRechnung specification identifier (XRechnung in CII
syntax), and with the plain EN 16931 identifier as the XML embedded in a
ZUGFeRD / Factur-X "EN 16931" (formerly COMFORT) hybrid PDF.
"""

from __future__ import annotations

from datetime import date

from lxml import etree

from .model import (
    EN16931_CUSTOMIZATION_ID,
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

RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"

PROFILES = {
    "xrechnung": XRECHNUNG_CUSTOMIZATION_ID,
    "en16931": EN16931_CUSTOMIZATION_ID,
}


def _ram(parent: etree._Element, tag: str, text: str | None = None, **attrs: str) -> etree._Element:
    el = etree.SubElement(parent, f"{{{RAM}}}{tag}", **attrs)
    if text is not None:
        el.text = text
    return el


def _opt(parent: etree._Element, tag: str, text: str | None, **attrs: str) -> None:
    if text:  # empty elements are invalid (PEPPOL-EN16931-R008)
        _ram(parent, tag, text, **attrs)


def _datetime(parent: etree._Element, tag: str, value: date) -> None:
    holder = _ram(parent, tag)
    el = etree.SubElement(holder, f"{{{UDT}}}DateTimeString", format="102")
    el.text = value.strftime("%Y%m%d")


def _address(parent: etree._Element, address: Address) -> None:
    el = _ram(parent, "PostalTradeAddress")
    _opt(el, "PostcodeCode", address.postcode)
    _opt(el, "LineOne", address.line1)
    _opt(el, "LineTwo", address.line2)
    _opt(el, "CityName", address.city)
    _opt(el, "CountryID", address.country_code)
    _opt(el, "CountrySubDivisionName", address.state)


def _party(parent: etree._Element, tag: str, party: Party) -> None:
    p = _ram(parent, tag)
    _opt(p, "ID", party.effective_identifier)
    _ram(p, "Name", party.name)
    if party.legal_registration_id or party.trading_name:
        legal = _ram(p, "SpecifiedLegalOrganization")
        _opt(legal, "ID", party.legal_registration_id)
        _opt(legal, "TradingBusinessName", party.trading_name)
    if party.contact:
        contact = _ram(p, "DefinedTradeContact")
        _ram(contact, "PersonName", party.contact.name)
        _ram(_ram(contact, "TelephoneUniversalCommunication"), "CompleteNumber", party.contact.phone)
        _ram(_ram(contact, "EmailURIUniversalCommunication"), "URIID", party.contact.email)
    _address(p, party.address)
    if party.electronic_address:
        _ram(
            _ram(p, "URIUniversalCommunication"),
            "URIID",
            party.electronic_address,
            schemeID=party.electronic_address_scheme,
        )
    if party.vat_id:
        _ram(_ram(p, "SpecifiedTaxRegistration"), "ID", party.vat_id, schemeID="VA")
    if party.tax_number:
        _ram(_ram(p, "SpecifiedTaxRegistration"), "ID", party.tax_number, schemeID="FC")


def _period(parent: etree._Element, start: date | None, end: date | None) -> None:
    if not (start or end):
        return
    period = _ram(parent, "BillingSpecifiedPeriod")
    if start:
        _datetime(period, "StartDateTime", start)
    if end:
        _datetime(period, "EndDateTime", end)


def _line(parent: etree._Element, invoice: Invoice, line: Line) -> None:
    item = _ram(parent, "IncludedSupplyChainTradeLineItem")
    _ram(_ram(item, "AssociatedDocumentLineDocument"), "LineID", line.id)
    product = _ram(item, "SpecifiedTradeProduct")
    _ram(product, "Name", line.name)
    _opt(product, "Description", line.description)
    agreement = _ram(item, "SpecifiedLineTradeAgreement")
    _ram(_ram(agreement, "NetPriceProductTradePrice"), "ChargeAmount", fmt_decimal(line.net_price))
    _ram(_ram(item, "SpecifiedLineTradeDelivery"), "BilledQuantity", fmt_decimal(line.quantity), unitCode=line.unit_code)
    settlement = _ram(item, "SpecifiedLineTradeSettlement")
    tax = _ram(settlement, "ApplicableTradeTax")
    _ram(tax, "TypeCode", "VAT")
    _ram(tax, "CategoryCode", line.vat_category.value)
    if line.vat_category != VatCategory.NOT_SUBJECT:  # BR-O-05: no rate outside the scope of VAT
        _ram(tax, "RateApplicablePercent", fmt_decimal(line.vat_rate))
    _period(settlement, line.period_start, line.period_end)
    for allowance in line.allowances:
        ac = _ram(settlement, "SpecifiedTradeAllowanceCharge")
        etree.SubElement(_ram(ac, "ChargeIndicator"), f"{{{UDT}}}Indicator").text = "false"
        _ram(ac, "ActualAmount", fmt_amount(allowance.amount))
        _ram(ac, "Reason", allowance.reason)
    _ram(
        _ram(settlement, "SpecifiedTradeSettlementLineMonetarySummation"),
        "LineTotalAmount",
        fmt_amount(line.net_amount),
    )


def to_cii(invoice: Invoice, profile: str = "xrechnung") -> bytes:
    root = etree.Element(
        f"{{{RSM}}}CrossIndustryInvoice",
        nsmap={"rsm": RSM, "ram": RAM, "udt": UDT, "qdt": QDT},
    )

    context = etree.SubElement(root, f"{{{RSM}}}ExchangedDocumentContext")
    _ram(_ram(context, "BusinessProcessSpecifiedDocumentContextParameter"), "ID", PEPPOL_PROFILE_ID)
    _ram(_ram(context, "GuidelineSpecifiedDocumentContextParameter"), "ID", PROFILES[profile])

    doc = etree.SubElement(root, f"{{{RSM}}}ExchangedDocument")
    _ram(doc, "ID", invoice.number)
    _ram(doc, "TypeCode", invoice.type_code)
    _datetime(doc, "IssueDateTime", invoice.issue_date)
    for note in invoice.notes:
        _ram(_ram(doc, "IncludedNote"), "Content", note)

    transaction = etree.SubElement(root, f"{{{RSM}}}SupplyChainTradeTransaction")
    for line in invoice.lines:
        _line(transaction, invoice, line)

    agreement = _ram(transaction, "ApplicableHeaderTradeAgreement")
    _opt(agreement, "BuyerReference", invoice.buyer_reference)
    _party(agreement, "SellerTradeParty", invoice.seller)
    _party(agreement, "BuyerTradeParty", invoice.buyer)
    if invoice.order_reference:
        _ram(_ram(agreement, "BuyerOrderReferencedDocument"), "IssuerAssignedID", invoice.order_reference)

    delivery = _ram(transaction, "ApplicableHeaderTradeDelivery")
    if invoice.delivery_date:
        _datetime(_ram(delivery, "ActualDeliverySupplyChainEvent"), "OccurrenceDateTime", invoice.delivery_date)

    settlement = _ram(transaction, "ApplicableHeaderTradeSettlement")
    # BT-90 marks the invoice as direct debit (BG-19) in CII, so only send it then.
    if invoice.is_direct_debit:
        _opt(settlement, "CreditorReferenceID", invoice.seller.creditor_id)
    pay = invoice.payment
    _opt(settlement, "PaymentReference", pay.remittance_info)
    _ram(settlement, "InvoiceCurrencyCode", invoice.currency)

    means = _ram(settlement, "SpecifiedTradeSettlementPaymentMeans")
    _ram(means, "TypeCode", pay.means_code)
    _opt(means, "Information", pay.means_text)
    if pay.card_last_digits:
        card = _ram(means, "ApplicableTradeSettlementFinancialCard")
        _ram(card, "ID", pay.card_last_digits)
        _opt(card, "CardholderName", pay.card_holder)
    if pay.debited_iban:
        _ram(_ram(means, "PayerPartyDebtorFinancialAccount"), "IBANID", pay.debited_iban)
    if pay.iban:
        account = _ram(means, "PayeePartyCreditorFinancialAccount")
        _ram(account, "IBANID", pay.iban)
        _opt(account, "AccountName", pay.account_name)
        if pay.bic:
            _ram(_ram(means, "PayeeSpecifiedCreditorFinancialInstitution"), "BICID", pay.bic)

    for b in invoice.vat_breakdown():
        tax = _ram(settlement, "ApplicableTradeTax")
        _ram(tax, "CalculatedAmount", fmt_amount(b.tax_amount))
        _ram(tax, "TypeCode", "VAT")
        _opt(tax, "ExemptionReason", b.exemption_reason)
        _ram(tax, "BasisAmount", fmt_amount(b.taxable_amount))
        _ram(tax, "CategoryCode", b.category.value)
        _opt(tax, "ExemptionReasonCode", b.exemption_code)
        _ram(tax, "RateApplicablePercent", fmt_decimal(b.rate))  # XRechnung needs it even for O (BR-DE-14)

    _period(settlement, invoice.period_start, invoice.period_end)

    if invoice.payment_terms or invoice.due_date or pay.mandate_reference:
        terms = _ram(settlement, "SpecifiedTradePaymentTerms")
        _opt(terms, "Description", invoice.payment_terms)
        if invoice.due_date:
            _datetime(terms, "DueDateDateTime", invoice.due_date)
        _opt(terms, "DirectDebitMandateID", pay.mandate_reference)

    totals = _ram(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation")
    _ram(totals, "LineTotalAmount", fmt_amount(invoice.line_total))
    _ram(totals, "TaxBasisTotalAmount", fmt_amount(invoice.tax_exclusive_total))
    _ram(totals, "TaxTotalAmount", fmt_amount(invoice.tax_total), currencyID=invoice.currency)
    _ram(totals, "GrandTotalAmount", fmt_amount(invoice.tax_inclusive_total))
    if invoice.paid_amount:
        _ram(totals, "TotalPrepaidAmount", fmt_amount(invoice.paid_amount))
    _ram(totals, "DuePayableAmount", fmt_amount(invoice.amount_due))

    if invoice.preceding_invoice:
        ref = _ram(settlement, "InvoiceReferencedDocument")
        _ram(ref, "IssuerAssignedID", invoice.preceding_invoice)
        if invoice.preceding_invoice_date:
            holder = _ram(ref, "FormattedIssueDateTime")
            el = etree.SubElement(holder, f"{{{QDT}}}DateTimeString", format="102")
            el.text = invoice.preceding_invoice_date.strftime("%Y%m%d")

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
