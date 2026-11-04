# Architecture and Data Layer

## Contents
1. Folder layout (feature-first)
2. Layering and dependency direction
3. API contract with a replaceable dummy adapter
4. Error model
5. State ownership map
6. Hooks and component patterns
7. Auth and sensitive data
8. Translating requirements into frontend design
9. Adapting to the existing project

---

## 1. Folder layout (feature-first)

Adapt to the project's existing structure; this is the default when none exists.

```
src/
  app/                    # bootstrap, providers, router, global error boundary
  shared/
    ui/                   # design-system primitives (Button, Input, Dialog, Skeleton...)
    components/           # reusable composed components (DataTable, FormField, EmptyState, ErrorState)
    hooks/                # generic hooks (useDebouncedValue, useMediaQuery, usePagedQuery)
    lib/                  # pure utilities, formatters, validators, constants
    api/                  # http client, error normalization, adapter selection
    types/
  features/
    students/
      api/                # studentRepository interface + http/mock implementations, query keys
      components/         # feature-specific UI
      hooks/              # useStudent, useStudentSearch, useStudentForm
      schemas/            # validation schemas + inferred types
      routes/ or pages/   # route-level components (lazy-loaded boundary)
      index.ts            # the feature's public API; other features import only from here
```

Rules:
- Features do not import from each other's internals; go through `index.ts` or lift the shared piece to `shared/`.
- Promote code to `shared/` on its **second or third real use**, not before.
- Pages compose; they contain little logic. Logic lives in hooks and pure functions that can be tested without rendering.

---

## 2. Layering and dependency direction

```
shared/ui  <-  shared/components  <-  features/*  <-  app/routes
   (primitives)    (composed)         (business UI)     (assembly)
```

Dependencies point one way. Presentational components receive data and callbacks via props; container components or hooks connect them to data. This keeps UI testable and the backend replaceable.

---

## 3. API contract with a replaceable dummy adapter

Design the contract first (from the PRD/API doc if available, otherwise propose it), type it, then implement two adapters behind one interface.

```ts
// features/students/api/types.ts
export interface Student { id: string; name: string; grade: number; email: string; status: 'active' | 'inactive'; }
export interface Page<T> { items: T[]; total: number; nextCursor?: string; }
export interface ListParams { q?: string; page: number; pageSize: number; sort?: string; filters?: Record<string, string>; }
export interface RequestOptions { signal?: AbortSignal }

// features/students/api/studentRepository.ts  (the interface components depend on)
export interface StudentRepository {
  list(params: ListParams, opts?: RequestOptions): Promise<Page<Student>>;
  get(id: string, opts?: RequestOptions): Promise<Student>;
  create(input: NewStudent, opts?: RequestOptions): Promise<Student>;
  update(id: string, input: Partial<NewStudent>, opts?: RequestOptions): Promise<Student>;
}
```

```ts
// features/students/api/studentRepository.http.ts  (real)
export const httpStudentRepo: StudentRepository = {
  list: (p, o) => http.get('/students', { params: p, signal: o?.signal }),
  get:  (id, o) => http.get(`/students/${id}`, { signal: o?.signal }),
  // ...
};
```

```ts
// features/students/api/studentRepository.mock.ts  (dummy; same contract, realistic behavior)
import { simulate } from '@/shared/api/simulate';
let db: Student[] = seedStudents(250);

export const mockStudentRepo: StudentRepository = {
  async list({ q, page, pageSize, sort }, o) {
    await simulate({ signal: o?.signal });                 // latency + optional random failure + abort support
    let rows = q ? db.filter(s => s.name.toLowerCase().includes(q.toLowerCase())) : db;
    rows = sortRows(rows, sort);
    return { items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length };
  },
  async get(id, o) {
    await simulate({ signal: o?.signal });
    const s = db.find(x => x.id === id);
    if (!s) throw new ApiError({ kind: 'not_found', status: 404, message: 'Student not found' });
    return s;
  },
  // create/update enforce the same validation the real server would and may throw 422 with field errors
};
```

```ts
// shared/api/simulate.ts
export async function simulate({ min = 300, max = 900, failRate = 0, signal }: {
  min?: number; max?: number; failRate?: number; signal?: AbortSignal;
} = {}) {
  const ms = min + Math.random() * (max - min);
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('Aborted', 'AbortError')); });
  });
  if (Math.random() < failRate) throw new ApiError({ kind: 'server', status: 500, message: 'Simulated failure' });
}
```

```ts
// features/students/api/index.ts  (the single swap point)
export const studentRepo: StudentRepository =
  import.meta.env.VITE_USE_MOCK_API === 'true' ? mockStudentRepo : httpStudentRepo;
```

Why this works: components and hooks only know `StudentRepository`. Going live means flipping one env flag and fixing contract mismatches in one place. Make the dummy **realistic**: latency, abort support, pagination/sort/filter semantics, validation errors (422 with field map), not-found, auth failure, and a configurable failure rate so loading and error states are actually exercised during development. Keep dummy data and mocks out of production bundles (dynamic import behind the flag, or tree-shaken).

Document each assumed endpoint (method, path, request, response, errors) in a short `API_CONTRACT.md` or in the feature plan so backend and frontend can reconcile.

If the project uses MSW (Mock Service Worker), mocking at the network level is an equally good option and exercises the real HTTP client; follow whatever the project already does.

---

## 4. Error model

Normalize every failure into one shape at the API boundary so UI code never parses raw errors.

```ts
type ApiErrorKind = 'network' | 'timeout' | 'unauthenticated' | 'forbidden' | 'not_found' | 'conflict' | 'validation' | 'rate_limited' | 'server' | 'unknown';
class ApiError extends Error {
  kind: ApiErrorKind; status?: number; fieldErrors?: Record<string, string>; retryAfter?: number; requestId?: string;
}
```

UI mapping: `network/timeout/server` -> retry; `unauthenticated` -> re-auth flow; `forbidden` -> permission message; `not_found` -> not-found state; `conflict` -> resolution flow; `validation` -> map `fieldErrors` onto form fields; `rate_limited` -> show cooldown using `retryAfter`. Never show raw stack traces or server internals to users; log them.

---

## 5. State ownership map

Fill this in per feature. Each piece of state has exactly one owner.

| State | Owner | Example |
|---|---|---|
| Transient UI (open, hover, draft text) | Local `useState` in the lowest component that needs it | dropdown open, tooltip |
| Shareable view state | URL (search params / route params) | page, sort, filters, search term, selected tab, selected record id |
| Server data | Data layer cache (TanStack Query/SWR/RTK Query/loaders) | students list, student record |
| Form data | Form library (React Hook Form, Formik, TanStack Form) or one reducer | create student form |
| Cross-cutting client state | Small global store/context (Zustand, Context) | auth session, theme, toasts, feature flags |
| Derived data | Computed during render (memoize only if costly) | filtered list, totals, `isValid` |
| Persistent preferences | `localStorage` behind a small hook (non-sensitive only) | table density, column visibility |

Smells to fix: same data in two places; `useEffect` syncing state A to state B; global store holding server responses; props drilled through 4+ levels (use composition, context for stable cross-cutting values, or the data layer's shared hook); contexts whose value changes constantly and re-render large trees (split contexts or use a selector-based store).

---

## 6. Hooks and component patterns

- **Custom hooks** own one concern and return a small, stable interface: `useStudent(id)`, `useStudentSearch()`, `useStudentForm({ onSuccess })`, `useDebouncedValue`, `useDisclosure`. Hooks wrap the data layer so components never import the repository directly.
- **Presentational vs container:** presentational components are pure of data fetching and easy to story/test; containers (or route components) wire hooks to them.
- **Composition over configuration:** prefer children, slots, and compound components (`<Table><Table.Header/>...`) to props explosion. Avoid more than ~2-3 boolean props controlling variants; use a `variant` prop or composition.
- **Reusable building blocks to establish early:** `DataTable` (loading/empty/error/pagination built in), `FormField` (label + control + error + hint wired for a11y), `AsyncBoundary` / `QueryState` (renders skeleton/error/empty/content from query state), `ConfirmDialog`, `EmptyState`, `ErrorState`, `PageHeader`, `useConfirmLeave`.
- **Async rendering helper** keeps state handling uniform and nearly impossible to forget:

```tsx
<QueryState query={studentQuery} skeleton={<StudentSkeleton />} empty={<EmptyStudent />}>
  {(student) => <StudentCard student={student} />}
</QueryState>
```

- Keys: stable IDs, never array indexes for dynamic lists. Controlled vs uncontrolled inputs: be consistent per form.
- Side effects belong in event handlers and the data layer first; `useEffect` is for synchronizing with external systems (subscriptions, DOM APIs), not for deriving state.
- TypeScript: strict mode, types derived from schemas, discriminated unions for async/view state, no `any` at boundaries.
- Styling: follow the project's system (tokens, utility classes, CSS modules); no magic numbers; support dark mode and reduced motion if the design system does.

---

## 7. Auth and sensitive data

- **The server is the only security boundary.** Every endpoint authenticates and authorizes; the frontend never decides access on its own. Route guards, hidden menu items, and disabled buttons are UX conveniences and must be paired with server enforcement.
- Do not ship sensitive data to the client "and hide it". If a user is not allowed to see a field or record, the API must not return it. This also applies to filters and aggregations: perform them server-side on authorized data.
- Handle 401 (refresh/re-login and resume) and 403 (clear message) globally in the API client.
- Prefer `HttpOnly`, `Secure`, `SameSite` cookies for session tokens over `localStorage`; use CSRF protection for cookie auth; never put secrets or private keys in env vars exposed to the bundle (`VITE_*`/`NEXT_PUBLIC_*` are public).
- Sanitize any HTML you must render (DOMPurify), avoid `dangerouslySetInnerHTML`, validate and encode URL params, and avoid logging PII in client telemetry.
- Mask sensitive fields in the UI by default where appropriate, and clear sensitive data from memory/cache on logout (reset the query cache).

---

## 8. Translating requirements into frontend design

For each requirement in the BRD/PRD:

1. Restate it as a **user outcome** ("A teacher can find a student by name in under 3 seconds").
2. Extract the **data and rules** (entities, fields, validation, permissions, limits such as max rows or file size).
3. Derive **UI states and flows** (happy path, empty, error, permission, edge cases).
4. Derive **non-functional constraints** (devices, languages, accessibility level, performance targets, offline needs).
5. Decide the **architecture implications** (which route boundary, which state owner, which list strategy, what to prefetch).
6. Note **ambiguity** and either ask (if it would change the architecture) or assume and record the assumption.

Keep a short traceability note: requirement -> component/route -> test. When a requirement conflicts with sound engineering (for example "load all 50k records and filter instantly"), propose the alternative that serves the underlying goal and explain the tradeoff.

---

## 9. Adapting to the existing project

- Detect and follow the existing stack: framework (React/Next/Vue/Svelte/Angular), router, data layer, form lib, UI kit, styling, test runner, lint rules, folder conventions. Prefer the project's established tools over introducing equivalents.
- The principles here are framework-agnostic: for Vue/Svelte/Angular, map "hooks" to composables/stores/services, "memoization" to computed/derived state, "Suspense/lazy" to the framework's async component and route-level splitting. Keep the same state-ownership and data-layer discipline.
- For SSR/meta-frameworks (Next.js, Remix, Nuxt, SvelteKit): fetch on the server or in loaders where it removes client waterfalls, keep server and client component boundaries deliberate, and keep secrets server-side.
- If the existing code violates these practices, do not rewrite everything. Follow local convention for consistency, apply the better practice in new code, and flag the debt.
