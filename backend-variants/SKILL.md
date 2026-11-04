---
name: backend-variants
description: Analyze distinct approaches to one consequential backend decision, compare evidence and tradeoffs, and obtain the user's agreed choice through sequential multiple-choice questions. Use for uncertain module, transaction, persistence, API, or integration designs, independently or from backend-engineering.
---

# Backend Variants

Explore one backend decision through concrete alternatives with fixed requirements. Adapt the controlled comparison approach of Jakub Krehel's variant skill to contracts, invariants, execution scenarios, and operations. The user selects the approach; a recommendation is never authorization.

## Working mode and permission

At the beginning of a new assignment, ask one clickable multiple-choice question: **Complete planning and review before editing (Recommended)** or **Edit incrementally as we go**. Reuse an explicit answer from this assignment, including one passed by backend-engineering or frontend-engineering. Do not repeat it at a handoff.

In plan-first mode, inspect and analyze without changing project files, including prototypes and generated plans, until the user approves implementation. A requested written plan authorizes that artifact only. In incremental mode, only already-approved decisions may be implemented; candidate prototypes need scope authorization before creating files. Existing authorized read-only checks may inform either mode.

## 1. Frame one decision

Read the actual requirements, architecture, relevant code, contracts, deployment constraints, and prior decisions. State the decision in one sentence. For a broad request, identify the first consequential unresolved decision and ask which to address if priorities cannot be inferred. Do not produce three entire backends when one uncertain boundary needs exploration.

Establish the fixed floor: business invariants, authorization and data visibility, integrity, required consistency/delivery behavior, client compatibility, and operating constraints. Reject candidates that cannot meet mandatory requirements. Security, correctness, and recoverability required by the brief are not axes to trade away.

Read [comparison-and-decisions.md](references/comparison-and-decisions.md) before comparing candidates or asking for selections.

## 2. Analyze distinct candidates

Choose one primary axis, such as concurrency control, side-effect coordination, or module ownership. Describe the axis and name each candidate by its approach, not Option A. Normally present three viable candidates; use two when only two are credible and do not fabricate an inferior third. Secondary differences must follow from the primary choice. If only one approach meets the fixed floor, explain the rejected alternatives and ask for confirmation of the remaining approach rather than pretending there is a choice.

Compare fit, complexity, failure and recovery behavior, performance implications, migration/compatibility, operational burden, and reversibility as relevant. Mark predictions, assumptions, and measured results separately. A diagram is explanatory evidence, not proof of runtime behavior.

Prototype only enough to resolve material uncertainty. Read [experiments.md](references/experiments.md) when execution would add evidence, and obtain authorization if the working mode or scope does not allow the experiment. Do not implement all candidates by default.

## 3. Always ask the user after analysis

Present a concise tradeoff comparison and a justified recommended approach. Then **always ask the user which approach to select before dependent implementation**, even if the recommendation appears obvious or incremental editing is enabled.

- Prefer the available multiple-choice input tool. Ask exactly one question at a time. Include named viable approaches, mark the recommendation, and describe each option's practical consequence. Never bundle architectural decisions into a multi-question call.
- If the tool cannot fit all viable candidates, narrow the decision through an explicit first question or use numbered text choices. Do not silently omit viable alternatives to fit a tool limit.
- A user may supply their own approach or decline the candidates. Analyze that input, revise the set, and ask again. Do not coerce selection from an obsolete list.
- A preselected choice, timeout, or silence is not an answer. Wait for required input and continue only independent authorized work.

Do not defer this question until after implementation. Do not treat a broad instruction to build the backend as a variant selection.

## 4. Reconcile until one consistent approach is agreed

After each answer, check compatibility with requirements and prior choices. If it introduces a conflict, explain the specific incompatibility and ask one multiple-choice question offering valid resolutions. Reopen only affected decisions and do not override the user's choice silently.

Continue one question at a time until all material decisions in scope fit together. Do not ask the same resolved question repeatedly without new evidence. If required facts are unavailable, identify them and ask for the next useful decision or evidence rather than claiming convergence.

Then summarize the consolidated approach, assumptions, tradeoffs, migration implications, and remaining non-blocking uncertainty. Ask one final multiple-choice confirmation: **Approve this approach (Recommended)** or **Revisit a decision**. On revisit, ask which decision next. This confirmation approves the stated architecture; implementation must also be within the authorized scope and working agreement. It may serve as plan-first implementation approval only if the question explicitly states the concrete edits it authorizes.

## 5. Hand back and adopt

Return the agreed decision, requirement sources, evidence, rejected alternatives and reasons, consequences, and follow-ups to backend-engineering or the calling workflow. Once writing is authorized, store a compact decision record in the existing project plan or architecture records. Standalone use returns the same information without requiring another skill.

After authorized adoption, remove temporary candidate implementations and selection plumbing; retain useful tests and the durable decision record. Verify the selected behavior and search for temporary selectors/imports. Do not remove established production flags merely because they resemble an experiment. Reopen an agreed choice only when new evidence or requirements materially change it.
