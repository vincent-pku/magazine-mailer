from datetime import date
from email.message import EmailMessage

import pytest

from magazine_mailer.email_delivery import (
    EmailDelivery,
    EmailDeliveryError,
    SmtpConfig,
    SmtpConfigError,
)
from magazine_mailer.models import Issue


def make_issue():
    return Issue(
        magazine_key="economist",
        magazine_name="The Economist",
        issue_id="2026.08.29",
        issue_date=date(2026, 8, 29),
        epub_url="https://example.test/e.epub",
        filename="TheEconomist.2026.08.29.epub",
    )


def test_smtp_config_requires_account_specific_values():
    with pytest.raises(SmtpConfigError, match="MAIL_USERNAME"):
        SmtpConfig.from_env({})


def test_smtp_config_uses_gmail_friendly_defaults():
    config = SmtpConfig.from_env(
        {
            "MAIL_USERNAME": "sender@example.com",
            "MAIL_PASSWORD": "app-password",
            "MAIL_TO": "reader@example.com",
        }
    )

    assert config.host == "smtp.gmail.com"
    assert config.port == 587
    assert config.username == "sender@example.com"
    assert config.password == "app-password"
    assert config.recipient == "reader@example.com"


def test_smtp_config_treats_empty_optional_values_as_unset():
    config = SmtpConfig.from_env(
        {
            "MAIL_USERNAME": "sender@example.com",
            "MAIL_PASSWORD": "app-password",
            "MAIL_TO": "reader@example.com",
            "SMTP_HOST": "",
            "SMTP_PORT": "",
        }
    )

    assert config.host == "smtp.gmail.com"
    assert config.port == 587


class FakeSMTP:
    def __init__(self, host, port, timeout=30, *, fail_login=False):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.fail_login = fail_login
        self.calls = []
        self.sent_message = None

    def __enter__(self):
        self.calls.append(("enter",))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.calls.append(("exit",))
        return False

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, username, password):
        self.calls.append(("login", username, password))
        if self.fail_login:
            raise RuntimeError(f"login rejected: {password}")

    def send_message(self, message):
        self.calls.append(("send_message",))
        self.sent_message = message


class SMTPFactory:
    def __init__(self, *, fail_login=False):
        self.instances = []
        self.fail_login = fail_login

    def __call__(self, host, port, timeout=30):
        instance = FakeSMTP(host, port, timeout, fail_login=self.fail_login)
        self.instances.append(instance)
        return instance


def make_config():
    return SmtpConfig(
        host="smtp.gmail.com",
        port=587,
        username="sender@example.com",
        password="app-password",
        recipient="reader@example.com",
    )


def test_send_issue_builds_epub_attachment_and_uses_starttls_login_send_sequence():
    factory = SMTPFactory()
    delivery = EmailDelivery(make_config(), smtp_factory=factory)
    issue = make_issue()

    delivery.send_issue(issue, b"epub-bytes")

    smtp = factory.instances[0]
    assert smtp.host == "smtp.gmail.com"
    assert smtp.port == 587
    assert [call[0] for call in smtp.calls] == [
        "enter",
        "starttls",
        "login",
        "send_message",
        "exit",
    ]
    message = smtp.sent_message
    assert isinstance(message, EmailMessage)
    assert message["From"] == "sender@example.com"
    assert message["To"] == "reader@example.com"
    assert message["Subject"] == "The Economist · 2026.08.29"
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "TheEconomist.2026.08.29.epub"
    assert attachments[0].get_content_type() == "application/epub+zip"
    assert attachments[0].get_payload(decode=True) == b"epub-bytes"


def test_send_stale_alert_contains_issue_and_age_without_attachment():
    factory = SMTPFactory()
    delivery = EmailDelivery(make_config(), smtp_factory=factory)

    delivery.send_stale_alert(make_issue(), age_days=11)

    message = factory.instances[0].sent_message
    assert message["Subject"] == "The Economist source may be stale"
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "2026.08.29" in body
    assert "11 days" in body
    assert list(message.iter_attachments()) == []


def test_delivery_error_does_not_expose_password():
    factory = SMTPFactory(fail_login=True)
    delivery = EmailDelivery(make_config(), smtp_factory=factory)

    with pytest.raises(EmailDeliveryError) as exc_info:
        delivery.send_issue(make_issue(), b"epub-bytes")

    assert "app-password" not in str(exc_info.value)
