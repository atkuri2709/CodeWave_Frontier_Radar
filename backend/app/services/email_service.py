"""Email delivery with PDF attachment, inline highlights, and retry with backoff.

Supports two providers:
  1. SMTP (primary) — uses smtp_host/smtp_user/smtp_password
  2. Mailgun API (fallback) — uses mailgun_api_key/mailgun_domain

If SMTP is configured, it is tried first. If it fails (e.g. port blocked on
cloud hosting), Mailgun is used as a fallback. If only Mailgun is configured,
it is used directly.
"""

import asyncio
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2.0
BACKOFF_MAX = 30.0

MAILGUN_API_URL = "https://api.mailgun.net/v3/{domain}/messages"


class EmailService:
    """Send digest email via SMTP or Mailgun with automatic fallback."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def _smtp_configured(self) -> bool:
        return bool(self.settings.smtp_host and self.settings.smtp_user)

    @property
    def _mailgun_configured(self) -> bool:
        return bool(self.settings.mailgun_api_key and self.settings.mailgun_domain)

    async def send_digest(
        self,
        recipients: List[str],
        subject: str,
        body_html: str,
        body_plain: str,
        pdf_path: Optional[Path] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        if not recipients:
            logger.warning("No recipients configured")
            return False

        if self._smtp_configured:
            retries = 1 if self._mailgun_configured else MAX_RETRIES
            ok = await self._send_smtp_with_retry(
                recipients, subject, body_plain, body_html, pdf_path, attachment_filename,
                max_retries=retries,
            )
            if ok:
                return True
            if self._mailgun_configured:
                logger.info("SMTP failed; falling back to Mailgun...")
            else:
                logger.warning("SMTP failed and no Mailgun configured.")

        if self._mailgun_configured:
            return await self._send_mailgun_with_retry(
                recipients, subject, body_plain, body_html, pdf_path, attachment_filename
            )

        logger.warning("Email not configured (no SMTP or Mailgun). Skipping send.")
        return False

    # ── SMTP ──────────────────────────────────────────────────────────

    async def _send_smtp_with_retry(
        self,
        recipients: List[str],
        subject: str,
        body_plain: str,
        body_html: str,
        pdf_path: Optional[Path] = None,
        attachment_filename: Optional[str] = None,
        max_retries: int = MAX_RETRIES,
    ) -> bool:
        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.settings.smtp_from or self.settings.smtp_user
                msg["To"] = ", ".join(recipients)
                msg.attach(MIMEText(body_plain, "plain"))
                msg.attach(MIMEText(body_html, "html"))

                if pdf_path and Path(pdf_path).exists():
                    with open(pdf_path, "rb") as f:
                        part = MIMEApplication(f.read(), _subtype="pdf")
                        name = attachment_filename or Path(pdf_path).name
                        part.add_header(
                            "Content-Disposition", "attachment", filename=name
                        )
                        msg.attach(part)

                with smtplib.SMTP(
                    self.settings.smtp_host, self.settings.smtp_port
                ) as server:
                    server.starttls()
                    server.login(
                        self.settings.smtp_user, self.settings.smtp_password or ""
                    )
                    server.sendmail(msg["From"], recipients, msg.as_string())

                logger.info("Digest email sent via SMTP to %s", recipients)
                return True

            except smtplib.SMTPAuthenticationError:
                logger.warning(
                    "Gmail rejected login (535). Use an App Password, not your normal password."
                )
                return False

            except (
                smtplib.SMTPServerDisconnected,
                smtplib.SMTPConnectError,
                smtplib.SMTPResponseException,
                OSError,
            ) as e:
                last_error = e
                if attempt < max_retries:
                    wait = min(BACKOFF_MAX, BACKOFF_BASE ** (attempt + 1))
                    logger.info(
                        "SMTP send failed (%s), retry %d/%d in %.1fs",
                        type(e).__name__,
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.warning("SMTP send failed after %d retries: %s", max_retries, e)
                return False

            except Exception as e:
                logger.exception("SMTP send failed: %s", e)
                return False

        if last_error:
            logger.warning("SMTP send exhausted retries: %s", last_error)
        return False

    # ── Mailgun ───────────────────────────────────────────────────────

    async def _send_mailgun_with_retry(
        self,
        recipients: List[str],
        subject: str,
        body_plain: str,
        body_html: str,
        pdf_path: Optional[Path] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        url = MAILGUN_API_URL.format(domain=self.settings.mailgun_domain)
        sender = (
            self.settings.mailgun_from
            or f"Frontier AI Radar <radar@{self.settings.mailgun_domain}>"
        )

        any_sent = False
        for recipient in recipients:
            ok = await self._mailgun_send_one(
                url, sender, recipient, subject, body_plain, body_html,
                pdf_path, attachment_filename,
            )
            if ok:
                any_sent = True

        return any_sent

    async def _mailgun_send_one(
        self,
        url: str,
        sender: str,
        recipient: str,
        subject: str,
        body_plain: str,
        body_html: str,
        pdf_path: Optional[Path] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                data = {
                    "from": sender,
                    "to": [recipient],
                    "subject": subject,
                    "text": body_plain,
                    "html": body_html,
                }

                files = []
                file_handles = []
                try:
                    if pdf_path and Path(pdf_path).exists():
                        name = attachment_filename or Path(pdf_path).name
                        fh = open(pdf_path, "rb")
                        file_handles.append(fh)
                        files.append(("attachment", (name, fh, "application/pdf")))

                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            url,
                            auth=("api", self.settings.mailgun_api_key),
                            data=data,
                            files=files if files else None,
                        )
                finally:
                    for fh in file_handles:
                        fh.close()

                if resp.status_code == 200:
                    logger.info("Mailgun email sent to %s", recipient)
                    return True
                elif resp.status_code == 403:
                    logger.warning(
                        "Mailgun rejected %s (not authorized on sandbox): %s",
                        recipient, resp.text,
                    )
                    return False
                else:
                    logger.warning(
                        "Mailgun API error %d for %s: %s",
                        resp.status_code, recipient, resp.text,
                    )
                    raise httpx.HTTPStatusError(
                        f"Mailgun returned {resp.status_code}: {resp.text}",
                        request=resp.request,
                        response=resp,
                    )

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = min(BACKOFF_MAX, BACKOFF_BASE ** (attempt + 1))
                    logger.info(
                        "Mailgun send to %s failed (%s), retry %d/%d in %.1fs",
                        recipient, type(e).__name__,
                        attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.warning(
                    "Mailgun send to %s failed after %d retries: %s",
                    recipient, MAX_RETRIES, e,
                )
                return False

        if last_error:
            logger.warning("Mailgun send to %s exhausted retries: %s", recipient, last_error)
        return False
