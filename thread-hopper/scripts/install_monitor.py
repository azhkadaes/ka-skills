"""Register or remove only Thread Hopper's user-level hooks; never edits hook trust."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

from thread_hopper_hook import atomic_json


EVENTS = ("SessionStart", "UserPromptSubmit", "PostModelRequest", "PostToolUse", "Stop")
START = "<!-- thread-hopper:start -->"
END = "<!-- thread-hopper:end -->"


def merged_instructions(original, skill, remove=False):
    text = original.decode("utf-8-sig")
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError("Ambiguous Thread Hopper instruction markers; review AGENTS.md")
    block = ""
    if not remove:
        template = skill / "references" / "agent-fallback.md"
        block = START + "\n" + template.read_text(encoding="utf-8").replace(
            "{{SKILL_PATH}}", (skill / "SKILL.md").as_posix()).strip() + "\n" + END
    if START in text:
        left, rest = text.split(START, 1)
        managed, right = rest.split(END, 1)
        text = left + block + right
    elif block:
        text += ("\n\n" if text and not text.endswith("\n\n") else "") + block + "\n"
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    return bom + text.encode("utf-8")


def install_fallback(root, skill, remove=False, dry_run=False):
    # A global override replaces AGENTS.md. Update the active file, preserving its other guidance.
    override = root / "AGENTS.override.md"
    path = override if override.exists() and override.stat().st_size else root / "AGENTS.md"
    original = path.read_bytes() if path.exists() else b""
    updated = merged_instructions(original, skill, remove)
    if original != updated and not dry_run:
        backups = root / "thread-hopper" / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (backups / f"{path.name}-{stamp}.bak").write_bytes(original)
        if (path.read_bytes() if path.exists() else b"") != original:
            raise ValueError("Agent instructions changed during installation; retry")
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_bytes(updated)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return {"file": str(path), "enabled": not remove, "changed": original != updated}


def merged_hooks(data, command, remove=False):
    data = json.loads(json.dumps(data))
    hooks = data.setdefault("hooks", {})
    for event in EVENTS:
        groups = hooks.get(event, [])
        kept = []
        for group in groups:
            group = dict(group)
            handlers = group.get("hooks", [])
            group["hooks"] = [handler for handler in handlers
                              if handler.get("command") != command]
            if group["hooks"]:
                kept.append(group)
        if not remove:
            handler = {"type": "command", "command": command, "timeout": 3}
            if event != "Stop":
                handler["async"] = True
            if event in ("SessionStart", "UserPromptSubmit", "PostToolUse"):
                handler["additionalContextLimit"] = 400
            group = {"hooks": [handler]}
            if event == "PostToolUse":
                group["matcher"] = ".*"
            kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--agent-fallback", action="store_true",
                        help="Also manage a persistent, agent-driven fallback in global instructions")
    args = parser.parse_args()
    root = Path(args.codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
    script = Path(__file__).with_name("thread_hopper_hook.py").resolve()
    # Forward slashes keep quoted Windows paths valid in the hook shell.
    command = f'"{Path(sys.executable).as_posix()}" -B "{script.as_posix()}"'
    path = root / "hooks.json"
    original = path.read_bytes() if path.exists() else None
    data = json.loads(original.decode("utf-8-sig")) if original else {}
    updated = merged_hooks(data, command, args.remove)
    fallback = None
    if args.agent_fallback:
        fallback = install_fallback(root, script.parents[1], args.remove, args.dry_run)
    if args.dry_run:
        print(json.dumps({"hooks_config": updated, "agent_fallback": fallback}, indent=2))
        return
    if data != updated:
        if original is not None:
            backup_dir = root / "thread-hopper" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copyfile(path, backup_dir / f"hooks-{timestamp}.json")
        # Refuse to overwrite another process's intervening configuration change.
        if (path.read_bytes() if path.exists() else None) != original:
            raise ValueError("Hooks changed during installation; retry")
        atomic_json(path, updated)
    print(json.dumps({"registered": not args.remove, "hooks_file": str(path),
                      "agent_fallback": fallback,
                      "events": list(EVENTS), "trust": "Requires Codex hook review; not modified",
                      "activation": "Reload/resume a chat after trusting hooks"}))


if __name__ == "__main__":
    main()
