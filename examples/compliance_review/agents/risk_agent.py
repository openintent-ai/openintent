#!/usr/bin/env python3
"""
Risk Agent - Risk assessment with cost tracking.

Demonstrates RFC-0009 (Cost Tracking):
- Recording costs per intent
- Cost types (compute, API, storage)
- Budget tracking and summaries

Run with:
    python examples/compliance_review/agents/risk_agent.py
"""

import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from openintent import Agent, Intent, on_assignment


@Agent("risk-agent")
class RiskAgent:
    """
    Risk assessment agent with cost tracking.

    Demonstrates:
    - Recording compute costs
    - API call costs
    - Cost summaries per intent
    """

    @on_assignment
    async def assess_risk(self, intent: Intent) -> dict:
        """
        Assess document risk with full cost tracking.

        Records all computational and API costs for
        transparency and budget management.
        """
        print(f"\n[RISK] Processing: {intent.title}")

        # Get analysis from previous phase
        state = (
            intent.state.to_dict()
            if hasattr(intent.state, "to_dict")
            else intent.state or {}
        )
        analysis = state.get("analysis", {})
        sections = analysis.get("sections", [])

        if not sections:
            print("   [WARN] No analysis data found")
            return {"risk": {"status": "skipped", "reason": "no_analysis"}}

        print(f"   [INFO] Assessing risk for {len(sections)} sections")

        # Track costs for this assessment
        total_cost = 0.0

        # Simulate compute cost
        compute_cost = 0.002  # $0.002 per section
        await self._record_cost(
            intent.id,
            "compute",
            compute_cost * len(sections),
            f"Risk assessment compute for {len(sections)} sections",
        )
        total_cost += compute_cost * len(sections)

        # Simulate risk model API cost
        api_cost = 0.01  # $0.01 per API call
        await self._record_cost(
            intent.id, "api", api_cost, "Risk model inference API call"
        )
        total_cost += api_cost

        # Perform risk assessment
        await asyncio.sleep(2)

        risk_scores = []
        total_issues = 0
        high_risk_count = 0

        for section in sections:
            issues = section.get("issues", [])
            total_issues += len(issues)

            # Calculate section risk score
            risk_score = self._calculate_risk_score(issues)
            if risk_score >= 0.7:
                high_risk_count += 1

            risk_scores.append(
                {
                    "section_id": section.get("section_id"),
                    "title": section.get("title"),
                    "risk_score": risk_score,
                    "issue_count": len(issues),
                    "high_severity": sum(
                        1 for i in issues if i.get("severity") == "high"
                    ),
                }
            )

        # Calculate overall risk
        avg_risk = (
            sum(r["risk_score"] for r in risk_scores) / len(risk_scores)
            if risk_scores
            else 0
        )

        # Determine risk category
        if avg_risk >= 0.7:
            risk_category = "HIGH"
            recommendation = "Requires legal review before proceeding"
        elif avg_risk >= 0.4:
            risk_category = "MEDIUM"
            recommendation = "Review flagged sections before approval"
        else:
            risk_category = "LOW"
            recommendation = "Standard review process recommended"

        print(f"   [OK] Risk Category: {risk_category}")
        print(f"   [OK] Average Score: {avg_risk:.2f}")
        print(f"   [OK] Total Issues: {total_issues}")
        print(f"   [COST] Total: ${total_cost:.4f}")

        return {
            "risk": {
                "status": "complete",
                "agent": self.agent_id,
                "category": risk_category,
                "average_score": round(avg_risk, 3),
                "recommendation": recommendation,
                "sections": risk_scores,
                "summary": {
                    "total_issues": total_issues,
                    "high_risk_sections": high_risk_count,
                    "total_cost_usd": round(total_cost, 4),
                },
            }
        }

    async def _record_cost(
        self, intent_id: str, cost_type: str, amount: float, description: str
    ):
        """Record a cost entry for the intent."""
        try:
            await self.client.record_cost(
                intent_id=intent_id,
                cost_type=cost_type,
                amount=amount,
                currency="USD",
                description=description,
            )
            print(f"   [COST] Recorded: ${amount:.4f} ({cost_type})")
        except Exception as e:
            print(f"   [WARN] Failed to record cost: {e}")

    def _calculate_risk_score(self, issues: list) -> float:
        """Calculate risk score from issues (0-1 scale)."""
        if not issues:
            return 0.0

        severity_weights = {
            "high": 0.4,
            "medium": 0.2,
            "low": 0.1,
        }

        total_weight = sum(
            severity_weights.get(issue.get("severity", "low"), 0.1) for issue in issues
        )

        # Normalize to 0-1 scale (cap at 1.0)
        return min(total_weight, 1.0)


if __name__ == "__main__":
    from examples.compliance_review.config import OPENINTENT_API_KEY, OPENINTENT_URL

    print("=" * 60)
    print("OpenIntent Risk Agent")
    print("Demonstrates: RFC-0009 (Cost Tracking)")
    print("=" * 60)
    print(f"Server: {OPENINTENT_URL}")
    print("Agent ID: risk-agent")
    print("=" * 60)
    print("\nWaiting for risk assessment assignments...\n")

    RiskAgent.run(base_url=OPENINTENT_URL, api_key=OPENINTENT_API_KEY)
