"""
YouTube Data API v3 integration — handle and channel lookup.

YouTube handles (@username) and channel names are distinct:
- Handle: unique @identifier (e.g., @stripe)
- Channel name: display name (e.g., "Stripe")
- Channel ID: internal ID (e.g., UCxxxxxxx)

We check both the handle and channel name for brand matching.

Rate limits:
- 10,000 quota units/day (free tier)
- Channel list by forUsername: 1 unit
- Search: 100 units (avoid unless necessary)
- Channel list by ID: 1 unit

Strategy: Use channels.list with forHandle first (1 unit), fall back to search only if needed.
"""

import httpx
from typing import Optional
from datetime import datetime, timezone

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

BASE_URL = "https://www.googleapis.com/youtube/v3"


async def lookup_channel_by_handle(handle: str) -> Optional[dict]:
    """
    Look up a YouTube channel by its @handle.

    Args:
        handle: The handle to search for (with or without @)

    Returns:
        Channel data dict or None if not found
    """
    if not settings.youtube_api_key:
        logger.warning("youtube_api_key_not_configured")
        return None

    clean_handle = handle.lstrip("@").lower()

    # Check daily limit
    if not rate_limiter.check_daily_limit("youtube", settings.max_youtube_calls_per_day):
        return None

    await rate_limiter.acquire("youtube")

    try:
        async with httpx.AsyncClient() as client:
            # Try forHandle parameter (costs 1 quota unit)
            resp = await client.get(
                f"{BASE_URL}/channels",
                params={
                    "part": "snippet,statistics,brandingSettings",
                    "forHandle": clean_handle,
                    "key": settings.youtube_api_key,
                },
                timeout=15.0,
            )

            rate_limiter.track_daily_usage("youtube", 1)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("items"):
                    channel = data["items"][0]
                    return _parse_channel_data(channel, clean_handle)

            elif resp.status_code == 403:
                logger.error("youtube_quota_exceeded", status=resp.status_code)
                return None
            else:
                logger.warning("youtube_api_error", status=resp.status_code, body=resp.text[:200])

    except httpx.TimeoutException:
        logger.warning("youtube_timeout", handle=clean_handle)
    except Exception as e:
        logger.error("youtube_error", handle=clean_handle, error=str(e))

    return None


async def search_channel_by_name(brand_name: str) -> Optional[dict]:
    """
    Search YouTube for a channel matching a brand name.
    EXPENSIVE: costs 100 quota units. Use sparingly.

    Args:
        brand_name: The brand name to search for

    Returns:
        Best matching channel data dict or None
    """
    if not settings.youtube_api_key:
        return None

    # This costs 100 units — only use if we have budget
    if not rate_limiter.check_daily_limit("youtube", settings.max_youtube_calls_per_day - 100):
        logger.warning("youtube_budget_too_low_for_search")
        return None

    await rate_limiter.acquire("youtube")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/search",
                params={
                    "part": "snippet",
                    "q": brand_name,
                    "type": "channel",
                    "maxResults": 3,
                    "key": settings.youtube_api_key,
                },
                timeout=15.0,
            )

            rate_limiter.track_daily_usage("youtube", 100)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("items"):
                    # Get full channel data for best match
                    channel_id = data["items"][0]["snippet"]["channelId"]
                    return await _get_channel_by_id(channel_id)

    except Exception as e:
        logger.error("youtube_search_error", brand=brand_name, error=str(e))

    return None


async def _get_channel_by_id(channel_id: str) -> Optional[dict]:
    """Get full channel data by ID (1 quota unit)."""
    await rate_limiter.acquire("youtube")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/channels",
                params={
                    "part": "snippet,statistics,brandingSettings",
                    "id": channel_id,
                    "key": settings.youtube_api_key,
                },
                timeout=15.0,
            )

            rate_limiter.track_daily_usage("youtube", 1)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("items"):
                    return _parse_channel_data(data["items"][0])

    except Exception as e:
        logger.error("youtube_channel_by_id_error", id=channel_id, error=str(e))

    return None


async def check_handle_availability(handle: str) -> dict:
    """
    Check if a YouTube handle is available or taken.

    Returns:
        {
            "handle": str,
            "available": bool,
            "channel_data": dict or None (if taken),
            "platform": "youtube"
        }
    """
    channel = await lookup_channel_by_handle(handle)

    if channel:
        return {
            "handle": handle,
            "available": False,
            "channel_data": channel,
            "platform": "youtube",
        }
    else:
        return {
            "handle": handle,
            "available": True,
            "channel_data": None,
            "platform": "youtube",
        }


def _parse_channel_data(channel: dict, queried_handle: str = None) -> dict:
    """Parse YouTube API channel response into our standard format."""
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})
    branding = channel.get("brandingSettings", {}).get("channel", {})

    # Extract the custom handle if present
    custom_url = snippet.get("customUrl", "")
    handle = custom_url.lstrip("@") if custom_url else None

    # Determine last activity from snippet
    published_at = snippet.get("publishedAt")

    # Calculate dormancy signals
    video_count = int(stats.get("videoCount", 0))
    subscriber_count = int(stats.get("subscriberCount", 0))
    view_count = int(stats.get("viewCount", 0))

    return {
        "platform": "youtube",
        "channel_id": channel.get("id"),
        "handle": handle,
        "display_name": snippet.get("title", ""),
        "description": snippet.get("description", "")[:500],
        "custom_url": custom_url,
        "country": snippet.get("country"),

        # Activity metrics
        "subscriber_count": subscriber_count,
        "video_count": video_count,
        "view_count": view_count,
        "published_at": published_at,

        # These will be populated by additional analysis
        "last_post_date": None,  # Would need playlist API for actual last upload
        "account_dormant": video_count <= 5 and subscriber_count < 100,
        "follower_count": subscriber_count,
        "post_count": video_count,

        "raw_response": channel,
    }
