"""
Reply Classifier — uses Claude Haiku to classify incoming email replies.

Categories:
    positive     — interested, wants to learn more, open to a meeting
    neutral      — asking questions, not yet committed either way
    negative     — not interested, asked to stop, hostile
    objection    — specific pushback that can be addressed (price, timing, etc.)
    ooo          — out of office / auto-reply
    unsubscribe  — explicit unsubscribe request

The classification drives the next action:
    positive     → book meeting (Calendly link), advance to "meeting" stage
    neutral      → continue sequence with more info
    negative     → stop sequence, add to cooldown
    objection    → flag for Sean's review with suggested response
    ooo          → pause sequence, retry after return date
    unsubscribe  → add to suppression list immediately, stop all outreach
"""

from typing import Optional
import httpx

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

CLASSIFIER_SYSTEM_PROMPT = """You are an email reply classifier for a B2B outreach system. Your job is to classify incoming replies to cold outreach emails.

Classify each reply into EXACTLY ONE category:

1. "positive" — The person is interested. They want to learn more, are open to a meeting, or expressed any form of positive engagement.
2. "neutral" — The person is asking questions or seeking clarification but hasn't committed. Not clearly positive or negative.
3. "negative" — The person is not interested. They declined, expressed annoyance, or said no.
4. "objection" — The person raised a specific concern that could potentially be addressed (budget, timing, authority, need). This is different from a flat "no."
5. "ooo" — This is an out-of-office or auto-reply. Look for patterns like "I am out of the office", "automatic reply", vacation notices, etc.
6. "unsubscribe" — The person explicitly asked to be removed from the mailing list, stop receiving emails, or used the word "unsubscribe."

Return your response as JSON with exactly these fields:
{
    "classification": "positive|neutral|negative|objection|ooo|unsubscribe",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation",
    "suggested_action": "what the outreach system should do next",
    "return_date": "YYYY-MM-DD or null (only for ooo)",
    "objection_type": "budget|timing|authority|need|other or null (only for objection)"
}
"""


async def classify_reply(
    reply_text: str,
    original_subject: Optional[str] = None,
    original_body: Optional[str] = None,
) -> dict:
    """
    Classify an email reply using Claude Haiku.

    Args:
        reply_text: The reply email content
        original_subject: The original outreach subject (for context)
        original_body: The original outreach body (for context)

    Returns:
        Classification result dict
    """
    if not reply_text or not reply_text.strip():
        return {
            "classification": "neutral",
            "confidence": 0.0,
            "reasoning": "Empty reply",
            "suggested_action": "ignore",
        }

    # Quick pattern matching for obvious cases (saves API calls)
    quick_result = _quick_classify(reply_text)
    if quick_result:
        return quick_result

    # Use Claude Haiku for nuanced classification
    if not settings.anthropic_api_key:
        return _rule_based_classify(reply_text)

    await rate_limiter.acquire("claude_haiku")
    rate_limiter.track_daily_usage("claude_haiku")

    context = ""
    if original_subject:
        context += f"\nORIGINAL SUBJECT: {original_subject}"
    if original_body:
        # Truncate to save tokens
        context += f"\nORIGINAL EMAIL (truncated): {original_body[:300]}"

    user_prompt = f"""Classify this email reply:

REPLY:
{reply_text[:1000]}
{context}

Return classification as JSON."""

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 300,
                    "system": CLASSIFIER_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )

            if response.status_code != 200:
                logger.error("classify_api_error", status=response.status_code)
                return _rule_based_classify(reply_text)

            data = response.json()
            content = data.get("content", [{}])[0].get("text", "")

            import json
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)

            logger.info(
                "reply_classified",
                classification=result.get("classification"),
                confidence=result.get("confidence"),
            )

            return result

    except Exception as e:
        logger.error("classify_error", error=str(e))
        return _rule_based_classify(reply_text)


def _quick_classify(text: str) -> Optional[dict]:
    """Fast pattern matching for obvious reply types."""
    text_lower = text.lower().strip()

    # Out of office
    ooo_patterns = [
        "out of office", "out of the office", "automatic reply",
        "auto-reply", "autoreply", "i am currently away",
        "i will be out", "on vacation", "on leave", "returning on",
    ]
    if any(p in text_lower for p in ooo_patterns):
        return {
            "classification": "ooo",
            "confidence": 0.95,
            "reasoning": "Auto-reply / out of office detected",
            "suggested_action": "pause_sequence_retry_later",
            "return_date": None,
        }

    # Unsubscribe
    unsub_patterns = [
        "unsubscribe", "remove me", "take me off",
        "stop emailing", "stop sending", "do not contact",
        "opt out", "opt-out",
    ]
    if any(p in text_lower for p in unsub_patterns):
        return {
            "classification": "unsubscribe",
            "confidence": 0.95,
            "reasoning": "Explicit unsubscribe request detected",
            "suggested_action": "add_to_suppression_list_immediately",
        }

    # Very short negative replies
    if text_lower in ["no", "no thanks", "not interested", "no thank you", "pass", "no thx", "nope"]:
        return {
            "classification": "negative",
            "confidence": 0.90,
            "reasoning": "Short negative reply",
            "suggested_action": "stop_sequence_add_cooldown",
        }

    return None


def _rule_based_classify(text: str) -> dict:
    """Fallback rule-based classification when API is unavailable."""
    text_lower = text.lower()

    # Score positive signals
    positive_signals = [
        "interested", "tell me more", "sounds good", "let's chat",
        "schedule", "calendar", "meet", "call me", "when are you free",
        "sure", "yes", "absolutely", "love to", "happy to",
    ]
    positive_score = sum(1 for p in positive_signals if p in text_lower)

    # Score negative signals
    negative_signals = [
        "not interested", "no thanks", "don't need", "don't want",
        "stop", "leave me alone", "spam", "waste of time",
        "not relevant", "wrong person",
    ]
    negative_score = sum(1 for p in negative_signals if p in text_lower)

    # Score objection signals
    objection_signals = [
        "budget", "expensive", "cost", "price", "timing",
        "not now", "maybe later", "next quarter", "busy",
        "need to check", "talk to my", "not the right person",
    ]
    objection_score = sum(1 for p in objection_signals if p in text_lower)

    if negative_score > positive_score and negative_score > objection_score:
        return {
            "classification": "negative",
            "confidence": 0.6,
            "reasoning": "Rule-based: negative signals detected",
            "suggested_action": "stop_sequence_add_cooldown",
        }
    elif objection_score > positive_score:
        return {
            "classification": "objection",
            "confidence": 0.5,
            "reasoning": "Rule-based: objection signals detected",
            "suggested_action": "flag_for_review",
        }
    elif positive_score > 0:
        return {
            "classification": "positive",
            "confidence": 0.6,
            "reasoning": "Rule-based: positive signals detected",
            "suggested_action": "send_calendly_link",
        }
    else:
        return {
            "classification": "neutral",
            "confidence": 0.4,
            "reasoning": "Rule-based: no strong signals detected",
            "suggested_action": "continue_sequence",
        }
