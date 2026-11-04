# Review Checklist (final quality gate)

Walk this before declaring a feature done. For each unchecked item, either fix it or write down why it does not apply. Report the result briefly to the user.

## Requirements and fit
- [ ] Every requirement in scope traces to a component/route; non-goals are stated
- [ ] Follows existing project conventions (structure, naming, styling, data layer, form lib)
- [ ] Assumptions and open questions are listed
- [ ] New patterns pass the design-fit check (fit, frequency, cost of ignoring, reversibility)

## The three questions
- [ ] Unneeded requests, calculations, re-renders, and dependencies removed
- [ ] Non-essential work deferred (lazy-loaded, on demand, after first interaction)
- [ ] Remaining work runs in the right place (server / worker / small subtree / main thread)

## States and resilience
- [ ] Loading (skeleton, no layout shift, no flash), refetching, empty, no-results, error, partial, offline/stale, permission-denied, success
- [ ] Errors are categorized, human-readable, retryable, and never lose user input
- [ ] Error boundaries around route, independent widgets, and lazy chunks
- [ ] Edge-case catalog scanned (data extremes, timing, network, environment, state)

## Forms
- [ ] Schema-based validation shared by form, mock API, and tests
- [ ] Inline, accessible error messages; first invalid field focused on submit
- [ ] Double-submit prevented; server errors mapped to fields; unsaved-change guard where needed
- [ ] Correct input types, autocomplete, inputmode; normalization and locale handled

## Data and state
- [ ] Each piece of state has one owner; no duplicated or effect-synced state
- [ ] Server data in the data layer; filters/sort/page in the URL; local state local
- [ ] Shared records fetched once through a shared hook and query key
- [ ] Stale/obsolete responses cannot overwrite newer ones; requests are abortable
- [ ] Mutations invalidate or update the right keys; optimistic updates roll back
- [ ] Derived values computed from existing state; memoization justified or absent

## Performance
- [ ] List strategy matches data shape (server pagination / virtualization / plain DOM) and the assumed max size is documented
- [ ] Filtering/aggregation of large data done on the backend
- [ ] Urgent interactions stay instant; heavy updates deferred (`useDeferredValue`/transition/debounce)
- [ ] Pacing chosen by intent (debounce, throttle, queue/rate-limit, in-flight guard); important actions protected without hurting normal use
- [ ] Code split at meaningful boundaries; startup bundle limited to what the first screen needs
- [ ] Lazy loading paired with preloading (hover/focus/idle/likely next step), Suspense fallback, and chunk-error retry
- [ ] Web Worker used only where justified and measured; none for trivial work
- [ ] No new dependency without passing the library gate; bundle impact checked
- [ ] Images sized, lazy-loaded; no layout shift; animations use transform/opacity

## Accessibility and responsiveness
- [ ] Semantic HTML; keyboard-operable; visible focus; focus managed on route/dialog changes
- [ ] Labels, names, alt text; live regions for async status; no color-only signals
- [ ] Contrast, target size, zoom/reflow to 320px and 200%, reduced motion honored
- [ ] Layout verified at phone, tablet, desktop; tables have a small-screen strategy
- [ ] Hover has focus/tap equivalent; safe-area and on-screen keyboard considered

## Architecture and maintainability
- [ ] SOLID applied pragmatically: single-purpose components/hooks, adapters behind interfaces, small props
- [ ] Feature-first modules with one-way dependencies; shared code promoted on 2nd-3rd use
- [ ] Reusable pieces (DataTable, FormField, QueryState, dialogs) used instead of re-implemented
- [ ] Strict types; derived types from schemas; no `any` at boundaries
- [ ] Tests for validation, pure logic, and critical flows; states can be exercised via the mock API

## API readiness and security
- [ ] Typed contract documented; dummy adapter matches it (latency, abort, pagination, validation errors, failures)
- [ ] Single swap point between mock and real API; mocks not shipped to production
- [ ] All sensitive data and permissions enforced server-side; client guards are UX only
- [ ] No secrets in the bundle; tokens handled safely; HTML sanitized; PII not logged
- [ ] 401/403 handled globally; cache cleared on logout

## Handoff note (always include)
- What was built and what was deliberately left out (and why)
- How to run it and how to switch from the dummy to the real API
- Backend items needed (endpoints, validation parity, auth, rate limits, pagination support)
- Known follow-ups and risks
- Bidirectional integration section updated in existing project documents: outgoing assumptions/contracts and incoming backend changes linked without duplicate schemas
- Returned backend contract checked against the real adapter; affected connected states verified, or remaining mock/unavailable checks explicitly identified
- Required frontend/backend changes outside scope identified, with working mode and settled decisions preserved across handoffs
