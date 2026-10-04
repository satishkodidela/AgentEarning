from __future__ import annotations

import re

import pytest

from einvoice_bridge.validation import NotAnInvoice, validate

from .conftest import FIXTURES

OFFICIAL = FIXTURES / "official"


@pytest.mark.parametrize("name", ["01.01a-INVOICE_ubl.xml", "01.01a-INVOICE_uncefact.xml"])
def test_official_kosit_samples_are_valid(name):
    report = validate((OFFICIAL / name).read_bytes())
    assert report.valid, [(f.rule_id, f.message) for f in report.errors]
    assert report.is_xrechnung


def test_schematron_error_has_rule_id_and_german_hint():
    xml = (OFFICIAL / "01.01a-INVOICE_ubl.xml").read_bytes()
    broken = re.sub(rb"<cbc:BuyerReference>.*?</cbc:BuyerReference>", b"", xml)
    report = validate(broken)
    assert not report.valid
    (finding,) = [f for f in report.errors]
    assert finding.rule_id == "BR-DE-15"
    assert finding.source == "xrechnung"
    assert "Leitweg-ID" in finding.hint


def test_wrong_total_is_reported():
    xml = (OFFICIAL / "01.01a-INVOICE_ubl.xml").read_bytes()
    broken = re.sub(rb'(<cbc:PayableAmount currencyID="EUR">)[0-9.]+', rb"\g<1>1.00", xml)
    assert "BR-CO-16" in {f.rule_id for f in validate(broken).errors}


def test_schema_error_stops_before_schematron():
    xml = (OFFICIAL / "01.01a-INVOICE_ubl.xml").read_bytes()
    broken = xml.replace(b"<cbc:IssueDate>", b"<cbc:IssueDate>not-a-date", 1)
    report = validate(broken)
    assert {f.source for f in report.findings} == {"xsd"}


def test_rejects_non_invoices():
    with pytest.raises(NotAnInvoice):
        validate(b"<html/>")
    with pytest.raises(NotAnInvoice):
        validate(b"not xml at all")


def test_doctype_and_entities_are_refused():
    xxe = b"""<?xml version="1.0"?>
<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">&e;</Invoice>"""
    with pytest.raises(NotAnInvoice):
        validate(xxe)
