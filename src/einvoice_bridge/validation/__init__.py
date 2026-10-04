"""Validate e-invoices with the official XSD and Schematron rule sets.

The pipeline mirrors the KoSIT reference validator's XRechnung scenarios:
XML Schema first, then the CEN EN 16931 rules, then the XRechnung (CIUS)
rules when the document declares an XRechnung specification identifier.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from lxml import etree

from .hints import hint_for

ARTIFACTS = Path(__file__).parent / "artifacts"

NS_UBL_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_UBL_CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_CII = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
NS_SVRL = "http://purl.oclc.org/dsdl/svrl"

XRECHNUNG_PREFIX = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"

SEVERITY_BY_FLAG = {
    "fatal": "error",
    "error": "error",
    "warning": "warning",
    "information": "info",
    "info": "info",
}


class NotAnInvoice(ValueError):
    """The input is not XML, or not a UBL/CII invoice document."""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str  # "error" | "warning" | "info"
    message: str
    location: str
    source: str  # "xsd" | "en16931" | "xrechnung"

    @property
    def hint(self) -> str | None:
        return hint_for(self.rule_id)


@dataclass
class ValidationReport:
    syntax: str  # "UBL-Invoice" | "UBL-CreditNote" | "CII"
    specification_id: str | None
    findings: list[Finding] = field(default_factory=list)

    @property
    def is_xrechnung(self) -> bool:
        return bool(self.specification_id and self.specification_id.startswith(XRECHNUNG_PREFIX))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "syntax": self.syntax,
            "specification_id": self.specification_id,
            "is_xrechnung": self.is_xrechnung,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "message": f.message,
                    "location": f.location,
                    "source": f.source,
                    "hint": f.hint,
                }
                for f in self.findings
            ],
        }


# Saxon/C keeps one JVM-free processor per process; compiled stylesheets are
# reused across calls, and a lock serialises transforms because the Python
# bindings are not documented as thread-safe.
_saxon_lock = threading.Lock()
_saxon = None
_executables: dict[str, object] = {}


def _executable(name: str):
    global _saxon
    from saxonche import PySaxonProcessor

    if _saxon is None:
        _saxon = PySaxonProcessor(license=False)
    if name not in _executables:
        xslt = _saxon.new_xslt30_processor()
        _executables[name] = xslt.compile_stylesheet(stylesheet_file=str(ARTIFACTS / "xslt" / name))
    return _executables[name]


def _run_schematron(xml: bytes, stylesheet: str, source: str) -> list[Finding]:
    with _saxon_lock:
        executable = _executable(stylesheet)
        node = _saxon.parse_xml(xml_text=xml.decode("utf-8"))
        svrl = executable.transform_to_string(xdm_node=node)
    return _parse_svrl(svrl.encode("utf-8"), source)


def _parse_svrl(svrl: bytes, source: str) -> list[Finding]:
    root = etree.fromstring(svrl)
    findings = []
    for el in root.iter(f"{{{NS_SVRL}}}failed-assert", f"{{{NS_SVRL}}}successful-report"):
        text = " ".join("".join(el.findtext(f"{{{NS_SVRL}}}text") or "").split())
        rule_id = el.get("id") or _rule_id_from_text(text)
        findings.append(
            Finding(
                rule_id=rule_id,
                severity=SEVERITY_BY_FLAG.get((el.get("flag") or "fatal").lower(), "error"),
                message=text,
                location=el.get("location", ""),
                source=source,
            )
        )
    return findings


def _rule_id_from_text(text: str) -> str:
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    return "UNKNOWN"


@lru_cache(maxsize=None)
def _schema(syntax: str) -> etree.XMLSchema:
    paths = {
        "UBL-Invoice": ARTIFACTS / "xsd" / "ubl21" / "maindoc" / "UBL-Invoice-2.1.xsd",
        "UBL-CreditNote": ARTIFACTS / "xsd" / "ubl21" / "maindoc" / "UBL-CreditNote-2.1.xsd",
        "CII": ARTIFACTS
        / "xsd"
        / "cii-d16b"
        / "uncefact"
        / "data"
        / "standard"
        / "CrossIndustryInvoice_100pD16B.xsd",
    }
    return etree.XMLSchema(etree.parse(str(paths[syntax])))


def _detect(root: etree._Element) -> tuple[str, str | None]:
    ns = etree.QName(root).namespace
    if ns == NS_UBL_INVOICE:
        syntax = "UBL-Invoice"
    elif ns == NS_UBL_CREDIT_NOTE:
        syntax = "UBL-CreditNote"
    elif ns == NS_CII:
        syntax = "CII"
    else:
        raise NotAnInvoice(f"Unbekanntes Dokument: Wurzelelement {root.tag}")

    if syntax == "CII":
        spec = root.findtext(
            "{*}ExchangedDocumentContext/{*}GuidelineSpecifiedDocumentContextParameter/{*}ID"
        )
    else:
        spec = root.findtext(
            "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CustomizationID"
        )
    return syntax, spec.strip() if spec else None


def extract_xml_from_pdf(pdf: bytes) -> bytes:
    """Return the invoice XML embedded in a ZUGFeRD/Factur-X PDF."""
    from facturx import get_xml_from_pdf

    _filename, xml = get_xml_from_pdf(pdf, check_xsd=False)
    if not xml:
        raise NotAnInvoice("Die PDF-Datei enthält keine eingebettete E-Rechnung (ZUGFeRD/Factur-X).")
    return xml


def validate(document: bytes) -> ValidationReport:
    """Validate an XRechnung/EN 16931 document (XML, or ZUGFeRD PDF)."""
    if document.lstrip()[:5] == b"%PDF-":
        document = extract_xml_from_pdf(document)

    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        tree = etree.fromstring(document, parser)
    except etree.XMLSyntaxError as exc:
        raise NotAnInvoice(f"Kein gültiges XML: {exc}") from exc
    if tree.getroottree().docinfo.doctype:
        # E-invoices never use DTDs; refusing them rules out entity tricks.
        raise NotAnInvoice("Dokumente mit DOCTYPE-Deklaration werden nicht verarbeitet.")

    syntax, spec = _detect(tree)
    report = ValidationReport(syntax=syntax, specification_id=spec)

    schema = _schema(syntax)
    if not schema.validate(tree):
        for err in schema.error_log:
            report.findings.append(
                Finding(
                    rule_id="XSD",
                    severity="error",
                    message=err.message,
                    location=f"Zeile {err.line}",
                    source="xsd",
                )
            )
        # Schematron rules assume a schema-valid document; stop here like KoSIT.
        return report

    xml = etree.tostring(tree, encoding="utf-8", xml_declaration=True)
    family = "CII" if syntax == "CII" else "UBL"
    report.findings += _run_schematron(xml, f"EN16931-{family}-validation.xslt", "en16931")
    if report.is_xrechnung:
        report.findings += _run_schematron(xml, f"XRechnung-{family}-validation.xsl", "xrechnung")
    return report
