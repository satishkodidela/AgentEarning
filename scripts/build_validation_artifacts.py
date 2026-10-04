#!/usr/bin/env python3
"""Assemble the official e-invoice validation artifacts into the package.

The validator must give the same verdicts as the KoSIT reference validator, so
it runs the official rule sets rather than home-grown checks:

* OASIS UBL 2.1 XSDs (via the ph-ubl repository, which mirrors them)
* UN/CEFACT CII D16B XSDs (shipped with the CEN EN 16931 validation artifacts)
* CEN EN 16931 Schematron, already compiled to XSLT by CEN
* KoSIT XRechnung Schematron, merged with the Peppol BIS rules it adopts and
  compiled to XSLT here with SchXslt (the same pipeline KoSIT's Ant build uses)

Sources are fetched with git (and SchXslt from Maven Central) into a cache
directory, pinned to the versions below. Re-run this script when bumping a
version; the output under src/einvoice_bridge/validation/artifacts is
committed so the package works offline.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "einvoice_bridge" / "validation" / "artifacts"

XRECHNUNG_VERSION = "3.0.2"
XR_SCHEMATRON_VERSION = "2.6.0"

SOURCES = {
    "en16931": {
        "url": "https://github.com/ConnectingEurope/eInvoicing-EN16931",
        "ref": "validation-1.3.16",
    },
    "xr-schematron": {
        "url": "https://github.com/itplr-kosit/xrechnung-schematron",
        "ref": f"v{XR_SCHEMATRON_VERSION}",
    },
    # KoSIT's build takes the Peppol rules from this branch when the release
    # archive is unavailable, which is the case for BIS 3.0.21.
    "peppol-bis": {
        "url": "https://github.com/OpenPEPPOL/peppol-bis-invoice-3",
        "ref": "2026-Q2-QA2",
    },
    "ph-ubl": {
        "url": "https://github.com/phax/ph-ubl",
        "ref": None,
        "sparse": ["/ph-ubl21/src/main/resources/external/schemas/"],
    },
    # ph-ubl strips schemaLocation from imports and resolves them from these
    # modules via a catalog; the build restores the locations instead.
    "ph-xsds": {
        "url": "https://github.com/phax/ph-xsds",
        "ref": None,
        "sparse": [
            f"/ph-xsds-{module}/src/main/resources/schemas/"
            for module in ("ccts-cct-schemamodule", "xmldsig", "xades132", "xades141")
        ],
    },
}
SCHXSLT_VERSION = "1.10.1"
SCHXSLT_JAR = (
    "https://repo1.maven.org/maven2/name/dmaus/schxslt/schxslt/"
    f"{SCHXSLT_VERSION}/schxslt-{SCHXSLT_VERSION}.jar"
)


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", "-c", "advice.detachedHead=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def fetch_sources(cache: Path) -> dict[str, str]:
    """Clone each pinned source once; return the commit of each."""
    commits = {}
    cache.mkdir(parents=True, exist_ok=True)
    for name, spec in SOURCES.items():
        dest = cache / name
        if not dest.exists():
            args = ["clone", "-q", "--depth", "1"]
            if spec["ref"]:
                args += ["--branch", spec["ref"]]
            if spec.get("sparse"):
                args += ["--filter=blob:none", "--sparse"]
            git(*args, spec["url"], str(dest))
            if spec.get("sparse"):
                git("sparse-checkout", "set", "--no-cone", *spec["sparse"], cwd=dest)
        commits[name] = git("rev-parse", "HEAD", cwd=dest)

    schxslt = cache / "schxslt"
    if not schxslt.exists():
        with urllib.request.urlopen(SCHXSLT_JAR, timeout=60) as resp:
            jar = resp.read()
        zipfile.ZipFile(io.BytesIO(jar)).extractall(schxslt)
    commits["schxslt"] = SCHXSLT_VERSION
    return commits


def compile_xrechnung_schematron(cache: Path, xslt_out: Path) -> None:
    """Merge Peppol rules into the XRechnung Schematron and compile it."""
    from saxonche import PySaxonProcessor

    xr = cache / "xr-schematron"
    build = xr / "build"
    shutil.rmtree(build, ignore_errors=True)
    (build / "bis").mkdir(parents=True)
    (build / "schematron" / "tmp").mkdir(parents=True)

    # peppol-into-xr.xsl reads the Peppol rules from ../../build/bis/.
    for syntax in ("UBL", "CII"):
        shutil.copy(
            cache / "peppol-bis" / "rules" / "sch" / f"PEPPOL-EN16931-{syntax}.sch",
            build / "bis",
        )

    validation = xr / "src" / "validation" / "schematron"
    shutil.copy(validation / "common.sch", build / "schematron" / "common.sch")
    for syntax in ("ubl", "cii"):
        src = (validation / syntax / f"XRechnung-{syntax.upper()}-validation.sch").read_text(
            encoding="utf-8"
        )
        src = src.replace("@xr-schematron.version.full@", XR_SCHEMATRON_VERSION)
        src = src.replace("@xrechnung.version@", XRECHNUNG_VERSION)
        (build / "schematron" / "tmp" / f"XRechnung-{syntax.upper()}-validation.sch").write_text(
            src, encoding="utf-8"
        )

    with PySaxonProcessor(license=False) as proc:
        xslt = proc.new_xslt30_processor()
        merge = xslt.compile_stylesheet(stylesheet_file=str(xr / "src" / "xsl" / "peppol-into-xr.xsl"))
        compiler = xslt.compile_stylesheet(
            stylesheet_file=str(cache / "schxslt" / "xslt" / "2.0" / "pipeline-for-svrl.xsl")
        )
        for syntax in ("UBL", "CII"):
            merged = build / "schematron" / syntax.lower() / f"XRechnung-{syntax}-validation.sch"
            merged.parent.mkdir(parents=True, exist_ok=True)
            merge.set_parameter("syntax", proc.make_string_value(syntax))
            merge.transform_to_file(
                source_file=str(build / "schematron" / "tmp" / f"XRechnung-{syntax}-validation.sch"),
                output_file=str(merged),
            )
            target = xslt_out / f"XRechnung-{syntax}-validation.xsl"
            compiler.transform_to_file(source_file=str(merged), output_file=str(target))


UBL_NAMESPACE_FILES = {
    "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2": "UBL-CommonAggregateComponents-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2": "UBL-CommonBasicComponents-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2": "UBL-CommonExtensionComponents-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2": "UBL-CommonSignatureComponents-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDataTypes-2": "UBL-QualifiedDataTypes-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:UnqualifiedDataTypes-2": "UBL-UnqualifiedDataTypes-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2": "UBL-SignatureAggregateComponents-2.1.xsd",
    "urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2": "UBL-SignatureBasicComponents-2.1.xsd",
    "urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2": "CCTS_CCT_SchemaModule-2.1.xsd",
    "http://www.w3.org/2000/09/xmldsig#": "UBL-xmldsig-core-schema-2.1.xsd",
    "http://uri.etsi.org/01903/v1.3.2#": "UBL-XAdESv132-2.1.xsd",
    "http://uri.etsi.org/01903/v1.4.1#": "UBL-XAdESv141-2.1.xsd",
}


def assemble_ubl_schemas(cache: Path, out: Path) -> None:
    """Copy the UBL 2.1 Invoice/CreditNote XSDs with resolvable imports."""
    from lxml import etree

    ubl = cache / "ph-ubl" / "ph-ubl21" / "src" / "main" / "resources" / "external" / "schemas" / "ubl21"
    (out / "maindoc").mkdir(parents=True)
    shutil.copytree(ubl / "common", out / "common")
    for doc in ("Invoice", "CreditNote"):
        shutil.copy(ubl / "maindoc" / f"UBL-{doc}-2.1.xsd", out / "maindoc")

    xsds = cache / "ph-xsds"
    for module, src, name in (
        ("ccts-cct-schemamodule", "CCTS_CCT_SchemaModule.xsd", "CCTS_CCT_SchemaModule-2.1.xsd"),
        ("xmldsig", "xmldsig-core-schema.xsd", "UBL-xmldsig-core-schema-2.1.xsd"),
        ("xades132", "XAdES01903v132-201601.xsd", "UBL-XAdESv132-2.1.xsd"),
        ("xades141", "XAdES01903v141-201601.xsd", "UBL-XAdESv141-2.1.xsd"),
    ):
        shutil.copy(xsds / f"ph-xsds-{module}" / "src" / "main" / "resources" / "schemas" / src, out / "common" / name)

    xs = "{http://www.w3.org/2001/XMLSchema}"
    for path in out.rglob("*.xsd"):
        tree = etree.parse(str(path), etree.XMLParser(resolve_entities=False, load_dtd=False))
        changed = False
        for imp in tree.iter(f"{xs}import"):
            if imp.get("schemaLocation"):
                continue
            target = out / "common" / UBL_NAMESPACE_FILES[imp.get("namespace")]
            imp.set("schemaLocation", os.path.relpath(target, path.parent))
            changed = True
        if changed:
            tree.write(str(path), xml_declaration=True, encoding="UTF-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cache",
        type=Path,
        default=ROOT / "build" / "validation-sources",
        help="where pinned sources are cloned (default: build/validation-sources)",
    )
    args = parser.parse_args()
    cache: Path = args.cache

    commits = fetch_sources(cache)

    shutil.rmtree(OUT, ignore_errors=True)
    xslt_out = OUT / "xslt"
    xslt_out.mkdir(parents=True)

    for syntax in ("ubl", "cii"):
        shutil.copy(
            cache / "en16931" / syntax / "xslt" / f"EN16931-{syntax.upper()}-validation.xslt",
            xslt_out,
        )
    compile_xrechnung_schematron(cache, xslt_out)

    assemble_ubl_schemas(cache, OUT / "xsd" / "ubl21")
    shutil.copytree(
        cache / "en16931" / "cii" / "schema" / "D16B SCRDM (Subset)" / "uncoupled clm" / "CII",
        OUT / "xsd" / "cii-d16b",
        ignore=shutil.ignore_patterns("*.doc", "*.docx"),
    )

    licenses = OUT / "LICENSES"
    licenses.mkdir()
    shutil.copy(cache / "en16931" / "LICENSE.txt", licenses / "EN16931-validation-EUPL-1.2.txt")
    shutil.copy(cache / "xr-schematron" / "LICENSE", licenses / "XRechnung-Schematron-Apache-2.0.txt")

    (OUT / "VERSIONS.json").write_text(
        json.dumps(
            {
                "xrechnung": XRECHNUNG_VERSION,
                "xrechnung_schematron": XR_SCHEMATRON_VERSION,
                "en16931_validation": SOURCES["en16931"]["ref"],
                "peppol_bis_rules": SOURCES["peppol-bis"]["ref"],
                "schxslt": SCHXSLT_VERSION,
                "commits": commits,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Artifacts written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
