"""
Report Formatter — converts raw metrics into readable report formats.

Produces:
- Plain text summary for email/Slack notifications
- Structured HTML email for daily digest
- Persisted JSON record for historical tracking in the dashboard
"""

from datetime import datetime
from typing import Any

from app.database import get_service_client

import structlog

logger = structlog.get_logger()


def format_text_summary(report: dict[str, Any]) -> str:
    """Format report data as a concise plain-text summary."""
    p = report["pipeline"]
    s = report["scoring"]
    o = report["outreach"]
    a = report["attention_required"]
    top = report["top_opportunities"]

    lines = [
        f"=== Daily Report — {report['report_date']} ===",
        "",
        "PIPELINE",
        f"  Total companies: {p['total_companies']}",
        f"  New today: {p['new_companies_today']}",
        f"  Stage movements: {p['stage_movements_today']}",
    ]

    # Stage breakdown
    active_stages = {k: v for k, v in p["stage_breakdown"].items() if v > 0}
    if active_stages:
        lines.append("  Stages: " + ", ".join(f"{k}: {v}" for k, v in active_stages.items()))

    lines += [
        "",
        "SCORING",
        f"  Scored today: {s['scored_today']}",
        f"  Avg score: {s['avg_score_today']}",
        f"  High-value (≥0.65): {s['high_value_today']}",
    ]

    dist = s["priority_distribution"]
    bucket_str = ", ".join(f"{k}: {v}" for k, v in dist.items() if v > 0)
    if bucket_str:
        lines.append(f"  Buckets: {bucket_str}")

    lines += [
        "",
        "OUTREACH",
        f"  Sent today: {o['sent_today']}",
        f"  Replies: {o['replies_today']} ({o['reply_rate_today']}%)",
        f"  Meetings booked: {o['meetings_booked_today']}",
        f"  Bounces: {o['bounces_today']}",
        f"  Active sequences: {o['active_sequences_total']}",
    ]

    classifications = o.get("reply_classifications", {})
    class_str = ", ".join(f"{k}: {v}" for k, v in classifications.items() if v > 0)
    if class_str:
        lines.append(f"  Reply types: {class_str}")

    # Attention items
    total_attention = a.get("pending_approvals", 0) + a.get("stale_sequences", 0) + \
                      a.get("unreviewed_objections", 0) + a.get("hot_leads_no_meeting", 0)
    if total_attention > 0:
        lines += [
            "",
            "⚠ ATTENTION REQUIRED",
        ]
        if a.get("pending_approvals"):
            lines.append(f"  • {a['pending_approvals']} companies pending approval")
        if a.get("hot_leads_no_meeting"):
            lines.append(f"  • {a['hot_leads_no_meeting']} positive replies without meeting booked")
        if a.get("unreviewed_objections"):
            lines.append(f"  • {a['unreviewed_objections']} objections needing review")
        if a.get("stale_sequences"):
            lines.append(f"  • {a['stale_sequences']} stale sequences (>7 days no reply)")

    # Top opportunities
    if top:
        lines += ["", "TOP OPPORTUNITIES TODAY"]
        for i, opp in enumerate(top[:5], 1):
            lines.append(
                f"  {i}. {opp.get('brand_name', '?')} — "
                f"{opp.get('composite_score', 0):.3f} "
                f"({opp.get('priority_bucket', '?')})"
            )

    lines.append(f"\nGenerated: {report.get('generated_at', datetime.utcnow().isoformat())}")
    return "\n".join(lines)


def format_html_email(report: dict[str, Any]) -> str:
    """Format report data as a styled HTML email."""
    p = report["pipeline"]
    s = report["scoring"]
    o = report["outreach"]
    a = report["attention_required"]
    top = report["top_opportunities"]

    attention_count = sum(a.values())
    attention_color = "#dc2626" if attention_count > 3 else "#f59e0b" if attention_count > 0 else "#16a34a"

    top_rows = ""
    for opp in top[:5]:
        bucket = opp.get("priority_bucket", "")
        bucket_color = {
            "critical": "#dc2626", "very_high": "#f59e0b",
            "high": "#3b82f6", "medium": "#8b5cf6", "low": "#9ca3af",
        }.get(bucket, "#9ca3af")
        top_rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6">{opp.get('brand_name', '—')}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-family:monospace">{opp.get('composite_score', 0):.3f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6">
                <span style="background:{bucket_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{bucket}</span>
            </td>
        </tr>"""

    attention_items = ""
    if a.get("pending_approvals"):
        attention_items += f'<li>{a["pending_approvals"]} companies pending approval</li>'
    if a.get("hot_leads_no_meeting"):
        attention_items += f'<li>{a["hot_leads_no_meeting"]} positive replies without meeting booked</li>'
    if a.get("unreviewed_objections"):
        attention_items += f'<li>{a["unreviewed_objections"]} objections needing review</li>'
    if a.get("stale_sequences"):
        attention_items += f'<li>{a["stale_sequences"]} stale sequences (>7 days)</li>'

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f9fafb;padding:20px;color:#111827">
<div style="max-width:640px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb">

<!-- Header -->
<div style="background:#1e40af;padding:24px 32px;color:#fff">
    <h1 style="margin:0;font-size:20px;font-weight:600">Daily Pipeline Report</h1>
    <p style="margin:4px 0 0;opacity:0.8;font-size:14px">{report['report_date']}</p>
</div>

<!-- KPI Row -->
<div style="padding:24px 32px;display:flex;gap:16px;border-bottom:1px solid #f3f4f6">
    <div style="flex:1;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#1e40af">{p['total_companies']}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:2px">Total Pipeline</div>
    </div>
    <div style="flex:1;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#16a34a">{o['sent_today']}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:2px">Emails Sent</div>
    </div>
    <div style="flex:1;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#7c3aed">{o['meetings_booked_today']}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:2px">Meetings</div>
    </div>
    <div style="flex:1;text-align:center">
        <div style="font-size:28px;font-weight:700;color:{attention_color}">{attention_count}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:2px">Need Attention</div>
    </div>
</div>

<!-- Pipeline Section -->
<div style="padding:20px 32px;border-bottom:1px solid #f3f4f6">
    <h2 style="font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px">Pipeline</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:13px">
        <span>New today: <strong>{p['new_companies_today']}</strong></span>
        <span>·</span>
        <span>Stage movements: <strong>{p['stage_movements_today']}</strong></span>
        <span>·</span>
        <span>Scored: <strong>{s['scored_today']}</strong></span>
        <span>·</span>
        <span>Avg score: <strong>{s['avg_score_today']}</strong></span>
    </div>
</div>

<!-- Outreach Section -->
<div style="padding:20px 32px;border-bottom:1px solid #f3f4f6">
    <h2 style="font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px">Outreach</h2>
    <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:13px">
        <span>Sent: <strong>{o['sent_today']}</strong></span>
        <span>·</span>
        <span>Replies: <strong>{o['replies_today']}</strong> ({o['reply_rate_today']}%)</span>
        <span>·</span>
        <span>Bounces: <strong>{o['bounces_today']}</strong></span>
        <span>·</span>
        <span>Active sequences: <strong>{o['active_sequences_total']}</strong></span>
    </div>
</div>

<!-- Attention -->
{"" if not attention_items else f'''
<div style="padding:20px 32px;border-bottom:1px solid #f3f4f6;background:#fffbeb">
    <h2 style="font-size:14px;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 8px">Attention Required</h2>
    <ul style="margin:0;padding-left:20px;font-size:13px;color:#78350f">{attention_items}</ul>
</div>
'''}

<!-- Top Opportunities -->
{"" if not top_rows else f'''
<div style="padding:20px 32px">
    <h2 style="font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px">Top Opportunities</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr style="background:#f9fafb">
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase">Company</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase">Score</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase">Priority</th>
        </tr>
        {top_rows}
    </table>
</div>
'''}

<!-- Footer -->
<div style="padding:16px 32px;background:#f9fafb;text-align:center;font-size:11px;color:#9ca3af">
    Sean Lead Agent · Generated {report.get('generated_at', '')}
</div>

</div>
</body>
</html>"""

    return html


async def persist_report(report: dict[str, Any]) -> dict[str, Any]:
    """Save the report to the daily_reports table for historical tracking."""
    db = get_service_client()

    record = {
        "report_date": report["report_date"],
        "generated_at": report["generated_at"],
        "pipeline_total": report["pipeline"]["total_companies"],
        "new_companies": report["pipeline"]["new_companies_today"],
        "stage_movements": report["pipeline"]["stage_movements_today"],
        "scored_today": report["scoring"]["scored_today"],
        "avg_score": report["scoring"]["avg_score_today"],
        "high_value_today": report["scoring"]["high_value_today"],
        "emails_sent": report["outreach"]["sent_today"],
        "replies_received": report["outreach"]["replies_today"],
        "reply_rate": report["outreach"]["reply_rate_today"],
        "meetings_booked": report["outreach"]["meetings_booked_today"],
        "bounces": report["outreach"]["bounces_today"],
        "active_sequences": report["outreach"]["active_sequences_total"],
        "pending_approvals": report["attention_required"]["pending_approvals"],
        "attention_items": sum(report["attention_required"].values()),
        "full_report_json": report,
    }

    result = db.table("daily_reports").upsert(
        record,
        on_conflict="report_date",
    ).execute()

    logger.info(
        "daily_report_persisted",
        date=report["report_date"],
    )

    return result.data[0] if result.data else record


async def generate_and_persist_report(
    report_date: datetime | None = None,
    send_email: bool = False,
) -> dict[str, Any]:
    """End-to-end: collect → format → persist → optionally send."""
    from app.reporting.collector import collect_full_daily_report

    report = await collect_full_daily_report(report_date)
    text_summary = format_text_summary(report)
    html_email = format_html_email(report)

    persisted = await persist_report(report)

    logger.info("daily_report_generated", date=report["report_date"])

    return {
        "report": report,
        "text_summary": text_summary,
        "html_email": html_email,
        "persisted": persisted,
    }
