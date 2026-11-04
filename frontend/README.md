# Orkivo frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4.

Design tokens live in `app/globals.css` — components must use the semantic
tokens (`bg-primary`, `text-muted-foreground`, …), never raw palette values.
All HTTP access to the backend goes through `lib/api/client.ts`; feature code
lives under `features/<name>` (currently only `tasks`).

```bash
npm install
npm run dev    # http://localhost:3000  (expects the backend on :8000)
npm run lint
npm run build
```

The API base URL can be overridden via `NEXT_PUBLIC_API_BASE_URL`
(see `.env.example`).
