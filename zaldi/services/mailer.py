"""Sending email (password reset links), only when the server is set up for it: ``SMTP_HOST`` and ``SMTP_FROM``.

Without them nothing is sent and the portal says so: the server admin can create a reset link by hand instead.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from zaldi import config

log = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_FROM)


def send(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns whether it was sent; a failure is logged (without the body) and never raised to the shopper."""
    if not enabled():
        return False
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = config.SMTP_FROM, to, subject
    message.set_content(body)
    try:
        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        with server:
            if config.SMTP_PORT != 465 and config.SMTP_STARTTLS:
                server.starttls(context=ssl.create_default_context())
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception:
        log.exception("could not send email to a store account")
        return False
