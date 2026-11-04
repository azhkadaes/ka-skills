# Requirements and architecture

## Recover intent without inventing rules

For each capability capture its source, actor, trigger, inputs, preconditions, allowed transitions, result, failures, and side effects. Include time zones, uniqueness, ownership, and capacity or monetary rules where they affect behavior. Link existing definitions instead of duplicating schemas. Ask about conflicting rules before implementing either interpretation.

A frontend may demonstrate a desired interaction while omitting persistence or failure semantics. A disabled button does not enforce a permission. Cancelling a browser request does not imply the server rolled back. A retry after a lost response may repeat an operation that already committed. Turn these gaps into explicit backend scenarios.

Use a coverage table with requirement/source, workflow, operation, module, invariant, test/evidence, and status. Keep proposed, approved, implemented, and verified distinct. No frontend is necessary for scheduled or external-system workflows to enter the map.

## Establish module boundaries

Group by business capability and ownership of decisions. For each module state:

- Responsibility and exclusions.
- Owned records and authoritative rules.
- Public commands, queries, and events where needed.
- Dependencies and permitted access to other modules.
- Transaction boundary and consequences of partial failure.

Prefer one owner for writes to a business concept. Cross-module access uses explicit operations or documented query boundaries, not arbitrary mutation of another module's tables. A shared database does not require a service per module. Keep dependency cycles visible and resolve them through clearer responsibilities or orchestration before adding messaging.

Transport validates request shape and maps outcomes; application operations coordinate work and authorization; domain rules express business decisions; infrastructure handles persistence and external systems. These are responsibilities, not a mandate for four folders or a class hierarchy. Place simple rules directly where they stay clear and testable.

## Transactions and side effects

For each mutation define what must commit atomically, how concurrent writers are handled, and which uniqueness or integrity constraints backstop application logic. Choose isolation and locking based on the actual invariant and database behavior. Test the relevant race on real persistence.

External calls cannot be assumed atomic with a database commit. Define delivery guarantees, duplicate handling, retry ownership, and recovery. Use an outbox or another durable coordination mechanism when the required guarantee justifies it; do not add one automatically. Do not promise exactly-once external effects without an established end-to-end guarantee.

## Contracts and compatibility

Define identifiers, field visibility, nullability, date/time and numeric representations, validation, errors, and authentication. Specify pagination order and tie-breakers, filters and sort semantics, maximum sizes, and concurrency or idempotency behavior where needed. Public response DTOs need not mirror persistence models.

Frontend repository interfaces are client-facing abstractions, not necessarily HTTP specifications. Inspect the HTTP adapter's serialization and normalization. Reuse a machine-readable contract where established, with runtime boundary validation and relevant compatibility checks; do not require a new schema tool merely to share types.

For changes, identify affected consumers, compatible additions versus breaking behavior, migration order, and rollback implications. Surface client expectations that cannot satisfy approved business rules. Obtain agreement on the revised contract before implementing the incompatible behavior.

## Proportion and scale

State known or assumed workload: volume, concurrency, hot records, payload sizes, latency needs, availability, and recovery expectations relevant to the assignment. Never invent operating targets as requirements. Favor a bounded query, suitable index, or background operation over distributed infrastructure when sufficient.

For a proposed service split or major abstraction, record the concrete driver, simpler alternative, added failure modes, deployment burden, and reversibility. Independent scaling, ownership, security isolation, or deployment needs can justify a split; the word scalable alone cannot.
