Deploy 500 AI browser agents simulating real customer personas against any ecommerce URL. Get ranked A/B test recommendations before you go live.

## What It Does

You paste a URL. TestSim samples 500 customer personas from a weighted distribution — budget hunters, impulse buyers, methodical researchers, mobile shoppers, first-time visitors, loyal returners, and more. Each persona runs as an independent browser agent that actually navigates your site, clicks through categories, opens product pages, adds to cart, and attempts checkout.

As each agent finishes, results stream live to the UI. When all agents are done, Claude synthesizes every finding into a prioritized list of A/B tests with hypotheses, variants, and affected personas.

## Stack

- **Backend:** Python, FastAPI, asyncio
- **Browser automation:** Browser Use (Playwright + Claude agent loop)
- **AI:** Claude claude-sonnet-4-20250514 via Anthropic API
- **Frontend:** React, plain CSS-in-JS
- **Streaming:** Server-Sent Events (SSE)

## Quick Start

### 1. Set your API key

```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc && source ~/.zshrc
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 3001
```

### 3. Frontend

```bash
cd frontend
npm install
npm start
```

Open [http://localhost:3000](http://localhost:3000), enter a store URL, click **Analyze Site**.

## How It Works

### Personas

8 customer types defined in `backend/personas.py`, each with a weight reflecting real ecommerce traffic distribution:

| Persona | Weight | Description |
|---|---|---|
| Budget Hunter | 22% | Price-obsessed, abandons on hidden fees |
| Impulse Buyer | 19% | Emotion-driven, responds to urgency cues |
| Research Rachel | 17% | Reads every review, compares specs |
| Mobile Maya | 13% | Mobile-first, sensitive to UX friction |
| First-Time Visitor | 12% | Needs trust signals before committing |
| Loyal Returner | 9% | Returning customer, wants speed |
| Gift Giver | 5% | Shopping for someone else, needs guidance |
| Convenience Seeker | 3% | Wants fastest path to checkout |

`sample_personas(500)` uses `random.choices` with these weights to draw 500 personas per run.

### Agent Execution

Each persona runs as a `browser_use.Agent` instance with its own headless Chrome session. Browser Use runs a Claude agent loop — at each step, Claude sees a screenshot and simplified DOM, decides what to do (click, navigate, type, scroll), and Browser Use executes that action via Playwright against the live site.

Agents run 3 at a time using `asyncio.gather`, batched across all 500 (167 batches total). Each agent is instructed to report back as a JSON object:

```json
{
  "journey_steps": ["..."],
  "converted": true,
  "friction_points": ["..."],
  "drop_off_reason": "...",
  "ab_test_suggestion": "..."
}
```

### Streaming

The backend uses an `asyncio.Queue` as a bridge between agent callbacks and the SSE response generator. As each agent starts and finishes, events are pushed to the queue and streamed to the frontend in real time.

Event types: `status` → `scraped` → `persona_start` → `persona_done` → `complete`

### Synthesis

After all agents finish, a single Claude API call receives all 500 agents' findings and returns a structured JSON with a summary, top issues, and ranked A/B tests — each with a title, hypothesis, variant, affected personas, and priority.

## Project Structure

```
testsim/
  backend/
    main.py       # FastAPI routes + SSE streaming
    personas.py   # Persona definitions + weighted sampling
    agent.py      # Browser Use agent runner + batching
  frontend/
    src/
      App.js      # URL input, live activity feed, results display
      index.js
    public/
      index.html
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
