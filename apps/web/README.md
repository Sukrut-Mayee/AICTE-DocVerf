# DocVerf web (officer console)

Next.js + TypeScript + Tailwind + shadcn/ui, with `react-pdf` for document viewing.

```bash
# 1. backend (from the repo root)
.venv/Scripts/python -m uvicorn services.api.main:app --reload --port 8000

# 2. seed the mock app001 fixture once (git-ignored data)
.venv/Scripts/python -m scripts.seed_demo_data

# 3. web app
cd apps/web
npm install
npm run dev
```

Open <http://localhost:3000/officer>.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI origin. Set in `apps/web/.env.local`. |

All API calls are centralized in [`lib/api.ts`](./lib/api.ts). Pages and components never
call `fetch` directly.

## Routes

- `/officer` — priority-sorted queue with flag counts.
- `/officer/applications/[id]` — summary, documents (flagged first), PDF evidence boxes,
  findings, confirm/dismiss actions, and the locked decision workflow.

## Data source

The UI reads whatever the API serves from `data/out/pipeline/*.json`. `app001` is a
contract-shaped mock derived from `tests/fixtures/apps/app_conflict`; its `meta.source`
is `mock_fixture` and the UI labels it as fixture data. Replacing the mock with real
pipeline output requires no frontend changes.
