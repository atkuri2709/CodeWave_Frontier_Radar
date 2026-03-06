"""Final Agent — Digest Compiler + PDF + Email Sender.

Steps per spec:
1. Deduplicate findings (same URL, same diff_hash)
2. Cluster by topic + entity (release / research / benchmark)
3. Rank by impact & relevance (weighted scoring)
4. Generate narrative: exec summary (top 7), "What changed since yesterday", "Why it matters to us"
5. Render PDF (brandable header/footer, tables, clickable citations)
6. Send email: inline bullets, PDF attached, link to dashboard run
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import get_settings
from app.db.models import Digest as DigestModel, EmailRecipient, Finding
from app.schemas.finding import FindingOut
from app.services.email_service import EmailService
from app.services.pdf_generator import PDFGenerator

logger = logging.getLogger(__name__)


def _resolve_pdf_path(pdf_path: Optional[str], settings) -> Optional[Path]:
    """Resolve digest PDF to an absolute path that exists."""
    if not pdf_path:
        return None
    p = Path(pdf_path)
    if p.is_absolute():
        return p if p.exists() else None
    cwd_path = Path.cwd() / p
    if cwd_path.exists():
        return cwd_path
    storage = Path(settings.local_storage_path)
    if not storage.is_absolute():
        storage = Path.cwd() / storage
    storage_path = storage / Path(pdf_path).name
    return storage_path if storage_path.exists() else None


def _section_key(cat: str) -> str:
    c = (cat or "release").lower()
    if c in ("release", "research", "benchmark"):
        return c
    return "other"


class DigestAgent(BaseAgent):
    agent_id = "digest"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.pdf = PDFGenerator()
        self.email = EmailService()

    async def run(self, context: AgentContext) -> AgentResult:
        run_id = context.run_id
        settings = get_settings()
        result = await self.db.execute(
            select(Finding)
            .where(Finding.run_id == run_id)
            .order_by(
                Finding.impact_score.desc().nullslast(), Finding.confidence.desc()
            )
        )
        findings_orm = result.scalars().all()
        findings_out = [
            FindingOut(
                id=f.id,
                title=f.title,
                date_detected=f.date_detected,
                source_url=f.source_url,
                publisher=f.publisher,
                category=f.category,
                summary_short=f.summary_short,
                summary_long=f.summary_long,
                why_it_matters=f.why_it_matters,
                evidence=f.evidence,
                confidence=f.confidence,
                tags=f.tags or [],
                entities=f.entities or [],
                diff_hash=f.diff_hash,
                agent_id=f.agent_id,
                run_id=f.run_id,
                created_at=f.created_at or datetime.now(timezone.utc),
            )
            for f in findings_orm
        ]

        # Cluster by section: release, research, benchmark, other
        findings_by_section: Dict[str, List[FindingOut]] = {
            "release": [],
            "research": [],
            "benchmark": [],
            "other": [],
        }
        for fo in findings_out:
            key = _section_key(fo.category)
            findings_by_section.setdefault(key, []).append(fo)

        # Section counts for the "what changed" summary
        n_release = len(findings_by_section.get("release") or [])
        n_research = len(findings_by_section.get("research") or [])
        n_benchmark = len(findings_by_section.get("benchmark") or [])
        n_other = len(findings_by_section.get("other") or [])
        total = len(findings_out)

        # Top 7 by impact (already sorted)
        top7 = findings_out[:7]
        top_ids = [fo.id for fo in top7]

        # Executive summary: detailed narrative with full summaries
        if top7:
            exec_lines = [
                f"Today's intelligence scan captured {total} findings across {len([k for k, v in findings_by_section.items() if v])} categories. The top {len(top7)} developments are:\n"
            ]
            for i, fo in enumerate(top7, 1):
                summary = fo.summary_short or fo.title
                exec_lines.append(f"{i}. {fo.title}")
                if fo.publisher:
                    exec_lines.append(
                        f"   Source: {fo.publisher} | Confidence: {fo.confidence:.0%}"
                    )
                exec_lines.append(f"   {summary}")
                if fo.why_it_matters:
                    exec_lines.append(f"   Why it matters: {fo.why_it_matters}")
                exec_lines.append("")
            exec_summary = "\n".join(exec_lines)
        else:
            exec_summary = "No new updates today."

        # "What changed since yesterday"
        if total > 0:
            parts = []
            if n_release:
                parts.append(
                    f"{n_release} release update{'s' if n_release != 1 else ''}"
                )
            if n_research:
                parts.append(
                    f"{n_research} research publication{'s' if n_research != 1 else ''}"
                )
            if n_benchmark:
                parts.append(
                    f"{n_benchmark} benchmark update{'s' if n_benchmark != 1 else ''}"
                )
            if n_other:
                parts.append(f"{n_other} other update{'s' if n_other != 1 else ''}")
            what_changed = f"This run captured {total} findings: {', '.join(parts)}."

            top_entities = set()
            for fo in findings_out[:15]:
                top_entities.update(fo.entities or [])
            if top_entities:
                what_changed += (
                    f" Key entities mentioned: {', '.join(sorted(top_entities)[:12])}."
                )
        else:
            what_changed = "No new changes detected since the last run."

        # "Why it matters to us"
        if top7:
            impact_tags = set()
            impact_entities = set()
            for fo in top7:
                impact_tags.update(fo.tags or [])
                impact_entities.update(fo.entities or [])
            parts = []
            if impact_tags:
                parts.append(f"Key themes: {', '.join(sorted(impact_tags)[:10])}.")
            if impact_entities:
                parts.append(
                    f"Organizations involved: {', '.join(sorted(impact_entities)[:10])}."
                )
            parts.append(
                "Review the full report for source links, evidence, and confidence scores."
            )
            why_it_matters = " ".join(parts)
        else:
            why_it_matters = ""

        report_date = datetime.now(timezone.utc)
        pdf_path = self.pdf.generate(
            run_id=run_id,
            report_date=report_date,
            executive_summary=exec_summary,
            what_changed=what_changed,
            why_it_matters=why_it_matters,
            findings_by_section=findings_by_section,
            top_findings=top7,
        )
        digest = DigestModel(
            run_id=run_id,
            pdf_path=pdf_path,
            executive_summary=exec_summary,
            top_finding_ids=top_ids,
            recipients=[],
        )
        self.db.add(digest)
        await self.db.flush()

        pdf_path_obj = _resolve_pdf_path(pdf_path, settings)
        if not pdf_path_obj or not pdf_path_obj.exists():
            logger.warning(
                "Digest PDF file not found at %s; email will not have attachment.",
                pdf_path,
            )

        # Load recipients from DB then env fallback
        result = await self.db.execute(
            select(EmailRecipient.email).order_by(EmailRecipient.id)
        )
        recipients = [r[0] for r in result.all()] or (settings.email_recipients or [])

        # Build email content
        date_str = report_date.strftime("%B %d, %Y")
        subject = f"Frontier AI Radar — {date_str}"
        dashboard_url = f"{settings.dashboard_base_url}/runs/{run_id}"

        body_bullets = (
            "\n".join(f"• {fo.title}" for fo in top7)
            if top7
            else "No new updates today."
        )
        body_plain = (
            f"Frontier AI Radar — {date_str}\n\n"
            f"What changed since yesterday\n{what_changed}\n\n"
            f"Top updates today\n{body_bullets}\n\n"
            f"Why it matters\n{why_it_matters}\n\n"
            f"Full report attached.\n"
            f"View dashboard: {dashboard_url}\n"
        )
        bullet_items = (
            "".join(f"<li>{fo.title}</li>" for fo in top7)
            if top7
            else "<li>No new updates today.</li>"
        )
        body_html = (
            f"<h2>Frontier AI Radar — {date_str}</h2>"
            f"<h3>What changed since yesterday</h3><p>{what_changed}</p>"
            f"<h3>Top updates today</h3><ul>{bullet_items}</ul>"
            f"<h3>Why it matters to us</h3><p>{why_it_matters}</p>"
            f"<p>Full report attached.</p>"
            f'<p><a href="{dashboard_url}">View dashboard &rarr; Run #{run_id}</a></p>'
        )

        sent = False
        if recipients:
            if settings.smtp_host and settings.smtp_user:
                if pdf_path_obj and pdf_path_obj.exists():
                    sent = await self.email.send_digest(
                        recipients,
                        f"{subject} — Top AI releases, research & benchmark updates",
                        body_html,
                        body_plain,
                        pdf_path_obj,
                        attachment_filename=f"frontier_ai_radar_{report_date.strftime('%Y_%m_%d')}_run{run_id}.pdf",
                    )
                    if sent:
                        digest.sent_at = datetime.now(timezone.utc)
                        digest.recipients = recipients
                        logger.info(
                            "Digest email sent to %s recipients: %s",
                            len(recipients),
                            recipients,
                        )
                    else:
                        logger.warning(
                            "Digest email send failed (check SMTP settings)."
                        )
                else:
                    logger.warning(
                        "Digest email skipped: PDF file not found for attachment."
                    )
            else:
                logger.warning(
                    "Digest email skipped: SMTP not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env). "
                    "Recipients would be: %s",
                    recipients,
                )
        else:
            logger.info("No email recipients configured; digest PDF saved only.")

        try:
            size_kb = (
                pdf_path_obj.stat().st_size / 1024
                if pdf_path_obj and pdf_path_obj.exists()
                else 0
            )
            logger.info(
                "Digest generated. PDF size: %.1f KB. Email sent: %s (%s recipients).",
                size_kb,
                sent,
                len(recipients),
            )
        except Exception:
            logger.info(
                "Digest generated. Email sent: %s (%s recipients).",
                sent,
                len(recipients),
            )
        await self.db.flush()
        return AgentResult(
            agent_id=self.agent_id, findings=[], status="success", pages_processed=0
        )
