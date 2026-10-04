"""Entry point for cPanel "Setup Python App" (Phusion Passenger, WSGI).

install.sh copies this file to the application root. Settings come from
~/.einvoice-bridge.env (mode 600, outside the web root), so secrets are not
typed into the cPanel form one by one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from einvoice_bridge import envfile  # noqa: E402

envfile.load()

from a2wsgi import ASGIMiddleware  # noqa: E402

from einvoice_bridge.web.app import create_app  # noqa: E402

application = ASGIMiddleware(create_app())
