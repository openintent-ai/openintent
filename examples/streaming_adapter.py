#!/usr/bin/env python3
"""
OpenIntent Streaming Adapter Example

This example demonstrates how to handle streaming LLM engagements while
conforming to the OpenIntent protocol. Key considerations:

1. **Performance**: Stream tokens to user immediately, batch state updates
2. **Protocol Conformance**: Log events at semantic boundaries, not per-token
3. **Cost Tracking**: Accumulate token counts, record cost at completion
4. **Lease Management**: Hold scope lease during streaming for collision prevention

Architecture:
    User Request → OpenIntent → Agent → LLM (streaming) → User
                      ↓
              State updates batched
              Events at semantic points
              Costs recorded at completion

Run:
    export OPENAI_API_KEY=your-key
    export OPENINTENT_API_URL=http://localhost:5000
    python streaming_adapter.py
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Callable, Optional

from openai import AsyncOpenAI

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openintent import (
    AsyncOpenIntentClient,
    EventType,
    IntentStatus,
)


@dataclass
class StreamMetrics:
    """Track streaming performance metrics."""
    start_time: float = 0
    first_token_time: float = 0
    end_time: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    chunks_received: int = 0
    
    @property
    def time_to_first_token(self) -> float:
        """TTFT - critical UX metric."""
        if self.first_token_time and self.start_time:
            return self.first_token_time - self.start_time
        return 0
    
    @property
    def total_duration(self) -> float:
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return 0
    
    @property
    def tokens_per_second(self) -> float:
        if self.total_duration > 0:
            return self.output_tokens / self.total_duration
        return 0


class StreamingAdapter:
    """
    Adapter for streaming LLM responses while conforming to OpenIntent protocol.
    
    Key Design Principles:
    1. NEVER block on protocol operations during token streaming
    2. Batch state updates at semantic boundaries (sentences, paragraphs)
    3. Use background tasks for non-critical protocol updates
    4. Record costs only after stream completes (final token count)
    5. Hold lease to prevent scope collisions during generation
    """
    
    def __init__(
        self,
        agent_id: str,
        openintent_url: str = None,
        openintent_key: str = None,
        state_update_interval: float = 2.0,  # Batch state updates every 2s
    ):
        self.agent_id = agent_id
        self.openai = AsyncOpenAI()
        self.intent_client: AsyncOpenIntentClient = None
        self.state_update_interval = state_update_interval
        
        self._openintent_url = openintent_url or os.getenv(
            "OPENINTENT_API_URL", "http://localhost:5000"
        )
        self._openintent_key = openintent_key or os.getenv(
            "OPENINTENT_API_KEY", "dev-user-key"
        )
    
    async def connect(self):
        """Initialize connection to OpenIntent server."""
        self.intent_client = AsyncOpenIntentClient(
            base_url=self._openintent_url,
            api_key=self._openintent_key,
            agent_id=self.agent_id,
        )
    
    async def disconnect(self):
        """Close connection."""
        if self.intent_client:
            await self.intent_client.close()
    
    async def stream_completion(
        self,
        intent_id: str,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o",
        on_token: Callable[[str], None] = None,
    ) -> tuple[str, StreamMetrics]:
        """
        Stream LLM completion while maintaining protocol conformance.
        
        Performance Strategy:
        - Yield tokens immediately (no blocking)
        - Batch state updates on timer
        - Record events at completion only
        - Track costs for final recording
        
        Args:
            intent_id: The intent this generation is for
            prompt: User prompt
            system_prompt: System instructions
            model: OpenAI model to use
            on_token: Optional callback for each token (for UI streaming)
            
        Returns:
            Tuple of (complete_response, metrics)
        """
        metrics = StreamMetrics(start_time=time.time())
        accumulated_text = ""
        last_state_update = time.time()
        
        # Acquire lease to prevent collision during generation
        lease = await self.intent_client.acquire_lease(
            intent_id,
            scope="generation",
            duration_seconds=300,
        )
        
        try:
            # Mark generation started (one state update, not blocking)
            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "generation_status": "streaming",
                    "generation_started_at": datetime.now().isoformat(),
                }
            )
            
            # Stream from OpenAI
            stream = await self.openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                stream_options={"include_usage": True},
            )
            
            async for chunk in stream:
                # Track first token timing
                if metrics.first_token_time == 0 and chunk.choices:
                    metrics.first_token_time = time.time()
                
                metrics.chunks_received += 1
                
                # Extract content
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    accumulated_text += token
                    
                    # Yield to callback immediately (no blocking!)
                    if on_token:
                        on_token(token)
                
                # Extract usage from final chunk
                if chunk.usage:
                    metrics.input_tokens = chunk.usage.prompt_tokens
                    metrics.output_tokens = chunk.usage.completion_tokens
                
                # Batch state updates (every N seconds, non-blocking background)
                now = time.time()
                if now - last_state_update > self.state_update_interval:
                    # Fire-and-forget state update (don't await in hot path)
                    asyncio.create_task(
                        self._update_streaming_progress(
                            intent_id, 
                            len(accumulated_text),
                            metrics.chunks_received,
                        )
                    )
                    last_state_update = now
            
            metrics.end_time = time.time()
            
            # Final state update with complete response
            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "generation_status": "completed",
                    "generation_completed_at": datetime.now().isoformat(),
                    "generation_output": accumulated_text,
                    "generation_metrics": {
                        "ttft_ms": round(metrics.time_to_first_token * 1000, 2),
                        "total_ms": round(metrics.total_duration * 1000, 2),
                        "tokens_per_second": round(metrics.tokens_per_second, 2),
                    },
                }
            )
            
            # Log completion event (semantic boundary)
            await self.intent_client.log_event(
                intent_id,
                EventType.COMMENT,
                {
                    "message": "Generation completed",
                    "model": model,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "ttft_ms": round(metrics.time_to_first_token * 1000, 2),
                }
            )
            
            # Record cost (only after we know final token count)
            await self.intent_client.record_cost(
                intent_id,
                cost_type="tokens",
                amount=metrics.input_tokens + metrics.output_tokens,
                unit="tokens",
                provider="openai",
                metadata={
                    "model": model,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                }
            )
            
            return accumulated_text, metrics
            
        finally:
            # Always release lease
            await self.intent_client.release_lease(intent_id, lease.id)
    
    async def _update_streaming_progress(
        self,
        intent_id: str,
        chars_generated: int,
        chunks_received: int,
    ):
        """
        Background task to update streaming progress.
        Runs outside the hot token path to avoid blocking.
        """
        try:
            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "generation_progress": {
                        "chars": chars_generated,
                        "chunks": chunks_received,
                        "updated_at": datetime.now().isoformat(),
                    }
                }
            )
        except Exception:
            # Don't fail streaming on state update errors
            pass
    
    async def stream_with_async_generator(
        self,
        intent_id: str,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o",
    ) -> AsyncIterator[str]:
        """
        Alternative API: Yield tokens as async generator.
        
        Usage:
            async for token in adapter.stream_with_async_generator(intent_id, prompt):
                print(token, end="", flush=True)
        """
        metrics = StreamMetrics(start_time=time.time())
        accumulated_text = ""
        
        lease = await self.intent_client.acquire_lease(
            intent_id, scope="generation", duration_seconds=300
        )
        
        try:
            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id, intent.version,
                {"generation_status": "streaming"}
            )
            
            stream = await self.openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                stream_options={"include_usage": True},
            )
            
            async for chunk in stream:
                if metrics.first_token_time == 0 and chunk.choices:
                    metrics.first_token_time = time.time()
                
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    accumulated_text += token
                    yield token  # Immediate yield, no blocking
                
                if chunk.usage:
                    metrics.output_tokens = chunk.usage.completion_tokens
            
            metrics.end_time = time.time()
            
            # Final updates after stream completes
            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id, intent.version,
                {
                    "generation_status": "completed",
                    "generation_output": accumulated_text,
                }
            )
            
            await self.intent_client.record_cost(
                intent_id, "tokens", metrics.output_tokens, "tokens", "openai"
            )
            
        finally:
            await self.intent_client.release_lease(intent_id, lease.id)


async def demo_streaming():
    """Demonstrate streaming with OpenIntent protocol conformance."""
    
    print("=" * 60)
    print("OpenIntent Streaming Adapter Demo")
    print("=" * 60)
    
    adapter = StreamingAdapter(agent_id="streaming-agent")
    await adapter.connect()
    
    try:
        # Create intent for this generation task
        intent = await adapter.intent_client.create_intent(
            title="Streaming Generation Demo",
            description="Demonstrate streaming LLM with protocol conformance",
            initial_state={"task": "generation"},
        )
        print(f"\nCreated intent: {intent.id}")
        
        # Stream with real-time output
        print("\n--- Streaming Response ---\n")
        
        def print_token(token: str):
            print(token, end="", flush=True)
        
        response, metrics = await adapter.stream_completion(
            intent.id,
            prompt="Explain in 2-3 sentences why streaming is important for LLM UX.",
            on_token=print_token,
        )
        
        print("\n\n--- Metrics ---")
        print(f"Time to first token: {metrics.time_to_first_token * 1000:.0f}ms")
        print(f"Total duration: {metrics.total_duration * 1000:.0f}ms")
        print(f"Tokens/second: {metrics.tokens_per_second:.1f}")
        print(f"Total tokens: {metrics.input_tokens + metrics.output_tokens}")
        
        # Complete the intent
        final = await adapter.intent_client.get_intent(intent.id)
        await adapter.intent_client.set_status(
            intent.id, final.version, IntentStatus.COMPLETED
        )
        
        # Show recorded costs
        costs = await adapter.intent_client.get_costs(intent.id)
        print(f"\nRecorded costs: {costs}")
        
    finally:
        await adapter.disconnect()


async def demo_async_generator():
    """Demonstrate async generator streaming API."""
    
    print("\n" + "=" * 60)
    print("Async Generator Streaming Demo")
    print("=" * 60)
    
    adapter = StreamingAdapter(agent_id="generator-agent")
    await adapter.connect()
    
    try:
        intent = await adapter.intent_client.create_intent(
            title="Async Generator Demo",
            description="Stream using async generator pattern",
        )
        
        print("\n--- Streaming via Async Generator ---\n")
        
        async for token in adapter.stream_with_async_generator(
            intent.id,
            prompt="What is the capital of France? Answer in one sentence.",
        ):
            print(token, end="", flush=True)
        
        print("\n")
        
    finally:
        await adapter.disconnect()


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable required")
        print("Set it with: export OPENAI_API_KEY=your-key")
        exit(1)
    
    asyncio.run(demo_streaming())
    asyncio.run(demo_async_generator())
