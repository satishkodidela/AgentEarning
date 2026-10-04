"""Read KEY=value settings files (the server's ~/.einvoice-bridge.env).

Same format systemd's EnvironmentFile accepts: one KEY=value per line,
``#`` comments, optional single or double quotes around the value (needed
for values like ``E-Rechnungsbote <rechnung@…>``). Values already set in the
process environment win.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT = Path.home() / ".einvoice-bridge.env"


def parse(text: str) -> dict[str, str]:
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load(path: str | Path | None = None) -> Path | None:
    """Load the given file, else $EINVOICE_ENV_FILE, else ~/.einvoice-bridge.env if present."""
    candidate = Path(path or os.environ.get("EINVOICE_ENV_FILE") or DEFAULT)
    if not candidate.is_file():
        return None
    for key, value in parse(candidate.read_text(encoding="utf-8")).items():
        os.environ.setdefault(key, value)
    return candidate
