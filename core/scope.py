"""
Engagement scope guard.

The scope list is data, not code: it lives in a JSON file that a human
writes (`scope.json`, gitignored — see `scope.example.json` for the format)
and the LLM/agent never edits. Whether a target may be scanned, and whether
exploit-class modules may be run against it, is decided by looking that
target up in this file — never by asking the model to "confirm" itself.

Every check (allowed or rejected) is appended to `logs/scope_audit.log`.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

logger = logging.getLogger("scope_guard")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SCOPE_FILE = _REPO_ROOT / "scope.json"
_AUDIT_LOG_PATH = _REPO_ROOT / "logs" / "scope_audit.log"

# Characters that indicate Metasploit RHOSTS range syntax (e.g. "10.0.0.1-50")
# or an otherwise-ambiguous expression we deliberately do not parse. Any
# target segment containing one of these that isn't an exact scope-entry
# match is rejected rather than guessed at.
_AMBIGUOUS_CHARS = ("-", "*", "[", "]")


@dataclass(frozen=True)
class ScopeEntry:
    target: str
    allow_exploit: bool = False
    note: str = ""

    def network(self) -> "ipaddress.IPv4Network | ipaddress.IPv6Network | None":
        try:
            return ipaddress.ip_network(self.target, strict=False)
        except ValueError:
            return None

    def matches_hostname(self, host: str) -> bool:
        return host == self.target or fnmatch(host, self.target)


def _audit(
    *,
    tool_name: str,
    target: str,
    require_exploit: bool,
    allowed: bool,
    reason: str | None,
    audit_log_path: Path,
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "target": target,
        "require_exploit": require_exploit,
        "allowed": allowed,
        "reason": reason,
    }
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    log_fn = logger.info if allowed else logger.warning
    log_fn(
        "scope check tool=%s target=%s require_exploit=%s allowed=%s reason=%s",
        tool_name, target, require_exploit, allowed, reason,
    )


@dataclass
class EngagementScope:
    entries: list[ScopeEntry] = field(default_factory=list)
    source: str = "<empty>"
    audit_log_path: Path = _AUDIT_LOG_PATH

    @classmethod
    def load(cls, path: "str | Path | None" = None) -> "EngagementScope":
        """
        Load scope entries from a JSON file (see `scope.example.json`).

        Resolution order: explicit `path` arg > `SCOPE_FILE` env var >
        `scope.json` at the repo root. If no file is found, returns an
        EMPTY scope — every target is then rejected until the operator
        creates the file. This is intentional: a missing scope file must
        never be silently treated as "anything goes".
        """
        resolved = Path(path) if path is not None else Path(os.getenv("SCOPE_FILE", _DEFAULT_SCOPE_FILE))

        if not resolved.exists():
            logger.warning(
                "No scope file at %s — failing closed, every target will be rejected. "
                "Copy scope.example.json to %s and list authorized targets to proceed.",
                resolved, resolved,
            )
            return cls(entries=[], source=str(resolved))

        raw = json.loads(resolved.read_text(encoding="utf-8"))
        entries = [
            ScopeEntry(
                target=item["target"],
                allow_exploit=bool(item.get("allow_exploit", False)),
                note=item.get("note", ""),
            )
            for item in raw.get("targets", [])
        ]
        logger.info("Loaded %d scope entries from %s", len(entries), resolved)
        return cls(entries=entries, source=str(resolved))

    def _matching_entries(self, piece: str) -> "list[ScopeEntry] | None":
        """
        Return the scope entries covering a single host/CIDR segment, or
        None if the segment itself can't be resolved and must be rejected
        (fail closed) rather than guessed at.
        """
        piece = piece.strip()
        if not piece:
            return None

        try:
            piece_net = ipaddress.ip_network(piece, strict=False)
        except ValueError:
            piece_net = None

        if piece_net is not None:
            return [
                entry for entry in self.entries
                if (entry_net := entry.network()) is not None
                and piece_net.version == entry_net.version
                and piece_net.subnet_of(entry_net)
            ]

        if any(ch in piece for ch in _AMBIGUOUS_CHARS):
            # Not a parseable IP/CIDR, and looks like Metasploit range syntax
            # (e.g. "10.0.0.1-50") or a glob — only accept it if it's an
            # exact, literal match against a configured hostname entry.
            return [e for e in self.entries if e.target == piece] or None

        return [e for e in self.entries if e.matches_hostname(piece)] or None

    def is_authorized(self, target: str) -> bool:
        segments = [p for p in (s.strip() for s in target.split(",")) if p]
        if not segments:
            return False
        return all(self._matching_entries(seg) for seg in segments)

    def allows_exploit(self, target: str) -> bool:
        segments = [p for p in (s.strip() for s in target.split(",")) if p]
        if not segments:
            return False
        for seg in segments:
            entries = self._matching_entries(seg)
            if not entries or not all(e.allow_exploit for e in entries):
                return False
        return True

    def authorize(self, target: str, *, tool_name: str, require_exploit: bool = False) -> "str | None":
        """
        Returns None if `target` is authorized for the requested action;
        otherwise a human-readable rejection reason. Every call is recorded
        in the audit log regardless of outcome.
        """
        if not target:
            reason = "empty target"
        elif not self.is_authorized(target):
            reason = f"target '{target}' is not listed in scope (source: {self.source})"
        elif require_exploit and not self.allows_exploit(target):
            reason = f"target '{target}' is in scope for scanning but not authorized for exploit-class modules"
        else:
            reason = None

        _audit(
            tool_name=tool_name,
            target=target,
            require_exploit=require_exploit,
            allowed=reason is None,
            reason=reason,
            audit_log_path=self.audit_log_path,
        )
        return reason
