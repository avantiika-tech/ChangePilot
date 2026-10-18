
from pathlib import Path
from typing import Any

from app.diff_engine import compare_specs, load_spec
from app.impact_analyzer import analyze_python_project, match_changes_to_calls
from app.migration_agent import generate_migration_plan
from app.patch_generator import create_patch_preview
from app.patch_policy import check_patch_policy
from app.patch_verifier import verify_python_patch


def review_migration_patch(
    original_code: str,
    proposed_code: str,
    filename: str,
    expected_filename: str | None = None,
) -> dict[str, Any]:
    """Preview and check a proposed Python migration patch."""
    patch_preview = create_patch_preview(
        original_code=original_code,
        proposed_code=proposed_code,
        filename=filename,
    )

    policy_result = check_patch_policy(
        patch_result=patch_preview,
        expected_filename=expected_filename or filename,
    )

    return {
        "preview": patch_preview,
        "policy": policy_result,
        "ready_for_review": policy_result["allowed_for_review"],
        "semantic_correctness_verified": False,
    }


def analyze_migration(
    old_spec_path: str | Path,
    new_spec_path: str | Path,
    project_path: str | Path,
    original_code: str | None = None,
    proposed_code: str | None = None,
    patch_filename: str | None = None,
    expected_patch_filename: str | None = None,
) -> dict[str, Any]:
    """Run API diffing, impact analysis, and migration planning."""

    # Check patch inputs before trying to load API specification files.
    patch_inputs_provided = any(
        value is not None
        for value in (
            original_code,
            proposed_code,
            patch_filename,
            expected_patch_filename,
        )
    )

    if patch_inputs_provided and (
        original_code is None
        or proposed_code is None
        or not patch_filename
    ):
        raise ValueError(
            "Provide original_code, proposed_code, and "
            "patch_filename together to review a patch."
        )

    # Load API specifications only after validating the inputs.
    old_spec = load_spec(old_spec_path)
    new_spec = load_spec(new_spec_path)
    changes = compare_specs(old_spec, new_spec)
    findings = analyze_python_project(project_path)
    matches = match_changes_to_calls(changes, findings)
    plan = generate_migration_plan(matches)

    patch_inputs_provided = any(
        value is not None
        for value in (
            original_code,
            proposed_code,
            patch_filename,
            expected_patch_filename,
        )
    )

    patch_review = None

    if patch_inputs_provided:
        if (
            original_code is None
            or proposed_code is None
            or not patch_filename
        ):
            raise ValueError(
                "Provide original_code, proposed_code, and "
                "patch_filename together to review a patch."
            )

        patch_review = review_migration_patch(
            original_code=original_code,
            proposed_code=proposed_code,
            filename=patch_filename,
            expected_filename=expected_patch_filename,
        )

    report = {
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

    if patch_review is not None:
        report["patch_review"] = patch_review

    return report


def verify_proposed_patch(
    source_code: str,
    filename: str = "<proposed_patch>",
) -> dict[str, Any]:
    """Validate proposed Python code without executing or applying it."""
    return verify_python_patch(source_code, filename)
