"""Tests for per-chunk task extraction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.task_extractor import deduplicate_tasks


class TestDeduplicateTasks:
    def test_no_duplicates(self):
        tasks = [
            {"title": "Enforce JWT auth"},
            {"title": "Use camelCase for functions"},
            {"title": "Log all errors"},
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 3

    def test_exact_duplicates_removed(self):
        tasks = [
            {"title": "Enforce JWT auth"},
            {"title": "Enforce JWT auth"},
            {"title": "Use camelCase for functions"},
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 2

    def test_near_duplicates_removed(self):
        tasks = [
            {"title": "Enforce JWT authentication for API endpoints"},
            {"title": "Enforce JWT authentication for all API endpoints"},
            {"title": "Use camelCase naming convention"},
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 2

    def test_different_tasks_kept(self):
        tasks = [
            {"title": "Security: enforce authentication"},
            {"title": "Quality: enforce naming conventions"},
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 2

    def test_empty_list(self):
        assert deduplicate_tasks([]) == []

    def test_single_task(self):
        tasks = [{"title": "One task"}]
        assert deduplicate_tasks(tasks) == tasks

    def test_first_occurrence_kept(self):
        tasks = [
            {"title": "Enforce JWT auth", "id": "first"},
            {"title": "Enforce JWT auth", "id": "second"},
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 1
        assert result[0]["id"] == "first"

    def test_missing_title_handled(self):
        tasks = [
            {"title": ""},
            {"title": "Real task"},
            {"description": "no title field"},
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) >= 2
