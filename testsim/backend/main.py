import asyncio
import json
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

import anthropic
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import run_agents_parallel
from personas import sample_personas

app = FastAPI(title="BlitzTest API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


async def simulate_stream(url: str) -> AsyncGenerator[str, None]:
    # Queues let the agent callbacks push events into the stream
    queue: asyncio.Queue = asyncio.Queue()

    async def on_start(persona):
        await queue.put(
            sse_event(
                "persona_start",
                {
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "persona_initials": persona.initials,
                    "description": persona.description,
                },
            )
        )

    async def on_done(persona, result):
        await queue.put(sse_event("persona_done", {"result": result}))

    yield sse_event("status", {"message": f"Starting simulation for {url}"})

    personas = sample_personas(500)

    yield sse_event(
        "scraped",
        {
            "url": url,
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "initials": p.initials,
                    "description": p.description,
                }
                for p in personas
            ],
        },
    )

    # Run agents in background; drain queue as events arrive
    agent_task = asyncio.create_task(
        run_agents_parallel(personas, url, on_start=on_start, on_done=on_done)
    )

    finished_agents = 0
    total = len(personas)

    while finished_agents < total or not queue.empty():
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.1)
            yield event
            if '"persona_done"' in event or '"type": "persona_done"' in event:
                finished_agents += 1
        except asyncio.TimeoutError:
            if agent_task.done():
                # Drain any remaining events
                while not queue.empty():
                    yield await queue.get()
                break

    results = await agent_task

    # Synthesize findings with Claude
    yield sse_event("status", {"message": "Synthesizing findings with Claude..."})

    synthesis = await synthesize_findings(url, results)

    yield sse_event(
        "complete",
        {
            "url": url,
            "results": results,
            "synthesis": synthesis,
        },
    )


async def synthesize_findings(url: str, results: list) -> dict:
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    summaries = []
    for r in results:
        summaries.append(
            f"Persona: {r['persona_name']}\n"
            f"Converted: {r['converted']}\n"
            f"Friction points: {', '.join(r['friction_points']) if r['friction_points'] else 'None'}\n"
            f"Drop-off reason: {r['drop_off_reason'] or 'N/A'}\n"
            f"A/B suggestion: {r['ab_test_suggestion']}\n"
            f"Journey: {' → '.join(r['journey_steps'][:5]) if r['journey_steps'] else 'No steps recorded'}"
        )

    prompt = f"""You analyzed an ecommerce site ({url}) using {len(results)} shopper personas.

Here are their findings:

{chr(10).join(f'--- Agent {i+1} ---{chr(10)}{s}' for i, s in enumerate(summaries))}

Based on these findings, produce a prioritized list of A/B test recommendations.
Return ONLY a JSON object with this structure:
{{
  "summary": "<2-3 sentence overview of main issues found>",
  "conversion_rate": "<X of Y personas converted>",
  "top_issues": ["<issue 1>", "<issue 2>", "<issue 3>"],
  "ab_tests": [
    {{
      "rank": 1,
      "title": "<test title>",
      "hypothesis": "<what you expect to improve and why>",
      "variant": "<what to change>",
      "personas_affected": ["<persona name>", ...],
      "priority": "high|medium|low"
    }}
  ]
}}
"""

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    # Extract JSON
    import re

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"summary": raw, "ab_tests": [], "top_issues": [], "conversion_rate": "unknown"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/simulate")
async def simulate(url: str = Query(..., description="Ecommerce URL to analyze")):
    return StreamingResponse(
        simulate_stream(url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
