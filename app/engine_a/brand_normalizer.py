"""
Brand Normalizer — the canonical brand identity layer.

Converts messy company names into clean, normalized brand identities.
This is the foundation that everything else depends on.

Examples:
    "Meta Platforms, Inc." → brand_name="Meta", aliases=["Meta AI", "Meta Quest"]
    "Stripe, Inc."         → brand_name="Stripe"
    "The Coca-Cola Company" → brand_name="Coca-Cola", aliases=["Coke"]
"""

import re
import structlog

logger = structlog.get_logger()

# Common suffixes to strip from company names
CORPORATE_SUFFIXES = [
    r"\bInc\.?$",
    r"\bIncorporated$",
    r"\bCorp\.?$",
    r"\bCorporation$",
    r"\bLLC$",
    r"\bLLP$",
    r"\bLtd\.?$",
    r"\bLimited$",
    r"\bPLC$",
    r"\bGmbH$",
    r"\bAG$",
    r"\bS\.?A\.?$",
    r"\bS\.?A\.?S\.?$",
    r"\bB\.?V\.?$",
    r"\bN\.?V\.?$",
    r"\bPty\.?\s*Ltd\.?$",
    r"\bCo\.?$",
    r"\bCompany$",
    r"\bGroup$",
    r"\bHoldings?$",
    r"\bEnterprises?$",
    r"\bInternational$",
    r"\bGlobal$",
    r"\bPlatforms?$",
    r"\bTechnolog(?:y|ies)$",
    r"\bSolutions$",
    r"\bServices$",
    r"\bSystems$",
    r"\bSoftware$",
    r"\bMedia$",
    r"\bDigital$",
    r"\bLabs?$",
    r"\bStudios?$",
    r"\bNetwork(?:s)?$",
    r"\bVentures?$",
]

# Common prefixes to strip
CORPORATE_PREFIXES = [
    r"^The\s+",
]

# Known brand mappings for large companies where legal name != brand name
KNOWN_BRAND_MAPPINGS = {
    "alphabet": "Google",
    "meta platforms": "Meta",
    "amazon.com": "Amazon",
    "apple inc": "Apple",
    "microsoft corporation": "Microsoft",
    "nvidia corporation": "NVIDIA",
    "tesla motors": "Tesla",
    "the walt disney company": "Disney",
    "the coca-cola company": "Coca-Cola",
    "pepsico": "Pepsi",
    "procter & gamble": "P&G",
    "johnson & johnson": "J&J",
    "jpmorgan chase": "JPMorgan",
    "berkshire hathaway": "Berkshire Hathaway",
    "unitedhealth group": "UnitedHealth",
    "walmart": "Walmart",
    "home depot": "Home Depot",
    "salesforce": "Salesforce",
    "adobe systems": "Adobe",
    "netflix": "Netflix",
    "uber technologies": "Uber",
    "airbnb": "Airbnb",
    "snap": "Snapchat",
    "pinterest": "Pinterest",
    "spotify technology": "Spotify",
    "block": "Square",
    "shopify": "Shopify",
    "twilio": "Twilio",
    "cloudflare": "Cloudflare",
    "datadog": "Datadog",
    "crowdstrike holdings": "CrowdStrike",
    "palantir technologies": "Palantir",
    "roblox corporation": "Roblox",
    "rivian automotive": "Rivian",
    "lucid group": "Lucid Motors",
}


def normalize_brand_name(raw_name: str) -> str:
    """
    Convert a raw company/legal name into a clean brand name.

    Steps:
    1. Check known brand mappings first
    2. Strip corporate suffixes (Inc, Corp, LLC, etc.)
    3. Strip common prefixes (The)
    4. Clean up whitespace and punctuation
    5. Handle special characters

    Args:
        raw_name: The raw company name (e.g., "Stripe, Inc.")

    Returns:
        Clean brand name (e.g., "Stripe")
    """
    if not raw_name:
        return ""

    name = raw_name.strip()

    # Check known mappings first (case-insensitive)
    name_lower = name.lower()
    for key, brand in KNOWN_BRAND_MAPPINGS.items():
        if key in name_lower:
            logger.debug("brand_mapped", raw=raw_name, brand=brand, mapping_key=key)
            return brand

    # Strip corporate suffixes
    for suffix_pattern in CORPORATE_SUFFIXES:
        name = re.sub(suffix_pattern, "", name, flags=re.IGNORECASE).strip()

    # Strip corporate prefixes
    for prefix_pattern in CORPORATE_PREFIXES:
        name = re.sub(prefix_pattern, "", name, flags=re.IGNORECASE).strip()

    # Remove trailing commas, periods, hyphens
    name = re.sub(r"[,.\-]+$", "", name).strip()

    # Remove leading/trailing quotes
    name = name.strip("'\"")

    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()

    logger.debug("brand_normalized", raw=raw_name, normalized=name)
    return name


def generate_handle_slug(brand_name: str) -> str:
    """
    Convert a brand name into a social media handle slug.

    Examples:
        "Coca-Cola" → "cocacola"
        "Under Armour" → "underarmour"
        "H&M" → "hm"
        "7-Eleven" → "7eleven"

    Args:
        brand_name: The normalized brand name

    Returns:
        Lowercase handle slug with no spaces or special characters
    """
    if not brand_name:
        return ""

    slug = brand_name.lower()

    # Remove special characters but keep alphanumeric
    slug = re.sub(r"[^a-z0-9]", "", slug)

    return slug


def extract_domain_from_name(brand_name: str) -> str:
    """
    Guess the most likely domain from a brand name.
    This is a heuristic — should be verified with actual DNS lookup.

    Examples:
        "Stripe" → "stripe.com"
        "Coca-Cola" → "coca-cola.com"
    """
    if not brand_name:
        return ""

    # Lowercase, replace spaces with hyphens, remove non-alphanumeric except hyphens
    domain_slug = brand_name.lower()
    domain_slug = re.sub(r"\s+", "-", domain_slug)
    domain_slug = re.sub(r"[^a-z0-9\-]", "", domain_slug)
    domain_slug = re.sub(r"-+", "-", domain_slug).strip("-")

    return f"{domain_slug}.com"


def build_canonical_record(
    raw_name: str,
    legal_name: str = None,
    domain: str = None,
    known_aliases: list[str] = None,
) -> dict:
    """
    Build a complete canonical brand identity record.

    Returns a dict with:
        - brand_name: clean brand name
        - legal_name: original legal name
        - handle_slug: social media handle base
        - domain: company domain (provided or guessed)
        - aliases: list of known aliases
    """
    brand_name = normalize_brand_name(raw_name)
    handle_slug = generate_handle_slug(brand_name)

    # If no domain provided, guess it
    if not domain:
        domain = extract_domain_from_name(brand_name)

    # Build aliases list
    aliases = set()
    if known_aliases:
        aliases.update(known_aliases)

    # Add the raw name as an alias if it differs from brand name
    if raw_name.strip() != brand_name:
        aliases.add(raw_name.strip())

    # Add the legal name as an alias if provided and different
    if legal_name and legal_name.strip() != brand_name:
        aliases.add(legal_name.strip())

    record = {
        "brand_name": brand_name,
        "legal_name": legal_name or raw_name,
        "handle_slug": handle_slug,
        "domain": domain,
        "aliases": sorted(aliases) if aliases else [],
    }

    logger.info(
        "canonical_record_built",
        brand=brand_name,
        slug=handle_slug,
        domain=domain,
        alias_count=len(aliases),
    )

    return record
