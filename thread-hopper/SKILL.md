---
name: thread-hopper
description: Assess Codex chat context and cache-adjusted continuation costs, monitor usage at checkpoints, and prepare a retrievable handoff to a fresh chat after the user's choice. Use when asked to manage long sessions, reduce context costs, or arrange session handoffs.
---

# Thread Hopper

Keep working context small without discarding evidence or restarting unnecessarily. A skill supplies decisions and workflow; it is not a background service. Never claim monitoring is active beyond the checks or integration actually running.

## Assess and monitor

When invoked for an ongoing task, check at meaningful milestones, before a large read, and after compaction. Stay quiet while the recommendation is unchanged. Reuse a recent snapshot rather than polling through repeated model calls. Use account usage-limit tools if available, but never interpret account percentages as this chat's context occupancy or monetary cost.

Prefer exposed App Server token-usage events. Otherwise use the bundled reader with the explicitly identified session file or thread ID. Do not choose the most recently modified chat: another task may be running. Discover the current thread ID from trusted task context when available; otherwise ask for it or an explicit session path. Never read authentication files.

Run relative to this skill directory:

```powershell
python scripts/session_usage.py snapshot --thread-id <current-thread-id>
python scripts/session_usage.py snapshot --session <absolute-rollout-path>
```

The reader emits only usage and model metadata, scans bounded regions, and does not send transcripts to a service. Check freshness, model, missing fields, and reported counters. Latest input/window is a proxy for the last request's occupancy, not exact current headroom. Cumulative usage is repeated processing, not resident context. Do not add reasoning tokens to output when already included.

For numerical economics, read [costs.md](references/costs.md) and construct explicit forecast cases. Include the actual fixed instructions/tools, handoff, essential source rereads, first-request cache misses, output/reasoning, and possible cache writes. Compare normal compaction as a third strategy when it can be reasonably forecast. Never assume a new chat starts with only the handoff or loses every shared cached prefix.

```powershell
python scripts/session_usage.py compare --scenario <forecast-json>
```

Publish observed numbers separately from estimated costs. Unknown billing, rates, cache behavior, or remaining work means unknown savings; offer a context-based checkpoint without inventing a financial recommendation. For included Plus/Pro allowances, credit-rate comparisons are proxies, not an exact allowance forecast. Consult current official pricing for the selected model, billing mode and speed; do not reuse this conversation's rates blindly.

## Offer a transition

Recommend a fresh chat only at a safe stopping point when conservative forecasts show savings above the configured margin (default 20%) against staying and any modeled compaction alternative. Flag missing compaction estimates. A separate context-pressure signal may warrant a choice even when economics are unknown. The reader's default 80% threshold is an adjustable warning heuristic, not an overflow prediction.

Prepare a short draft checkpoint before the question when feasible. Use the available multiple-choice input tool with: **Start a fresh chat and continue**, **Compact and continue here**, **Remind me later**. State the reason, estimated savings range or unknown economics, and material assumptions. A selection authorizes that specific transition. Silence is not selection. Defer reminders until a material change or the agreed milestone; avoid repeated questions each turn.

If compacting is selected, use an exposed compaction capability; otherwise explain the supported manual action. Do not simulate it by claiming to forget history. If reminders are selected, continue authorized work and preserve the checkpoint. Do not block automatic compaction merely to wait for a cheaper restart.

## Prepare and transfer

Maintain one current checkpoint, normally about 500–1,000 tokens when sufficient. Link to older evidence instead of appending prior summaries. Use an existing project handoff location or a task-specific file under an allowed local directory; keep unrelated task checkpoints separate.

Include goal and done criteria; exact workspace/branch/commit when applicable; latest user decisions and authorized scope; implemented versus verified versus pending work; relevant file/evidence references; blockers and uncertainty; running operations/owners; and the next concrete step. Record the source chat ID and a retrievable archive location. Never put secrets in a checkpoint. User authorization does not expand during handoff.

After the user selects a fresh chat, discover the available chat-creation tool and its current schema. Create a genuinely fresh chat, not a history fork, in the correct project and same checkout when continuing uncommitted changes. If the tool cannot preserve the workspace, disclose that and resolve it before launching edits elsewhere. Seed it with the checkpoint, retrieval pointers and an instruction to verify current files before continuing. Never automatically commit or move unfinished changes.

The tool named `handoff_thread` may move a checkout/worktree; inspect its description instead of assuming it resets context. If creation is unavailable, deliver the checkpoint and startup prompt without claiming a new chat exists. Do not automatically archive the old chat. Confirm the new chat exists and report its link; follow the host's required created-thread directive. Keep the full old history retrievable, and let only one chat own ongoing edits.

## Optional continuous integration

Read [monitoring.md](references/monitoring.md) when the user wants unattended monitoring. The bundled bounded watcher produces machine-readable change events; it cannot itself display a Codex multiple-choice dialog or wake this agent. A host integration must deliver actionable events. Do not silently install hooks, scheduled jobs, or background processes merely because this skill was invoked.
