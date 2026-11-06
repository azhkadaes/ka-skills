# Reliability concerns and session choice

Use this workflow when the user reports a material false/unsupported claim, or the task agent verifies a material contradiction, fabricated citation/file, invented test result, or repeated loss of an approved requirement. The same agent can miss its own errors; no universal hallucination detector is implemented. Hooks route recorded incidents and keep alert preferences separate. They do not assess the truth of arbitrary prose.

## Verify and offer

Stop relying on the disputed claim for dependent actions. Inspect the owning source, actual files, command results, or user decision. Distinguish a user report from verified evidence. A passing build alone cannot prove a factual claim or a workflow's correctness. An ordinary test failure, uncertain answer, user disagreement, or mention of hallucination does not automatically warrant a session reset. Explain the concrete issue without diagnosing the entire chat.

For a material incident, record a concise report in an allowed task-specific local file. Use a stable `incident_id` for the same underlying issue; do not manufacture new IDs to repeat a dismissed warning. Do not store secrets or full conversations. Example shape:

```json
{
  "incident_id": "test-result-claim-001",
  "basis": "verified",
  "summary": "The completion message claimed a passing check, but the recorded check failed.",
  "evidence": "Reference to the actual result and the conflicting claim, including timestamp or file location."
}
```

Use `basis: "user_reported"` when verification is pending. This example illustrates the format, not an incident in the current chat. The helper validates required fields and length, not truth. Arguments should refer to the report file rather than interpolate its prose into shell commands.

```powershell
python scripts/thread_hopper_hook.py --control report-reliability --session-id <id> --incident-file <absolute-json-path>
```

The agent should present the concern and multiple-choice question promptly at a safe point. It need not wait for a hook warning if the concern is already known. If a hook has already shown a warning, avoid repeating it. Offer:

- **Start a fresh chat with corrected context:** prepare a reviewed checkpoint and create the chat after selection.
- **Stay and verify/correct here:** fix and verify the affected work in the current chat; dismiss only this incident.
- **Review the evidence first:** show the relevant evidence and uncertainty; keep the session choice open.

For a fresh chat, follow SKILL.md's transfer procedure. Preserve explicit corrections and unresolved uncertainty rather than carrying the disputed claim forward as fact. For staying, run:

```powershell
python scripts/thread_hopper_hook.py --control dismiss-reliability --session-id <id>
```

This updates only reliability state. It never changes context thresholds, context snooze, context alert latches, cost forecasts, or global enablement. A new material incident can notify again. The latest 32 dismissed incident IDs are retained to bound state size. Updating the same incident's evidence does not retrigger an alert.

## Delivery and limitations

Incident alerts can be delivered even when usage counters are missing or stale. They are separate from context-pressure/cost pending flags. A context snooze does not snooze reliability. Context compaction rearms context warnings without automatically dismissing an unresolved reliability concern.

The session-start hook adds a short agent reminder once per loaded session and after compaction. Subsequent ordinary checks stay silent. Semantic recognition comes from the task agent's verification or the user's explicit report; there is no continuous second-model inspection or transcript keyword classifier. Existing chats need their hooks loaded for automatic guidance, and delivery still follows the host's safe-point behavior. Do not promise that every error will be noticed.
