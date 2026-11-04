# Delivery and verification

Apply checks relevant to the capability and its risk. Record not-applicable reasons. These are evidence requirements, not a requirement to install every category of tooling.

## Business rules and access

- Trace acceptance scenarios to approved rules, including invalid transitions and system-initiated operations.
- Enforce authentication and record/action/field authorization server-side, including tenant boundaries when present. Explicit public endpoints are deliberate exceptions to authentication, not authorization gaps.
- Validate input at trust boundaries and enforce data integrity in persistence. Restrict mass assignment and sensitive fields in responses. Test direct API access independently of UI guards.
- Use established secret and session management. For browser integration verify the relevant cookie/token, CORS, and CSRF behavior. Avoid secrets and sensitive personal data in logs.
- Bound expensive inputs, result sets, and resource consumption; justify rate limits or other abuse controls based on exposed operations.

## Persistence and concurrency

- Exercise migrations from a representative existing schema; document backfills, compatibility during rollout, and rollback or restore limitations. Avoid treating destructive data migration rollback as guaranteed.
- Test meaningful database constraints and the race that could violate each concurrency-sensitive invariant.
- Define duplicate-request semantics for operations with repeated costs or side effects. If idempotency is needed, specify scope, request-payload matching, retention, concurrent repeats, and result replay.
- Check filtering, authorization, aggregation, pagination, stable ordering, and query plans where scale or evidence warrants it. Mock arrays do not verify database behavior.

## Integrations and recovery

- Define timeouts, which failures are retryable, retry ownership, bounded backoff, and a stopping or escalation condition. Avoid multiplying retries across layers.
- Test relevant failure windows: before commit, after commit but before response, and during external delivery. Define safe replay or reconciliation.
- For background work, establish durable scheduling/queue needs, worker restart behavior, duplicate processing, failed-job handling, and how operators recover.
- Stub unavailable external providers for local verification and clearly separate that evidence from live integration checks. Do not trigger live messages, payments, or other external effects without applicable authorization.

## Operations and release

- Provide environment/configuration instructions, migrations, startup, and dependency readiness behavior.
- Include useful structured diagnostics, correlation IDs, and metrics or alerts proportional to operational needs; distinguish liveness from readiness when deployed under an orchestrator.
- Define graceful shutdown and in-flight work behavior where relevant. Document deployment order and compatibility with existing clients.
- Document backups and recovery steps where data durability is in scope. Report whether restore/recovery was actually exercised.

## Evidence and handoff

Prefer meaningful business-rule, API, persistence, and integration tests over tests mirroring implementation details. Use deterministic failure scenarios rather than relying on random mock failures. Run required project checks and targeted tests; broaden only when changes or unresolved risks warrant it.

Report coverage with evidence and limitations. Separate these claims:
1. Local API and database behavior verified.
2. Existing frontend verified against the real adapter and backend.
3. External provider or deployment verified in the specified environment.
4. Production operational acceptance established against agreed criteria.

Do not infer later claims from earlier ones. Return contract and integration changes to frontend work through the shared project documents.
