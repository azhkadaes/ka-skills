"""Install Context Vault and merge its hooks without changing Codex hook trust."""

import argparse
import json
import os
from pathlib import Path
import shutil
import shlex
import sys

from vault import Vault, VaultError, atomic_json, load_json, now


EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")


def hook_command(executable, script, config, windows=None):
    windows = os.name == "nt" if windows is None else windows
    arguments = [Path(executable).as_posix(), "-B", Path(script).as_posix(), "--config", Path(config).as_posix()]
    if windows:
        # Bare, safe path tokens work in both PowerShell and cmd. Quoted program
        # expressions are not executable PowerShell calls without a call operator.
        if any(not all(c.isalnum() or c in "_:/\\.-" for c in argument) for argument in arguments):
            raise VaultError("Windows hook setup requires launcher paths without spaces or shell metacharacters; use a supported explicit shell launcher for other paths")
        return " ".join(arguments)
    return shlex.join(arguments)


def merge_hooks(data, command, old_command=None, remove=False):
    updated = json.loads(json.dumps(data))
    hooks = updated.setdefault("hooks", {})
    owned_commands = {command}
    if old_command:
        owned_commands.add(old_command)
    for event in EVENTS:
        groups = []
        for original in hooks.get(event, []):
            group = dict(original)
            group["hooks"] = [x for x in group.get("hooks", []) if not
                              (x.get("type") == "command" and x.get("command") in owned_commands)]
            if group["hooks"]:
                groups.append(group)
        if not remove:
            handler = {"type": "command", "command": command, "timeout": 3}
            if event == "Stop":
                handler["async"] = True
            if event in {"SessionStart", "UserPromptSubmit"}:
                handler["additionalContextLimit"] = 2000
            groups.append({"hooks": [handler]})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    return updated


def install(vault_path, codex_home, dry_run=False, remove=False):
    home = Path(codex_home).expanduser().resolve()
    source = Path(__file__).resolve().parents[1]
    target = home / "skills" / "context-vault"
    config_file = home / "context-vault" / "config.json"
    hook_file = home / "hooks.json"
    previous = load_json(config_file) if config_file.exists() else {}
    if previous and Path(previous["vault"]).resolve() != Path(vault_path).expanduser().resolve():
        raise VaultError("An existing installation uses another vault; resolve that explicitly")
    command = hook_command(Path(sys.executable).resolve(), target / "scripts" / "hook.py", config_file)
    original = hook_file.read_bytes() if hook_file.exists() else None
    data = json.loads(original.decode("utf-8-sig")) if original else {}
    updated = merge_hooks(data, command, previous.get("installed_command"), remove)
    config = {"enabled": not remove, "vault": str(Path(vault_path).expanduser().resolve()),
              "transcript_roots": [str(home / "sessions")], "installed_command": command,
              "background_task_id": previous.get("background_task_id"),
              "background_verified": previous.get("background_verified", False)}
    plan = {"skill": str(target), "vault": config["vault"], "hooks_file": str(hook_file),
            "events": list(EVENTS), "registered": not remove,
            "hook_trust": "unchanged; Codex review is required",
            "activation": "unverified until an actual host hook event is observed",
            "background": "use the Codex automation tool after a bounded worker test"}
    if dry_run:
        return {**plan, "dry_run": True, "proposed_hooks": updated}
    if not remove:
        if target.exists() and target.resolve() != source:
            for path in source.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    existing = target / path.relative_to(source)
                    if existing.exists() and existing.read_bytes() != path.read_bytes():
                        raise VaultError("Installed skill differs; review and upgrade it explicitly")
        Vault.initialize(vault_path)
        if target.resolve() != source:
            shutil.copytree(source, target, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if (hook_file.read_bytes() if hook_file.exists() else None) != original:
        raise VaultError("Hook configuration changed during setup; retry")
    if original is not None and updated != data:
        backup = home / "context-vault" / "backups" / ("hooks-" + now().replace(":", "-") + ".json")
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            backup.write_bytes(original)
    atomic_json(config_file, config)
    if data != updated:
        atomic_json(hook_file, updated)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.vault, args.codex_home, args.dry_run, args.remove), ensure_ascii=False))
    except (VaultError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc) if isinstance(exc, VaultError) else "Installation failed; review paths and existing configuration"}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
