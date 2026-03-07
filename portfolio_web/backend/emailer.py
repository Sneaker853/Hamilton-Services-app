import logging
import smtplib
from email.message import EmailMessage

from config import SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body_text: str) -> bool:
    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        logger.info("SMTP not configured. Skipping email send to %s. Subject=%s", to_email, subject)
        logger.info("Email body preview: %s", body_text)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(body_text)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False
