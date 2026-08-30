from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Mapping

from magazine_mailer.models import Issue


class SmtpConfigError(ValueError):
    pass


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    recipient: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SmtpConfig":
        values = os.environ if env is None else env
        required = ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_TO")
        missing = [name for name in required if not values.get(name)]
        if missing:
            raise SmtpConfigError(
                "Missing required email configuration: " + ", ".join(missing)
            )
        host = values.get("SMTP_HOST", "smtp.gmail.com")
        try:
            port = int(values.get("SMTP_PORT", "587"))
        except ValueError as exc:
            raise SmtpConfigError("SMTP_PORT must be an integer") from exc
        return cls(
            host=host,
            port=port,
            username=values["MAIL_USERNAME"],
            password=values["MAIL_PASSWORD"],
            recipient=values["MAIL_TO"],
        )


class EmailDelivery:
    def __init__(
        self,
        config: SmtpConfig,
        smtp_factory: Callable = smtplib.SMTP,
        timeout: int = 30,
    ) -> None:
        self._config = config
        self._smtp_factory = smtp_factory
        self._timeout = timeout

    def send_issue(self, issue: Issue, payload: bytes) -> None:
        message = self._base_message(
            subject=f"{issue.magazine_name} · {issue.issue_id}",
            body=(
                f"{issue.magazine_name}\n"
                f"Issue: {issue.issue_id}\n\n"
                "The latest EPUB is attached.\n"
                "Source: hehonghui/awesome-english-ebooks\n"
            ),
        )
        message.add_attachment(
            payload,
            maintype="application",
            subtype="epub+zip",
            filename=issue.filename,
        )
        self._send(message)

    def send_stale_alert(self, issue: Issue, age_days: int) -> None:
        message = self._base_message(
            subject="The Economist source may be stale",
            body=(
                "The Economist upstream source may have stopped updating.\n\n"
                f"Latest detected issue: {issue.issue_id}\n"
                f"Issue age: {age_days} days\n"
                "Source: hehonghui/awesome-english-ebooks\n"
            ),
        )
        self._send(message)

    def _base_message(self, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._config.username
        message["To"] = self._config.recipient
        message["Subject"] = subject
        message.set_content(body)
        return message

    def _send(self, message: EmailMessage) -> None:
        try:
            with self._smtp_factory(
                self._config.host,
                self._config.port,
                timeout=self._timeout,
            ) as smtp:
                smtp.starttls()
                smtp.login(self._config.username, self._config.password)
                smtp.send_message(message)
        except Exception as exc:
            raise EmailDeliveryError("SMTP delivery failed") from exc
