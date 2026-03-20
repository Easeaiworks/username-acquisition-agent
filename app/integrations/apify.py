"""
Apify integration — Instagram and TikTok handle scanning.

Instagram and TikTok have no official APIs for public profile/handle lookup.
We use Apify actors (serverless scrapers) that return clean JSON.

Apify actors used:
- Instagram: "apify/instagram-profile-scraper" (or similar)
- TikTok: "clockworks/tiktok-profile-scraper" (or similar)

Rate limits:
- Apify concurrent actor runs: configurable (default 3)
- Pay-per-use pricing based on compute units

The actor IDs are configurable via environment to swap in better actors
as the Apify marketplace evolves.
"""

import httpx
import asyncio
from typing import Optional
from datetime import datetime, timezone

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

APIFY_BASE_URL = "https://api.apify.com/v2"

# Default actor IDs — can be overridden via env vars
INSTAGRAM_ACTOR_ID = "apify~instagram-profile-scraper"
TIKTOK_ACTOR_ID = "clockworks~tiktok-profile-scraper"


async def _run_actor(actor_id: str, input_data: dict, timeout_secs: int = 120) -> Optional[dict]:
    """
    Run an Apify actor and wait for results.

    Args:
        actor_id: The Apify actor identifier
        input_data: Input JSON for the actor
        timeout_secs: Max seconds to wait for completion

    Returns:
        Actor run results or None on failure
    """
    if not settings.apify_api_token:
        logger.warning("apify_api_token_not_configured")
        return None

    await rate_limiter.acquire("apify")

    try:
        async with httpx.AsyncClient() as client:
            # Start the actor run
            resp = await client.post(
                f"{APIFY_BASE_URL}/acts/{actor_id}/runs",
                params={"token": settings.apify_api_token},
                json=input_data,
                timeout=30.0,
            )

            if resp.status_code not in (200, 201):
                logger.error("apify_start_error", actor=actor_id, status=resp.status_code, body=resp.text[:300])
                return None

            run_data = resp.json().get("data", {})
            run_id = run_data.get("id")

            if not run_id:
                logger.error("apify_no_run_id", actor=actor_id)
                return None

            logger.info("apify_run_started", actor=actor_id, run_id=run_id)

            # Poll for completion
            elapsed = 0
            poll_interval = 5
            while elapsed < timeout_secs:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                status_resp = await client.get(
                    f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                    params={"token": settings.apify_api_token},
                    timeout=15.0,
                )

                if status_resp.status_code == 200:
                    status_data = status_resp.json().get("data", {})
                    status = status_data.get("status")

                    if status == "SUCCEEDED":
                        # Fetch results from dataset
                        dataset_id = status_data.get("defaultDatasetId")
                        if dataset_id:
                            return await _get_dataset_items(dataset_id)
                        return None

                    elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                        logger.error("apify_run_failed", actor=actor_id, run_id=run_id, status=status)
                        return None

                    # Still running — continue polling

            logger.warning("apify_run_timeout", actor=actor_id, run_id=run_id, timeout=timeout_secs)
            return None

    except Exception as e:
        logger.error("apify_error", actor=actor_id, error=str(e))
        return None


async def _get_dataset_items(dataset_id: str) -> Optional[list]:
    """Fetch results from an Apify dataset."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
                params={
                    "token": settings.apify_api_token,
                    "format": "json",
                    "limit": 10,
                },
                timeout=15.0,
            )

            if resp.status_code == 200:
                return resp.json()

    except Exception as e:
        logger.error("apify_dataset_error", dataset_id=dataset_id, error=str(e))

    return None


async def lookup_instagram_profile(username: str) -> Optional[dict]:
    """
    Look up an Instagram profile by username.

    Args:
        username: Instagram handle (without @)

    Returns:
        Profile data dict or None
    """
    clean_username = username.lower().lstrip("@")

    results = await _run_actor(
        INSTAGRAM_ACTOR_ID,
        {
            "usernames": [clean_username],
            "resultsLimit": 1,
        },
        timeout_secs=90,
    )

    if results and len(results) > 0:
        profile = results[0]
        return _parse_instagram_profile(profile, clean_username)

    return None


async def lookup_tiktok_profile(username: str) -> Optional[dict]:
    """
    Look up a TikTok profile by username.

    Args:
        username: TikTok handle (without @)

    Returns:
        Profile data dict or None
    """
    clean_username = username.lower().lstrip("@")

    results = await _run_actor(
        TIKTOK_ACTOR_ID,
        {
            "profiles": [clean_username],
            "resultsPerPage": 1,
        },
        timeout_secs=90,
    )

    if results and len(results) > 0:
        profile = results[0]
        return _parse_tiktok_profile(profile, clean_username)

    return None


async def check_instagram_handle(handle: str) -> dict:
    """
    Check if an Instagram handle is taken or available.

    Returns standard handle check result.
    """
    profile = await lookup_instagram_profile(handle)

    if profile:
        return {
            "handle": handle,
            "available": False,
            "profile_data": profile,
            "platform": "instagram",
        }
    else:
        return {
            "handle": handle,
            "available": True,
            "profile_data": None,
            "platform": "instagram",
        }


async def check_tiktok_handle(handle: str) -> dict:
    """
    Check if a TikTok handle is taken or available.

    Returns standard handle check result.
    """
    profile = await lookup_tiktok_profile(handle)

    if profile:
        return {
            "handle": handle,
            "available": False,
            "profile_data": profile,
            "platform": "tiktok",
        }
    else:
        return {
            "handle": handle,
            "available": True,
            "profile_data": None,
            "platform": "tiktok",
        }


def _parse_instagram_profile(profile: dict, queried_username: str) -> dict:
    """Parse Apify Instagram profile response into our standard format."""
    # Apify actor responses vary by actor — handle common formats
    username = profile.get("username") or profile.get("userName") or queried_username
    followers = profile.get("followersCount") or profile.get("followers") or 0
    following = profile.get("followingCount") or profile.get("following") or 0
    posts = profile.get("postsCount") or profile.get("posts") or profile.get("mediaCount") or 0

    # Try to extract last post date
    last_post_date = None
    latest_posts = profile.get("latestPosts") or profile.get("recentPosts") or []
    if latest_posts and len(latest_posts) > 0:
        last_post_date = (
            latest_posts[0].get("timestamp")
            or latest_posts[0].get("takenAt")
            or latest_posts[0].get("date")
        )

    # Determine dormancy
    account_dormant = False
    dormancy_months = None
    if last_post_date:
        try:
            if isinstance(last_post_date, str):
                last_dt = datetime.fromisoformat(last_post_date.replace("Z", "+00:00"))
            elif isinstance(last_post_date, (int, float)):
                last_dt = datetime.fromtimestamp(last_post_date, tz=timezone.utc)
            else:
                last_dt = None

            if last_dt:
                now = datetime.now(timezone.utc)
                dormancy_months = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
                account_dormant = dormancy_months >= 12
        except (ValueError, TypeError):
            pass

    return {
        "platform": "instagram",
        "handle": username,
        "display_name": profile.get("fullName") or profile.get("full_name") or "",
        "description": (profile.get("biography") or profile.get("bio") or "")[:500],
        "is_verified": profile.get("verified") or profile.get("isVerified") or False,
        "is_business": profile.get("isBusinessAccount") or False,
        "category": profile.get("businessCategoryName") or profile.get("category") or None,

        # Activity metrics
        "follower_count": followers,
        "following_count": following,
        "post_count": posts,
        "last_post_date": last_post_date,

        # Dormancy
        "account_dormant": account_dormant,
        "dormancy_months": dormancy_months,

        "raw_response": profile,
    }


def _parse_tiktok_profile(profile: dict, queried_username: str) -> dict:
    """Parse Apify TikTok profile response into our standard format."""
    username = profile.get("uniqueId") or profile.get("username") or queried_username
    followers = profile.get("fans") or profile.get("followerCount") or profile.get("followers") or 0
    following = profile.get("following") or profile.get("followingCount") or 0
    videos = profile.get("video") or profile.get("videoCount") or profile.get("videos") or 0
    likes = profile.get("heart") or profile.get("likes") or profile.get("totalLikes") or 0

    # Try to extract last post date
    last_post_date = None
    latest_videos = profile.get("latestVideos") or profile.get("recentVideos") or []
    if latest_videos and len(latest_videos) > 0:
        last_post_date = (
            latest_videos[0].get("createTime")
            or latest_videos[0].get("timestamp")
            or latest_videos[0].get("date")
        )

    # Determine dormancy
    account_dormant = False
    dormancy_months = None
    if last_post_date:
        try:
            if isinstance(last_post_date, (int, float)):
                last_dt = datetime.fromtimestamp(last_post_date, tz=timezone.utc)
            elif isinstance(last_post_date, str):
                last_dt = datetime.fromisoformat(last_post_date.replace("Z", "+00:00"))
            else:
                last_dt = None

            if last_dt:
                now = datetime.now(timezone.utc)
                dormancy_months = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
                account_dormant = dormancy_months >= 12
        except (ValueError, TypeError):
            pass

    return {
        "platform": "tiktok",
        "handle": username,
        "display_name": profile.get("nickname") or profile.get("displayName") or "",
        "description": (profile.get("signature") or profile.get("bio") or "")[:500],
        "is_verified": profile.get("verified") or False,

        # Activity metrics
        "follower_count": followers,
        "following_count": following,
        "post_count": videos,
        "like_count": likes,
        "last_post_date": last_post_date,

        # Dormancy
        "account_dormant": account_dormant,
        "dormancy_months": dormancy_months,

        "raw_response": profile,
    }
