"""
Unit tests for core.scope.EngagementScope.

Pure unit tests: no live msfrpcd required. Scope objects are built in
memory (not loaded from scope.json) so these run anywhere.

Run:
    pytest tests/tool_tests/test_scope_guard.py -v
"""
import json

import pytest

from core.scope import EngagementScope, ScopeEntry


def make_scope(tmp_path, entries):
    return EngagementScope(
        entries=entries,
        source="test-scope",
        audit_log_path=tmp_path / "scope_audit.log",
    )


def test_single_ip_in_scope_is_authorized(tmp_path):
    scope = make_scope(tmp_path, [ScopeEntry(target="192.168.56.101")])
    assert scope.authorize("192.168.56.101", tool_name="nmap_scan") is None


def test_ip_not_in_scope_is_rejected(tmp_path):
    scope = make_scope(tmp_path, [ScopeEntry(target="192.168.56.101")])
    reason = scope.authorize("10.0.0.5", tool_name="nmap_scan")
    assert reason is not None
    assert "10.0.0.5" in reason


def test_cidr_target_covered_by_broader_entry_is_authorized(tmp_path):
    scope = make_scope(tmp_path, [ScopeEntry(target="192.168.56.0/24")])
    assert scope.authorize("192.168.56.50", tool_name="nmap_scan") is None
    assert scope.authorize("192.168.56.0/25", tool_name="nmap_scan") is None


def test_cidr_target_broader_than_authorized_host_is_rejected(tmp_path):
    scope = make_scope(tmp_path, [ScopeEntry(target="192.168.56.101")])  # implicit /32
    reason = scope.authorize("192.168.56.0/24", tool_name="nmap_scan")
    assert reason is not None


def test_hostname_glob_entry_matches(tmp_path):
    scope = make_scope(tmp_path, [ScopeEntry(target="*.lab.local")])
    assert scope.authorize("target1.lab.local", tool_name="nmap_scan") is None
    reason = scope.authorize("target1.evil.com", tool_name="nmap_scan")
    assert reason is not None


def test_metasploit_range_syntax_is_rejected_fail_closed(tmp_path):
    # "192.168.56.101" is in scope, but the RHOSTS range syntax below is not
    # parsed by design — it must be rejected outright rather than guessed at.
    scope = make_scope(tmp_path, [ScopeEntry(target="192.168.56.0/24")])
    reason = scope.authorize("192.168.56.1-50", tool_name="run_module")
    assert reason is not None


def test_exploit_requires_allow_exploit_flag(tmp_path):
    scope = make_scope(
        tmp_path,
        [ScopeEntry(target="192.168.56.101", allow_exploit=False)],
    )
    # scanning/auxiliary is fine
    assert scope.authorize("192.168.56.101", tool_name="run_module", require_exploit=False) is None
    # exploit-class is not
    reason = scope.authorize("192.168.56.101", tool_name="run_module", require_exploit=True)
    assert reason is not None
    assert "exploit" in reason


def test_exploit_allowed_when_flag_set(tmp_path):
    scope = make_scope(
        tmp_path,
        [ScopeEntry(target="192.168.56.101", allow_exploit=True)],
    )
    assert scope.authorize("192.168.56.101", tool_name="run_module", require_exploit=True) is None


def test_missing_scope_file_fails_closed(tmp_path):
    scope = EngagementScope.load(path=tmp_path / "does-not-exist.json")
    scope.audit_log_path = tmp_path / "audit.log"  # keep this test's audit trail out of the real log
    assert scope.entries == []
    assert scope.authorize("127.0.0.1", tool_name="nmap_scan") is not None


def test_authorize_writes_audit_log_for_both_outcomes(tmp_path):
    scope = make_scope(tmp_path, [ScopeEntry(target="192.168.56.101")])

    scope.authorize("192.168.56.101", tool_name="nmap_scan")  # allowed
    scope.authorize("10.0.0.5", tool_name="nmap_scan")        # rejected

    lines = scope.audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert records[0]["allowed"] is True
    assert records[0]["target"] == "192.168.56.101"
    assert records[1]["allowed"] is False
    assert records[1]["target"] == "10.0.0.5"


def test_load_reads_targets_from_file(tmp_path):
    scope_file = tmp_path / "scope.json"
    scope_file.write_text(json.dumps({
        "targets": [
            {"target": "192.168.56.101", "allow_exploit": True, "note": "lab VM"},
        ]
    }))

    scope = EngagementScope.load(path=scope_file)
    scope.audit_log_path = tmp_path / "audit.log"  # keep this test's audit trail out of the real log
    assert len(scope.entries) == 1
    assert scope.authorize("192.168.56.101", tool_name="run_module", require_exploit=True) is None
