from __future__ import annotations

import io

from pypdf import PdfReader
from facturx import get_xml_from_pdf

from einvoice_bridge.pdf import eur, to_zugferd_pdf
from einvoice_bridge.validation import validate


def test_zugferd_pdf_embeds_valid_en16931_xml(make_invoice):
    pdf = to_zugferd_pdf(make_invoice())
    assert pdf.startswith(b"%PDF-")
    filename, xml = get_xml_from_pdf(pdf, check_xsd=True)
    assert filename == "factur-x.xml"
    report = validate(pdf)
    assert report.valid, [(f.rule_id, f.message) for f in report.errors]
    assert report.specification_id == "urn:cen.eu:en16931:2017"


def test_pdf_declares_pdfa3_and_factur_x(make_invoice):
    reader = PdfReader(io.BytesIO(to_zugferd_pdf(make_invoice())))
    root = reader.trailer["/Root"]
    xmp = root["/Metadata"].get_object().get_data().decode()
    assert "<pdfaid:part>3</pdfaid:part>" in xmp
    assert "<pdfaid:conformance>B</pdfaid:conformance>" in xmp
    assert "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#" in xmp
    assert "/OutputIntents" in root
    assert list(reader.attachments) == ["factur-x.xml"]


def test_german_money_format():
    from decimal import Decimal

    assert eur(Decimal("1234.5")) == "1.234,50 €"
    assert eur(Decimal("0")) == "0,00 €"
