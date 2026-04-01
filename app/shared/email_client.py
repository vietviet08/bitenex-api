import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "email"

# Use ThreadPoolExecutor to run expensive synchronous smtp processes in background
_executor = ThreadPoolExecutor(max_workers=3)

def _send_email_sync(to_email: str, subject: str, html_body: str):
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP credentials not configured. Cannot send email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = to_email

    part = MIMEText(html_body, "html")
    msg.attach(part)

    try:
        if settings.smtp_tls_ssl:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
            
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, to_email, msg.as_string())
        server.quit()
        logger.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

def _render_template(template_name: str, **context) -> str:
    template_path = TEMPLATES_DIR / template_name
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
            for key, value in context.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            return content
    except Exception as e:
        logger.error(f"Failed to load email template {template_name}: {e}")
        return ""

class EmailClient:
    @staticmethod
    async def send_verification_email(to_email: str, token: str, base_url: str):
        subject = "Account Verification"
        
        # Build full URL dynamically
        base_url = base_url.rstrip('/')
        verify_url = f"{base_url}/api/v1/auth/verify/{token}"
        
        html = _render_template("verification.html", token=token, verify_url=verify_url)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _send_email_sync, to_email, subject, html)

    @staticmethod
    async def send_password_reset_email(to_email: str, token: str, base_url: str):
        subject = "Password Reset Request"
        
        base_url = base_url.rstrip('/')
        reset_url = f"{base_url}/api/v1/auth/password/reset/confirm?token={token}"
        
        html = _render_template("password_reset.html", token=token, reset_url=reset_url)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _send_email_sync, to_email, subject, html)
