---
name: thread-hopper
description: Monitor Codex context and costs, respond to reported or verified reliability concerns, and offer a corrected session handoff. Use for long chats, unsupported claims, contradictions, automatic Thread Hopper alerts, or session handoffs.
---

# Thread Hopper

Keep working context small without discarding evidence or restarting unnecessarily. The installed background hooks monitor usage without explicit skill invocation; this skill handles decisions and transfer. Reliability concerns are reported by the user or recognized and checked by the task agent, not diagnosed by a token counter. Never claim monitoring is active until hooks are registered, trusted, and observed running in the host.

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

Reliability and context/cost alerts are independent. Read [reliability.md](references/reliability.md) when the user reports unreliable output or you discover a material unsupported claim, contradiction, or fabricated evidence. At milestones and before consequential actions, check relevant claims against actual sources and test results; do not add a separate AI evaluator for every response. Ordinary uncertainty, a typo, or a failing test alone is not evidence of hallucination.

For a material concern, explain what is reported versus verified, record the incident, and offer **Start a fresh chat with corrected context**, **Stay and verify/correct here**, or **Review the evidence first** using multiple-choice input when available. Do not wait for cost savings or high context usage to offer this choice. Silence is not a choice. If the user stays, correct and verify the affected work and run `--control dismiss-reliability` for that incident. Never use context `dismiss`, `snooze`, or global disable to implement that choice. Later context warnings and new material reliability incidents remain eligible. Reviewing evidence first leaves the choice open and never authorizes a new chat.

Recommend a fresh chat only at a safe stopping point when conservative forecasts show savings above the configured margin (default 20%) against staying and any modeled compaction alternative. Flag missing compaction estimates. A separate context-pressure signal may warrant a choice even when economics are unknown. The reader's default 80% threshold is an adjustable warning heuristic, not an overflow prediction.

Prepare a short draft checkpoint before the question when feasible. Use the available multiple-choice input tool with: **Start a fresh chat and continue**, **Compact and continue here**, **Remind me later**. State the reason, estimated savings range or unknown economics, and material assumptions. A selection authorizes that specific transition. Silence is not selection. Defer reminders until a material change or the agreed milestone; avoid repeated questions each turn.

If compacting is selected, use an exposed compaction capability; otherwise explain the supported manual action. Do not simulate it by claiming to forget history. If reminders are selected, continue authorized work and preserve the checkpoint. Do not block automatic compaction merely to wait for a cheaper restart.

## Prepare and transfer

Maintain one current checkpoint, normally about 500–1,000 tokens when sufficient. Link to older evidence instead of appending prior summaries. Use an existing project handoff location or a task-specific file under an allowed local directory; keep unrelated task checkpoints separate.

Include goal and done criteria; exact workspace/branch/commit when applicable; latest user decisions and authorized scope; implemented versus verified versus pending work; relevant file/evidence references; blockers and uncertainty; running operations/owners; and the next concrete step. Record the source chat ID and a retrievable archive location. Never put secrets in a checkpoint. User authorization does not expand during handoff.

For a reliability handoff, explicitly retract disproven claims and preserve supporting evidence, unresolved concerns, and which affected outputs need rechecking. Exclude the incorrect claims from the new checkpoint's factual baseline. Starting a fresh chat does not establish that the error is fixed.

After the user selects a fresh chat, discover the available chat-creation tool and its current schema. Create a genuinely fresh chat, not a history fork, in the correct project and same checkout when continuing uncommitted changes. If the tool cannot preserve the workspace, disclose that and resolve it before launching edits elsewhere. Seed it with the checkpoint, retrieval pointers and an instruction to verify current files before continuing. Never automatically commit or move unfinished changes.

The tool named `handoff_thread` may move a checkout/worktree; inspect its description instead of assuming it resets context. If creation is unavailable, deliver the checkpoint and startup prompt without claiming a new chat exists. Do not automatically archive the old chat. Confirm the new chat exists and report its link; follow the host's required created-thread directive. Keep the full old history retrievable, and let only one chat own ongoing edits.

## Continuous monitoring

Read [monitoring.md](references/monitoring.md) to install or troubleshoot unattended monitoring. Background lifecycle hooks perform local checks and deliver only actionable warnings. Normal checks add no model context or model calls. Hooks never stop an operation or force an extra turn. Host delivery may wait until the next safe point or user turn; it cannot guarantee an immediate popup while idle. Do not silently install hooks merely because this skill was invoked; an explicit request to enable continuous monitoring authorizes installation.

One short reliability reminder is injected on session start and after compaction so the agent can recognize material concerns without explicit invocation. This adds a small context cost, without an extra model call. Incident reports are not inferred by keyword scanning or treated as proof that the AI is hallucinating.

For an explicit request for automatic coverage across local Codex chats, install the optional persistent agent fallback described in monitoring.md. It loads independently of skill invocation and requests milestone checks if hooks are unavailable. It adds a small fixed instruction cost; it cannot extend local hooks into ordinary ChatGPT chats or guarantee that every unreliable claim is recognized. Zero input counters mean unknown occupancy, never proof of an empty context window.

After **Remind me later**, run `python scripts/thread_hopper_hook.py --control snooze --session-id <id> --minutes 30`, using the chosen interval if specified. Use `--control dismiss` only when the user wants alerts suppressed until context drops below the rearm threshold. Do not repeat the hook's warning in prose unless clarification is needed.
