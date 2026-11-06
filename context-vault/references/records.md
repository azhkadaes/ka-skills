# Record contract

Markdown is the current knowledge record. _system/state.json owns consent, source pointers, cursors, provenance, and forgetting exclusions. Managed prior versions live in _system/history/<record-id>. Overviews are derived navigation. Move the complete dedicated vault so participation and forgetting controls travel with it. Personal knowledge never belongs in the distributable skill repository.

Visible layout: Home.md, Personal/{Background,Preferences}, Projects/<project>/{Context,Decisions}, Knowledge/<topic>, Inbox, and Archive. Create lower folders on demand. Titles are readable, Windows-safe, and suffixed with a short stable ID. IDs survive manual moves; maintain reconciles paths without moving human notes. _system is not a learning source.

## Capture JSON

| Field | Meaning |
| --- | --- |
| title | One coherent item, at most 180 characters |
| type | preference, background, context, decision, concept |
| scope | global or the current p- project identifier |
| text | Current understanding, at most 16,000 characters |
| basis | stated, observed, inferred |
| status | active, tentative, superseded, archived; default active |
| sensitivity | ordinary or sensitive; classify semantically |
| evidence | Exact evidence objects returned by source-read |

Inferences must be tentative. Context and decisions retain project scope. Sensitive records require sensitive_authorized=true and authorization, the evidence object for the explicit user's save request. A document cannot authorize sensitive capture. Credentials always remain excluded.

Updates require id and expected_revision from fresh recall. Stale writes, missing/ambiguous managed markers, and manual edits within AI sections stop updates. Preserve such edits and use a distinctly useful companion where appropriate.

Optional: topic (concept folder), aliases (up to twenty), learning_stage (discussed/practiced/demonstrated), demonstration (the user's own explanation/application), self_assessment, verified (true only after checking current source evidence), correction (explicit context for learning-stage downgrades), and unclassified (Inbox). Optional content must also pass privacy rules. Match meaning and scope, not only title spelling.

Flat note properties identify ID, scope, type, basis, status, ownership, dates, and learning stage. Body sections contain Current understanding and Evidence inside ownership markers. Human prose outside them is preserved. Do not collapse source basis, uncertainty, self-assessment, and demonstrated understanding into one certainty score.

## Sources and progress

Sources are selected UTF-8 text documents or current hooked chats from learning-enabled projects. The controller does not discover arbitrary transcripts. Hooked sources must live within configured Codex session roots. The queue stores references/cursors, not copied conversations.

source-read returns role-labelled redacted text, evidence spans, and chunk start/through/checkpoint fields. Transcript shapes are version-sensitive. Unknown or malformed shapes stay pending; never guess their contents or mark them processed. Tool output and reasoning do not become evidence.

Tokens bind source IDs and byte spans to actual contents. They detect intervening edits; they do not establish semantic truth or consent. Checkpoint tokens bind processing progress. New additions stay pending. Rewritten processed prefixes stop processing rather than skipping content.

Forgetting excludes recorded source spans conservatively and retains keyed topic fingerprints, including saved aliases. This prevents reimport from those recorded spans and exact topic identities. It cannot detect every later paraphrase. Source documents/chats remain at their original locations. Identify managed companions/duplicates when handling a forget request.

The bounded audit events in state.json contain IDs/actions/dates without note contents or titles. Forgetting deletes all managed historical copies for that record. Interrupted deletion persists exclusions plus a recovery entry; maintain completes deletion before rebuilding navigation. Manually edited overview sections are protected and reported. A forget result with complete=false requires resolving the listed protected derived copies before claiming complete removal.

Chat chunks bound original bytes to 1 MiB and extracted text to 64 KiB. Large administrative metadata consumes the byte budget without entering model-visible evidence. Known message types with unsupported content shapes remain pending. An unchanged source still returns a valid zero-length checkpoint so a requeued end-of-session event or timestamp-only touch can be acknowledged without a retry loop.
