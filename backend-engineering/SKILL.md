---
name: backend-engineering
description: Plan, build, and extend backends from business requirements, existing systems, or frontend contracts. Use for backend architecture, APIs, persistence, business workflows, integrations, and completing a mock-backed frontend with a real service. Use backend-variants for a focused comparison of uncertain approaches.
---

# Backend Engineering

Deliver a backend that satisfies the business rules through a proportionate, modular architecture. Reuse project knowledge without treating frontend assumptions as proven rules. This skill works independently and continues work from frontend-engineering through project documents, not a dependency on that skill being installed.

## Working agreement: resolve before edits

At the beginning of each new assignment, ask one multiple-choice question: **Complete planning and review before editing (Recommended)** or **Edit incrementally as we go**. Explain the consequence briefly. Reuse an explicit choice already given for this assignment, including a choice passed from frontend-engineering or backend-variants; do not ask again on a skill handoff.

- Prefer an available clickable multiple-choice input tool. Ask one question at a time, mark the recommended option, and explain each option's consequence. If no suitable tool is available, use numbered choices and wait for a reply.
- In plan-first mode, inspect and analyze without changing project files, including generated plans, scaffolds, migrations, and prototype files. Present the complete plan and obtain explicit approval before implementation. If a written planning artifact is requested, that authorizes the artifact, not application changes.
- In incremental mode, make changes within the authorized scope as decisions settle. This does not authorize choosing an unresolved architectural variant for the user.
- A missing response, preselected choice, or timeout is not consent. While awaiting a required answer, continue only independent authorized work.

## 1. Ground in requirements and the actual system

Read relevant repository instructions, business requirements, approved plans, architecture and deployment docs, existing services, frontend flows, API clients, schemas, mocks, and tests. Start with an inventory and inspect relevant areas; do not load every document or frontend reference indiscriminately.

Choose the starting path:

- Frontend with a handoff: reuse it and verify referenced contracts against current code.
- Frontend without a handoff: reconstruct operations, states, assumptions, and integration gaps from the implementation.
- Requirements without a frontend: derive capabilities and contracts directly; do not require a frontend first.
- Existing backend: extend established modules and contracts before proposing replacements.

Explicit current user decisions and approved requirements establish intent. Documents and code provide evidence, not an automatic precedence by file type. Surface material contradictions, stale contracts, and security or correctness conflicts; ask before choosing between incompatible requirements. Record minor assumptions without stalling. Frontend mocks and hidden controls do not establish authorization or concurrency rules.

Maintain a compact coverage map in the project's existing plan or requirements document:

`requirement/source -> user or system workflow -> operation/contract -> owning module -> invariant -> verification/status`

Include backend-only workflows such as scheduled processing, integration callbacks, audit history, retention, and reconciliation when required. Distinguish approved rules, observed behavior, assumptions, and missing evidence. Read [requirements-and-architecture.md](references/requirements-and-architecture.md) when constructing this map or designing boundaries.

## 2. Design a proportionate architecture

Present a plan proportional to the assignment before coding, in the conversation while project writes are not authorized. Establish:

- Scope, users and system actors, requirement sources, non-goals, assumptions, and unresolved decisions.
- Business invariants, lifecycle transitions, validation, and permission rules.
- Module responsibilities, owned data, public operations, allowed dependencies, and transaction boundaries.
- API and integration contracts, error behavior, compatibility, and client integration implications.
- Workload assumptions, consistency needs, deployment constraints, and operational acceptance criteria.
- The first vertical slice, subsequent build order, verification, migrations, rollout, and recovery.

Start with the simplest architecture that meets the requirements. A modular application is a starting candidate, not a mandatory stack. Existing frameworks and sound project conventions take precedence over a prescribed folder tree. Do not equate frontend features, endpoints, or database tables with backend modules.

Apply SOLID at useful boundaries: coherent responsibilities; extension points justified by real variation; implementations honoring behavioral contracts; small consumer-specific interfaces; business decisions insulated from replaceable transport and external infrastructure. Do not require an interface, repository wrapper, service layer, or class per entity.

For every additional service, queue, cache, shared framework, or abstraction, state the requirement it serves, why the simpler design is insufficient, its maintenance and failure costs, and when the choice should be revisited. Explain scalability through a concrete growth dimension and workload assumption, not hypothetical traffic.

Adapt frontend-engineering's three questions to each operation and dependency:

1. Must this work exist? Can it be removed, combined, derived, or satisfied by existing capabilities?
2. Must it finish before responding? What consistency or delivery guarantee permits deferral?
3. Where should it run and who owns it? Choose the owning module, transaction, database operation, or background processor with a reason.

Evaluate patterns by fit, recurrence, cost of ignoring, and reversibility. Prefer explicit local boundaries over machinery for hypothetical reuse.

## 3. Resolve consequential uncertainty

Use backend-variants when multiple viable approaches remain and the choice materially affects correctness, compatibility, operations, cost, or reversibility. Do not invoke it for routine naming, established conventions, or decisions already agreed.

Pass the decision, requirement sources, invariants, environment, constraints, prior decisions, evidence, working mode, and editing scope. If the skill is available, read its instructions; otherwise apply the fallback here: compare viable candidates, distinguish evidence from predictions, mark a justified recommendation, and ask one multiple-choice selection at a time. Never silently select the recommendation.

Reconcile each choice with prior decisions and obtain explicit confirmation of the consolidated approach before dependent implementation. Persist decisions in existing project documents once writing is authorized. Return to the architecture plan with the agreed choice, consequences, and remaining uncertainty.

## 4. Build one thin vertical slice

After the required approvals, implement one representative useful operation through API, authorization, business rules, persistence, and relevant side effects. If a frontend exists, connect its real adapter and verify the workflow when that editing is in scope; otherwise provide the integration handoff and test at the API boundary. Do not delay backend work solely because a frontend is absent.

Keep business decisions out of transport handlers and enforce invariants at the appropriate application and database boundaries. Keep module data ownership explicit. Integrate real persistence early; an in-memory success path does not establish transaction or concurrency behavior.

Verify acceptance, validation, denied access, and relevant concurrency, duplicate-request, and failure scenarios before expanding. Confirm that the architecture fits the operation; if evidence invalidates an agreed decision, explain the change and reopen only the affected decision through the user-choice process.

## 5. Complete, verify, and hand back

Expand by capability, following the validated boundaries. Read [delivery-and-verification.md](references/delivery-and-verification.md) for migrations, security, concurrency, integrations, recovery, and operational checks. Mark requirements verified, failed, blocked, or not applicable with evidence. Never convert unavailable live dependencies into claimed passes.

Read [frontend-handoff.md](references/frontend-handoff.md) when a frontend exists or is expected. Maintain bidirectional handoff in existing contracts and plans: receive frontend expectations and return confirmed backend behavior, adapter instructions, required client changes, and verification gaps. Do not silently rewrite an agreed contract or expand into frontend edits outside scope.

Deliver the implementation summary, requirement coverage, how to run it, migrations and rollout implications, verification evidence, known limitations, and operational instructions. Distinguish API verification, real frontend integration, deployment checks, and production readiness. Remove temporary variant harnesses after adoption, preserving durable decision records and useful tests.
