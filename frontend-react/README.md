# frontend-react

Primary Wealth Orbit UI — React 18 + Vite + TypeScript, served by FastAPI at `/ui/`.

## Build

From repo root (setup runs this automatically):

```bash
cd frontend-react
npm ci
npm run build
```

Output: `frontend-react/dist/` — mounted by `backend_api/app/main.py`.

Vite `base` is `/ui/` (`vite.config.ts`). Asset URLs assume that prefix.

## Local development

With API running on port 8000, optional hot reload:

```bash
cd frontend-react
npm run dev
```

Use the dev server URL Vite prints. For full-stack cookie auth against the real API, most contributors use the built `/ui/` bundle behind FastAPI instead.

## Tests

```bash
cd frontend-react
npm test
```

Vitest covers formatters, sync failure helpers, and add-instrument logic under `src/lib/`.

## API usage

Browser calls same-origin `/api/v1/*` (see `src/api.ts`). React Query caches list/detail data.

## Pages (high level)

| Area | Path under `/ui/` |
|------|-------------------|
| Home / indexes | `/` |
| Portfolio | `/portfolio` |
| Stocks list / detail / screener | `/stocks`, `/stocks/:symbol`, screener routes |
| Funds list / detail / compare / screener | `/mutualfunds` and nested routes |
| Auth | login flow on first visit |

## Related docs

- [../docs/architecture.md](../docs/architecture.md)
- [../docs/getting-started.md](../docs/getting-started.md)
- [../screens/README.md](../screens/README.md) — stock screen authoring