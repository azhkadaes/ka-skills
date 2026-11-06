# Setup and background operation

## Install and observe

scripts/install.py --vault <dedicated-folder> --dry-run produces a plan without writes. Installation copies this package into $CODEX_HOME/skills/context-vault, initializes a dedicated empty vault, writes $CODEX_HOME/context-vault/config.json, and merges only its four hooks into hooks.json. Existing handlers survive and existing hook configuration is backed up. A differing installed package is never overwritten implicitly. --remove disables this integration and removes its handlers, preserving the notebook.

The installer never modifies trust settings or bypasses review. Use Codex's hook review controls to trust it. Start/resume a chat and inspect status for observed events. Hook firing alone does not prove semantic capture.

On Windows the registered command uses unquoted, shell-safe launcher paths so it executes through PowerShell as well as cmd. Paths containing spaces or shell metacharacters are rejected explicitly rather than registering a broken command. The dedicated notebook itself can contain spaces: its location is read from the configuration file, not interpolated into the hook command. A command-definition correction changes its trust hash and needs a fresh normal hook review.

SessionStart/UserPromptSubmit handlers deliver enrollment/recall before the next model request. Stop queues a pointer asynchronously; SessionEnd provides final short queueing. Unknown, off, and retrieval-only projects cannot queue learning. Hook failures leave ordinary work running and report a short warning.

The installed Python needs PyYAML; scripts/requirements.txt declares it. Do not install dependencies silently. A dependency present on the development machine may be missing elsewhere.

## Background processor

Unattended catch-up operates while the computer and Codex app remain running. Async hooks cannot initiate model turns and are cancelled at session end; they are not an always-running AI service. Use the Codex automation action after a bounded processor test. Never substitute handwritten automation directives, an OS scheduled task, or a hidden daemon.

Discover automation_update, check existing matching tasks, then create/update one. Default to a thread heartbeat unless the user requests a separate task/chat per run. The user authorized quiet catch-up; use notificationPolicy=failed_runs_only. A fifteen-minute interval is a starting cadence. Process only changed sources, cap each run at three chunks, and use bounded failure backoff. Background model passes consume model usage.

Use this task prompt with actual installed paths:

> CONTEXT_VAULT_BACKGROUND_PROCESSOR: Maintain Context Vault using <installed-skill-path> and its record contract. This task is a processor, not user knowledge. Before accessing the queue, confirm exclusion of this processor turn using the processor command and its explicit runtime session identity. Never guess an ID or select an arbitrary latest chat. If identity or an observed processor prompt hook is unavailable, report a setup failure and stop. Check pending sources in <vault-path>. Finish quietly when none exist. Process at most three new chunks from already enrolled learning projects. Read each source chunk, distinguish user/document evidence from generated assistant content, inspect existing scoped notes, and capture only durable supported information. Respect sensitive-data exclusions, protected human writing, uncertainty, and forgetting. Never enroll a project, import an unrelated chat, or expand source access. Acknowledge only completely processed chunks with their exact checkpoints, including unchanged zero-length checkpoints. On failure retain progress, record a content-free failure, and stop that source. Maintain navigation after successful changes. Report only actionable failures.

processor defaults to CODEX_THREAD_ID when the runtime provides it. Otherwise use an explicit supported runtime identity or stop setup. The task prompt must start with the exact marker above. Only processor turns and their generated replies are excluded; later ordinary user messages in the same chat remain eligible. Source parsing carries this exclusion across chunks. Never permanently exclude the whole user chat merely because a heartbeat runs there. Test this before calling unattended capture operational.

Verify separately: trusted live hooks without invocation; unknown-project multiple-choice gating; scoped recall/capture after explicit enrollment; successful background save/checkpoint with self-capture excluded; and later recall of that save without the original conversation. An automation merely existing is insufficient. Keep setup failures and pending work visible in status. On pause/removal, pause its matching automation as well; never touch unrelated tasks.

Official references: [Hooks](https://learn.chatgpt.com/docs/hooks), [Scheduled tasks](https://learn.chatgpt.com/docs/automations), [Obsidian properties](https://obsidian.md/help/properties), [Internal links](https://obsidian.md/help/links).
