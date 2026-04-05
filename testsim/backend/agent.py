import json
import os
import re
import asyncio
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent
from browser_use.llm import ChatAnthropic
from browser_use.browser.profile import BrowserProfile

from personas import Persona


def build_task(persona: Persona, url: str) -> str:
    return f"""
{persona.system_prompt}

Your task: Visit {url} and shop the site as the persona described above.

Steps to follow:
1. Land on the homepage and note first impressions.
2. Browse at least two product categories or use the search bar.
3. Open at least one product detail page.
4. Attempt to add an item to the cart and proceed toward checkout.
5. Go as far through checkout as you can without placing a real order.

As you browse, note every friction point, confusion, or moment you felt like leaving.

When you are done, output ONLY a JSON object (no other text) with exactly these fields:
{{
  "journey_steps": ["<step 1 description>", "<step 2 description>", ...],
  "converted": true or false,
  "friction_points": ["<issue 1>", "<issue 2>", ...],
  "drop_off_reason": "<reason you did not complete purchase, or null if converted>",
  "ab_test_suggestion": "<one specific A/B test this persona's experience suggests>"
}}
""".strip()


def extract_json_from_result(raw: str) -> Dict[str, Any]:
    """Pull the JSON block out of whatever the agent returned."""
    # Try to find a JSON object in the string
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def run_persona_agent(persona: Persona, url: str) -> Dict[str, Any]:
    """Run a Browser Use agent for one persona and return structured results."""
    llm = ChatAnthropic(model="claude-sonnet-4-20250514")
    task = build_task(persona, url)

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=BrowserProfile(headless=True),
    )

    try:
        result = await agent.run()
        # Browser Use returns AgentHistoryList; get the final text output
        raw_output = ""
        if hasattr(result, "final_result") and callable(result.final_result):
            raw_output = result.final_result() or ""
        elif hasattr(result, "__str__"):
            raw_output = str(result)

        data = extract_json_from_result(raw_output)

        return {
            "persona_id": persona.id,
            "persona_name": persona.name,
            "persona_initials": persona.initials,
            "journey_steps": data.get("journey_steps", []),
            "converted": bool(data.get("converted", False)),
            "friction_points": data.get("friction_points", []),
            "drop_off_reason": data.get("drop_off_reason"),
            "ab_test_suggestion": data.get("ab_test_suggestion", ""),
            "raw_output": raw_output,
            "error": None,
        }
    except Exception as exc:
        return {
            "persona_id": persona.id,
            "persona_name": persona.name,
            "persona_initials": persona.initials,
            "journey_steps": [],
            "converted": False,
            "friction_points": [],
            "drop_off_reason": None,
            "ab_test_suggestion": "",
            "raw_output": "",
            "error": str(exc),
        }


async def run_agents_parallel(personas, url: str, on_start=None, on_done=None):
    """Run up to 3 persona agents in parallel, calling callbacks as each starts/finishes."""

    async def run_one(persona):
        if on_start:
            await on_start(persona)
        result = await run_persona_agent(persona, url)
        if on_done:
            await on_done(persona, result)
        return result

    # Run all personas in batches of 3 in parallel
    results = []
    for i in range(0, len(personas), 3):
        batch = personas[i:i + 3]
        batch_results = await asyncio.gather(*[run_one(p) for p in batch])
        results.extend(batch_results)
    return results
