"""Email delivery with PDF attachment, inline highlights, and retry with backoff."""

import asyncio
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2.0
BACKOFF_MAX = 30.0


class EmailService:
    """Send digest email via SMTP with retries."""

    def __init__(self):
        self.settings = get_settings()

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
        if self.settings.smtp_host and self.settings.smtp_user:
            return await self._send_smtp_with_retry(
                recipients, subject, body_plain, body_html,
                pdf_path, attachment_filename,
            )
        logger.warning("Email not configured (no SMTP). Skipping send.")
        return False

    async def _send_smtp_with_retry(
        self,
        recipients: List[str],
        subject: str,
        body_plain: str,
        body_html: str,
        pdf_path: Optional[Path] = None,
        attachment_filename: Optional[str] = None,
    ) -> bool:
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
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
                        part.add_header("Content-Disposition", "attachment", filename=name)
                        msg.attach(part)

                with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                    server.starttls()
                    server.login(self.settings.smtp_user, self.settings.smtp_password or "")
                    server.sendmail(msg["From"], recipients, msg.as_string())

                logger.info("Digest email sent to %s", recipients)
                return True

            except smtplib.SMTPAuthenticationError:
                logger.warning(
                    "Gmail rejected login (535). Use an App Password, not your normal password. "
                    "See backend/EMAIL_SETUP.md or https://support.google.com/mail/?p=BadCredentials"
                )
                return False

            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                    smtplib.SMTPResponseException, OSError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = min(BACKOFF_MAX, BACKOFF_BASE ** (attempt + 1))
                    logger.info(
                        "Email send failed (%s), retry %d/%d in %.1fs",
                        type(e).__name__, attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.warning("Email send failed after %d retries: %s", MAX_RETRIES, e)
                return False

            except Exception as e:
                logger.exception("SMTP send failed: %s", e)
                return False

        if last_error:
            logger.warning("Email send exhausted retries: %s", last_error)
        return False
