"""Catalogue of every validation rule, read from the official artifacts.

Feeds the public rule pages ("Was bedeutet BR-DE-15?"), which is what
people search for when a recipient rejects their e-invoice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from lxml import etree

from . import ARTIFACTS, NS_SVRL
from .hints import hint_for

SOURCES = {
    "EN16931-UBL-validation.xslt": "EN 16931",
    "EN16931-CII-validation.xslt": "EN 16931",
    "XRechnung-UBL-validation.xsl": "XRechnung",
    "XRechnung-CII-validation.xsl": "XRechnung",
}

RULE_ID = re.compile(r"^[A-Z][A-Z0-9-]*-[A-Z0-9-]+$")


@dataclass(frozen=True)
class Rule:
    id: str
    text: str
    severity: str
    standard: str
    hint: str | None

    @property
    def slug(self) -> str:
        return self.id.lower()


def _severity(flag: str | None) -> str:
    return {"fatal": "Fehler", "error": "Fehler", "warning": "Warnung"}.get((flag or "").lower(), "Hinweis")


@lru_cache(maxsize=1)
def rules() -> dict[str, Rule]:
    found: dict[str, Rule] = {}
    xsl = "http://www.w3.org/1999/XSL/Transform"
    for filename, standard in SOURCES.items():
        tree = etree.parse(str(ARTIFACTS / "xslt" / filename))
        for el in tree.iter(f"{{{NS_SVRL}}}failed-assert", f"{{{NS_SVRL}}}successful-report"):
            rule_id = el.get("id")
            flag = el.get("flag")
            # CEN's compiled XSLT sets id/flag through xsl:attribute children.
            for attr in el.iter(f"{{{xsl}}}attribute"):
                if attr.get("name") == "id":
                    rule_id = rule_id or "".join(attr.itertext()).strip()
                elif attr.get("name") == "flag":
                    flag = flag or "".join(attr.itertext()).strip()
            text = " ".join("".join(el.findtext(f"{{{NS_SVRL}}}text") or "").split())
            if not rule_id or not RULE_ID.match(rule_id) or rule_id in found:
                continue
            text = re.sub(r"^\[[^\]]+\]\s*-?\s*", "", text)
            found[rule_id] = Rule(rule_id, text, _severity(flag), standard, hint_for(rule_id))
    return dict(sorted(found.items(), key=lambda kv: _sort_key(kv[0])))


def _sort_key(rule_id: str) -> tuple:
    parts = re.split(r"(\d+)", rule_id)
    return tuple(int(p) if p.isdigit() else p for p in parts)


def by_slug(slug: str) -> Rule | None:
    return next((r for r in rules().values() if r.slug == slug.lower()), None)
