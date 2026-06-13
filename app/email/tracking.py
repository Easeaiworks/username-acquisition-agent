"""
Email tracking -- open pixels, click wrapping, unsubscribe management.

Provides functions to:
    - Generate tracking pixel URLs for open detection
    - Wrap links for click tracking
    - Create secure one-click unsubscribe tokens and URLs
    - Inject all of the above into raw HTML email content
"""

from __future__ import annotations

import base64
import re
import secrets
from typing import Optional
from urllib.parse import quote, urlencode

import structlog

logger = structlog.get_logger()


def _get_base_url() -> str:
    """Resolve the app's public base URL for tracking links."""
    try:
        from app.config import settings
        return settings.app_url or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------


def encode_tracking_id(campaign_id: str, contact_id: str) -> str:
    """Base64-url encode a campaign_id:contact_id pair."""
    raw = f"{campaign_id}:{contact_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_tracking_id(encoded: str) -> tuple[str, str]:
    """
    Decode a base64-url encoded tracking ID back to (campaign_id, contact_id).

    Raises ValueError if the encoded value is malformed.
    """
    # Re-add padding
    padded = encoded + "=" * (4 - len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Invalid tracking ID: {e}") from e

    parts = raw.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Malformed tracking ID: expected 'campaign:contact', got '{raw}'")

    return parts[0], parts[1]


# ---------------------------------------------------------------------------
# URL generators
# ---------------------------------------------------------------------------


def generate_tracking_pixel_url(campaign_id: str, contact_id: str) -> str:
    """
    Generate the URL for a 1x1 tracking pixel image.

    Format: {base_url}/t/open/{encoded_id}.gif
    """
    encoded = encode_tracking_id(campaign_id, contact_id)
    base = _get_base_url()
    return f"{base}/t/open/{encoded}.gif"


def generate_click_url(
    campaign_id: str,
    contact_id: str,
    original_url: str,
) -> str:
    """
    Generate a click-tracking redirect URL.

    Format: {base_url}/t/click/{encoded_id}?url={encoded_original}
    """
    encoded = encode_tracking_id(campaign_id, contact_id)
    base = _get_base_url()
    params = urlencode({"url": original_url})
    return f"{base}/t/click/{encoded}?{params}"


def generate_unsubscribe_url(
    contact_id: str,
    campaign_id: str,
) -> str:
    """
    Create a secure unsubscribe token in the database and return its URL.

    Each call creates a new single-use token so that tokens cannot be
    guessed or replayed.

    Format: {base_url}/t/unsubscribe/{token}
    """
    token = secrets.token_urlsafe(32)

    try:
        from app.database import get_service_client

        db = get_service_client()
        db.table("email_unsubscribe_tokens").insert({
            "contact_id": contact_id,
            "campaign_id": campaign_id,
            "token": token,
        }).execute()
    except Exception as e:
        logger.error(
            "unsubscribe_token_create_failed",
            contact_id=contact_id,
            campaign_id=campaign_id,
            error=str(e),
        )
        # Still return the URL so the email can be sent; the token simply
        # won't resolve when clicked, which is safer than blocking the send.

    base = _get_base_url()
    return f"{base}/t/unsubscribe/{token}"


# ---------------------------------------------------------------------------
# HTML injection
# ---------------------------------------------------------------------------

# Regex to find <a href="..."> (captures the URL in group 1)
_LINK_PATTERN = re.compile(
    r'(<a\s[^>]*?href=")([^"]+)(")',
    re.IGNORECASE,
)


def inject_tracking(
    html: str,
    campaign_id: str,
    contact_id: str,
) -> str:
    """
    Inject tracking elements into an HTML email body.

    1. Wrap all ``<a href="...">`` links with click-tracking redirect URLs
       (skips mailto: links and anchors starting with #).
    2. Insert a 1x1 open-tracking pixel before ``</body>`` (or at the end).
    3. Replace ``{{unsubscribe_url}}`` placeholder with a real unsubscribe link.

    Returns the modified HTML string.
    """
    # --- 1. Click-wrap links -----------------------------------------------
    def _wrap_link(match: re.Match) -> str:
        prefix = match.group(1)   # '<a ... href="'
        url = match.group(2)      # the original URL
        suffix = match.group(3)   # '"'

        # Don't track mailto links, anchor links, or already-tracked links
        if url.startswith(("mailto:", "#", "{{")) or "/t/click/" in url:
            return match.group(0)

        tracked = generate_click_url(campaign_id, contact_id, url)
        return f"{prefix}{tracked}{suffix}"

    html = _LINK_PATTERN.sub(_wrap_link, html)

    # --- 2. Open-tracking pixel --------------------------------------------
    pixel_url = generate_tracking_pixel_url(campaign_id, contact_id)
    pixel_tag = (
        f'<img src="{pixel_url}" width="1" height="1" '
        f'alt="" style="display:none;border:0;" />'
    )

    if "</body>" in html.lower():
        # Insert before closing body tag (case-insensitive)
        idx = html.lower().rfind("</body>")
        html = html[:idx] + pixel_tag + html[idx:]
    else:
        html += pixel_tag

    # --- 3. Unsubscribe URL placeholder ------------------------------------
    if "{{unsubscribe_url}}" in html:
        unsub_url = generate_unsubscribe_url(
            contact_id=contact_id,
            campaign_id=campaign_id,
        )
        html = html.replace("{{unsubscribe_url}}", unsub_url)

    return html
