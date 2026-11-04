# UI States, Forms, Edge Cases, Accessibility, Responsive, Browser Behavior

## Contents
1. UI state matrix
2. Forms and validation
3. Edge-case catalog
4. Accessibility checklist
5. Responsive design
6. Browser behavior

---

## 1. UI state matrix

Every data-driven view should explicitly handle each of these. If one is intentionally not applicable, say why in the plan.

| State | What the user sees | Notes |
|---|---|---|
| **Initial loading** | Skeleton matching final layout | Delay showing it ~150-200ms to avoid flash on fast responses; keep it up at least ~300ms once shown to avoid flicker |
| **Refetching / background update** | Existing data stays visible, subtle indicator | Do not blank the screen on refetch; keep previous data while loading the next page/filter (`keepPreviousData`/`placeholderData`) |
| **Empty (no data yet)** | Explanation + primary action ("Add your first student") | Different from "no results" |
| **No results (filtered)** | "No matches for X" + clear filters | Preserve filters so the user can adjust |
| **Error** | Plain-language message, retry, details collapsed | Preserve user input; categorize: network / timeout / 401 / 403 / 404 / 409 / 422 / 5xx |
| **Partial** | Show what loaded, mark what failed | A failing widget should not blank the whole page (error boundary per section) |
| **Stale / offline** | Banner + last-known data | Mutations queue or fail clearly, never silently |
| **Permission denied** | Explain, offer a way forward | UI hiding is UX only; the server enforces |
| **Success** | Confirmation, next step | Toast for low-stakes, inline/page for important |
| **Optimistic pending** | Immediate update, rollback on failure | Only for low-risk, highly predictable mutations |

Rules:
- Model async status as a discriminated union or use the data layer's flags; avoid scattered booleans that can contradict each other (`isLoading && isError`).
- Error boundaries: one at the app shell, one per route, and one around independent widgets and lazy-loaded chunks.
- Announce status changes to assistive tech (`role="status"` / `aria-live="polite"`; `role="alert"` for errors that need immediate attention).

---

## 2. Forms and validation

**Principle:** client validation is for fast feedback; server validation is the source of truth. Always do both for anything that matters, and map server errors back onto fields.

- Define the rules once as a **schema** (Zod, Yup, Valibot, or the project's choice) and derive types from it. Share it between the form, the dummy API, and tests.
- **Timing:** validate on blur for first touch; after a field has shown an error, re-validate on change so the error clears as soon as it is fixed. Validate all on submit and focus the first invalid field.
- **Messages:** specific and actionable ("Enter a date in the future"), shown next to the field, linked with `aria-describedby`, field marked `aria-invalid`. A summary at the top for long forms, linking to fields.
- **Submit behavior:** disable or lock only while submitting (not while invalid, since a disabled button gives no explanation); prevent double submit with an in-flight guard; show progress; keep input on failure.
- **Input affordances:** correct `type`, `inputmode`, `autocomplete`, `autocapitalize`, `enterkeyhint`; visible labels (placeholders are not labels); show format hints and required indicators; do not block paste.
- **Normalization:** trim whitespace, normalize case/format for comparison (emails, IDs), handle IME composition (do not validate mid-composition), handle locale-specific number/date formats via `Intl`.
- **Dirty state:** warn before navigating away from unsaved changes (`beforeunload` + router blocker); autosave drafts with debounce where the PRD calls for it.
- **Concurrency:** handle 409/stale-version conflicts with a clear resolution path.
- **Uploads:** validate type and size client-side before upload, show progress, support cancel and retry, and never trust client-side type checks for security.
- **Dependent fields and async validation** (uniqueness checks): debounce, cancel stale checks, show pending state, and do not block typing.

---

## 3. Edge-case catalog (scan this list for each feature)

**Data**
- Zero, one, many, and "too many" items; very long text; missing optional fields (`null`/`undefined`/empty string); unexpected enum values; duplicate keys/IDs
- Unicode, emoji, RTL text, names with apostrophes or hyphens, very long unbroken strings (use `overflow-wrap`)
- Dates and times: time zones, DST, locale formats, date-only vs datetime; numbers: currency, decimals, negatives, big values, rounding
- Pagination edge: last page shrinks after deletion, page beyond range, items inserted while paging

**Network and timing**
- Slow, failed, timed-out, or offline requests; retry storms; request that resolves after navigation or unmount; out-of-order responses
- Double click, rapid repeated actions, back/forward during in-flight mutation, multiple tabs editing the same record
- Session expiry mid-action (401 -> re-auth and resume), permission changed (403)

**User and environment**
- Keyboard-only and screen-reader use; zoom to 200%+; text-size increase; high-contrast and forced-colors mode; reduced motion; dark mode
- Small phones, tablets, landscape, foldables, notches (safe-area insets), on-screen keyboard resizing the viewport
- Slow devices and low-end CPUs; throttled 3G; Save-Data
- Paste, drag-drop, autofill, browser translation, password managers, text selection
- JavaScript errors in one widget, failed chunk load after a deploy (stale cached HTML pointing to deleted chunk)

**State**
- Component unmounted during async work; state reset when route params change; stale closures; deep links to a state that needs data not yet loaded; refresh in the middle of a flow

---

## 4. Accessibility checklist (target WCAG 2.2 AA unless the PRD says otherwise)

- **Semantics first:** use `button`, `a`, `nav`, `main`, `ul`, `table`, `label`, `fieldset/legend`, `dialog`. Add ARIA only when native HTML cannot express it; wrong ARIA is worse than none.
- **Keyboard:** everything operable with Tab/Shift+Tab/Enter/Space/Escape/Arrow keys as appropriate; logical tab order; no keyboard traps; skip-to-content link.
- **Focus:** always visible (`:focus-visible`); move focus on route change (to the page heading) and into dialogs; trap focus in modals and restore it on close; return focus sensibly after deleting an item.
- **Names and labels:** every control has an accessible name; icon-only buttons need `aria-label`; images have meaningful `alt` or `alt=""` if decorative.
- **Status and errors:** live regions for async updates, form errors tied to inputs, loading announced (`aria-busy`).
- **Color and contrast:** 4.5:1 text, 3:1 UI components; never color alone for meaning (add icon/text).
- **Targets and motion:** targets at least 24px (aim 44px on touch); honor `prefers-reduced-motion`; no content that flashes.
- **Tables and lists:** real `<table>` with `<th scope>` and caption for tabular data; virtualized lists keep correct `aria-rowcount`/`aria-posinset` and remain keyboard-navigable.
- **Zoom/reflow:** works at 320 CSS px wide and 200% zoom without two-dimensional scrolling (except for data tables/maps).
- **Test:** keyboard-only pass, a screen reader smoke test, axe/Lighthouse in CI, and test with browser zoom.

---

## 5. Responsive design

- Mobile-first CSS; use fluid layout (`grid`, `flex`, `clamp()`, `minmax()`), container queries for components that live in varying contexts, and relative units.
- Breakpoints follow content, not device names; keep the number small and defined as tokens.
- Tables: choose a strategy up front: horizontal scroll container with sticky first column, card/stacked layout, or column prioritization with a "details" row.
- Navigation: collapsible on small screens, reachable by thumb, with visible current location.
- Images/media: `srcset`/`sizes`, explicit width/height or `aspect-ratio` to prevent layout shift, lazy-load below the fold, modern formats.
- Use `dvh/svh` units instead of `vh` for full-height mobile layouts; account for safe-area insets and the on-screen keyboard.
- Support both pointer types: hover is an enhancement only; every hover affordance needs a tap/focus equivalent.

---

## 6. Browser behavior

- **Navigation:** meaningful URLs for meaningful states; back/forward and refresh restore the view; deep links work; scroll restoration is intentional; use real `<a href>` for navigation and `<button>` for actions.
- **History & storage:** know the difference: URL (shareable, bookmarkable), `sessionStorage` (tab), `localStorage` (persistent, readable by any script, so no sensitive data), cookies (`HttpOnly`, `Secure`, `SameSite` for sessions).
- **Lifecycle:** handle tab visibility (pause polling when hidden via the Page Visibility API), online/offline events, `pagehide`/`beforeunload` sparingly, and bfcache friendliness (avoid `unload` handlers).
- **Rendering costs:** avoid layout thrash (batch reads then writes), prefer compositor-only animation (`transform`, `opacity`), use `content-visibility: auto` for long off-screen sections, use `IntersectionObserver` instead of scroll listeners, and passive event listeners for scroll/touch.
- **Compatibility:** check the project's browser support target; use feature detection and progressive enhancement; verify any new API on caniuse before depending on it.
- **Security headers and content:** rely on server-set CSP and cookie flags; never inject unsanitized HTML; validate and encode URL params; treat all client-side checks as advisory.
- **Resource hints:** `preconnect` to API/CDN origins, `preload` only truly critical assets, `fetchpriority` for the LCP image, `font-display: swap` with sized fallbacks.
