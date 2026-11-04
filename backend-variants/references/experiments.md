# Backend comparison experiments

An experiment is useful when execution can resolve the uncertainty more cheaply than committing to an untested design. Do not build a full service or benchmark rig for an obvious local decision.

## Scope and isolation

Respect the inherited working mode. Plan-first analysis does not authorize prototype files, migrations, or database mutations. Describe the smallest useful experiment and obtain approval when necessary. Incremental mode does not authorize experiments against production or live providers.

Use isolated development data and an explicit development selector or runner. Do not add a public request parameter that changes production persistence behavior. Separate candidate state between runs, keep contracts and requirements fixed, and document differences required by each design.

## Common scenarios

Choose scenarios from the actual invariant, such as:

- Simultaneous requests for the final capacity slot.
- Repeated requests with the same logical identity, including concurrent duplicates.
- Commit succeeds but the response is lost.
- A worker restarts during processing or a provider times out after accepting work.
- Conflicting edits, authorization changes, or integration redelivery.

Use the actual database and relevant application boundary when transaction behavior is the question. Mock success cannot prove isolation or durability. Use provider stubs for controlled failure scenarios and distinguish that from live delivery evidence.

## Comparison evidence

Record outcomes and invariant violations before speed. Where measurements matter, report workload, data size, concurrency, environment, repetitions, and limitations. Compare latency, contention, retries, resource use, or recovery effort only when relevant. Do not invent performance numbers or extrapolate a local run into a production guarantee.

If an experiment cannot run, mark the result unknown and explain how that affects the recommendation. Return the evidence to the decision protocol and ask the user to select; never automatically promote the measured fastest candidate.

After adoption, remove temporary selectors and unused candidates, preserve valuable regression scenarios and decision evidence, and verify that the selected implementation retains the agreed behavior.
