"""
Email Sending Engine -- abstraction layer over SMTP, SendGrid, and AWS SES.
Supports tracking pixel injection, click-wrap links, and unsubscribe headers.

Usage:
    from app.email.sender import get_default_sender, EmailMessage

    sender = await get_default_sender()
    result = await sender.send(EmailMessage(
        to_email="jane@example.com",
        from_email="noreply@s2media.live",
        subject="Welcome!",
        html_content="<h1>Hello</h1>",
    ))
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# TTL cache for sender config
# ---------------------------------------------------------------------------

_SENDER_CACHE_TTL = 120  # 2 minutes

_sender_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    entry = _sender_cache.get(key)
    if entry is None:
        return None
    expires_at, obj = entry
    if time.monotonic() > expires_at:
        del _sender_cache[key]
        return None
    return obj


def _cache_set(key: str, obj):
    _sender_cache[key] = (time.monotonic() + _SENDER_CACHE_TTL, obj)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EmailMessage:
    """A single outgoing email message."""

    to_email: str
    to_name: str = ""
    from_email: str = ""
    from_name: str = ""
    reply_to: str = ""
    subject: str = ""
    html_content: str = ""
    text_content: str = ""
    headers: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    campaign_id: str | None = None
    contact_id: str | None = None


@dataclass
class SendResult:
    """Result of a send attempt."""

    success: bool
    message_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class BaseSender(ABC):
    """Protocol for email sending backends."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> SendResult:
        """Send a single email. Returns a SendResult."""

    async def send_batch(self, messages: list[EmailMessage]) -> list[SendResult]:
        """
        Send a batch of emails.
        Default implementation sends sequentially; subclasses can override for
        connection pooling or API batching.
        """
        results: list[SendResult] = []
        for msg in messages:
            results.append(await self.send(msg))
        return results

    @abstractmethod
    async def verify_config(self) -> bool:
        """Test the connection / credentials. Returns True on success."""


# ---------------------------------------------------------------------------
# SMTP Sender (aiosmtplib)
# ---------------------------------------------------------------------------


class SmtpSender(BaseSender):
    """Send emails via SMTP using aiosmtplib for async I/O."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        """Build a multipart MIME message with HTML and optional plain text."""
        mime = MIMEMultipart("alternative")
        mime["From"] = (
            f"{message.from_name} <{message.from_email}>"
            if message.from_name
            else message.from_email
        )
        mime["To"] = (
            f"{message.to_name} <{message.to_email}>"
            if message.to_name
            else message.to_email
        )
        mime["Subject"] = message.subject

        if message.reply_to:
            mime["Reply-To"] = message.reply_to

        # List-Unsubscribe header (RFC 2369) for mailbox providers
        if message.campaign_id and message.contact_id:
            from app.email.tracking import generate_unsubscribe_url

            unsub_url = generate_unsubscribe_url(
                contact_id=message.contact_id,
                campaign_id=message.campaign_id,
            )
            mime["List-Unsubscribe"] = f"<{unsub_url}>"
            mime["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Custom headers
        for key, value in message.headers.items():
            mime[key] = value

        # Attach plain text first (lower priority), then HTML
        if message.text_content:
            mime.attach(MIMEText(message.text_content, "plain", "utf-8"))
        mime.attach(MIMEText(message.html_content, "html", "utf-8"))

        return mime

    async def send(self, message: EmailMessage) -> SendResult:
        """Connect, send one message, disconnect."""
        try:
            import aiosmtplib

            mime = self._build_mime(message)
            response = await aiosmtplib.send(
                mime,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
            # aiosmtplib.send returns a tuple of (response_dict, message_str)
            logger.info(
                "smtp_email_sent",
                to=message.to_email,
                subject=message.subject,
                campaign_id=message.campaign_id,
            )
            return SendResult(success=True, message_id=str(response))
        except Exception as e:
            logger.error(
                "smtp_send_failed",
                to=message.to_email,
                error=str(e),
                campaign_id=message.campaign_id,
            )
            return SendResult(success=False, error=str(e))

    async def send_batch(self, messages: list[EmailMessage]) -> list[SendResult]:
        """Connect once, send all messages, disconnect."""
        if not messages:
            return []

        results: list[SendResult] = []
        try:
            import aiosmtplib

            smtp = aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                start_tls=self.use_tls,
            )
            await smtp.connect()
            await smtp.login(self.username, self.password)

            for message in messages:
                try:
                    mime = self._build_mime(message)
                    response = await smtp.send_message(mime)
                    logger.info(
                        "smtp_email_sent",
                        to=message.to_email,
                        subject=message.subject,
                        campaign_id=message.campaign_id,
                    )
                    results.append(SendResult(success=True, message_id=str(response)))
                except Exception as e:
                    logger.error(
                        "smtp_send_failed",
                        to=message.to_email,
                        error=str(e),
                        campaign_id=message.campaign_id,
                    )
                    results.append(SendResult(success=False, error=str(e)))

            await smtp.quit()
        except Exception as e:
            # Connection-level failure -- mark remaining messages as failed
            logger.error("smtp_batch_connection_failed", error=str(e))
            while len(results) < len(messages):
                results.append(SendResult(success=False, error=f"Connection failed: {e}"))

        return results

    async def verify_config(self) -> bool:
        """Try to connect and AUTH against the SMTP server."""
        try:
            import aiosmtplib

            smtp = aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                start_tls=self.use_tls,
            )
            await smtp.connect()
            await smtp.login(self.username, self.password)
            await smtp.quit()
            logger.info("smtp_verify_ok", host=self.host, port=self.port)
            return True
        except Exception as e:
            logger.error("smtp_verify_failed", host=self.host, error=str(e))
            return False


# ---------------------------------------------------------------------------
# SendGrid Sender (httpx REST API)
# ---------------------------------------------------------------------------


class SendGridSender(BaseSender):
    """Send emails via the SendGrid v3 REST API."""

    BASE_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _build_payload(self, message: EmailMessage) -> dict:
        """Build the SendGrid v3 API payload."""
        to_entry: dict = {"email": message.to_email}
        if message.to_name:
            to_entry["name"] = message.to_name

        from_entry: dict = {"email": message.from_email}
        if message.from_name:
            from_entry["name"] = message.from_name

        payload: dict = {
            "personalizations": [{"to": [to_entry]}],
            "from": from_entry,
            "subject": message.subject,
            "content": [],
        }

        # Content -- plain text first (lower priority), then HTML
        if message.text_content:
            payload["content"].append(
                {"type": "text/plain", "value": message.text_content}
            )
        payload["content"].append(
            {"type": "text/html", "value": message.html_content}
        )

        if message.reply_to:
            payload["reply_to"] = {"email": message.reply_to}

        # Categories / tags
        if message.tags:
            payload["categories"] = message.tags[:10]  # SendGrid caps at 10

        # Custom headers
        if message.headers:
            payload["headers"] = message.headers

        # List-Unsubscribe
        if message.campaign_id and message.contact_id:
            from app.email.tracking import generate_unsubscribe_url

            unsub_url = generate_unsubscribe_url(
                contact_id=message.contact_id,
                campaign_id=message.campaign_id,
            )
            payload.setdefault("headers", {})
            payload["headers"]["List-Unsubscribe"] = f"<{unsub_url}>"
            payload["headers"]["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Tracking settings -- disable SendGrid's own tracking since we do our own
        payload["tracking_settings"] = {
            "click_tracking": {"enable": False},
            "open_tracking": {"enable": False},
        }

        # Custom args for webhook correlation
        if message.metadata:
            payload["personalizations"][0]["custom_args"] = {
                k: str(v) for k, v in message.metadata.items()
            }

        return payload

    async def send(self, message: EmailMessage) -> SendResult:
        """POST a single email to the SendGrid API."""
        try:
            payload = self._build_payload(message)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.BASE_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )

            if resp.status_code in (200, 201, 202):
                message_id = resp.headers.get("X-Message-Id", "")
                logger.info(
                    "sendgrid_email_sent",
                    to=message.to_email,
                    subject=message.subject,
                    message_id=message_id,
                    campaign_id=message.campaign_id,
                )
                return SendResult(success=True, message_id=message_id)
            else:
                body = resp.text[:500]
                logger.error(
                    "sendgrid_send_failed",
                    to=message.to_email,
                    status=resp.status_code,
                    body=body,
                    campaign_id=message.campaign_id,
                )
                return SendResult(
                    success=False,
                    error=f"SendGrid API {resp.status_code}: {body}",
                )
        except Exception as e:
            logger.error(
                "sendgrid_send_exception",
                to=message.to_email,
                error=str(e),
                campaign_id=message.campaign_id,
            )
            return SendResult(success=False, error=str(e))

    async def verify_config(self) -> bool:
        """Validate the API key by calling the SendGrid scopes endpoint."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.sendgrid.com/v3/scopes",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            ok = resp.status_code == 200
            if ok:
                logger.info("sendgrid_verify_ok")
            else:
                logger.error("sendgrid_verify_failed", status=resp.status_code)
            return ok
        except Exception as e:
            logger.error("sendgrid_verify_exception", error=str(e))
            return False


# ---------------------------------------------------------------------------
# AWS SES Sender (boto3)
# ---------------------------------------------------------------------------


class SesSender(BaseSender):
    """
    Send emails via AWS SES using boto3.

    Requires the ``boto3`` package to be installed. SES is optional, so boto3
    is not listed as a hard dependency -- install it with:
        pip install boto3
    """

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        region: str = "us-east-1",
    ) -> None:
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region
        self._client = None

    def _get_client(self):
        """Lazily initialise the boto3 SES client."""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for the SES sender. "
                    "Install it with: pip install boto3"
                )
            self._client = boto3.client(
                "sesv2",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
        return self._client

    async def send(self, message: EmailMessage) -> SendResult:
        """Send a single email via SES v2 SendEmail API."""
        try:
            import asyncio

            client = self._get_client()

            from_addr = (
                f"{message.from_name} <{message.from_email}>"
                if message.from_name
                else message.from_email
            )

            body: dict = {
                "Html": {"Data": message.html_content, "Charset": "UTF-8"},
            }
            if message.text_content:
                body["Text"] = {"Data": message.text_content, "Charset": "UTF-8"}

            email_content: dict = {
                "Simple": {
                    "Subject": {
                        "Data": message.subject,
                        "Charset": "UTF-8",
                    },
                    "Body": body,
                }
            }

            destination: dict = {
                "ToAddresses": [message.to_email],
            }

            kwargs: dict = {
                "FromEmailAddress": from_addr,
                "Destination": destination,
                "Content": email_content,
            }

            if message.reply_to:
                kwargs["ReplyToAddresses"] = [message.reply_to]

            # Add List-Unsubscribe header
            headers = []
            if message.campaign_id and message.contact_id:
                from app.email.tracking import generate_unsubscribe_url

                unsub_url = generate_unsubscribe_url(
                    contact_id=message.contact_id,
                    campaign_id=message.campaign_id,
                )
                headers.append({"Name": "List-Unsubscribe", "Value": f"<{unsub_url}>"})
                headers.append(
                    {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"}
                )

            for key, value in message.headers.items():
                headers.append({"Name": key, "Value": value})

            if headers:
                kwargs["Content"]["Simple"]["Headers"] = headers

            if message.tags:
                kwargs["EmailTags"] = [
                    {"Name": "tag", "Value": tag} for tag in message.tags[:50]
                ]

            # boto3 is synchronous -- run in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: client.send_email(**kwargs)
            )

            message_id = response.get("MessageId", "")
            logger.info(
                "ses_email_sent",
                to=message.to_email,
                subject=message.subject,
                message_id=message_id,
                campaign_id=message.campaign_id,
            )
            return SendResult(success=True, message_id=message_id)

        except Exception as e:
            logger.error(
                "ses_send_failed",
                to=message.to_email,
                error=str(e),
                campaign_id=message.campaign_id,
            )
            return SendResult(success=False, error=str(e))

    async def verify_config(self) -> bool:
        """Verify credentials by calling GetAccount."""
        try:
            import asyncio

            client = self._get_client()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, client.get_account)
            logger.info("ses_verify_ok", region=self.region)
            return True
        except Exception as e:
            logger.error("ses_verify_failed", error=str(e))
            return False


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _build_sender_from_row(row: dict) -> BaseSender | None:
    """Instantiate the correct sender class from a DB config row."""
    sender_type = row.get("sender_type")
    config = row.get("config") or {}

    try:
        if sender_type == "smtp":
            return SmtpSender(
                host=config["host"],
                port=int(config.get("port", 587)),
                username=config["username"],
                password=config["password"],
                use_tls=config.get("use_tls", True),
            )
        elif sender_type == "sendgrid":
            return SendGridSender(api_key=config["api_key"])
        elif sender_type == "ses":
            return SesSender(
                access_key_id=config["access_key_id"],
                secret_access_key=config["secret_access_key"],
                region=config.get("region", "us-east-1"),
            )
        else:
            logger.error("unknown_sender_type", sender_type=sender_type)
            return None
    except KeyError as e:
        logger.error(
            "sender_config_missing_field",
            sender_type=sender_type,
            missing=str(e),
        )
        return None


async def get_default_sender() -> BaseSender | None:
    """
    Load the default sender configuration from the ``email_sender_config``
    table. Result is cached for 2 minutes.

    Returns None if no default sender is configured.
    """
    cached = _cache_get("__default__")
    if cached is not None:
        return cached

    try:
        from app.database import get_service_client

        db = get_service_client()
        result = (
            db.table("email_sender_config")
            .select("*")
            .eq("is_default", True)
            .maybe_single()
            .execute()
        )
        if not result.data:
            logger.warning("no_default_email_sender_configured")
            return None

        sender = _build_sender_from_row(result.data)
        if sender is not None:
            _cache_set("__default__", sender)
        return sender

    except Exception as e:
        logger.error("get_default_sender_failed", error=str(e))
        return None


async def get_sender(config_id: str) -> BaseSender | None:
    """
    Load a specific sender configuration by its UUID.
    Result is cached for 2 minutes.
    """
    cached = _cache_get(config_id)
    if cached is not None:
        return cached

    try:
        from app.database import get_service_client

        db = get_service_client()
        result = (
            db.table("email_sender_config")
            .select("*")
            .eq("id", config_id)
            .maybe_single()
            .execute()
        )
        if not result.data:
            logger.warning("email_sender_config_not_found", config_id=config_id)
            return None

        sender = _build_sender_from_row(result.data)
        if sender is not None:
            _cache_set(config_id, sender)
        return sender

    except Exception as e:
        logger.error("get_sender_failed", config_id=config_id, error=str(e))
        return None
