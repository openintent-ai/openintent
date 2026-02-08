#!/usr/bin/env python3
"""
Compliance Review Coordinator - Orchestrates the full document review workflow.

Demonstrates RFC-0004 (Governance):
- Human approval gates
- Arbitration requests
- Governance decisions
- Policy enforcement

Run with:
    python examples/compliance_review/coordinator.py --document "Contract Agreement Q1 2024"
"""

import argparse
import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from examples.compliance_review.config import OPENINTENT_API_KEY, OPENINTENT_URL
from openintent import (
    Coordinator,
    IntentPortfolio,
    IntentSpec,
    PortfolioSpec,
    on_all_complete,
)


class ComplianceCoordinator(Coordinator):
    """
    Orchestrates the compliance document review workflow.

    Workflow:
    1. OCR Extraction (with retry policy)
    2. Clause Analysis (with leasing)
    3. Risk Assessment (with cost tracking)
    4. Report Generation (with attachments)
    5. Governance Gate (human approval for high-risk)

    Demonstrates all 17 RFCs working together.
    """

    async def plan(
        self, document_name: str, document_description: str = ""
    ) -> PortfolioSpec:
        """
        Create the compliance review workflow plan.

        Returns a PortfolioSpec with all phases and dependencies.
        """
        return PortfolioSpec(
            name=f"Compliance Review: {document_name[:50]}",
            description=document_description
            or f"Full compliance review for {document_name}",
            governance_policy={
                "require_approval_for_high_risk": True,
                "max_cost_usd": 5.00,
                "timeout_hours": 24,
                "escalation_contact": "legal@company.com",
            },
            metadata={
                "document_name": document_name,
                "workflow_type": "compliance_review",
                "rfc_showcase": [
                    "0001",
                    "0002",
                    "0003",
                    "0004",
                    "0005",
                    "0006",
                    "0007",
                    "0008",
                    "0009",
                    "0010",
                    "0011",
                ],
            },
            intents=[
                # Phase 1: OCR Extraction (RFC-0010: Retry Policies)
                IntentSpec(
                    title="Document Extraction",
                    description=f"Extract text and structure from: {document_name}",
                    assign="ocr-agent",
                    constraints=["max_retries:3", "backoff:exponential"],
                    initial_state={
                        "phase": "extraction",
                        "retry_policy": {
                            "max_attempts": 3,
                            "backoff_type": "exponential",
                            "initial_delay_ms": 1000,
                        },
                    },
                ),
                # Phase 2: Clause Analysis (RFC-0003: Leasing)
                IntentSpec(
                    title="Clause Analysis",
                    description="Analyze document clauses for compliance issues",
                    assign="analyzer-agent",
                    depends_on=["Document Extraction"],
                    constraints=["lease_per_section:true"],
                    initial_state={
                        "phase": "analysis",
                        "leasing_enabled": True,
                    },
                ),
                # Phase 3: Risk Assessment (RFC-0009: Cost Tracking)
                IntentSpec(
                    title="Risk Assessment",
                    description="Assess overall document risk and compliance score",
                    assign="risk-agent",
                    depends_on=["Clause Analysis"],
                    constraints=["track_costs:true", "budget_usd:1.00"],
                    initial_state={
                        "phase": "risk",
                        "cost_tracking": True,
                    },
                ),
                # Phase 4: Report Generation (RFC-0005: Attachments)
                IntentSpec(
                    title="Report Generation",
                    description="Generate comprehensive compliance report",
                    assign="report-agent",
                    depends_on=["Risk Assessment"],
                    constraints=["output_formats:json,markdown"],
                    initial_state={
                        "phase": "report",
                        "output_formats": ["json", "markdown"],
                    },
                ),
            ],
        )

    @on_all_complete
    async def finalize(self, portfolio: IntentPortfolio) -> dict:
        """
        Called when all phases complete.

        Checks if governance approval is needed based on risk level.
        """
        print("\n" + "=" * 60)
        print("ALL PHASES COMPLETE")
        print("=" * 60)

        # Collect results from all intents
        results = {}
        final_report = None
        requires_approval = False

        for membership in portfolio.intents or []:
            intent = await self.client.get_intent(membership.intent_id)
            state = (
                intent.state.to_dict()
                if hasattr(intent.state, "to_dict")
                else intent.state or {}
            )
            results[intent.title] = state

            # Check if report phase indicates approval needed
            if "report" in state:
                final_report = state["report"]
                requires_approval = final_report.get("requires_approval", False)

        # Handle governance gate (RFC-0004)
        if requires_approval:
            print("\n[GOVERNANCE] High-risk document detected!")
            print("[GOVERNANCE] Requesting human approval...")

            try:
                # Request arbitration for high-risk documents
                await self.client.request_arbitration(
                    intent_id=portfolio.intents[-1].intent_id,  # Report intent
                    reason="High-risk compliance review requires human approval",
                    requested_by=self.agent_id,
                    context={
                        "risk_category": final_report.get("summary", {}).get(
                            "risk_category"
                        ),
                        "total_issues": final_report.get("summary", {}).get(
                            "total_issues"
                        ),
                        "portfolio_id": portfolio.id,
                    },
                )
                print("[GOVERNANCE] Arbitration requested - awaiting human decision")
            except Exception as e:
                print(f"[GOVERNANCE] Failed to request arbitration: {e}")
        else:
            print("\n[GOVERNANCE] Low-risk document - auto-approved")

        return {
            "portfolio_id": portfolio.id,
            "portfolio_name": portfolio.name,
            "status": "pending_approval" if requires_approval else "approved",
            "requires_human_approval": requires_approval,
            "results": results,
            "summary": final_report.get("summary", {}) if final_report else {},
        }


async def main():
    parser = argparse.ArgumentParser(description="Run compliance document review")
    parser.add_argument("--document", required=True, help="Document name to review")
    parser.add_argument("--description", default="", help="Document description")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    args = parser.parse_args()

    print("=" * 60)
    print("OpenIntent Compliance Review Coordinator")
    print("Demonstrates: RFC-0004 (Governance)")
    print("=" * 60)
    print(f"Document: {args.document}")
    print(f"Server: {OPENINTENT_URL}")
    print("=" * 60)

    # Create coordinator
    coordinator = ComplianceCoordinator(
        agent_id="compliance-coordinator",
        base_url=OPENINTENT_URL,
        api_key=OPENINTENT_API_KEY,
    )

    # Create the plan
    print("\n[PLAN] Creating workflow plan...")
    spec = await coordinator.plan(args.document, args.description)

    print(f"   Portfolio: {spec.name}")
    print(f"   Phases: {len(spec.intents)}")
    for i, intent in enumerate(spec.intents, 1):
        deps = f" (after: {', '.join(intent.depends_on)})" if intent.depends_on else ""
        print(f"   {i}. {intent.title} -> {intent.assign}{deps}")

    print("\n[RUN] Executing workflow...")
    print("   Make sure all agents are running:")
    print("   - ocr-agent")
    print("   - analyzer-agent")
    print("   - risk-agent")
    print("   - report-agent")
    print()

    try:
        result = await coordinator.execute(spec, timeout=args.timeout)

        print("\n" + "=" * 60)
        print("WORKFLOW RESULT")
        print("=" * 60)

        if result.get("requires_human_approval"):
            print("\n[!] PENDING HUMAN APPROVAL")
            print(
                f"    Risk Category: {result.get('summary', {}).get('risk_category', 'UNKNOWN')}"
            )
            print(
                f"    Issues Found: {result.get('summary', {}).get('total_issues', 0)}"
            )
            print("    Use the dashboard to approve or reject.")
        else:
            print("\n[OK] Workflow completed and auto-approved")
            print(
                f"    Risk Category: {result.get('summary', {}).get('risk_category', 'LOW')}"
            )

    except TimeoutError:
        print(f"\n[TIMEOUT] After {args.timeout}s")
        print("   Check that all agents are running!")
    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    asyncio.run(main())
