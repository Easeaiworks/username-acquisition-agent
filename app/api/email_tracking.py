"""
Email Tracking API routes -- open pixels, click redirects, and unsubscribe handling.

These are PUBLIC endpoints (no auth required). The router prefix is /t for short URLs.
"""

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response, HTMLResponse

from app.database import get_service_client
from app.email.tracking import decode_tracking_id

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/t", tags=["Email Tracking"])

# 1x1 transparent GIF
TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


# ---------------------------------------------------------------------------
# Open tracking pixel
# ---------------------------------------------------------------------------


@router.get("/open/{tracking_id}.gif")
async def track_open(tracking_id: str, request: Request):
    """
    Open tracking pixel. Decodes the tracking ID, records an 'opened' event,
    and returns a 1x1 transparent GIF.
    """
    try:
        campaign_id, contact_id = decode_tracking_id(tracking_id)
    except ValueError:
        # Return the GIF anyway -- don't expose tracking internals
        return Response(
            content=TRANSPARENT_GIF,
            media_type="image/gif",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Record opened event
        db.table("email_events").insert({
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "event_type": "opened",
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
            "created_at": now,
        }).execute()

        # Update contact engagement
        try:
            db.rpc("", {}).execute()  # no-op; fall through to manual update
        except Exception:
            pass

        # Update contact stats
        contact = db.table("email_contacts").select("open_count").eq("id", contact_id).execute()
        if contact.data:
            current_count = contact.data[0].get("open_count", 0) or 0
            db.table("email_contacts").update({
                "last_opened_at": now,
                "open_count": current_count + 1,
            }).eq("id", contact_id).execute()

        # Update campaign open count
        campaign = db.table("email_campaigns").select("open_count").eq("id", campaign_id).execute()
        if campaign.data:
            current_opens = campaign.data[0].get("open_count", 0) or 0
            db.table("email_campaigns").update({
                "open_count": current_opens + 1,
            }).eq("id", campaign_id).execute()

    except Exception as e:
        # Log but don't fail -- always return the pixel
        logger.error("track_open_error", error=str(e), campaign_id=campaign_id, contact_id=contact_id)

    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


# ---------------------------------------------------------------------------
# Click tracking
# ---------------------------------------------------------------------------


@router.get("/click/{tracking_id}")
async def track_click(
    tracking_id: str,
    request: Request,
    url: str = Query(..., description="Original destination URL"),
):
    """
    Click tracking redirect. Records a 'clicked' event and redirects to the
    original URL (302).
    """
    try:
        campaign_id, contact_id = decode_tracking_id(tracking_id)
    except ValueError:
        # Redirect anyway if we have the URL
        return RedirectResponse(url=url, status_code=302)

    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Record click event
        db.table("email_events").insert({
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "event_type": "clicked",
            "link_url": url,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
            "created_at": now,
        }).execute()

        # Update contact stats
        contact = db.table("email_contacts").select("click_count").eq("id", contact_id).execute()
        if contact.data:
            current_count = contact.data[0].get("click_count", 0) or 0
            db.table("email_contacts").update({
                "last_clicked_at": now,
                "click_count": current_count + 1,
            }).eq("id", contact_id).execute()

        # Update campaign click count
        campaign = db.table("email_campaigns").select("click_count").eq("id", campaign_id).execute()
        if campaign.data:
            current_clicks = campaign.data[0].get("click_count", 0) or 0
            db.table("email_campaigns").update({
                "click_count": current_clicks + 1,
            }).eq("id", campaign_id).execute()

    except Exception as e:
        logger.error("track_click_error", error=str(e), campaign_id=campaign_id, contact_id=contact_id)

    return RedirectResponse(url=url, status_code=302)


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------

UNSUBSCRIBE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unsubscribed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f5f5f5;
            color: #333;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 48px;
            text-align: center;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
            max-width: 480px;
        }}
        h1 {{ font-size: 24px; margin-bottom: 16px; }}
        p {{ color: #666; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>You've been unsubscribed</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""


@router.get("/unsubscribe/{token}")
async def unsubscribe_get(token: str):
    """
    Unsubscribe page. Looks up the token, marks the contact as unsubscribed,
    and returns a simple confirmation page.
    """
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Look up token
        token_result = (
            db.table("email_unsubscribe_tokens")
            .select("*")
            .eq("token", token)
            .execute()
        )

        if not token_result.data:
            return HTMLResponse(
                content=UNSUBSCRIBE_HTML.format(
                    message="This unsubscribe link is invalid or has expired."
                ),
                status_code=400,
            )

        token_data = token_result.data[0]

        if token_data.get("used"):
            return HTMLResponse(
                content=UNSUBSCRIBE_HTML.format(
                    message="You have already been unsubscribed. No further action is needed."
                ),
            )

        contact_id = token_data["contact_id"]
        campaign_id = token_data.get("campaign_id")

        # Mark contact as unsubscribed
        db.table("email_contacts").update({
            "status": "unsubscribed",
            "unsubscribed_at": now,
            "updated_at": now,
        }).eq("id", contact_id).execute()

        # Mark token as used
        db.table("email_unsubscribe_tokens").update({
            "used": True,
            "used_at": now,
        }).eq("id", token_data["id"]).execute()

        # Record unsubscribe event
        event_record = {
            "contact_id": contact_id,
            "event_type": "unsubscribed",
            "created_at": now,
        }
        if campaign_id:
            event_record["campaign_id"] = campaign_id

            # Update campaign unsubscribe count
            campaign = db.table("email_campaigns").select("unsubscribe_count").eq("id", campaign_id).execute()
            if campaign.data:
                current = campaign.data[0].get("unsubscribe_count", 0) or 0
                db.table("email_campaigns").update({
                    "unsubscribe_count": current + 1,
                }).eq("id", campaign_id).execute()

        db.table("email_events").insert(event_record).execute()

        # Update list memberships to unsubscribed
        db.table("email_list_members").update({
            "status": "unsubscribed",
        }).eq("contact_id", contact_id).execute()

        logger.info("email_contact_unsubscribed_via_link", contact_id=contact_id, campaign_id=campaign_id)

        return HTMLResponse(
            content=UNSUBSCRIBE_HTML.format(
                message="You will no longer receive emails from us. We're sorry to see you go."
            ),
        )

    except Exception as e:
        logger.error("unsubscribe_error", token=token, error=str(e))
        return HTMLResponse(
            content=UNSUBSCRIBE_HTML.format(
                message="An error occurred processing your request. Please try again later."
            ),
            status_code=500,
        )


@router.post("/unsubscribe/{token}")
async def unsubscribe_post(token: str):
    """
    API unsubscribe endpoint for List-Unsubscribe-Post header support (RFC 8058).
    Performs the same action as the GET handler.
    """
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Look up token
        token_result = (
            db.table("email_unsubscribe_tokens")
            .select("*")
            .eq("token", token)
            .execute()
        )

        if not token_result.data:
            raise HTTPException(status_code=404, detail="Invalid unsubscribe token")

        token_data = token_result.data[0]

        if token_data.get("used"):
            return {"status": "already_unsubscribed"}

        contact_id = token_data["contact_id"]
        campaign_id = token_data.get("campaign_id")

        # Mark contact as unsubscribed
        db.table("email_contacts").update({
            "status": "unsubscribed",
            "unsubscribed_at": now,
            "updated_at": now,
        }).eq("id", contact_id).execute()

        # Mark token as used
        db.table("email_unsubscribe_tokens").update({
            "used": True,
            "used_at": now,
        }).eq("id", token_data["id"]).execute()

        # Record event
        event_record = {
            "contact_id": contact_id,
            "event_type": "unsubscribed",
            "created_at": now,
        }
        if campaign_id:
            event_record["campaign_id"] = campaign_id

            # Update campaign unsubscribe count
            campaign = db.table("email_campaigns").select("unsubscribe_count").eq("id", campaign_id).execute()
            if campaign.data:
                current = campaign.data[0].get("unsubscribe_count", 0) or 0
                db.table("email_campaigns").update({
                    "unsubscribe_count": current + 1,
                }).eq("id", campaign_id).execute()

        db.table("email_events").insert(event_record).execute()

        # Update list memberships
        db.table("email_list_members").update({
            "status": "unsubscribed",
        }).eq("contact_id", contact_id).execute()

        logger.info("email_contact_unsubscribed_via_post", contact_id=contact_id, campaign_id=campaign_id)
        return {"status": "unsubscribed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("unsubscribe_post_error", token=token, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process unsubscribe")
