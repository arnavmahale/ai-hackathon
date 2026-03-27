"""Tests for validate_code.py core functions."""
import sys
import json
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from validate_code import (
    _truncate_code,
    _build_ai_messages,
    _task_summary,
    _rule_applies_to_file,
    normalize_tasks_config,
    _convert_guardian_task,
    Finding,
)


class TestTruncateCode:
    def test_short_code_unchanged(self):
        code = "print('hello')"
        result, truncated = _truncate_code(code, limit=100)
        assert result == code
        assert truncated is False

    def test_long_code_truncated(self):
        code = "x" * 200
        result, truncated = _truncate_code(code, limit=100)
        assert truncated is True
        assert len(result) < len(code)
        assert "..." in result

    def test_truncation_preserves_head_and_tail(self):
        code = "HEAD" + "x" * 200 + "TAIL"
        result, truncated = _truncate_code(code, limit=100)
        assert result.startswith("HEAD")
        assert result.endswith("TAIL")

    def test_exact_limit(self):
        code = "x" * 100
        result, truncated = _truncate_code(code, limit=100)
        assert truncated is False
        assert result == code


class TestBuildAIMessages:
    def test_basic_message_structure(self):
        payloads = [{"internalRef": 0, "name": "test", "description": "desc"}]
        messages = _build_ai_messages(payloads, "test.py", "print('hi')")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "test.py" in messages[1]["content"]
        assert "print('hi')" in messages[1]["content"]

    def test_rag_context_included(self):
        payloads = [{"internalRef": 0, "name": "test", "description": "desc"}]
        rag_context = [
            {"doc_id": "security-doc", "text": "Must use JWT auth", "score": 0.5},
        ]
        messages = _build_ai_messages(payloads, "test.py", "code", rag_context=rag_context)
        content = messages[1]["content"]
        assert "REFERENCE DOCUMENTATION" in content
        assert "security-doc" in content
        assert "Must use JWT auth" in content

    def test_no_rag_context(self):
        payloads = [{"internalRef": 0, "name": "test", "description": "desc"}]
        messages = _build_ai_messages(payloads, "test.py", "code", rag_context=None)
        content = messages[1]["content"]
        assert "REFERENCE DOCUMENTATION" not in content

    def test_multiple_rag_contexts(self):
        payloads = [{"internalRef": 0, "name": "test", "description": "desc"}]
        rag_context = [
            {"doc_id": "sec-doc", "text": "Use JWT auth", "score": 0.3},
            {"doc_id": "quality-doc", "text": "Use camelCase", "score": 0.6},
        ]
        messages = _build_ai_messages(payloads, "test.py", "code", rag_context=rag_context)
        content = messages[1]["content"]
        assert "sec-doc" in content
        assert "quality-doc" in content
        assert "Use JWT auth" in content
        assert "Use camelCase" in content

    def test_source_chunk_context_format(self):
        """Source chunks from linked tasks use score 0.0 (direct link, not search)."""
        payloads = [{"internalRef": 0, "name": "test"}]
        rag_context = [
            {"doc_id": "policy.md", "text": "All endpoints must use auth", "score": 0.0},
        ]
        messages = _build_ai_messages(payloads, "test.py", "code", rag_context=rag_context)
        content = messages[1]["content"]
        assert "policy.md" in content
        assert "All endpoints must use auth" in content

    def test_truncation_note(self):
        payloads = [{"internalRef": 0, "name": "test"}]
        long_code = "x" * 10000
        messages = _build_ai_messages(payloads, "test.py", long_code)
        assert "truncated" in messages[1]["content"].lower()


class TestTaskSummary:
    def test_basic_summary(self):
        rule = {
            "id": "task_001",
            "name": "Test Rule",
            "description": "A test rule",
            "severity": "warning",
        }
        summary = _task_summary(rule, 5)
        assert summary["internalRef"] == 5
        assert summary["name"] == "Test Rule"

    def test_ai_spec_used(self):
        rule = {
            "name": "outer",
            "ai_spec": {"name": "inner", "id": "t1", "description": "inner desc"},
        }
        summary = _task_summary(rule, 0)
        assert summary["name"] == "inner"


class TestRuleAppliesToFile:
    def test_wildcard_matches_all(self):
        rule = {"file_globs": ["*"]}
        assert _rule_applies_to_file(rule, "anything.py") is True

    def test_py_glob(self):
        rule = {"file_globs": ["*.py"]}
        assert _rule_applies_to_file(rule, "test.py") is True
        assert _rule_applies_to_file(rule, "test.js") is False

    def test_no_globs_matches_all(self):
        rule = {"file_globs": None}
        assert _rule_applies_to_file(rule, "test.py") is True
        rule2 = {}
        assert _rule_applies_to_file(rule2, "test.py") is True


class TestNormalizeTasksConfig:
    def test_dict_format(self):
        cfg = {"rules": [{"id": "t1"}]}
        result = normalize_tasks_config(cfg)
        assert "rules" in result

    def test_list_format(self):
        cfg = [{"id": "t1", "title": "Test", "description": "desc"}]
        result = normalize_tasks_config(cfg)
        assert "rules" in result
        assert len(result["rules"]) == 1

    def test_invalid_format(self):
        with pytest.raises(RuntimeError):
            normalize_tasks_config("invalid")


class TestConvertGuardianTask:
    def test_valid_task(self):
        task = {
            "id": "task_001",
            "title": "Test",
            "description": "Test desc",
            "category": "Security",
            "severity": "critical",
            "checkType": "Pattern",
            "fileTypes": ["*.py"],
        }
        result = _convert_guardian_task(task)
        assert result is not None
        assert result["id"] == "task_001"
        assert result["file_globs"] == ["*.py"]

    def test_non_dict_returns_none(self):
        assert _convert_guardian_task("not a dict") is None
        assert _convert_guardian_task(42) is None


class TestFinding:
    def test_as_dict(self):
        f = Finding(task="test", file="a.py", line=10, column=5, message="bad", fix="good")
        d = f.as_dict()
        assert d["task"] == "test"
        assert d["file"] == "a.py"
        assert d["line"] == 10
        assert d["fix"] == "good"
