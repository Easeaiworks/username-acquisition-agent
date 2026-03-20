"""
Shared rate limiter for all external API integrations.
Prevents exceeding API quotas and handles backoff gracefully.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import structlog
from aiolimiter import AsyncLimiter

logger = structlog.get_logger()


class RateLimitManager:
    """Centralized rate limit management for all API integrations."""

    def __init__(self):
        self._limiters: dict[str, AsyncLimiter] = {}
        self._daily_counters: dict[str, dict] = {}

    def get_limiter(self, name: str, max_rate: float, time_period: float = 1.0) -> AsyncLimiter:
        """Get or create a rate limiter for a specific API.

        Args:
            name: Identifier for the API (e.g., "youtube", "twitch")
            max_rate: Maximum number of requests per time_period
            time_period: Time window in seconds
        """
        if name not in self._limiters:
            self._limiters[name] = AsyncLimiter(max_rate, time_period)
            logger.info("rate_limiter_created", api=name, max_rate=max_rate, period=time_period)
        return self._limiters[name]

    async def acquire(self, name: str) -> None:
        """Acquire a rate limit slot. Blocks if limit is reached."""
        if name in self._limiters:
            await self._limiters[name].acquire()

    def track_daily_usage(self, name: str, count: int = 1) -> None:
        """Track daily API call count."""
        today = datetime.utcnow().date().isoformat()

        if name not in self._daily_counters:
            self._daily_counters[name] = {"date": today, "count": 0}

        # Reset counter if new day
        if self._daily_counters[name]["date"] != today:
            self._daily_counters[name] = {"date": today, "count": 0}

        self._daily_counters[name]["count"] += count

    def get_daily_usage(self, name: str) -> int:
        """Get today's API call count for a specific integration."""
        today = datetime.utcnow().date().isoformat()

        if name not in self._daily_counters:
            return 0

        if self._daily_counters[name]["date"] != today:
            return 0

        return self._daily_counters[name]["count"]

    def check_daily_limit(self, name: str, max_daily: int) -> bool:
        """Check if daily limit has been reached. Returns True if allowed."""
        usage = self.get_daily_usage(name)
        allowed = usage < max_daily

        if not allowed:
            logger.warning(
                "daily_limit_reached",
                api=name,
                usage=usage,
                limit=max_daily,
            )

        return allowed

    def get_all_usage(self) -> dict:
        """Get usage stats for all tracked APIs."""
        return {
            name: {
                "date": info["date"],
                "count": info["count"],
            }
            for name, info in self._daily_counters.items()
        }


# Singleton instance
rate_limiter = RateLimitManager()

# Pre-configure rate limiters for known APIs
def setup_rate_limiters():
    """Initialize rate limiters with configured limits."""
    from app.config import settings

    # YouTube: ~10,000 units/day, conservatively ~3 requests/second
    rate_limiter.get_limiter("youtube", max_rate=3, time_period=1.0)

    # Twitch: ~30 requests/minute
    rate_limiter.get_limiter("twitch", max_rate=settings.max_twitch_calls_per_minute, time_period=60.0)

    # Apify: concurrent run limit
    rate_limiter.get_limiter("apify", max_rate=settings.max_apify_concurrent_runs, time_period=1.0)

    # RocketReach: 15 requests/second, but monthly cap matters more
    rate_limiter.get_limiter("rocketreach", max_rate=10, time_period=1.0)

    # Hunter.io: 15 requests/second, 500/minute
    rate_limiter.get_limiter("hunter", max_rate=15, time_period=1.0)

    # Claude API: conservative to manage costs
    rate_limiter.get_limiter("claude_haiku", max_rate=5, time_period=1.0)
    rate_limiter.get_limiter("claude_sonnet", max_rate=2, time_period=1.0)

    logger.info("rate_limiters_configured")
