"""Pull the headline facts out of a UBL or CII invoice for display."""

from __future__ import annotations

from lxml import etree

UBL_NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}
CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

UBL_PATHS = {
    "number": "cbc:ID",
    "issue_date": "cbc:IssueDate",
    "currency": "cbc:DocumentCurrencyCode",
    "buyer_reference": "cbc:BuyerReference",
    "seller": "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName",
    "buyer": "cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName",
    "total": "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
    "due": "cac:LegalMonetaryTotal/cbc:PayableAmount",
}
CII_PATHS = {
    "number": "rsm:ExchangedDocument/ram:ID",
    "issue_date": "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString",
    "currency": "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
    "buyer_reference": "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerReference",
    "seller": "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:Name",
    "buyer": "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:Name",
    "total": "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/"
    "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount",
    "due": "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/"
    "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:DuePayableAmount",
}


def summarize(xml: bytes) -> dict[str, str | None]:
    root = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    is_cii = root.tag.endswith("CrossIndustryInvoice")
    paths, ns = (CII_PATHS, CII_NS) if is_cii else (UBL_PATHS, UBL_NS)
    facts = {key: root.findtext(path, namespaces=ns) for key, path in paths.items()}
    if is_cii and facts["issue_date"] and len(facts["issue_date"]) == 8:
        d = facts["issue_date"]
        facts["issue_date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if is_cii:
        facts["lines"] = str(len(root.findall("rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", CII_NS)))
    else:
        facts["lines"] = str(len(root.findall("cac:InvoiceLine", UBL_NS)) + len(root.findall("cac:CreditNoteLine", UBL_NS)))
    return facts
