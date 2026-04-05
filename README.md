# BlitzTest

AI-powered A/B testing tool. Deploys browser agents simulating real customer personas to crawl ecommerce sites and surface what to test before going live.

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=your_key uvicorn main:app --reload --port 3001
```

### Frontend

```bash
cd frontend
npm install
npm start
```

Open http://localhost:3000, enter a store URL, click **Analyze Site**.

## How it works

1. You enter an ecommerce URL
2. 3 browser agents (sampled from 5 persona types by weight) browse the site concurrently
3. Each agent navigates, clicks, and reports friction points and drop-off reasons
4. Claude synthesizes findings into ranked A/B test recommendations streamed live to the UI

## Environment

- `ANTHROPIC_API_KEY` — required in backend environment
- Frontend proxies `/simulate` and `/health` to `localhost:3001`
