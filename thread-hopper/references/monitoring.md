# Monitoring support

Start with active-task checkpoint checks. For unattended operation, a small local integration should observe usage, perform deterministic calculations, persist a compact recommendation and notify only on actionable changes. It should not run an LLM for every usage event.

Preferred input is the host's documented App Server `thread/tokenUsage/updated` notifications. `PostModelRequest` hooks can collect usage where supported but are diagnostic: they cannot by themselves block requests or present an interactive choice. `PreCompact` is a lifecycle signal, not a general cost meter. Check the target version's documentation at https://learn.chatgpt.com/docs/app-server and https://learn.chatgpt.com/docs/hooks before integrating. Do not connect a second process and assume it can subscribe to an already-running desktop session.

The fallback watcher uses an explicitly selected local rollout:

```powershell
python scripts/session_usage.py watch --thread-id <thread-id> --interval 30 --duration 600
```

It polls locally for a bounded duration and emits JSON only when the alert state changes. The initial state is emitted as a baseline. It reads at most bounded head/tail regions per changed file and never outputs conversation text. No API calls, hooks, persistent service, desktop notifications, or dialogs are installed. `--pressure 0.8` controls a heuristic context warning; provide `--scenario <json>` to include economics. A consumer must decide how to surface the event and route the user's response. Stop the watcher when the chat changes ownership or ends.

The rollout reader is a fallback against a local implementation format. Unknown/invalid usage and stale snapshots must be reported as unavailable; never fall back to scanning unrelated chats. Files may be locked, truncated, or partially written. Bounded scans can miss old model metadata; prefer missing metadata over guessing. Polling uses file metadata to avoid re-reading unchanged content. The watcher never writes to the source log.

To activate end-to-end automation, first verify the host's supported event subscription, notification delivery, multiple-choice input, and fresh-chat creation. Install only the specific integration the user authorizes, test delivery, and report its lifetime and scope. A watcher that merely writes JSON is not a working user notification system.
