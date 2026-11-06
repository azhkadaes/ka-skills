"""Local Markdown knowledge store. No model calls, transcript discovery, or network access."""

from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import unicodedata
from urllib.parse import quote
import uuid

import yaml


BEGIN = "<!-- context-vault:managed:start -->"
END = "<!-- context-vault:managed:end -->"
KINDS = {"preference", "background", "context", "decision", "concept"}
STATES = {"active", "tentative", "superseded", "archived"}
STAGES = {"discussed", "practiced", "demonstrated"}
MODES = {"learn", "retrieve", "off"}
TOPS = ("Personal", "Projects", "Knowledge", "Inbox", "Archive")
MAX_NOTE = 262144
MAX_CHUNK = 65536
MAX_TRANSCRIPT_BYTES = 1048576
WORKER_MARKER = "CONTEXT_VAULT_BACKGROUND_PROCESSOR:"
SECRET = re.compile(
    r"-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----|"
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?):\/\/[^\s/:]+:[^\s/@]+@|"
    r"\b(?:[A-Z0-9]+_)*(?:password|passwd|api[_ -]?key|access[_ -]?token|client[_ -]?secret)"
    r"\s*[:=]\s*[\"']?[^\s\"']{6,}", re.I)
SENSITIVE = re.compile(
    r"\b(?:my (?:salary|diagnosis|bank account|medical record)|"
    r"I (?:was diagnosed|have been diagnosed))\b", re.I)


class VaultError(ValueError):
    pass


class PropertiesLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise VaultError("Duplicate or invalid note property")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


PropertiesLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, data):
    atomic(path, (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


@contextmanager
def lock(path, timeout=4):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        acquired = False
        while not acquired:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise VaultError("Vault is busy; retry later") from None
                time.sleep(.025)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)


def project_root(path):
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise VaultError("Project must be a directory")
    try:
        result = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve(strict=True)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return path


def project_id(root):
    key = os.path.normcase(str(Path(root).resolve()))
    return "p-" + digest(key.encode())[:20]


def safe_name(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f#^%]', "-", str(text)).strip(" .-")[:90]
    if not text:
        text = "Note"
    if text.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        text = "_" + text
    return text


def split_note(raw):
    if len(raw.encode()) > MAX_NOTE:
        raise VaultError("Note exceeds size limit")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", raw, re.S)
    if not match:
        return {}, raw
    try:
        meta = yaml.load(match.group(1), Loader=PropertiesLoader) or {}
    except (yaml.YAMLError, RecursionError):
        raise VaultError("Invalid note properties") from None
    if not isinstance(meta, dict) or len(meta) > 40:
        raise VaultError("Invalid note properties")
    for key, value in meta.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float, bool, type(None), list, date)):
            raise VaultError("Properties must be flat values or lists")
        if isinstance(value, list) and (len(value) > 80 or any(not isinstance(x, (str, int, float, bool)) for x in value)):
            raise VaultError("Properties must be flat values or lists")
        if isinstance(value, date):
            meta[key] = value.isoformat()
    return meta, raw[match.end():]


def pack_note(meta, body):
    # JSON scalar/list values are valid YAML and keep Obsidian properties flat.
    head = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False, allow_nan=False)}"
                     for key, value in meta.items())
    return "---\n" + head + "\n---\n" + body


def managed(body):
    if body.count(BEGIN) != 1 or body.count(END) != 1 or body.index(BEGIN) >= body.index(END):
        raise VaultError("Managed section is missing or ambiguous; preserve the note")
    start = body.index(BEGIN)
    end = body.index(END) + len(END)
    return body[start:end]


def redact(text):
    text = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                  "[credential removed]", text, flags=re.S)
    return SECRET.sub("[credential removed]", text)


def processor_after(active, data):
    for raw in data.splitlines():
        event = json.loads(raw)
        payload = event.get("payload", {})
        text = None
        if event.get("type") == "event_msg" and payload.get("type") == "user_message":
            text = payload.get("message")
        elif event.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            text = "\n".join(x.get("text", "") for x in payload.get("content", []) if isinstance(x, dict))
        if isinstance(text, str):
            active = text.startswith(WORKER_MARKER)
    return active


class Vault:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.system = self.root / "_system"
        self.state_file = self.system / "state.json"
        if not inside(self.system, self.root):
            raise VaultError("System state must stay inside the vault")

    @classmethod
    def initialize(cls, root):
        vault = cls(root)
        if vault.root.exists() and any(vault.root.iterdir()) and not vault.state_file.exists():
            raise VaultError("Use an empty dedicated folder; existing notes will not be adopted implicitly")
        vault.root.mkdir(parents=True, exist_ok=True)
        with lock(vault.system / "vault.lock"):
            if vault.state_file.exists():
                vault._state()
            if not vault.state_file.exists():
                for folder in TOPS:
                    (vault.root / folder).mkdir(exist_ok=True)
                state = {"version": 1, "salt": secrets.token_hex(32),
                    "projects": {}, "sources": {}, "records": {}, "exclusions": [],
                    "forgotten_keys": [], "sessions": {}, "errors": {}, "events": [],
                    "hook_observations": {}}
                atomic_json(vault.state_file, state)
                atomic(vault.root / "Home.md", (
                    "# Context Vault\n\nYour personal and project knowledge.\n\n"
                    "- [Personal](Personal/Overview.md)\n- [Projects](Projects/Overview.md)\n- [Knowledge](Knowledge/Overview.md)\n"
                    "- [Inbox](Inbox/Overview.md)\n- [Archive](Archive/Overview.md)\n\n"
                    "Project participation is selected before retrieval or learning.\n"
                ).encode())
                vault._views(state)
                vault._save(state)
        return vault

    def _state(self):
        if not inside(self.system, self.root):
            raise VaultError("System state must stay inside the vault")
        if not self.state_file.exists():
            raise VaultError("Vault has not been initialized")
        state = load_json(self.state_file)
        if state.get("version") != 1:
            raise VaultError("Unsupported vault schema; no writes performed")
        return state

    def _path(self, relative):
        path = self.root / relative
        if not inside(path, self.root) or inside(path, self.system):
            raise VaultError("Note path escapes the knowledge folders")
        if Path(relative).parts[0] not in TOPS:
            raise VaultError("Note must belong to a knowledge folder")
        return path

    def _save(self, state):
        state["events"] = state["events"][-1000:]
        atomic_json(self.state_file, state)

    def _event(self, state, action, record=None):
        # Keep content and titles out of the audit trail so forgetting is effective.
        state["events"].append({"at": now(), "action": action, "id": record})

    def _project(self, state, cwd, learning=False):
        root = project_root(cwd)
        item = state["projects"].get(project_id(root))
        if not item or item["mode"] == "off" or (learning and item["mode"] != "learn"):
            raise VaultError("Project is not enrolled for this operation")
        return item

    def enrollment(self, cwd):
        state = self._state()
        root = project_root(cwd)
        item = state["projects"].get(project_id(root))
        return item or {"id": project_id(root), "root": str(root), "name": root.name, "mode": "unknown"}

    def enroll(self, cwd, mode, confirmed=False):
        if not confirmed or mode not in MODES:
            raise VaultError("An explicit user enrollment choice is required")
        root = project_root(cwd)
        if inside(root, self.root) or inside(self.root, root):
            raise VaultError("The vault must be outside participating project folders")
        with lock(self.system / "vault.lock"):
            state = self._state()
            pid = project_id(root)
            item = state["projects"].get(pid, {"id": pid, "root": str(root), "name": root.name})
            item.update(mode=mode, updated=now())
            item.setdefault("folder", safe_name(root.name) + "--" + pid[2:10])
            state["projects"][pid] = item
            if mode != "learn":
                for source in state["sources"].values():
                    if source["project"] == pid:
                        source["pending"] = False
            self._event(state, "enrollment:" + mode, pid)
            self._save(state)
            return item

    def source_add(self, cwd, path, kind="file", confirmed=False, session=None, transcript_roots=()):
        path = Path(path).expanduser().resolve(strict=True)
        if not path.is_file() or inside(path, self.root):
            raise VaultError("Sources must be original files outside the vault")
        if kind not in {"file", "chat"}:
            raise VaultError("Unknown source type")
        if kind == "file" and not confirmed:
            raise VaultError("Select each source document explicitly")
        if kind == "chat" and (path.suffix != ".jsonl" or not session or
                not any(inside(path, root) for root in transcript_roots)):
            raise VaultError("Transcript is outside the configured Codex session roots")
        if SECRET.search(str(path)):
            raise VaultError("Credential-like source path rejected")
        with lock(self.system / "vault.lock"):
            state = self._state()
            project = self._project(state, cwd, learning=True)
            sid = "s-" + digest((os.path.normcase(str(path)) + project["id"]).encode())[:24]
            if sid not in state["sources"]:
                state["sources"][sid] = {"id": sid, "path": str(path), "project": project["id"],
                    "kind": kind, "session": session, "cursor": 0, "prefix": digest(b""),
                    "pending": True, "failures": 0, "next_attempt": 0}
            elif kind == "file" and confirmed:
                source = state["sources"][sid]
                if source["kind"] != kind:
                    raise VaultError("A transcript cannot be reselected as an ordinary document")
                with path.open("rb") as handle:
                    prefix = handle.read(source["cursor"])
                if digest(prefix) != source["prefix"]:
                    source.update(cursor=0, prefix=digest(b""), failures=0, next_attempt=0)
            state["sources"][sid]["pending"] = True
            self._save(state)
            source_page = self.system / "Sources" / (sid + ".md")
            if not inside(source_page, self.root):
                raise VaultError("Source reference path escapes the vault")
            atomic(source_page, ("# Source " + sid + "\n\nType: " + kind +
                "\n\nOriginal location: " + json.dumps(str(path), ensure_ascii=False) +
                "\n\nThis is a reference to an original source, not a copied conversation or independent evidence.\n").encode())
            return sid

    def _source(self, state, sid):
        source = state["sources"].get(sid)
        if not source or state["projects"].get(source["project"], {}).get("mode") != "learn":
            raise VaultError("Source is not authorized for learning")
        path = Path(source["path"])
        if not path.is_file() or str(path.resolve()) != source["path"] or inside(path, self.root):
            raise VaultError("Source is unavailable or resolves into generated vault data")
        if source["kind"] == "chat":
            try:
                with path.open("rb") as handle:
                    header = json.loads(handle.readline(MAX_TRANSCRIPT_BYTES + 1))
                payload = header.get("payload", {})
                if header.get("type") != "session_meta" or not isinstance(payload, dict):
                    raise VaultError("Unsupported transcript identity metadata")
                identity = str(payload.get("id", "")).removeprefix("thr_")
                expected = str(source["session"]).removeprefix("thr_")
                if not identity or identity != expected:
                    raise VaultError("Transcript belongs to a different session")
                root = project_root(payload["cwd"])
                if project_id(root) != source["project"]:
                    raise VaultError("Transcript belongs to a different project")
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                if isinstance(exc, VaultError):
                    raise
                raise VaultError("Transcript identity could not be verified") from None
        return source

    def _token(self, state, source, start, end, content):
        message = f"{source}:{start}:{end}:".encode() + content
        return hmac.new(bytes.fromhex(state["salt"]), message, hashlib.sha256).hexdigest()

    def _excluded(self, state, sid, start, end):
        return any(x["source"] == sid and start < x["end"] and end > x["start"]
                   for x in state["exclusions"])

    def source_read(self, sid):
        state = self._state()
        source = self._source(state, sid)
        path = Path(source["path"])
        cursor = source["cursor"]
        with path.open("rb") as handle:
            prefix = handle.read(cursor)
            if len(prefix) != cursor or digest(prefix) != source["prefix"]:
                raise VaultError("Processed source history changed; reselect this source before continuing")
            raw_budget = MAX_TRANSCRIPT_BYTES if source["kind"] == "chat" else MAX_CHUNK
            data = handle.read(raw_budget + 1)
        if not data:
            return {"source": sid, "project": source["project"], "messages": [],
                    "start": cursor, "through": cursor, "unchanged": True,
                    "checkpoint": self._token(state, sid, cursor, cursor, b"")}
        if source["kind"] == "chat":
            cut = data.rfind(b"\n", 0, raw_budget + 1)
            if cut < 0:
                raise VaultError("Transcript line is incomplete or too large")
            data = data[:cut + 1]
        else:
            data = data[:MAX_CHUNK]
            while data:
                try:
                    data.decode("utf-8-sig")
                    break
                except UnicodeDecodeError as exc:
                    if exc.start < len(data) - 4:
                        raise VaultError("Source must be UTF-8 text") from None
                    data = data[:-1]
        messages = []
        text_bytes = 0
        processor_active = source.get("processor_active", False)
        position = cursor
        spans = data.splitlines(keepends=True) if source["kind"] == "chat" else [data]
        for raw in spans:
            recognized = False
            end = position + len(raw)
            text = None
            role = "document"
            if source["kind"] == "chat":
                try:
                    event = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise VaultError("Malformed transcript; checkpoint was not advanced") from None
                if not isinstance(event, dict):
                    raise VaultError("Unsupported transcript object; checkpoint was not advanced")
                payload = event.get("payload", {})
                if not isinstance(payload, dict):
                    raise VaultError("Unsupported transcript object; checkpoint was not advanced")
                if event.get("type") in {"session_meta", "turn_context", "compacted",
                        "inter_agent_communication_metadata", "token_usage_record", "world_state"}:
                    recognized = True
                if event.get("type") == "event_msg" and payload.get("type") in {"user_message", "agent_message"}:
                    role = "user" if payload["type"] == "user_message" else "assistant"
                    text = payload.get("message")
                    if not isinstance(text, str):
                        raise VaultError("Unsupported message content; checkpoint was not advanced")
                    recognized = True
                if event.get("type") == "response_item" and payload.get("type") == "message":
                    role = payload.get("role")
                    if role in {"system", "developer", "tool"}:
                        recognized = True
                    if role in {"user", "assistant"}:
                        content = payload.get("content")
                        if not isinstance(content, list) or any(not isinstance(x, dict) or
                                x.get("type") not in {"input_text", "output_text", "text"} or
                                not isinstance(x.get("text"), str) for x in content):
                            raise VaultError("Unsupported message content; checkpoint was not advanced")
                        text = "\n".join(x["text"] for x in content)
                        recognized = True
                if event.get("type") == "response_item" and payload.get("type") == "agent_message":
                    content = payload.get("content")
                    if not isinstance(content, list):
                        raise VaultError("Unsupported agent message content")
                    pieces = []
                    for part in content:
                        if not isinstance(part, dict):
                            raise VaultError("Unsupported agent message content")
                        if isinstance(part.get("text"), str):
                            pieces.append(part["text"])
                        elif not isinstance(part.get("encrypted_content"), str):
                            raise VaultError("Unsupported agent message content")
                    role, text, recognized = "assistant", "\n".join(pieces), True
                if event.get("type") == "event_msg" and payload.get("type") in {"token_count", "task_started", "task_complete", "agent_reasoning", "item_completed", "turn_aborted", "thread_settings_applied"}:
                    recognized = True
                if event.get("type") == "response_item" and payload.get("type") in {"function_call", "function_call_output", "custom_tool_call", "custom_tool_call_output", "reasoning", "web_search_call", "additional_tools"}:
                    recognized = True
            else:
                text = raw.decode("utf-8-sig")
                recognized = True
            if not recognized:
                raise VaultError("Unsupported transcript item; checkpoint was not advanced")
            if role == "user" and isinstance(text, str):
                processor_active = text.startswith(WORKER_MARKER)
            if isinstance(text, str) and text.strip() and not processor_active and not self._excluded(state, sid, position, end):
                size = len(text.encode())
                if size > MAX_CHUNK:
                    raise VaultError("Message exceeds the supported text budget; checkpoint was not advanced")
                if text_bytes + size > MAX_CHUNK:
                    break
                text_bytes += size
                ref = {"source": sid, "start": position, "end": end,
                       "token": self._token(state, sid, position, end, raw)}
                messages.append({"role": role, "text": redact(text), "evidence": ref})
            position = end
        return {"source": sid, "project": source["project"], "messages": messages,
                "through": position, "start": cursor,
                "checkpoint": self._token(state, sid, cursor, position, data[:position - cursor]), "unchanged": False}

    def _refs(self, state, refs, project):
        if not isinstance(refs, list) or not refs or len(refs) > 40:
            raise VaultError("Provide between one and forty source evidence spans")
        result = []
        for ref in refs:
            source = self._source(state, ref.get("source"))
            if source["project"] != project:
                raise VaultError("Evidence belongs to another project")
            start, end = ref.get("start"), ref.get("end")
            budget = MAX_TRANSCRIPT_BYTES if source["kind"] == "chat" else MAX_CHUNK
            if type(start) is not int or type(end) is not int or not 0 <= start < end or end - start > budget:
                raise VaultError("Invalid evidence range")
            if self._excluded(state, source["id"], start, end):
                raise VaultError("Evidence was excluded by a forgetting request")
            with Path(source["path"]).open("rb") as handle:
                handle.seek(start)
                data = handle.read(end - start)
            if len(data) != end - start or not hmac.compare_digest(str(ref.get("token", "")), self._token(state, source["id"], start, end, data)):
                raise VaultError("Evidence changed; read the source again")
            result.append({key: ref[key] for key in ("source", "start", "end", "token")})
        return result

    def _evidence_role(self, state, ref):
        source = self._source(state, ref["source"])
        with Path(source["path"]).open("rb") as handle:
            handle.seek(ref["start"])
            raw = handle.read(ref["end"] - ref["start"])
        if source["kind"] == "file":
            return "document", raw.decode("utf-8-sig")
        try:
            event = json.loads(raw)
            payload = event.get("payload", {})
            if event.get("type") == "event_msg" and payload.get("type") == "user_message":
                return "user", str(payload.get("message", ""))
            if event.get("type") == "response_item" and payload.get("role") == "user":
                return "user", "\n".join(str(x.get("text", "")) for x in payload.get("content", []) if isinstance(x, dict))
        except (ValueError, AttributeError):
            pass
        return "assistant", ""

    def _scan(self, state):
        notes = {}
        for top in TOPS:
            folder = self.root / top
            if not folder.exists():
                continue
            for path in folder.rglob("*.md"):
                if not inside(path, folder) or not inside(path, self.root) or path.stat().st_size > MAX_NOTE:
                    raise VaultError("Unsafe or oversized note found; inspect the vault")
                raw = path.read_bytes().decode("utf-8-sig")
                meta, body = split_note(raw)
                rid = meta.get("id")
                if not rid or meta.get("type") not in KINDS or rid in state.get("deleting", {}) or rid in state.get("forgotten_ids", []):
                    continue
                if not re.fullmatch(r"[a-f0-9]{32}", str(rid)):
                    raise VaultError("Invalid note identity")
                if rid in notes:
                    raise VaultError("Duplicate note identity; resolve the copies before continuing")
                notes[rid] = {"meta": meta, "body": body, "raw": raw, "path": path,
                              "revision": digest(raw.encode())}
        return notes

    def _key(self, state, scope, kind, title):
        return hmac.new(bytes.fromhex(state["salt"]),
                        (scope + "|" + kind + "|" + normalize(title)).encode(), hashlib.sha256).hexdigest()

    def upsert(self, cwd, item):
        if not isinstance(item, dict):
            raise VaultError("Capture must be an object")
        with lock(self.system / "vault.lock"):
            state = self._state()
            project = self._project(state, cwd, learning=True)
            kind, scope = item.get("type"), item.get("scope")
            title, text = item.get("title"), item.get("text")
            basis, status = item.get("basis"), item.get("status", "active")
            if kind not in KINDS or scope not in {"global", project["id"]}:
                raise VaultError("Invalid note type or scope")
            if kind in {"context", "decision"} and scope == "global":
                raise VaultError("Project context and decisions must retain their project scope")
            if not isinstance(title, str) or not title.strip() or len(title) > 180 or not isinstance(text, str) or not text.strip() or len(text) > 16000:
                raise VaultError("Provide a concise title and substantive text")
            if basis not in {"stated", "observed", "inferred"} or status not in STATES:
                raise VaultError("Invalid basis or status")
            if basis == "inferred" and status == "active":
                raise VaultError("Inferences must remain tentative")
            if BEGIN in text or END in text:
                raise VaultError("Capture text may not contain ownership markers")
            if SECRET.search(json.dumps(item, ensure_ascii=False)):
                raise VaultError("Credential-like content rejected; no capture was saved")
            sensitivity = item.get("sensitivity")
            if sensitivity not in {"ordinary", "sensitive"}:
                raise VaultError("Classify sensitivity explicitly")
            if SENSITIVE.search(title + " " + text) and sensitivity != "sensitive":
                raise VaultError("Potentially sensitive personal content needs explicit authorization")
            refs = self._refs(state, item.get("evidence"), project["id"])
            roles = [self._evidence_role(state, ref)[0] for ref in refs]
            if all(role == "assistant" for role in roles):
                raise VaultError("Assistant-only output cannot establish user knowledge or preferences")
            if sensitivity == "sensitive":
                if item.get("sensitive_authorized") is not True or not item.get("authorization"):
                    raise VaultError("Sensitive content requires an explicit save request")
                auth = self._refs(state, [item["authorization"]], project["id"])[0]
                auth_role, auth_text = self._evidence_role(state, auth)
                if auth_role != "user" or not re.search(r"\b(?:remember|save|store|record|keep|ingat|simpan|catat)\b", auth_text, re.I):
                    raise VaultError("Sensitive-save authorization must be an explicit user request")
            stage = item.get("learning_stage")
            if stage is not None and (kind != "concept" or stage not in STAGES):
                raise VaultError("Invalid learning stage")
            if stage == "demonstrated" and not item.get("demonstration"):
                raise VaultError("Demonstrated understanding requires evidence of the user's own work")
            aliases = item.get("aliases", [])
            if not isinstance(aliases, list) or len(aliases) > 20 or any(not isinstance(x, str) or len(x) > 180 for x in aliases):
                raise VaultError("Invalid aliases")
            if any(field in item and type(item[field]) is not bool for field in ("verified", "unclassified", "sensitive_authorized")):
                raise VaultError("Boolean capture options must be true or false")
            key = self._key(state, scope, kind, title)
            if any(candidate in state["forgotten_keys"] for candidate in
                   [key] + [self._key(state, scope, kind, alias) for alias in aliases]):
                raise VaultError("This topic was forgotten; a fresh explicit remember request is required")
            notes = self._scan(state)
            rid = item.get("id")
            if rid and rid not in notes:
                raise VaultError("Note identity not found")
            if not rid:
                candidates = [i for i, note in notes.items() if note["meta"].get("scope") == scope
                              and note["meta"].get("type") == kind and normalize(title) in
                              {normalize(note["meta"].get("title", "")), *map(normalize, note["meta"].get("aliases", []))}]
                if len(candidates) > 1:
                    raise VaultError("Multiple matching notes; inspect before merging")
                rid = candidates[0] if candidates else uuid.uuid4().hex
            previous = notes.get(rid)
            if previous:
                old = previous["meta"]
                if old.get("scope") != scope or old.get("type") != kind:
                    raise VaultError("An update cannot silently change scope or note type")
                if item.get("expected_revision") != previous["revision"]:
                    raise VaultError("Read the current note and supply its revision before updating")
                old_managed = managed(previous["body"])
                known_hash = state["records"].get(rid, {}).get("managed_hash")
                if old.get("owner") == "human" or known_hash != digest(old_managed.encode()):
                    raise VaultError("Human edits are protected; preserve this note and use a companion note")
                if basis == "inferred" and old.get("basis") in {"stated", "observed"}:
                    raise VaultError("An inference cannot replace explicit or observed knowledge")
                if stage and old.get("learning_stage") in STAGES:
                    order = ["discussed", "practiced", "demonstrated"]
                    if order.index(stage) < order.index(old["learning_stage"]) and not item.get("correction"):
                        raise VaultError("A learning-stage downgrade needs explicit correction context")
                meta = dict(old)
                path = previous["path"]
                aliases = list(dict.fromkeys(old.get("aliases", []) + aliases +
                               ([old["title"]] if old.get("title") != title else [])))[:20]
            else:
                meta = {"id": rid, "created": now(), "owner": "ai"}
                if scope == "global":
                    parent = Path("Knowledge") / safe_name(item.get("topic", "General")) if kind == "concept" else Path("Personal") / ("Preferences" if kind == "preference" else "Background")
                else:
                    parent = Path("Projects") / project["folder"] / ("Decisions" if kind == "decision" else "Context")
                if item.get("unclassified"):
                    parent = Path("Inbox")
                path = self._path(parent / (safe_name(title) + "--" + rid[:8] + ".md"))
            meta.update(title=title.strip(), type=kind, scope=scope, status=status, basis=basis,
                        sensitivity=sensitivity, updated=now(), aliases=aliases)
            if stage:
                meta["learning_stage"] = stage
            for field in ("self_assessment", "demonstration"):
                if item.get(field):
                    meta[field] = str(item[field])[:1200]
            if item.get("verified"):
                if basis != "observed":
                    raise VaultError("Verification dates require observed source evidence")
                meta["verified"] = now()
            evidence_text = "\n".join(
                f"- [Source {ref['source']}]({quote(Path(os.path.relpath(self.system / 'Sources' / (ref['source'] + '.md'), path.parent)).as_posix(), safe='/.-')}), bytes {ref['start']}-{ref['end']}"
                for ref in refs)
            block = BEGIN + "\n\n## Current understanding\n\n" + text.strip() + "\n\n## Evidence\n\n" + evidence_text + "\n\n" + END
            if previous:
                body = previous["body"].replace(old_managed, block, 1)
            else:
                body = "# " + title.strip() + "\n\n" + block + "\n"
            raw = pack_note(meta, body)
            if len(raw.encode()) > MAX_NOTE:
                raise VaultError("Note exceeds size limit")
            if previous and previous["raw"] != raw:
                history = self.system / "history" / rid / (previous["revision"] + ".md")
                if not inside(history, self.system / "history") or not inside(history, self.root):
                    raise VaultError("Invalid history path")
                atomic(history, previous["raw"].encode())
            all_refs = state["records"].get(rid, {}).get("evidence", []) + refs
            unique_refs = {json.dumps(ref, sort_keys=True): ref for ref in all_refs}
            state["records"][rid] = {"path": path.relative_to(self.root).as_posix(),
                "managed_hash": digest(block.encode()), "evidence": list(unique_refs.values()),
                "keys": list(set(state["records"].get(rid, {}).get("keys", []) + [key] +
                    [self._key(state, scope, kind, alias) for alias in aliases]))}
            atomic(path, raw.encode())
            self._event(state, "update" if previous else "create", rid)
            self._save(state)
            self._views(state)
            self._save(state)
            return {"id": rid, "path": path.relative_to(self.root).as_posix(), "revision": digest(raw.encode())}

    def recall(self, cwd, query="", limit=6):
        state = self._state()
        project = self._project(state, cwd)
        words = set(re.findall(r"\w+", normalize(query)))
        output = []
        for rid, note in self._scan(state).items():
            meta = note["meta"]
            if meta.get("scope") not in {"global", project["id"]} or meta.get("status") not in {"active", "tentative"}:
                continue
            if note["path"].relative_to(self.root).parts[0] == "Archive":
                continue
            haystack = normalize(str(meta.get("title", "")) + " " + note["body"])
            title_words = set(re.findall(r"\w+", normalize(meta.get("title", ""))))
            score = sum(3 if word in title_words else 1 for word in words if word in haystack)
            if words and not score:
                continue
            record = state["records"].get(rid, {})
            manual = meta.get("owner") == "human"
            try:
                manual = manual or record.get("managed_hash") != digest(managed(note["body"]).encode())
            except VaultError:
                manual = True
            output.append({"id": rid, "title": redact(str(meta.get("title", ""))), "scope": meta.get("scope"),
                "status": meta.get("status"), "basis": meta.get("basis"), "learning_stage": meta.get("learning_stage"),
                "path": note["path"].relative_to(self.root).as_posix(), "revision": note["revision"],
                "text": redact(note["body"])[:4000], "human_edited": manual,
                "evidence": record.get("evidence", []), "requires_recheck": meta.get("type") in {"context", "decision"},
                "score": score + (1 if meta.get("scope") == project["id"] else 0)})
        output.sort(key=lambda x: (-x["score"], x["title"] or "", x["id"]))
        return output[:max(1, min(int(limit), 12))]

    def _views(self, state):
        notes = self._scan(state)
        protected = []
        views = state.setdefault("views", {})
        groups = {top: [] for top in TOPS}
        for project in state["projects"].values():
            groups["Projects/" + project["folder"]] = []
        for rid, note in notes.items():
            meta = note["meta"]
            top = note["path"].relative_to(self.root).parts[0]
            if meta.get("status") not in {"active", "tentative"} or top == "Archive":
                relative = Path(os.path.relpath(note["path"], self.root / "Archive")).as_posix()
                groups["Archive"].append(f"- [{str(meta.get('title', 'Note')).replace('[', '').replace(']', '')}]({quote(relative, safe='/.-')}) ({meta.get('status')})")
                continue
            scope = meta.get("scope")
            group = "Knowledge" if meta.get("type") == "concept" else "Personal"
            if scope != "global":
                project = state["projects"].get(scope)
                if not project:
                    continue
                group = "Projects/" + project["folder"]
            relative = Path(os.path.relpath(note["path"], self.root / group)).as_posix()
            groups[group].append(f"- [{str(meta.get('title', 'Note')).replace('[', '').replace(']', '')}]({quote(relative, safe='/.-')}) ({meta.get('status')})")
            if top == "Inbox":
                relative = Path(os.path.relpath(note["path"], self.root / "Inbox")).as_posix()
                groups["Inbox"].append(f"- [{str(meta.get('title', 'Note')).replace('[', '').replace(']', '')}]({quote(relative, safe='/.-')}) ({meta.get('status')})")
        for project in state["projects"].values():
            folder = "Projects/" + project["folder"]
            if groups[folder] or (self.root / folder / "Overview.md").exists():
                relative = project["folder"] + "/Overview.md"
                groups["Projects"].append(f"- [{project['name'].replace('[', '').replace(']', '')}]({quote(relative, safe='/.-')})")
        for folder, links in groups.items():
            if folder not in TOPS and not links and not (self.root / folder / "Overview.md").exists():
                continue
            path = self.root / folder / "Overview.md"
            block = BEGIN + "\n\n" + "\n".join(sorted(links)) + "\n\n" + END
            if path.exists():
                raw = path.read_bytes().decode("utf-8-sig")
                try:
                    old = managed(raw)
                except VaultError:
                    protected.append(path.relative_to(self.root).as_posix())
                    continue
                if views.get(path.relative_to(self.root).as_posix()) != digest(old.encode()):
                    protected.append(path.relative_to(self.root).as_posix())
                    continue
                raw = raw.replace(old, block, 1)
            else:
                raw = "# " + Path(folder).name + "\n\nGenerated navigation; follow links for evidence.\n\n" + block + "\n"
            if not inside(path, self.root):
                raise VaultError("Overview path escapes the vault")
            atomic(path, raw.encode())
            views[path.relative_to(self.root).as_posix()] = digest(block.encode())
        state["protected_overviews"] = protected
        return protected

    def inspect(self, cwd, rid):
        state = self._state()
        project = self._project(state, cwd)
        note = self._scan(state).get(rid)
        if not note or note["meta"].get("scope") not in {"global", project["id"]}:
            raise VaultError("Note is unavailable in this project")
        sources = []
        for ref in state["records"].get(rid, {}).get("evidence", []):
            source = state["sources"].get(ref["source"], {})
            info = {"source": ref["source"], "start": ref["start"], "end": ref["end"]}
            if source.get("project") == project["id"]:
                info["path"] = source.get("path")
                try:
                    with Path(source["path"]).open("rb") as handle:
                        handle.seek(ref["start"])
                        data = handle.read(ref["end"] - ref["start"])
                    info["unchanged"] = hmac.compare_digest(ref["token"], self._token(state, ref["source"], ref["start"], ref["end"], data))
                except OSError:
                    info["unavailable"] = True
            else:
                info["originating_project_scope_required"] = True
            sources.append(info)
        return {"id": rid, "properties": note["meta"], "text": redact(note["body"]),
                "revision": note["revision"], "sources": sources}

    def allow_topic(self, cwd, kind, scope, title, confirmed=False):
        if not confirmed or kind not in KINDS or not isinstance(title, str) or not title.strip():
            raise VaultError("A fresh explicit remember request is required")
        with lock(self.system / "vault.lock"):
            state = self._state()
            project = self._project(state, cwd, learning=True)
            if scope not in {"global", project["id"]}:
                raise VaultError("Topic is outside this project's scope")
            key = self._key(state, scope, kind, title)
            state["forgotten_keys"] = [x for x in state["forgotten_keys"] if x != key]
            self._event(state, "allow-new-topic-evidence")
            self._save(state)
            return {"new_evidence_allowed": True, "old_source_exclusions_retained": True}

    def forget(self, cwd, rid, confirmed=False):
        if not confirmed:
            raise VaultError("An explicit forgetting request is required")
        with lock(self.system / "vault.lock"):
            state = self._state()
            project = self._project(state, cwd)
            notes = self._scan(state)
            note = notes.get(rid)
            if not note or note["meta"].get("scope") not in {"global", project["id"]}:
                raise VaultError("Note is unavailable in this project")
            record = state["records"].get(rid, {})
            keys = record.get("keys", []) + [self._key(state, note["meta"]["scope"], note["meta"]["type"], note["meta"]["title"])]
            state["forgotten_keys"] = sorted(set(state["forgotten_keys"] + keys))
            state.setdefault("forgotten_ids", []).append(rid)
            for ref in record.get("evidence", []):
                state["exclusions"].append({k: ref[k] for k in ("source", "start", "end")})
            # Persist exclusions first: an interrupted deletion cannot reimport the source.
            state["records"].pop(rid, None)
            state.setdefault("deleting", {})[rid] = note["path"].relative_to(self.root).as_posix()
            self._save(state)
            self._finish_delete(state)
            self._event(state, "forget", rid)
            self._save(state)
            self._views(state)
            self._save(state)
            return {"forgotten": rid, "external_sources_deleted": False,
                    "protected_overviews": state.get("protected_overviews", []),
                    "complete": not state.get("protected_overviews")}

    def _finish_delete(self, state):
        for rid, relative in list(state.get("deleting", {}).items()):
            self._path(relative).unlink(missing_ok=True)
            history = self.system / "history" / rid
            if not re.fullmatch(r"[a-f0-9]{32}", rid) or not inside(history, self.system / "history") or not inside(history, self.root):
                raise VaultError("Invalid history deletion target")
            if history.exists():
                shutil.rmtree(history)
            del state["deleting"][rid]

    def pending(self):
        state = self._state()
        result = []
        for sid, source in state["sources"].items():
            if state["projects"].get(source["project"], {}).get("mode") != "learn":
                continue
            if source.get("next_attempt", 0) > time.time():
                continue
            try:
                stat = Path(source["path"]).stat()
                changed = [stat.st_size, stat.st_mtime_ns] != source.get("signature")
            except OSError:
                changed = True
            if source["pending"] or changed:
                result.append({k: source[k] for k in ("id", "project", "path", "kind", "cursor", "failures")})
        return result[:20]

    def checkpoint(self, sid, start, through, token):
        with lock(self.system / "vault.lock"):
            state = self._state()
            source = self._source(state, sid)
            budget = MAX_TRANSCRIPT_BYTES if source["kind"] == "chat" else MAX_CHUNK
            if type(start) is not int or source["cursor"] != start or type(through) is not int or not start <= through or through - start > budget:
                raise VaultError("Checkpoint is stale or outside the source chunk")
            with Path(source["path"]).open("rb") as handle:
                prefix = handle.read(start)
                data = handle.read(through - start)
            if digest(prefix) != source["prefix"] or len(data) != through - start or not hmac.compare_digest(str(token), self._token(state, sid, start, through, data)):
                raise VaultError("Source changed before checkpoint; no work was acknowledged")
            stat = Path(source["path"]).stat()
            source.update(cursor=through, prefix=digest(prefix + data), pending=False, failures=0, next_attempt=0,
                          signature=[through, stat.st_mtime_ns])
            if source["kind"] == "chat":
                source["processor_active"] = processor_after(source.get("processor_active", False), data)
            state["errors"].pop(sid, None)
            self._save(state)
            return {"source": sid, "through": through}

    def fail(self, sid):
        with lock(self.system / "vault.lock"):
            state = self._state()
            source = self._source(state, sid)
            source["failures"] += 1
            source["pending"] = True
            source["next_attempt"] = time.time() + min(3600, 60 * 2 ** min(source["failures"], 6))
            state["errors"][sid] = {"at": now(), "message": "Source processing failed; pending work retained"}
            self._save(state)

    def processor(self, session):
        if not session:
            raise VaultError("Processor session identity is required")
        with lock(self.system / "vault.lock"):
            state = self._state()
            current = state["sessions"].get(session, {})
            if not current.get("turn") or not current.get("processor_turn"):
                raise VaultError("Processor requires an observed prompt hook with the background marker")
            current["processor_confirmed"] = current["turn"]
            self._save(state)

    def status(self):
        state = self._state()
        return {"projects": list(state["projects"].values()), "pending": self.pending(),
                "errors": state["errors"], "hook_observations": state["hook_observations"],
                "protected_overviews": state.get("protected_overviews", []),
                "automatic_capture": "requires installed trusted hooks and a tested background task"}

    def maintain(self):
        with lock(self.system / "vault.lock"):
            state = self._state()
            self._finish_delete(state)
            for rid, note in self._scan(state).items():
                if rid in state["records"]:
                    state["records"][rid]["path"] = note["path"].relative_to(self.root).as_posix()
            self._views(state)
            self._save(state)
            return {"maintained": True, "protected_overviews": state.get("protected_overviews", [])}
