#!/usr/bin/env python3
"""
OCR Agent - Document extraction with retry policies.

Demonstrates RFC-0010 (Retry Policies):
- Setting retry policies on intents
- Recording failures to event stream
- Configurable retry strategies (exponential backoff)
- Failure threshold handling

Run with:
    python examples/compliance_review/agents/ocr_agent.py
"""

import asyncio
import os
import random
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from openintent import Agent, Intent, on_assignment
from openintent.models import RetryStrategy

# Simulated OCR failures for demo
FAILURE_RATE = 0.4  # 40% chance of transient failure on first attempts
MAX_ATTEMPTS = 3


class TransientOCRError(Exception):
    """Simulated transient OCR failure."""

    pass


@Agent("ocr-agent")
class OCRAgent:
    """
    OCR extraction agent with retry policy handling.

    Demonstrates RFC-0010:
    - Sets retry policy on intent
    - Records failures to event stream
    - Retries with exponential backoff
    - Logs successful completion after retries
    """

    def __init__(self):
        self.attempt_counts = {}  # Track attempts per intent

    @on_assignment
    async def extract(self, intent: Intent) -> dict:
        """
        Extract text from document with retry handling.

        Demonstrates the full retry policy flow:
        1. Set retry policy on intent
        2. Attempt OCR extraction
        3. Record failures on transient errors
        4. Retry with backoff
        5. Complete successfully or fail after max retries
        """
        print(f"\n[OCR] Processing: {intent.title}")
        print(f"   Document: {intent.description}")

        # Track attempts for this intent
        if intent.id not in self.attempt_counts:
            self.attempt_counts[intent.id] = 0

        self.attempt_counts[intent.id] += 1
        attempt = self.attempt_counts[intent.id]

        print(f"   Attempt: {attempt}/{MAX_ATTEMPTS}")

        # Set retry policy on first attempt (RFC-0010)
        if attempt == 1:
            try:
                await self.client.set_retry_policy(
                    intent_id=intent.id,
                    strategy=RetryStrategy.EXPONENTIAL,
                    max_retries=MAX_ATTEMPTS,
                    base_delay_ms=1000,
                    max_delay_ms=30000,
                    failure_threshold=MAX_ATTEMPTS,
                )
                print(
                    f"   [POLICY] Set retry policy: exponential backoff, max {MAX_ATTEMPTS} attempts"
                )
            except Exception as e:
                print(f"   [WARN] Could not set retry policy: {e}")

        # Simulate OCR processing time
        await asyncio.sleep(2)

        # Simulate transient failure (for demo purposes)
        # Decreasing failure rate on later attempts to ensure eventual success
        adjusted_failure_rate = FAILURE_RATE * (1 - (attempt - 1) * 0.3)

        if random.random() < adjusted_failure_rate and attempt < MAX_ATTEMPTS:
            error_msg = f"Transient OCR failure on attempt {attempt}"
            print(f"   [FAIL] {error_msg}")

            # Record the failure (RFC-0010)
            try:
                await self.client.record_failure(
                    intent_id=intent.id,
                    error_type="TransientOCRError",
                    error_message=error_msg,
                    recoverable=True,
                    context={
                        "attempt": attempt,
                        "max_attempts": MAX_ATTEMPTS,
                        "agent": self.agent_id,
                    },
                )
                print("   [RECORD] Failure recorded to event stream")
            except Exception as e:
                print(f"   [WARN] Could not record failure: {e}")

            # Calculate backoff delay (exponential)
            delay_ms = 1000 * (2 ** (attempt - 1))
            delay_sec = min(delay_ms / 1000, 30)  # Cap at 30 seconds
            print(f"   [RETRY] Waiting {delay_sec:.1f}s before retry...")

            await asyncio.sleep(delay_sec)

            # Recursively retry
            return await self.extract(intent)

        # Success - extract content
        extracted_content = {
            "sections": [
                {
                    "id": "section-1",
                    "title": "Definitions",
                    "text": "This Agreement defines the terms and conditions...",
                    "page": 1,
                },
                {
                    "id": "section-2",
                    "title": "Obligations",
                    "text": "The Party agrees to fulfill all obligations...",
                    "page": 2,
                },
                {
                    "id": "section-3",
                    "title": "Liability",
                    "text": "Neither party shall be liable for indirect damages...",
                    "page": 3,
                },
                {
                    "id": "section-4",
                    "title": "Termination",
                    "text": "This agreement may be terminated with 30 days notice...",
                    "page": 4,
                },
            ],
            "metadata": {
                "pages": 4,
                "word_count": 2500,
                "language": "en",
                "document_type": "contract",
            },
        }

        print(f"   [OK] Extracted {len(extracted_content['sections'])} sections")
        print(f"   [OK] Total pages: {extracted_content['metadata']['pages']}")

        if attempt > 1:
            print(f"   [OK] Succeeded after {attempt} attempts (with {attempt - 1} retries)")

        # Clean up attempt tracking
        del self.attempt_counts[intent.id]

        # Return value is auto-patched to intent state
        return {
            "ocr": {
                "status": "complete",
                "agent": self.agent_id,
                "attempts": attempt,
                "retries": attempt - 1,
                "extracted": extracted_content,
            }
        }


if __name__ == "__main__":
    from examples.compliance_review.config import OPENINTENT_API_KEY, OPENINTENT_URL

    print("=" * 60)
    print("OpenIntent OCR Agent")
    print("Demonstrates: RFC-0010 (Retry Policies)")
    print("=" * 60)
    print(f"Server: {OPENINTENT_URL}")
    print("Agent ID: ocr-agent")
    print("Retry Strategy: Exponential backoff")
    print(f"Max Attempts: {MAX_ATTEMPTS}")
    print("=" * 60)
    print("\nWaiting for document extraction assignments...\n")

    OCRAgent.run(base_url=OPENINTENT_URL, api_key=OPENINTENT_API_KEY)
