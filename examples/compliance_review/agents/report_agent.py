#!/usr/bin/env python3
"""
Report Agent - Report generation with attachments.

Demonstrates RFC-0005 (Attachments):
- Creating and attaching files
- Document output generation
- File metadata tracking

Run with:
    python examples/compliance_review/agents/report_agent.py
"""

import asyncio
import base64
import json
import os
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from openintent import Agent, Intent, on_assignment, on_complete


@Agent("report-agent")
class ReportAgent:
    """
    Report generation agent with attachment handling.

    Demonstrates:
    - Creating report attachments
    - Multiple output formats
    - Attachment metadata
    """

    @on_assignment
    async def generate_report(self, intent: Intent) -> dict:
        """
        Generate compliance report with attachments.

        Creates a comprehensive report from all previous phases
        and attaches it to the intent.
        """
        print(f"\n[REPORT] Processing: {intent.title}")

        # Gather all phase data
        state = (
            intent.state.to_dict()
            if hasattr(intent.state, "to_dict")
            else intent.state or {}
        )
        ocr_data = state.get("ocr", {})
        analysis_data = state.get("analysis", {})
        risk_data = state.get("risk", {})

        print("   [INFO] Gathering data from all phases...")
        print(f"   - OCR: {ocr_data.get('status', 'missing')}")
        print(f"   - Analysis: {analysis_data.get('status', 'missing')}")
        print(f"   - Risk: {risk_data.get('status', 'missing')}")

        # Generate report content
        report = self._generate_report_content(
            intent=intent,
            ocr=ocr_data,
            analysis=analysis_data,
            risk=risk_data,
        )

        await asyncio.sleep(2)

        # Create JSON report attachment
        json_report = json.dumps(report, indent=2)
        json_content = base64.b64encode(json_report.encode()).decode()

        try:
            attachment = await self.client.create_attachment(
                intent_id=intent.id,
                filename="compliance_report.json",
                content_type="application/json",
                content=json_content,
                metadata={
                    "generated_by": self.agent_id,
                    "generated_at": datetime.utcnow().isoformat(),
                    "report_type": "compliance_review",
                },
            )
            print(f"   [ATTACH] Created: compliance_report.json (ID: {attachment.id})")
        except Exception as e:
            print(f"   [WARN] Failed to create attachment: {e}")

        # Create markdown summary attachment
        markdown_report = self._generate_markdown_summary(report)
        md_content = base64.b64encode(markdown_report.encode()).decode()

        try:
            attachment2 = await self.client.create_attachment(
                intent_id=intent.id,
                filename="compliance_summary.md",
                content_type="text/markdown",
                content=md_content,
                metadata={
                    "generated_by": self.agent_id,
                    "format": "markdown",
                },
            )
            print(f"   [ATTACH] Created: compliance_summary.md (ID: {attachment2.id})")
        except Exception as e:
            print(f"   [WARN] Failed to create markdown attachment: {e}")

        print("   [OK] Report generation complete")
        print(f"   [OK] Risk Category: {report['summary']['risk_category']}")

        return {
            "report": {
                "status": "complete",
                "agent": self.agent_id,
                "summary": report["summary"],
                "attachments": ["compliance_report.json", "compliance_summary.md"],
                "requires_approval": report["summary"]["risk_category"]
                in ["HIGH", "MEDIUM"],
            }
        }

    def _generate_report_content(
        self, intent: Intent, ocr: dict, analysis: dict, risk: dict
    ) -> dict:
        """Generate the full report content."""
        return {
            "report_id": f"CR-{intent.id[:8].upper()}",
            "generated_at": datetime.utcnow().isoformat(),
            "document": {
                "title": intent.title,
                "description": intent.description,
                "pages": ocr.get("extracted", {}).get("metadata", {}).get("pages", 0),
                "sections": len(ocr.get("extracted", {}).get("sections", [])),
            },
            "analysis": {
                "sections_analyzed": analysis.get("summary", {}).get(
                    "total_sections", 0
                ),
                "issues_found": analysis.get("summary", {}).get("issues_found", 0),
                "sections": analysis.get("sections", []),
            },
            "risk_assessment": {
                "category": risk.get("category", "UNKNOWN"),
                "score": risk.get("average_score", 0),
                "recommendation": risk.get("recommendation", ""),
                "high_risk_sections": risk.get("summary", {}).get(
                    "high_risk_sections", 0
                ),
            },
            "costs": {
                "total_usd": risk.get("summary", {}).get("total_cost_usd", 0),
            },
            "summary": {
                "risk_category": risk.get("category", "UNKNOWN"),
                "total_issues": analysis.get("summary", {}).get("issues_found", 0),
                "recommendation": risk.get("recommendation", "Review required"),
                "processing_agents": [
                    ocr.get("agent"),
                    analysis.get("agent"),
                    risk.get("agent"),
                    "report-agent",
                ],
            },
        }

    def _generate_markdown_summary(self, report: dict) -> str:
        """Generate a markdown summary of the report."""
        summary = report.get("summary", {})
        risk = report.get("risk_assessment", {})

        return f"""# Compliance Review Report

**Report ID:** {report.get("report_id", "N/A")}
**Generated:** {report.get("generated_at", "N/A")}

## Summary

| Metric | Value |
|--------|-------|
| Risk Category | **{summary.get("risk_category", "UNKNOWN")}** |
| Total Issues | {summary.get("total_issues", 0)} |
| Recommendation | {summary.get("recommendation", "N/A")} |

## Document Details

- **Pages:** {report.get("document", {}).get("pages", 0)}
- **Sections:** {report.get("document", {}).get("sections", 0)}

## Risk Assessment

- **Risk Score:** {risk.get("score", 0):.2f}
- **High Risk Sections:** {risk.get("high_risk_sections", 0)}

## Processing Chain

{chr(10).join(f"- {agent}" for agent in summary.get("processing_agents", []) if agent)}

---
*Generated by OpenIntent Compliance Review Pipeline*
"""

    @on_complete
    async def on_done(self, intent: Intent):
        """Called when the report intent completes."""
        print(f"   [DONE] Report completed for: {intent.title}")


if __name__ == "__main__":
    from examples.compliance_review.config import OPENINTENT_API_KEY, OPENINTENT_URL

    print("=" * 60)
    print("OpenIntent Report Agent")
    print("Demonstrates: RFC-0005 (Attachments)")
    print("=" * 60)
    print(f"Server: {OPENINTENT_URL}")
    print("Agent ID: report-agent")
    print("=" * 60)
    print("\nWaiting for report generation assignments...\n")

    ReportAgent.run(base_url=OPENINTENT_URL, api_key=OPENINTENT_API_KEY)
