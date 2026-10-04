"""Entry point for cPanel "Setup Python App" (Phusion Passenger, WSGI).

install.sh copies this file to the application root. Settings come from
~/.einvoice-bridge.env (mode 600, outside the web root), so secrets are not
typed into the cPanel form one by one.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

ENV_FILE = Path(os.environ.get("EINVOICE_ENV_FILE", Path.home() / ".einvoice-bridge.env"))
if ENV_FILE.is_file():
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

from a2wsgi import ASGIMiddleware  # noqa: E402

from einvoice_bridge.web.app import create_app  # noqa: E402

application = ASGIMiddleware(create_app())
