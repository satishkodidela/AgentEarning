from __future__ import annotations

from cryptography.fernet import Fernet

from einvoice_bridge.doctor import FAIL, OK, WARN, run

ENV = {
    "EINVOICE_BASE_URL": "https://erechnungsbote.de",
    "EINVOICE_CONTACT_EMAIL": "kontakt@erechnungsbote.de",
    "SMTP_HOST": "mail.privateemail.com",
    "SMTP_FROM": "E-Rechnungsbote <rechnung@erechnungsbote.de>",
    "SMTP_USER": "rechnung@erechnungsbote.de",
    "SMTP_PASSWORD": "secret-not-printed",
    "STRIPE_APP_SECRET_KEY": "sk_test_x",
    "STRIPE_APP_INSTALL_LINK": "https://marketplace.stripe.com/oauth/v2/chnlink_1/authorize?client_id=ca_1",
    "STRIPE_CONNECT_WEBHOOK_SECRET": "whsec_1",
    "PADDLE_CLIENT_TOKEN": "test_abc",
    "PADDLE_API_KEY": "pdl_sdbx_x",
    "PADDLE_WEBHOOK_SECRET": "s",
    "PADDLE_PRICES_STARTER": "pri_1",
    "PADDLE_PRICES_BUSINESS": "pri_2",
}


def status_of(report, topic):
    return next(status for status, t, _ in report.lines if t == topic)


def test_complete_dev_config_has_no_errors(monkeypatch, tmp_path, capsys):
    for key, value in {**ENV, "EINVOICE_SECRET_KEY": Fernet.generate_key().decode(),
                       "EINVOICE_DATA_DIR": str(tmp_path / "data"), "EINVOICE_LEGAL_DIR": str(tmp_path / "legal")}.items():
        monkeypatch.setenv(key, value)
    report = run()
    assert not report.failed, report.lines
    assert status_of(report, "Prüfregeln") == OK and status_of(report, "PDF") == OK
    assert status_of(report, "Rechtstexte") == WARN and status_of(report, "Paddle") == WARN  # sandbox
    report.print()
    assert "secret-not-printed" not in capsys.readouterr().out


def test_missing_and_mixed_up_settings_are_errors(monkeypatch, tmp_path):
    for key in list(ENV) + ["EINVOICE_SECRET_KEY", "EINVOICE_DATA_DIR"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EINVOICE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PADDLE_CLIENT_TOKEN", "live_abc")
    monkeypatch.setenv("PADDLE_API_KEY", "k")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("PADDLE_PRICES_STARTER", "pri_1")
    monkeypatch.setenv("PADDLE_PRICES_BUSINESS", "pri_2")
    report = run()
    assert report.failed
    assert status_of(report, "Schlüssel") == FAIL and status_of(report, "E-Mail") == FAIL
    assert status_of(report, "Paddle") == FAIL  # live token in sandbox mode


def test_env_file_with_quotes_and_comments(tmp_path, monkeypatch):
    from einvoice_bridge import envfile

    path = tmp_path / "env"
    path.write_text('# comment\nSMTP_FROM="E-Rechnungsbote <rechnung@erechnungsbote.de>"\nA=1\nB=\'two words\'\n\nC=x=y\n')
    for key in ("SMTP_FROM", "A", "B", "C"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("A", "already-set")
    assert envfile.load(path) == path
    import os

    assert os.environ["SMTP_FROM"] == "E-Rechnungsbote <rechnung@erechnungsbote.de>"
    assert os.environ["A"] == "already-set" and os.environ["B"] == "two words" and os.environ["C"] == "x=y"
