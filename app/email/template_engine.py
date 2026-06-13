"""
Email template engine -- variable substitution and content processing.

A lightweight, dependency-free template engine that replaces ``{{variable_name}}``
placeholders with values from a context dictionary. Supports dot-notation for
nested access (e.g. ``{{contact.first_name}}``).

No Jinja2 required.

Usage:
    from app.email.template_engine import render_template, get_default_variables

    variables = get_default_variables(contact=contact_row)
    html = render_template(campaign_html, variables)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

# Matches {{variable_name}} or {{contact.first_name}} style placeholders.
# Allows alphanumerics, underscores, and dots inside the braces.
_VAR_PATTERN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _resolve(path: str, variables: dict) -> str:
    """
    Resolve a dot-separated path against a nested dict.

    Examples:
        _resolve("contact.first_name", {"contact": {"first_name": "Jane"}})
        -> "Jane"

        _resolve("current_year", {"current_year": "2026"})
        -> "2026"

    Returns an empty string if the path cannot be resolved.
    """
    parts = path.split(".")
    current: Any = variables

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return ""
        if current is None:
            return ""

    return str(current)


def render_template(html: str, variables: dict) -> str:
    """
    Replace all ``{{variable_name}}`` placeholders in *html* with values
    from *variables*.

    Supports nested access via dot-notation: ``{{contact.first_name}}`` will
    look up ``variables["contact"]["first_name"]``.

    Unresolved placeholders are replaced with an empty string.
    """
    def _replacer(match: re.Match) -> str:
        path = match.group(1)
        return _resolve(path, variables)

    return _VAR_PATTERN.sub(_replacer, html)


# ---------------------------------------------------------------------------
# Default variable builder
# ---------------------------------------------------------------------------


def get_default_variables(
    contact: dict,
    campaign: Optional[dict] = None,
) -> dict:
    """
    Build the standard variable dictionary for template rendering.

    Provides the following namespaces:

    - ``contact.email``, ``contact.first_name``, ``contact.last_name``,
      ``contact.company``
    - ``campaign.name`` (if a campaign dict is provided)
    - ``unsubscribe_url`` -- placeholder; the actual URL is injected later
      by ``tracking.inject_tracking``.
    - ``current_date`` (YYYY-MM-DD), ``current_year``
    """
    now = datetime.now(timezone.utc)

    variables: dict = {
        "contact": {
            "email": contact.get("email", ""),
            "first_name": contact.get("first_name", ""),
            "last_name": contact.get("last_name", ""),
            "company": contact.get("company", ""),
        },
        "unsubscribe_url": "{{unsubscribe_url}}",  # replaced by tracking.inject_tracking
        "current_date": now.strftime("%Y-%m-%d"),
        "current_year": str(now.year),
    }

    if campaign:
        variables["campaign"] = {
            "name": campaign.get("name", ""),
        }

    return variables


# ---------------------------------------------------------------------------
# HTML to plain text
# ---------------------------------------------------------------------------

# Common block-level tags that should produce a newline break
_BLOCK_TAGS = re.compile(
    r"<\s*/?\s*(br|p|div|h[1-6]|li|tr|blockquote|hr)\b[^>]*>",
    re.IGNORECASE,
)

# All remaining HTML tags
_ALL_TAGS = re.compile(r"<[^>]+>")

# Runs of 3+ newlines collapsed to 2
_EXCESS_NEWLINES = re.compile(r"\n{3,}")

# Runs of 2+ spaces collapsed to 1
_EXCESS_SPACES = re.compile(r"[ \t]{2,}")


def strip_html(html: str) -> str:
    """
    Convert HTML to plain text suitable for the ``text/plain`` MIME part.

    - Replaces block-level tags (``<p>``, ``<br>``, ``<div>``, headings, ``<li>``)
      with newlines.
    - Strips all remaining tags.
    - Decodes HTML entities (``&amp;`` -> ``&``).
    - Collapses excessive whitespace.
    """
    # Replace block-level elements with newlines
    text = _BLOCK_TAGS.sub("\n", html)

    # Strip remaining tags
    text = _ALL_TAGS.sub("", text)

    # Decode HTML entities
    text = unescape(text)

    # Collapse whitespace
    text = _EXCESS_SPACES.sub(" ", text)
    text = _EXCESS_NEWLINES.sub("\n\n", text)

    return text.strip()
