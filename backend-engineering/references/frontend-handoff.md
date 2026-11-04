# Bidirectional frontend handoff

Use the project's existing plan, API specification, and requirements matrix. Add a small integration section where needed; do not maintain a second copy of schemas or conflicting completion trackers. Link source paths and decisions, and verify stale entries against current implementation.

## Receive from frontend work

- Workflow and requirement sources, including actors and relevant UI states.
- Client repository interfaces, HTTP serialization, runtime schemas, endpoint assumptions, and error normalization.
- Mocked business rules, client-only checks, fixture limitations, and unknown server behavior.
- Auth/session expectations, field visibility, filtering, sorting, pagination, and mutation refresh or optimistic update behavior.
- Relevant acceptance scenarios, test commands, and known integration gaps.

If frontend-engineering was not used or the handoff is missing, reconstruct only the needed information from existing artifacts. Do not stop backend work to require a document rewrite.

## Return to frontend work

- Confirmed operations and canonical contract references, implemented versus proposed behavior, and any agreed compatibility changes.
- Authentication/session setup, error and field-error mapping, conflicts, duplicate submission behavior, and any polling or asynchronous completion contract.
- Real-adapter setup: base URL/configuration, local startup, safe test data, and which operations still use mocks.
- Required frontend adjustments, affected workflows, cache invalidation or optimistic update consequences, and migration order.
- Evidence for connected workflows, remaining failure states to exercise, unavailable dependencies, and unresolved gaps.

## Resume frontend work

Frontend engineering verifies the returned contract against the real HTTP adapter, integrates within authorized scope, and exercises affected loading, validation, permission, conflict, empty, and success states. It returns mismatches and verified results to the same documents. Do not silently reshape the API or frontend behavior to hide a disagreement.

Switch at the existing adapter boundary where possible. An adapter can normalize wire representations; it cannot safely conceal a semantic conflict. Compatibility changes that affect business behavior require an agreed contract. Preserve mocks for development where useful and clearly label verification that still uses them.

An approved backend task does not automatically authorize unrelated frontend redesign or deployment. Carry the working mode and relevant decisions across the handoff without asking again; ask only for new scope or unresolved decisions.

If no frontend integration remains, close the handoff with that finding rather than invoking frontend work unnecessarily.
