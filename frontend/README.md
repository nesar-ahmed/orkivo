# Orkivo frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4.

```bash
npm install
npm run dev    # http://localhost:3000  (expects the backend on :8000)
npm run lint
npm run build  # includes TypeScript checks
```

Keep the host name identical to the one you browse on: session cookies are
per-host and ignore the port, so `127.0.0.1` for the API and `localhost` for the
app reads as signed out. The base URL itself comes from
`NEXT_PUBLIC_API_BASE_URL` (see `.env.example`).

## Routes

``` text
/                            landing page            (public, prerendered)
/login  /register            sign in, sign up        (public)
/app                         → /app/dashboard
/app/dashboard               tasks                   (signed in)
/app/workspaces              my tenants + open one   (signed in)
/app/workspaces/[id]/people  members, roles, offers  (signed in, members only)
/app/profile                 own account + offers    (signed in)
/app/platform/tenants        tenant console          (operator; the API decides)
/app/platform/accounts       account directory       (operator; the API decides)
```

`proxy.ts` keeps `/app/**` away from visitors with no session cookie and sends
signed-in people out of the public screens. That is a convenience, not the
control: `app/app/layout.tsx` asks the API who the caller is before it renders the
shell, and reads the role from that answer.

Two role axes reach this codebase, and they are deliberately different types:
`platform_role` on a `User` (`types/auth.ts`) versus `my_role` / `role` on a
`Workspace` (`types/workspace.ts`). Nothing in the UI may treat one as the other —
an operator is not a company admin, and the console has no route into a tenant's
content.

## Structure

- `lib/api/client.ts` — the only place that calls `fetch`. Typed, maps the backend
  error contract, sets the CSRF header on mutations, forwards the incoming
  `Cookie` header for server-rendered reads, and renews a stale access token before
  giving up on a request.
- `lib/api/server-cookies.ts` — hands the visitor's cookie header to that client so
  a server component runs as its caller.
- `features/{auth,users,workspaces,tasks}` — `api/` queries and mutations,
  `components/`, feature-local rules and display utils. `types/` mirrors the
  backend contracts.
- `components/ui` + `components/layout` — shared primitives, the app shell, the
  main navigation and the console sub-navigation. Design tokens live in
  `app/globals.css`; components use the semantic tokens (`bg-primary`,
  `text-muted-foreground`, …), never raw palette values.

## Session handling

Tokens are `HttpOnly` cookies set by the backend. Nothing authentication-shaped is
stored in `localStorage` or read by a script, and there is deliberately no auth
context or token variable in the component tree — the frontend asks "who am I?" and
treats the answer as the only routing signal it has.

An expiring access token is invisible: a 401 renews through the refresh cookie and
replays the call, and the login screen attempts the same renewal before showing a
form (`SessionRecovery`, with a one-shot mark so a renewal the dashboard still
refuses cannot bounce between the two). Renewal is browser-only because the refresh
cookie is scoped to the API's `/auth` path and is never sent to this origin —
see `docs/architecture/decisions/0002-session-cookies-and-csrf.md`.

## Known gaps

No component or end-to-end tests yet (Vitest/Playwright are not in this baseline),
so permission-denied and validation states are verified by the backend's API tests
plus manual runs rather than automated frontend checks.
