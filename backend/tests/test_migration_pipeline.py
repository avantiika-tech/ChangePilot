import pytest

from app.migration_pipeline import (
    analyze_migration,
    review_migration_patch,
)
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migration_pipeline_returns_report():
    report = analyze_migration(
        BACKEND_DIR / "samples" / "v1.yaml",
        BACKEND_DIR / "samples" / "v2.yaml",
        BACKEND_DIR,
    )

    assert "summary" in report
    assert "changes" in report
    assert "impact_analysis" in report
    assert "migration_plan" in report
    assert report["summary"]["total_changes"] == len(report["changes"])
    assert report["summary"]["migration_recommendations"] == len(
        report["migration_plan"]
    )


def test_pipeline_patch_review_accepts_valid_patch():
    result = review_migration_patch(
        original_code="response = 1\n",
        proposed_code="response = 2\n",
        filename="client.py",
    )

    assert result["ready_for_review"] is True
    assert result["preview"]["status"] == "ready_for_review"
    assert result["policy"]["status"] == "passed"
    assert result["semantic_correctness_verified"] is False


def test_pipeline_patch_review_rejects_invalid_syntax():
    result = review_migration_patch(
        original_code="response = 1\n",
        proposed_code="def broken(\n",
        filename="client.py",
    )

    assert result["ready_for_review"] is False
    assert result["preview"]["status"] == "rejected_invalid_syntax"
    assert result["policy"]["status"] == "blocked"


def test_pipeline_patch_review_rejects_wrong_filename():
    result = review_migration_patch(
        original_code="response = 1\n",
        proposed_code="response = 2\n",
        filename="other.py",
        expected_filename="client.py",
    )

    assert result["ready_for_review"] is False
    assert result["policy"]["status"] == "blocked"


def test_pipeline_requires_all_patch_inputs(tmp_path):
    with pytest.raises(ValueError, match="Provide original_code"):
        analyze_migration(
            old_spec_path=tmp_path / "old.yaml",
            new_spec_path=tmp_path / "new.yaml",
            project_path=tmp_path,
            original_code="response = 1\n",
        )
