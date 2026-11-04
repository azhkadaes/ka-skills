# Performance and Data Access

## Contents
1. Mindset
2. Lists and tables: pagination vs virtualization vs plain rendering
3. Request efficiency: dedupe, cache, cancel stale
4. Pacing: debounce, throttle, pacer, in-flight guards
5. Urgent vs non-urgent updates
6. Derived state, memoization, and re-render policy
7. Web Workers: when justified
8. Code loading, splitting, and preloading
9. Measuring

---

## 1. Mindset

Performance comes from architecture first: fewer requests, smaller subtrees, less state, less JavaScript up front. Micro-optimization comes last and only with measurements. Three outcomes to design for:

- **Loads quickly:** download, process, and display only what is needed for the initial interface.
- **Responds smoothly:** input is never blocked by JS, rendering, or layout work.
- **Avoids unnecessary work:** nothing is repeatedly fetched, calculated, rendered, or held in memory when it has not changed.

Do not add optimization machinery without a reason you can state. Every `useMemo`, worker, or virtualization layer is complexity that must pay for itself.

---

## 2. Lists and tables: choose by data shape

| Situation | Approach | Why |
|---|---|---|
| Ordinary table over thousands+ DB records (students, orders, logs) | **Server-side pagination** (cursor or offset) with server-side sort/filter/search | Browser never receives the full dataset; also enforces auth on the server |
| Long, continuously scrollable list (feeds, chat history, log viewer, big pickers) | **Virtualization** (TanStack Virtual, react-window) | Constant DOM size regardless of length; supports infinite scroll with cursor paging |
| Large dataset where filtering/aggregating in the browser would mean downloading everything | **Backend filtering and aggregation**; return only what the view shows | Saves bandwidth, memory, and CPU; keeps data protected |
| Small/moderate list (roughly under a few hundred simple rows) | **Plain DOM rendering**, client-side sort/filter | Simplest; virtualization adds complexity (a11y, find-in-page, dynamic heights) with no benefit. Revisit only if measurement shows jank |
| Moderate dataset the user explores heavily (instant sort/filter feel matters, data under a few thousand rows and already loaded) | **Client-side** sort/filter computed from the loaded list, possibly with deferral | One fetch, instant interaction. Compute from existing state; do not re-request |
| Very wide or heavy grid (spreadsheet-like) | Virtualize rows and columns; consider a grid library after the library gate | Cost scales with cells |

**Server-side vs client-side pagination:** use server-side when the total is large, grows unbounded, requires authorization per row, or changes often. Use client-side when the dataset is small and already loaded, and users benefit from instant filtering. When in doubt, ask for or assume the realistic maximum row count from the PRD and state it.

Details that matter:
- Keep page, page size, sort, and filters in the **URL**. Reset to page 1 when filters change. Keep previous page data visible while the next loads.
- Cursor pagination for feeds and rapidly changing data; offset is fine for stable admin tables.
- Show total count only if the backend can supply it cheaply.
- Virtualized lists: stable item keys, estimated size, overscan, preserve scroll position, and keep keyboard/screen-reader support.
- Reduce DOM size everywhere: avoid wrapper-div soup, render collapsed sections lazily, and avoid mounting hidden tabs/dialogs until opened.

---

## 3. Request efficiency

### Dedupe and share server data
If many components need the same entity (for example the current student record), they should call the same hook with the same **query key**. The data layer then issues one request, shares the result, and keeps all consumers consistent.

```ts
// One hook, one key, many consumers. No prop drilling, no duplicate fetches.
export function useStudent(id: string) {
  return useQuery({
    queryKey: ['students', id],
    queryFn: ({ signal }) => studentRepo.get(id, { signal }),
    staleTime: 60_000,
  });
}
// <StudentHeader/>, <GradesPanel/>, <AttendanceTab/> each call useStudent(id).
```

- Set `staleTime` deliberately per data type (reference data: long; live data: short).
- Normalize invalidation: after a mutation, invalidate or update the affected keys rather than refetching everything or hand-editing multiple copies.
- Prefer one request that returns what the screen needs (or a parallel `Promise.all` of independent ones) over waterfalls where request B waits for request A without needing its result. Start fetches as early as possible (route loaders, prefetch on hover).
- Batch or combine tiny repetitive requests (N+1 from the UI) by asking for a list endpoint.

### Ignore obsolete responses
A slow response for an old query must never overwrite a newer result.

```ts
// Option A: data layer keyed by input (preferred): the key change makes the old result irrelevant.
const { data } = useQuery({
  queryKey: ['students', 'search', debouncedTerm],
  queryFn: ({ signal }) => studentRepo.search(debouncedTerm, { signal }), // aborted automatically when superseded
  enabled: debouncedTerm.length >= 2,
  placeholderData: keepPreviousData,
});

// Option B: manual effect, abort previous request on cleanup.
useEffect(() => {
  const ctrl = new AbortController();
  api.search(term, { signal: ctrl.signal })
    .then(setResults)
    .catch((e) => { if (e.name !== 'AbortError') setError(e); });
  return () => ctrl.abort();
}, [term]);
```

- Pass `signal` through the API client so the network request is actually cancelled.
- For non-abortable work, use a request-id/ref guard: only apply the result if it still matches the latest id.
- Also ignore results after unmount or after the user navigates away.

### Retry and failure
Retry idempotent GETs with backoff and a cap; never auto-retry non-idempotent mutations without an idempotency key. Surface persistent failures to the user.

---

## 4. Pacing: debounce, throttle, pacer, in-flight guards

Pick by the behavior you want, not by habit:

| Tool | Behavior | Use for |
|---|---|---|
| **Debounce** | Fires after the user stops for N ms | Search-as-you-type (250-400ms), autosave, async field validation, resize-end |
| **Throttle** | Fires at most once per N ms (leading and/or trailing) | Scroll/resize/pointer-move handlers, "refresh" buttons, live preview updates, analytics pings |
| **Rate limiter / queue / batcher ("pacer")** | Enforces max calls per window, serializes or groups calls, retains order | API quota protection, bulk operations (updating 200 rows), sending a series of dependent requests, upload queues, chat message sends. Use when a tool such as TanStack Pacer, or a small queue utility, fits better than ad hoc timers |
| **In-flight guard / lock** | Ignores new triggers while one is running | Submit, pay, delete, export, "generate report": expensive or side-effecting actions |
| **Idle/visibility gating** | Runs only when idle or the tab is visible | Polling, prefetch, non-critical sync |

Guidance:
- **Throttle important buttons by case, not blanket.** Safe, cheap, idempotent actions need nothing. Costly or side-effecting actions need an in-flight guard (usually enough) plus server idempotency; add a cooldown only when repeat triggers load the server (refresh, resend OTP, export). Always give visible feedback (disabled + spinner + label like "Sending...", and a countdown for cooldowns) so a blocked click is not mistaken for a broken button.
- Debounced search: also use a minimum length, cancel stale requests (section 3), and keep showing the previous results while loading.
- Do not debounce discrete, expected-immediate interactions (toggles, tabs), because that makes the UI feel laggy.
- Never rely on client-side pacing for security or abuse protection; the server must rate-limit.

---

## 5. Urgent vs non-urgent updates

Classify every update:

- **Urgent (must feel instant):** typing in the input, caret, button press feedback, checkbox/toggle, drag, focus changes, opening a menu.
- **Non-urgent (may lag a frame or two):** filtered/sorted result rendering, chart redraw, large list re-render, derived summaries, background refresh.

Keep the urgent path tiny and let the non-urgent path trail:

```tsx
const [query, setQuery] = useState('');            // urgent: controlled input
const deferredQuery = useDeferredValue(query);      // non-urgent: drives heavy list
const rows = useMemo(() => filterRows(allRows, deferredQuery), [allRows, deferredQuery]);

<input value={query} onChange={(e) => setQuery(e.target.value)} />
<ResultsList rows={rows} dimmed={query !== deferredQuery} />
```

- `startTransition` for navigations or tab switches that trigger heavy rendering; keep showing the old UI with a pending indicator.
- Split heavy children into their own subtree (and `React.memo` when props are stable) so typing does not re-render them.
- For non-React work: `requestIdleCallback`/`scheduler.postTask`, or chunk work and yield (`await scheduler.yield?.()` / `setTimeout(0)`).
- Do not do synchronous heavy work in event handlers. Defer analytics, logging, and prefetch until after the interaction.

---

## 6. Derived state, memoization, and re-render policy

Order of operations (cheapest and simplest first):

1. **Colocate state:** move state down into the smallest subtree that needs it. This alone eliminates most unnecessary re-renders.
2. **Compute from existing state** during render: filtering/sorting a list you already hold, totals, flags. No effect, no duplicate state.
3. **Fix structure:** pass children/slots, split components so a frequently changing piece does not wrap a heavy one, avoid creating new context values every render.
4. **Then memoize,** and only where useful: `useMemo` for demonstrably expensive derivations; `React.memo` for heavy components with stable props; `useCallback` only when passed to memoized children or used as dependencies. If the React Compiler is enabled in the project, prefer writing plain code and let it memoize.
5. **Measure** with React DevTools Profiler or the browser Performance panel before and after.

Avoid:
- `useEffect` to copy props/state into other state (derive it), or to chain state updates
- Storing server data in `useState` when a data layer exists
- Premature memoization everywhere (adds noise and bugs from stale dependencies)
- Inline object/array creation as props to memoized children without stable references

Client-side sort/filter of a complete list is cheaper than refetching when the list is already loaded and modest in size. If the list is large or paginated server-side, sort/filter must be done by the server, because client-side would only affect the current page and gives wrong results.

---

## 7. Web Workers: when justified

Use a worker when **all** hold: the work is genuinely CPU-bound, it can exceed ~50ms or scales with input size, it cannot reasonably be done by the server, and it would otherwise block user interaction.

Good candidates: parsing/transforming large CSV/JSON/Excel files, client-side image processing, heavy diffing, complex aggregations over big in-memory datasets, cryptographic hashing, large search-index building, PDF/report generation.

Poor candidates: ordinary rendering logic, small filters/sorts, anything DOM-bound (workers cannot touch the DOM), work the backend should do.

Practices: keep the worker API a single typed function (`Comlink` or a small message protocol), transfer large buffers (`ArrayBuffer`) rather than cloning, support cancellation/termination, report progress, create workers lazily, and reuse them (a small pool) rather than spawning per call. Always provide a loading/progress UI and error handling for worker failure.

Decision order: avoid the work -> do it on the server -> reduce the main-thread cost (chunk, virtualize, defer) -> worker.

---

## 8. Code loading, splitting, and preloading

**Boundaries to split at:** routes (default), large editors (rich text, code, markdown), visualization/chart modules, PDF/export/import tools, admin or rarely used features, heavy modals, polyfills for old browsers.

**Keep in the startup bundle:** app shell, router, first route, auth/session bootstrap, design-system primitives actually used above the fold.

```tsx
const ReportsPage = lazy(() => import('./features/reports/ReportsPage'));

// Strategic preloading: user is likely to go there soon
const preloadReports = () => import('./features/reports/ReportsPage');
<Link to="/reports" onMouseEnter={preloadReports} onFocus={preloadReports} />;
// or after first paint / on idle for common next steps:
requestIdleCallback?.(() => preloadReports());

// Always: Suspense fallback shaped like the page + error boundary with retry for chunk failures
<ErrorBoundary fallback={<RetryChunk />}>
  <Suspense fallback={<ReportsSkeleton />}>
    <ReportsPage />
  </Suspense>
</ErrorBoundary>
```

- Preload data together with code (route loader or prefetch query) so the page is ready when the chunk arrives.
- Heuristics for preloading: hover/focus/touchstart on links, viewport proximity (`IntersectionObserver`), idle time after load, and likely next step in a funnel. Respect `navigator.connection.saveData` and slow connections by reducing speculative loading.
- Do not split tiny components; each chunk is a request. Group related modules into one chunk. Check the bundle visualizer (`vite-bundle-visualizer`, `source-map-explorer`) to find heavy dependencies and import only what is used (named imports, per-method imports, lighter alternatives).
- Handle the deploy case: a stale client requesting a chunk that no longer exists should show a "new version available, reload" message rather than a blank page.
- Set a performance budget (initial JS, LCP, INP, CLS) and check it in CI if the project cares.

---

## 9. Measuring

- Core Web Vitals: **LCP** (loading), **INP** (responsiveness), **CLS** (visual stability). Use Lighthouse, Chrome DevTools Performance panel, and field data (web-vitals library, RUM) when available.
- React Profiler for re-render hotspots; Network panel with throttling (Fast 3G, 4x CPU slowdown) as the default test condition, not an afterthought.
- Optimize what measurements show, state the before/after, and stop when the requirement is met.
