"""
Twitch Helix API integration — username lookup.

Twitch uses login names (lowercase usernames) as the primary handle.
The Helix API provides direct user lookup by login name.

Authentication: Client Credentials OAuth flow (app-level, no user auth needed).

Rate limits:
- 30 requests/minute per token (token bucket)
- Rate limit headers: Ratelimit-Limit, Ratelimit-Remaining, Ratelimit-Reset
"""

import httpx
from typing import Optional
from datetime import datetime, timezone

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

HELIX_URL = "https://api.twitch.tv/helix"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"

# Module-level token cache
_access_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None


async def _get_access_token() -> Optional[str]:
    """Get or refresh the Twitch app access token via Client Credentials flow."""
    global _access_token, _token_expires_at

    if not settings.twitch_client_id or not settings.twitch_client_secret:
        logger.warning("twitch_credentials_not_configured")
        return None

    # Return cached token if still valid
    if _access_token and _token_expires_at and datetime.now(timezone.utc) < _token_expires_at:
        return _access_token

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                params={
                    "client_id": settings.twitch_client_id,
                    "client_secret": settings.twitch_client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=15.0,
            )

            if resp.status_code == 200:
                data = resp.json()
                _access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                _token_expires_at = datetime.now(timezone.utc).replace(
                    second=0, microsecond=0
                )
                # Refresh 5 minutes before expiry
                from datetime import timedelta
                _token_expires_at += timedelta(seconds=expires_in - 300)

                logger.info("twitch_token_acquired", expires_in=expires_in)
                return _access_token
            else:
                logger.error("twitch_token_error", status=resp.status_code, body=resp.text[:200])
                return None

    except Exception as e:
        logger.error("twitch_token_exception", error=str(e))
        return None


async def lookup_user_by_login(login_name: str) -> Optional[dict]:
    """
    Look up a Twitch user by their login name (handle).

    Args:
        login_name: The Twitch username/login (e.g., "stripe")

    Returns:
        User data dict or None if not found
    """
    token = await _get_access_token()
    if not token:
        return None

    clean_login = login_name.lower().lstrip("@")

    await rate_limiter.acquire("twitch")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HELIX_URL}/users",
                params={"login": clean_login},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Client-Id": settings.twitch_client_id,
                },
                timeout=15.0,
            )

            rate_limiter.track_daily_usage("twitch", 1)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    user = data["data"][0]
                    return _parse_user_data(user)
                else:
                    # User not found = handle potentially available
                    return None

            elif resp.status_code == 401:
                # Token expired, clear cache and retry once
                global _access_token
                _access_token = None
                logger.warning("twitch_token_expired_retrying")
                return await lookup_user_by_login(login_name)

            elif resp.status_code == 429:
                logger.warning("twitch_rate_limited")
                return None
            else:
                logger.warning("twitch_api_error", status=resp.status_code, body=resp.text[:200])

    except httpx.TimeoutException:
        logger.warning("twitch_timeout", login=clean_login)
    except Exception as e:
        logger.error("twitch_error", login=clean_login, error=str(e))

    return None


async def get_channel_last_stream(user_id: str) -> Optional[dict]:
    """
    Get the most recent stream/video for a Twitch user.
    Used to determine account dormancy.

    Args:
        user_id: Twitch user ID

    Returns:
        Last stream info dict or None
    """
    token = await _get_access_token()
    if not token:
        return None

    await rate_limiter.acquire("twitch")

    try:
        async with httpx.AsyncClient() as client:
            # Check recent videos (VODs, highlights, uploads)
            resp = await client.get(
                f"{HELIX_URL}/videos",
                params={
                    "user_id": user_id,
                    "first": 1,
                    "sort": "time",
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Client-Id": settings.twitch_client_id,
                },
                timeout=15.0,
            )

            rate_limiter.track_daily_usage("twitch", 1)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    video = data["data"][0]
                    return {
                        "last_video_date": video.get("published_at") or video.get("created_at"),
                        "last_video_title": video.get("title"),
                        "last_video_type": video.get("type"),
                    }

    except Exception as e:
        logger.error("twitch_videos_error", user_id=user_id, error=str(e))

    return None


async def check_handle_availability(handle: str) -> dict:
    """
    Check if a Twitch handle is available or taken.

    Returns:
        {
            "handle": str,
            "available": bool,
            "user_data": dict or None (if taken),
            "platform": "twitch"
        }
    """
    user = await lookup_user_by_login(handle)

    if user:
        # Optionally check last stream for dormancy
        last_stream = await get_channel_last_stream(user["user_id"])
        if last_stream:
            user["last_post_date"] = last_stream["last_video_date"]

        return {
            "handle": handle,
            "available": False,
            "user_data": user,
            "platform": "twitch",
        }
    else:
        return {
            "handle": handle,
            "available": True,
            "user_data": None,
            "platform": "twitch",
        }


def _parse_user_data(user: dict) -> dict:
    """Parse Twitch Helix user response into our standard format."""
    created_at = user.get("created_at")

    return {
        "platform": "twitch",
        "user_id": user.get("id"),
        "handle": user.get("login"),
        "display_name": user.get("display_name", ""),
        "description": user.get("description", "")[:500],
        "broadcaster_type": user.get("broadcaster_type", ""),  # partner, affiliate, or ""
        "account_type": user.get("type", ""),

        # Activity metrics
        "view_count": user.get("view_count", 0),
        "created_at": created_at,

        # Dormancy signals (will be enriched with last_stream data)
        "last_post_date": None,
        "account_dormant": False,
        "follower_count": None,  # Requires separate API call
        "post_count": None,

        "raw_response": user,
    }
