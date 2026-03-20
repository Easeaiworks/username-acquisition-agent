"""
Handle Candidate Generator — creates the list of ideal handle variations to check.

For every company, generates a prioritized list of what their social media handle
SHOULD be, then the scanner checks what it actually IS.

Example for brand "Stripe":
    Priority 1: stripe          (exact match — best case)
    Priority 2: stripeapp       (common modifier)
    Priority 3: stripehq        (common modifier)
    Priority 4: stripeofficial  (common modifier)
    Priority 5: getstripe       (common modifier)
    Priority 6: usestripe       (common modifier)
    ...etc
"""

import structlog

logger = structlog.get_logger()

# Suffix modifiers that companies commonly append to their brand handle
SUFFIX_MODIFIERS = [
    "",            # exact match (highest priority)
    "app",
    "hq",
    "official",
    "inc",
    "co",
    "io",
    "global",
    "brand",
    "team",
    "live",
    "tv",
    "media",
    "studio",
    "labs",
    "ai",
    "tech",
    "games",
    "music",
    "sports",
    "news",
    "daily",
]

# Prefix modifiers that companies commonly prepend
PREFIX_MODIFIERS = [
    "get",
    "use",
    "try",
    "the",
    "my",
    "go",
    "hey",
    "join",
    "its",
    "weare",
    "real",
    "meet",
]

# Platform-specific handle conventions
PLATFORM_SPECIFIC = {
    "youtube": [
        "",           # @brand
        "official",   # @brandofficial (very common on YouTube)
        "tv",         # @brandtv
        "channel",    # @brandchannel
        "hq",         # @brandhq
    ],
    "twitch": [
        "",           # brand
        "official",   # brandofficial
        "tv",         # brandtv
        "live",       # brandlive
        "gaming",     # brandgaming
        "hq",         # brandhq
    ],
    "instagram": [
        "",           # @brand
        "official",   # @brandofficial (very common on Instagram)
        "hq",         # @brandhq
        "co",         # @brandco
        "brand",      # @brandbrand (rare but exists)
    ],
    "tiktok": [
        "",           # @brand
        "official",   # @brandofficial
        "hq",         # @brandhq
        "app",        # @brandapp
    ],
}


def generate_candidates(
    handle_slug: str,
    platform: str = None,
    max_candidates: int = 25,
) -> list[dict]:
    """
    Generate a prioritized list of handle candidates for a brand.

    Args:
        handle_slug: The normalized brand slug (e.g., "stripe")
        platform: Optional platform name to use platform-specific patterns
        max_candidates: Maximum number of candidates to generate

    Returns:
        List of dicts with 'handle' and 'priority' keys, sorted by priority (1 = best)
    """
    if not handle_slug:
        return []

    candidates = []
    seen = set()

    def add_candidate(handle: str, priority: int):
        if handle and handle not in seen and len(candidates) < max_candidates:
            seen.add(handle)
            candidates.append({"handle": handle, "priority": priority})

    # Priority 1: Exact match (always first)
    add_candidate(handle_slug, 1)

    # Priority 2-3: Platform-specific patterns (if platform specified)
    if platform and platform.lower() in PLATFORM_SPECIFIC:
        for i, modifier in enumerate(PLATFORM_SPECIFIC[platform.lower()]):
            if modifier:  # skip empty (already added as exact match)
                add_candidate(f"{handle_slug}{modifier}", 2 + i)

    # Priority 4+: Common suffix modifiers
    priority = 10
    for modifier in SUFFIX_MODIFIERS:
        if modifier:  # skip empty
            add_candidate(f"{handle_slug}{modifier}", priority)
            priority += 1

    # Priority 20+: Common prefix modifiers
    priority = 30
    for modifier in PREFIX_MODIFIERS:
        add_candidate(f"{modifier}{handle_slug}", priority)
        priority += 1

    # Sort by priority
    candidates.sort(key=lambda x: x["priority"])

    logger.debug(
        "handle_candidates_generated",
        slug=handle_slug,
        platform=platform,
        count=len(candidates),
    )

    return candidates[:max_candidates]


def get_exact_handle(handle_slug: str) -> str:
    """Get the ideal exact-match handle for a brand."""
    return handle_slug


def classify_observed_handle(
    brand_slug: str,
    observed_handle: str,
) -> dict:
    """
    Classify how an observed handle relates to the brand.

    Returns a dict with:
        - match_type: "exact" | "suffix_modified" | "prefix_modified" | "unrelated"
        - modifier: the modifier found (if any)
        - severity: 0.0-1.0 how problematic this mismatch is
    """
    if not observed_handle or not brand_slug:
        return {"match_type": "unknown", "modifier": None, "severity": 0.0}

    observed = observed_handle.lower().lstrip("@")
    brand = brand_slug.lower()

    # Exact match — no issue
    if observed == brand:
        return {"match_type": "exact", "modifier": None, "severity": 0.0}

    # Check suffix modifiers (e.g., "stripehq" → brand="stripe", modifier="hq")
    if observed.startswith(brand):
        modifier = observed[len(brand):]
        if modifier in [m for m in SUFFIX_MODIFIERS if m]:
            severity = _modifier_severity(modifier)
            return {"match_type": "suffix_modified", "modifier": modifier, "severity": severity}

    # Check prefix modifiers (e.g., "getstripe" → modifier="get", brand="stripe")
    if observed.endswith(brand):
        modifier = observed[:len(observed) - len(brand)]
        if modifier in PREFIX_MODIFIERS:
            severity = _modifier_severity(modifier)
            return {"match_type": "prefix_modified", "modifier": modifier, "severity": severity}

    # Check if brand is contained at all
    if brand in observed:
        return {"match_type": "contains_brand", "modifier": None, "severity": 0.6}

    # Completely different handle
    return {"match_type": "unrelated", "modifier": None, "severity": 0.9}


def _modifier_severity(modifier: str) -> float:
    """
    Rate how problematic a specific modifier is.
    Lower severity = less urgent, higher = more painful.
    """
    # Mild modifiers (common, somewhat acceptable)
    mild = {"hq", "official", "co", "app", "io"}
    # Medium modifiers (noticeable, brand dilution)
    medium = {"inc", "global", "team", "brand", "labs", "tech"}
    # Severe modifiers (clunky, clearly not ideal)
    severe = {"live", "tv", "media", "studio", "games", "news", "daily"}

    if modifier in mild:
        return 0.3
    elif modifier in medium:
        return 0.5
    elif modifier in severe:
        return 0.7
    else:
        return 0.4  # unknown modifier defaults to medium-low
