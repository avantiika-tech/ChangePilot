
from typing import Any


def check_patch_policy(
    patch_result: dict[str, Any],
    expected_filename: str,
) -> dict[str, Any]:
    """
    Check basic safety conditions for a proposed patch.

    This checks patch metadata and scope, not semantic correctness.
    """
    errors: list[str] = []

    actual_filename = patch_result.get("filename")
    status = patch_result.get("status")
    patch = patch_result.get("patch", "")

    if actual_filename != expected_filename:
        errors.append("Patch filename does not match the expected file.")

    if patch_result.get("applied", False):
        errors.append("Patch must not be applied automatically.")

    if patch_result.get("original_modified", False):
        errors.append("Original source must remain unchanged.")

    verification = patch_result.get("verification", {})
    if not verification.get("valid", False):
        errors.append("Proposed Python code did not pass syntax validation.")

    if status == "rejected_invalid_syntax":
        errors.append("Patch was rejected because of invalid syntax.")

    if status == "no_changes" or not patch:
        errors.append("Patch contains no changes.")

    return {
        "allowed_for_review": len(errors) == 0,
        "errors": errors,
        "filename": actual_filename,
        "status": "passed" if not errors else "blocked",
        "semantic_correctness_verified": False,
    }
