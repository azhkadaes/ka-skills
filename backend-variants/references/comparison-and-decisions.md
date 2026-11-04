# Comparison and decision protocol

## Decision brief

Capture only what matters to the decision:

- Decision and requirement/source references.
- Fixed invariants and compatibility guarantees.
- Existing stack, workload evidence or assumptions, deployment and team constraints.
- Prior choices and dependencies on this choice.
- Primary axis and named viable candidates.
- Evidence available, important unknowns, and prototype scope if authorized.
- Current working mode and editing authorization inherited from the caller.

Use the same floor and scenarios across candidates. A candidate failing a mandatory invariant is rejected, not recommended as a faster alternative. If an apparent requirement is itself disputed, resolve it with the user before evaluating against a changed floor.

## Present and ask

Use a compact table: approach, how it works, right when, costs/failure behavior, and evidence/unknowns. Explain the recommendation using stated requirements and constraints, not familiarity or novelty.

For example, a concurrency-control comparison might contain explicit row locking, atomic conditional updates, and serializable transactions. Their validity depends on the invariant, database, schema, and retry semantics; they are examples, not universally interchangeable solutions.

After analysis, use a multiple-choice input for the current decision only:

Question: Which concurrency approach should we use for this capacity operation?

- Atomic conditional allocation (Recommended): suitable if the stated invariant can be enforced in one bounded update; handle unsuccessful allocation explicitly.
- Lock the capacity record: explicit coordination with contention and lock-ordering costs.
- Serializable transaction: broader isolation with database-specific retry obligations.

Do not ask this example without first validating its assumptions against the project. Recommend only a candidate supported by the current evidence. If evidence cannot establish a sound recommendation, say so and recommend the next bounded investigation as the next question instead of inventing certainty. After investigation, return to the actual variant selection.

Use tool options within the available tool's limits and one question per invocation. If no clickable input is available, offer numbered choices with the same information and wait. Never interpret a default selection as a submitted answer.

## Convergence and approval

Track decision, user selection, rationale/evidence, dependencies, and status. During read-only planning keep this in the conversation; write to project documents only when authorized.

Example conflict: the user selected asynchronous delivery but an earlier requirement says the response guarantees completed external delivery. Explain the inconsistency and offer compatible resolutions, such as changing the response guarantee or choosing a synchronous completion design. Do not quietly weaken the guarantee.

A consistent conclusion means all material in-scope choices satisfy the fixed floor, dependent decisions agree, and blocking unknowns are resolved. Non-blocking assumptions remain visible with a validation or revisit condition.

Always ask for final confirmation of the consolidated approach. Do not make the user re-answer every settled choice. If requesting implementation approval in the same question, list the concrete edit scope so the choice is reviewable. Agreement on an architecture alone does not authorize deployment, unrelated edits, or live external effects.
