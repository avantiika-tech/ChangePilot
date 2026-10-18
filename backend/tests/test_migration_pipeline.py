from pathlib import Path

from app.migration_pipeline import analyze_migration


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
