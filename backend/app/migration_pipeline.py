from pathlib import Path
from typing import Any

from app.diff_engine import compare_specs, load_spec
from app.impact_analyzer import analyze_python_project, match_changes_to_calls
from app.migration_agent import generate_migration_plan
from app.patch_verifier import verify_python_patch


def analyze_migration(
    old_spec_path: str | Path,
    new_spec_path: str | Path,
    project_path: str | Path,
) -> dict[str, Any]:
    """Run API diffing, impact analysis, and migration planning."""
    old_spec = load_spec(old_spec_path)
    new_spec = load_spec(new_spec_path)

    changes = compare_specs(old_spec, new_spec)
    findings = analyze_python_project(project_path)
    matches = match_changes_to_calls(changes, findings)
    plan = generate_migration_plan(matches)

    return {
        "summary": {
            "total_changes": len(changes),
            "breaking_changes": sum(
                1 for change in changes if change.get("breaking")
            ),
            "affected_calls": sum(
                item["potential_impact_count"] for item in matches
            ),
            "migration_recommendations": len(plan),
        },
        "changes": changes,
        "impact_analysis": matches,
        "migration_plan": plan,
    }


def verify_proposed_patch(
    source_code: str,
    filename: str = "<proposed_patch>",
) -> dict[str, Any]:
    """Validate proposed Python code without executing or applying it."""
    return verify_python_patch(source_code, filename)
