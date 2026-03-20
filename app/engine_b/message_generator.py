"""
Outreach Message Generator — Claude Sonnet-powered personalized copy.

Generates cold outreach emails tailored to each prospect's situation:
- Company name, industry, and size
- Which platforms have handle mismatches
- Whether the ideal handle is available or held by a dormant account
- Contact's title and seniority (adjusts tone for CMO vs. Founder)

Sequence strategy (4 touches max):
    Step 1: Value-first intro — highlight the opportunity, no hard sell
    Step 2: Social proof + urgency — someone else could grab the handle
    Step 3: Direct ask — "15 min with Sean to discuss acquisition"
    Step 4: Breakup email — last chance, respectful close

All messages are CAN-SPAM compliant with unsubscribe link and physical address.
"""

from typing import Optional
import httpx

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

# System prompt for the message generator
SYSTEM_PROMPT = """You are a professional business development copywriter for a premium username/handle acquisition service. Your job is to write cold outreach emails that are:

1. Concise (under 150 words for the body)
2. Professional but warm — never pushy or salesy
3. Value-first: lead with the opportunity, not what you're selling
4. Personalized to the recipient's role and company
5. Written at a grade 8 reading level

The sender's name is Sean. He helps companies acquire their ideal social media handles across platforms like Instagram, TikTok, YouTube, and Twitch.

NEVER use:
- Excessive exclamation marks
- Phrases like "I hope this email finds you well" or "Just following up"
- Generic flattery ("I love what you're doing!")
- ALL CAPS for emphasis
- Emojis in the subject line

ALWAYS include:
- A clear, specific subject line (under 50 characters)
- One specific data point about their handle situation
- A soft CTA (no "Book a call NOW!")

Return your response as JSON with exactly these fields:
{"subject": "...", "body": "..."}
"""

# Step-specific instructions
STEP_PROMPTS = {
    1: """Write the FIRST email in a cold outreach sequence. This is the initial contact.
Focus on: Discovery of the opportunity. Lead with the specific handle problem you found.
Tone: Curious, helpful, like a friend pointing out something they noticed.
CTA: "Would it be worth a quick chat to explore this?"
""",
    2: """Write the SECOND email (follow-up). They didn't respond to the first one.
Focus on: Add urgency or social proof. Mention that handles get claimed fast.
Tone: Brief, respectful, adds new information they didn't have before.
CTA: "Happy to send over a quick analysis — just say the word."
""",
    3: """Write the THIRD email. This is the direct ask.
Focus on: Clear value proposition. "15 minutes with Sean to discuss your options."
Tone: Confident but not aggressive. Professional.
CTA: Include a specific meeting request with a Calendly link placeholder: {{calendly_link}}
""",
    4: """Write the FOURTH and FINAL email (breakup). This is the last touchpoint.
Focus on: Respectful close. "No hard feelings if this isn't a priority right now."
Tone: Gracious, brief, leaves the door open.
CTA: "If this ever becomes relevant, I'm here."
""",
}


async def generate_outreach_message(
    company_name: str,
    contact_name: str,
    contact_title: str,
    platform_details: list[dict],
    sequence_step: int = 1,
    industry: Optional[str] = None,
    company_size: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> dict:
    """
    Generate a personalized outreach email using Claude Sonnet.

    Args:
        company_name: Target company name
        contact_name: Recipient's name
        contact_title: Recipient's job title
        platform_details: List of platform handle findings
            e.g. [{"platform": "instagram", "issue": "uses @acmehq instead of @acme", "handle_available": False}]
        sequence_step: Which step in the sequence (1-4)
        industry: Company industry
        company_size: Employee range
        additional_context: Any extra context for personalization

    Returns:
        {"subject": str, "body": str, "step": int, "model": str}
    """
    if not settings.anthropic_api_key:
        logger.warning("anthropic_api_key_not_set")
        return _fallback_message(company_name, contact_name, sequence_step)

    await rate_limiter.acquire("claude_sonnet")
    rate_limiter.track_daily_usage("claude_sonnet")

    # Build the platform situation summary
    platform_summary = _build_platform_summary(platform_details)

    step_instruction = STEP_PROMPTS.get(sequence_step, STEP_PROMPTS[1])

    user_prompt = f"""{step_instruction}

RECIPIENT DETAILS:
- Name: {contact_name}
- Title: {contact_title}
- Company: {company_name}
{f'- Industry: {industry}' if industry else ''}
{f'- Company Size: {company_size}' if company_size else ''}

HANDLE SITUATION:
{platform_summary}

{f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}

Generate the email now. Return as JSON: {{"subject": "...", "body": "..."}}
Remember: Sean is the sender. Keep the body under 150 words. Subject under 50 characters."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )

            if response.status_code != 200:
                logger.error(
                    "claude_message_gen_error",
                    status=response.status_code,
                    body=response.text[:500],
                )
                return _fallback_message(company_name, contact_name, sequence_step)

            data = response.json()
            content = data.get("content", [{}])[0].get("text", "")

            # Parse JSON from Claude's response
            import json
            # Handle case where Claude wraps in markdown code blocks
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            message = json.loads(cleaned)

            # Append CAN-SPAM footer
            message["body"] = _add_compliance_footer(message.get("body", ""))

            logger.info(
                "message_generated",
                company=company_name,
                step=sequence_step,
                subject_len=len(message.get("subject", "")),
                body_len=len(message.get("body", "")),
            )

            return {
                "subject": message.get("subject", ""),
                "body": message.get("body", ""),
                "step": sequence_step,
                "model": "claude-sonnet-4-20250514",
            }

    except Exception as e:
        logger.error("message_generation_error", error=str(e))
        return _fallback_message(company_name, contact_name, sequence_step)


def _build_platform_summary(platform_details: list[dict]) -> str:
    """Build a human-readable summary of platform handle issues."""
    if not platform_details:
        return "No specific platform details available."

    lines = []
    for p in platform_details:
        platform = p.get("platform", "unknown").title()
        issue = p.get("issue", "handle mismatch detected")
        available = p.get("handle_available")
        dormant = p.get("dormant")

        line = f"- {platform}: {issue}"
        if dormant:
            line += " (current holder appears inactive)"
        elif available:
            line += " (ideal handle is AVAILABLE for registration)"
        lines.append(line)

    return "\n".join(lines)


def _add_compliance_footer(body: str) -> str:
    """Append CAN-SPAM compliant footer to the email body."""
    address = settings.physical_address or "[Physical Address]"
    footer = f"""

---
{address}
To stop receiving these emails, reply "unsubscribe" or click here: {{{{unsubscribe_link}}}}"""
    return body + footer


def _fallback_message(company_name: str, contact_name: str, step: int) -> dict:
    """Generate a basic template when Claude API is unavailable."""
    first_name = contact_name.split()[0] if contact_name else "there"

    templates = {
        1: {
            "subject": f"Quick question about {company_name}'s social handles",
            "body": f"""Hi {first_name},

I noticed {company_name} might be missing out on securing the ideal brand handle across a few social platforms. I help companies acquire and protect their usernames before someone else claims them.

Would it be worth a quick chat to see if there's an opportunity here?

Best,
Sean""",
        },
        2: {
            "subject": f"Following up — {company_name} handle availability",
            "body": f"""Hi {first_name},

Wanted to circle back on my note about {company_name}'s social media handles. These opportunities can disappear quickly when someone else registers the handle.

Happy to send over a quick analysis if that would be helpful.

Best,
Sean""",
        },
        3: {
            "subject": f"15 min to discuss {company_name}'s brand handles?",
            "body": f"""Hi {first_name},

I've been looking into the handle landscape for {company_name} and see some concrete opportunities worth discussing.

Would you have 15 minutes this week? Here's my calendar: {{{{calendly_link}}}}

Best,
Sean""",
        },
        4: {
            "subject": f"Closing the loop — {company_name}",
            "body": f"""Hi {first_name},

I've reached out a few times about securing {company_name}'s social handles. I understand if the timing isn't right.

If this ever becomes a priority, I'm here to help. Wishing you and the team all the best.

Cheers,
Sean""",
        },
    }

    template = templates.get(step, templates[1])
    template["body"] = _add_compliance_footer(template["body"])
    return {**template, "step": step, "model": "fallback_template"}
