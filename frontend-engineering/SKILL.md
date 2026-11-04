---
name: frontend-engineering
description: Plan, design, and implement frontend features with production-grade engineering judgment. Use this skill whenever the user asks to build, plan, scaffold, refactor, or review any frontend feature, page, component, form, table, dashboard, or UI flow, especially when a BRD, PRD, spec, or existing architecture is involved. Also use when the user mentions responsiveness, loading/error states, form validation, accessibility, performance, state management, API integration, pagination, virtualization, lazy loading, code splitting, Web Workers, debounce/throttle, or "how should I structure this frontend". Trigger even if the user only says "build this screen" or "code this feature", because the value of this skill is in the planning and the always-on quality bar, not in any single technique.
---

# Frontend Engineering

A planning-first approach to frontend work. The goal is an interface that **loads quickly**, **responds smoothly**, and **avoids unnecessary work**, built on sensible state ownership, efficient requests, and straightforward components. A simple app with the right architecture beats a heavily optimized app with the wrong one, so spend effort on decisions, not on tricks.

## Working agreement

At the beginning of a new assignment, ask one multiple-choice question: **Complete planning and review before editing (Recommended)** or **Edit incrementally as we go**. Reuse an explicit answer already given for this assignment, including one passed from backend-engineering or backend-variants; do not ask again at a skill handoff. Prefer an available clickable multiple-choice input, ask one question at a time, mark the recommendation, and explain the options briefly. If no suitable tool is available, use numbered choices and wait.

In plan-first mode, inspect and analyze without changing project files until the user approves the concrete implementation plan; a requested written plan authorizes that artifact only. In incremental mode, edit within authorized scope as decisions settle. A preselected choice, timeout, or silence is not approval. Continue only independent authorized work while required input is pending.

## The three questions (apply to every feature, request, calculation, and dependency)

1. **Does this work need to happen at all?** Can the request, calculation, re-render, or dependency be avoided? (Reuse cached data, derive from existing state, use a platform feature, delete the code.)
2. **If it must happen, does it need to happen now?** Can it be deferred, loaded on demand, lazy-loaded, or run after the first interaction?
3. **If it must happen now, where should it happen?** On the server, in a Web Worker, in a smaller component subtree, or on the main thread?

Run these in order. Most wins come from question 1. Write the answer down in the plan (Phase 1), even if it is one line, because skipping the question is how unnecessary work gets built.

## Workflow

### Phase 0: Ground in the project (before designing anything)

The existing system wins over generic best practice. Consistency with the codebase is worth more than a theoretically better pattern that nobody else follows.

- Read what exists: BRD/PRD/specs, architecture docs, folder structure, `package.json`, existing components, hooks, API client, routing, state and styling conventions, design tokens.
- Translate requirements into engineering terms: user goals, data entities, roles/permissions, user flows, success criteria, non-functional requirements (scale, devices, locales, accessibility level). Quote the requirement ID or sentence a decision traces back to when one exists.
- Identify gaps and contradictions. Ask the user only about questions that would change the architecture; for everything else, state an assumption and proceed. Do not stall on minor ambiguity.
- If no docs exist, say so, infer conventions from the code, and list the assumptions.

### Phase 1: Plan (write this out before coding; keep it proportional to feature size)

For a small component, a few lines is enough. For a feature or page, produce the plan below. Skip headings that genuinely do not apply, but never skip the ones in bold.

```
Feature: <name>            Traces to: <BRD/PRD ref or user request>
**Goal & users**: who does what, why
**Scope / non-goals**: what is explicitly not being built now
**Data & API contract**: entities, endpoints (real or dummy), request/response shapes, auth needs
**State ownership map**: each piece of state -> owner (local / URL / server-cache / global / form)
**Component tree**: container vs presentational, reused vs new shared components
**UI states**: loading, empty, error, partial, success, offline/stale, permission-denied
**Validation rules**: per field, plus where each is enforced (client for UX, server for truth)
**Edge cases**: see references/ux-states-forms-a11y.md
**Performance plan**: answers to the three questions; list/table strategy; code-loading boundary
**Library check**: any new dependency, with justification (see gate below)
**Pattern fit**: see "Design-fit check" below
**Build order**: smallest vertical slice first
**Risks & open questions**
```

### Phase 2: Build

- Build a **thin vertical slice first** (route -> data layer -> one working state path), then complete states, validation, and polish. This surfaces architectural mistakes while they are cheap.
- Start every API-dependent feature against a **replaceable dummy adapter** with the same contract as the real API (see references/architecture-and-data-layer.md). Swapping to the real backend should change one file or one env flag, not any component.
- Follow existing conventions for naming, file layout, styling, and tests. Add tests proportional to risk: pure logic and validation always; critical flows where cheap.
- Do not add abstractions for hypothetical future needs. Add them when the second or third real use appears (rule of three), unless the pattern is already established in the codebase.

### Phase 3: Review against the quality bar

Before declaring done, walk the checklist in `references/review-checklist.md`. Report what was done, what was deliberately not done and why, and what the user must do to go live (real endpoints, env vars, backend validation).

## Bidirectional backend handoff

Use existing project plans and API contracts as the shared source; link definitions instead of duplicating schemas or trackers. The skills remain independently usable. Read `references/architecture-and-data-layer.md` section 10 when preparing or receiving a backend handoff.

- **To backend-engineering:** provide requirement/workflow references, client and wire contracts, auth and error expectations, simulated or client-only rules, list/query semantics, acceptance scenarios, and unresolved gaps. Mark mock behavior as assumptions unless approved requirements establish it.
- **From backend-engineering:** inspect confirmed contracts, real-adapter setup, session/error/conflict behavior, compatibility changes, verification evidence, and remaining mocks or gaps. Verify these against current code before integrating.
- Preserve approved business rules and agreed compatibility. Surface disagreements instead of silently reshaping an API or UI to hide them. Integrate through existing adapters where possible, exercise affected UI states against the real backend, and return mismatches and results to the same project documents.
- Carry the working mode and prior decisions across handoffs. Identify required changes outside the authorized scope without automatically performing them. Neither a backend handoff nor API tests alone establishes connected frontend behavior or production readiness.

## Non-negotiables on every feature

These are not extras. A feature without them is not finished, because users hit these situations on day one.

| Area | Minimum bar |
|---|---|
| **Responsive** | Mobile-first layout, no horizontal page scroll, touch targets of at least 44px, tables have a small-screen strategy (cards, scroll container, column priority) |
| **Loading** | Every async path has a loading state; prefer skeletons that match final layout (no layout shift); no spinner flash for fast responses |
| **Error** | Every async path has an error state with a human message, a retry, and no lost user input; distinguish network, validation, auth, not-found, and server errors |
| **Empty** | Empty and zero-result states that explain and offer a next action |
| **Forms** | Schema-based validation, inline errors tied to fields, validate on blur then on change after first error, submit disabled only while submitting, double-submit prevented, server errors mapped back to fields |
| **Accessibility** | Semantic HTML first, keyboard operable, visible focus, labels, `aria-live` for async status, color is never the only signal, respects `prefers-reduced-motion`, focus management on route/dialog change |
| **API-ready** | Typed contract, dummy adapter behind the same interface, no hardcoded URLs or data inside components |
| **Security** | Anything sensitive is enforced by server-side authN/authZ. Client-side route guards and hidden buttons are UX only, never protection. No secrets in the bundle, no tokens in localStorage if avoidable, sanitize any rendered HTML |
| **Maintainability** | Small single-purpose components and hooks, state with a clear owner, no duplicated state, names that explain intent |

## Decision guides (short form; details in references)

### State: keep it where it belongs

- **Local UI state** (open/closed, input draft, hover) lives in the component that uses it. Lift only to the nearest common parent, and only when two components truly need it (colocation).
- **Server state** (anything fetched) lives in a data-fetching layer with caching, dedupe, and invalidation (TanStack Query, SWR, RTK Query, or the framework's loader). Never copy it into a global store or `useState` "to be safe", because duplicated state drifts.
- **URL state** (filters, sort, page, selected tab, search term) lives in the URL so refresh, back/forward, and sharing work.
- **Form state** lives in a form library or a single reducer, not scattered `useState`.
- **Global client state** is rare: auth session, theme, feature flags, cross-cutting UI like toasts.
- **Derived values are computed, not stored.** If it can be calculated from existing state during render (filtered list, totals, `isValid`), compute it. Reach for memoization only after measuring or when the computation is demonstrably expensive; do not use an effect to sync one state to another.

### Data access: fetch less, fetch once

- If several components need the same record (for example one student), they call the same cached query key. Do not prop-drill the data, and do not fetch it again per component.
- Cancel or ignore stale requests: a slow response to an old search must never overwrite a newer result (AbortController, query-key-driven fetching, or request-id guard).
- Prefetch on intent (hover/focus of a link, likely next page) for flows users commonly take.
- Pick pagination vs virtualization vs plain rendering by the table in `references/performance-and-data.md`. Short version: server-side pagination for ordinary tables over large datasets; virtualization for long continuous lists; backend filtering and aggregation when the dataset is large; plain DOM for small and medium lists unless measurement shows a problem. Authorization and sensitive filtering are always server-side.

### Interaction timing: urgent vs non-urgent

- **Urgent** (typing, clicking, toggling, drag) must update immediately. Keep handlers light.
- **Non-urgent** (filtering a big list as you type, rendering a chart for the new input, background sync) can lag slightly: use `useDeferredValue` / `startTransition`, debounce, or defer work so urgent input never blocks.
- Choose the pacing tool by intent: **debounce** (wait until the user stops: search-as-you-type, autosave), **throttle** (at most once per interval: scroll/resize handlers, rapid refresh), **rate limit / queue / batch** when sequencing or API quotas matter (a "pacer"), and **lock-on-submit** for destructive or costly actions (pay, submit, delete, export). Add idle-time or visibility gating for polling. Not every button needs throttling: throttle where repeat clicks cause duplicate cost, side effects, or server load, and prefer an in-flight guard to a timer for submits.

### Code loading: ship only what the first screen needs

- Split at meaningful boundaries: routes, large editors, charts and visualization modules, admin or rarely used features, heavy dialogs.
- Keep the startup bundle to the shell, the first route, and shared essentials.
- When lazy-loading, pair it with a loading strategy: a Suspense fallback shaped like the final UI, preload on hover/focus/idle or after the first paint when the user is likely to go there, and an error boundary with retry for chunk-load failures.
- Do not split tiny components. Each boundary costs a network round trip; split where the saved bytes are worth it.

### Main thread: protect it

- Move genuinely CPU-heavy work (large parsing, big sorts/aggregations the backend cannot do, image/crypto/diff processing, heavy charts' data prep) to a Web Worker only when it is measured or clearly expected to block interaction (rule of thumb: tasks over ~50ms). Workers add messaging, serialization, and build complexity, so do not use them for ordinary work.
- Otherwise reduce the work: virtualize, paginate, memoize at the right boundary, chunk work and yield, or compute on the server.
- Minimize DOM size and layout thrash: avoid reading layout then writing in loops, animate `transform`/`opacity`, reserve space for images and async content.

### Library gate: before adding any dependency

1. Can the platform or the existing framework already do this? (`<dialog>`, `<details>`, CSS grid/container queries, `Intl`, `AbortController`, `IntersectionObserver`, native form validation, existing project utilities.)
2. What does it cost in bundle size, maintenance, security surface, and architectural lock-in?
3. Is it tree-shakable, maintained, and typed? Is it replaceable behind a thin wrapper?
4. Is it used widely enough in this feature to justify itself, or is 20 lines of our own code simpler?

Prefer libraries already in the project. State the justification in the plan when adding a new one.

### Design-fit check (is this pattern worth it here?)

Before committing to a pattern, abstraction, or structure, answer briefly:

- **Fit**: does it match the actual shape of this problem and the existing code?
- **Frequency**: how often will this problem recur in the app? A recurring need (tables, forms, data fetching) justifies a shared abstraction; a one-off does not.
- **Cost of ignoring**: if a future developer ignores this pattern, what breaks, and how painful is the cleanup? Patterns that guard correctness, security, or consistency (API layer, auth, validation schema, query keys) deserve to be enforced; stylistic ones deserve a lighter touch.
- **Reversibility**: how hard is it to change later? Be careful with the hard-to-reverse choices (routing, state architecture, data layer, design-system foundations) and relaxed with easy ones.

## Architecture principles (SOLID, applied to frontend)

- **Single responsibility**: a component renders, a hook owns one concern (data, form logic, interaction), a service/adapter talks to the API, a util is a pure function.
- **Open/closed**: extend through props, composition, and slots rather than boolean-flag explosions; add a variant, not an `if` in five places.
- **Liskov**: components that share an interface (a `DataTable` variant, an input type) behave consistently when swapped.
- **Interface segregation**: small, specific props and hook return values; do not pass an entire entity when a component needs two fields.
- **Dependency inversion**: components depend on typed interfaces (an `ApiClient`, a `StudentRepository`), not on `fetch` or a specific backend, which is exactly what makes dummy-to-real API swaps painless.

Organize by **feature**, with shared primitives separate (see references/architecture-and-data-layer.md). Keep dependency direction one-way: `ui primitives <- shared components <- features <- app/routes`.

## Output expectations

- Lead with the plan, then code. Explain decisions in terms of the three questions and the requirements they serve.
- Be explicit about tradeoffs and what was intentionally left out ("no virtualization: max 200 rows per PRD section 4.2; revisit if limit rises").
- When code is delivered, include: file list, how to run it, how to swap the dummy API for the real one, and the known follow-ups.
- Do not over-engineer: apply the minimum amount of machinery that satisfies the requirement and the non-negotiables. Complexity is a cost that must be paid for by a concrete benefit.

## Reference files (read when relevant)

- `references/ux-states-forms-a11y.md`: UI state matrix, form validation approach, edge-case catalog, accessibility checklist, responsive and browser-behavior notes. Read when building forms, tables, async views, or anything interactive.
- `references/performance-and-data.md`: pagination vs virtualization decision table, request dedupe and stale-response handling, pacing tools, urgent vs non-urgent updates, memoization policy, Web Worker criteria, code-splitting and preloading patterns. Read when a feature involves lists, search, heavy computation, or lazy loading.
- `references/architecture-and-data-layer.md`: folder layout, API client with replaceable dummy adapter, state ownership map, error model, auth boundary, hooks and component patterns. Read at the start of any new feature or when setting up the data layer.
- `references/review-checklist.md`: final quality gate. Read before declaring work complete.
