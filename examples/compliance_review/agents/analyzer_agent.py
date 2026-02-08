#!/usr/bin/env python3
"""
Analyzer Agent - Clause analysis with exclusive leasing.

Demonstrates RFC-0003 (Leasing):
- Exclusive scope ownership
- Lease acquisition and release
- Collision prevention

Run with:
    python examples/compliance_review/agents/analyzer_agent.py
"""

import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from openintent import Agent, Intent, on_assignment


@Agent("analyzer-agent")
class AnalyzerAgent:
    """
    Document analyzer with lease-based exclusive access.

    Demonstrates:
    - Acquiring leases for document sections
    - Exclusive access prevents conflicts
    - Automatic lease release on completion
    """

    @on_assignment
    async def analyze(self, intent: Intent) -> dict:
        """
        Analyze document sections with exclusive leasing.

        Each section is leased before analysis to prevent
        concurrent modifications by other agents.
        """
        print(f"\n[ANALYZER] Processing: {intent.title}")

        # Get extracted content from OCR phase
        state = intent.state.to_dict() if hasattr(intent.state, "to_dict") else intent.state or {}
        ocr_data = state.get("ocr", {})
        extracted = ocr_data.get("extracted", {})
        sections = extracted.get("sections", [])

        if not sections:
            print("   [WARN] No sections found from OCR phase")
            return {"analysis": {"status": "skipped", "reason": "no_sections"}}

        print(f"   [INFO] Analyzing {len(sections)} sections")

        analyzed_sections = []

        for section in sections:
            section_id = section.get("id", "unknown")
            section_title = section.get("title", "Untitled")

            # Acquire lease for this section (exclusive access)
            lease_scope = f"section:{section_id}"
            print(f"   [LEASE] Acquiring lease for: {lease_scope}")

            try:
                # In real implementation, use: async with self.lease(intent.id, lease_scope):
                # For demo, simulate the lease acquisition
                lease = await self.client.acquire_lease(
                    intent_id=intent.id,
                    scope=lease_scope,
                    holder_agent_id=self.agent_id,
                    ttl_seconds=60,
                )
                print(f"   [LEASE] Acquired: {lease.id}")

                # Simulate analysis with exclusive access
                await asyncio.sleep(0.5)

                # Analyze the section
                analysis = self._analyze_section(section)
                analyzed_sections.append(analysis)

                print(f"   [OK] Analyzed: {section_title}")

                # Release lease
                await self.client.release_lease(intent.id, lease.id)
                print(f"   [LEASE] Released: {lease_scope}")

            except Exception as e:
                print(f"   [ERROR] Failed to analyze {section_title}: {e}")
                analyzed_sections.append(
                    {
                        "section_id": section_id,
                        "title": section_title,
                        "status": "error",
                        "error": str(e),
                    }
                )

        print(f"   [OK] Analysis complete: {len(analyzed_sections)} sections")

        return {
            "analysis": {
                "status": "complete",
                "agent": self.agent_id,
                "sections": analyzed_sections,
                "summary": {
                    "total_sections": len(analyzed_sections),
                    "issues_found": sum(1 for s in analyzed_sections if s.get("issues")),
                },
            }
        }

    def _analyze_section(self, section: dict) -> dict:
        """Analyze a single section for compliance issues."""
        section_id = section.get("id", "unknown")
        title = section.get("title", "Untitled")
        text = section.get("text", "")

        # Simulated analysis results
        issues = []

        # Check for common compliance issues
        if "liability" in title.lower():
            issues.append(
                {
                    "type": "liability_clause",
                    "severity": "medium",
                    "description": "Liability limitation clause requires legal review",
                }
            )

        if "terminate" in text.lower() or "termination" in title.lower():
            issues.append(
                {
                    "type": "termination_clause",
                    "severity": "low",
                    "description": "Standard termination clause detected",
                }
            )

        if "indirect" in text.lower() and "damages" in text.lower():
            issues.append(
                {
                    "type": "indirect_damages",
                    "severity": "high",
                    "description": "Indirect damages exclusion may conflict with policy",
                }
            )

        return {
            "section_id": section_id,
            "title": title,
            "status": "analyzed",
            "issues": issues,
            "risk_indicators": len(issues),
        }


if __name__ == "__main__":
    from examples.compliance_review.config import OPENINTENT_API_KEY, OPENINTENT_URL

    print("=" * 60)
    print("OpenIntent Analyzer Agent")
    print("Demonstrates: RFC-0003 (Leasing)")
    print("=" * 60)
    print(f"Server: {OPENINTENT_URL}")
    print("Agent ID: analyzer-agent")
    print("=" * 60)
    print("\nWaiting for analysis assignments...\n")

    AnalyzerAgent.run(base_url=OPENINTENT_URL, api_key=OPENINTENT_API_KEY)
