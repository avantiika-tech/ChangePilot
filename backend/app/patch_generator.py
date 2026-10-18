
from difflib import unified_diff
from typing import Any

from app.patch_verifier import verify_python_patch


def create_patch_preview(
    original_code: str,
    proposed_code: str,
    filename: str,
) -> dict[str, Any]:
    """
    Generate a reviewable code diff without applying or executing it.
    """
    verification = verify_python_patch(
        proposed_code,
        filename=filename,
    )

    diff_lines = unified_diff(
        original_code.splitlines(keepends=True),
        proposed_code.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )

    patch = "".join(diff_lines)

    if not verification["valid"]:
        status = "rejected_invalid_syntax"
    elif not patch:
        status = "no_changes"
    else:
        status = "ready_for_review"

    return {
        "filename": filename,
        "status": status,
        "patch": patch,
        "changed": bool(patch),
        "verification": verification,
        "applied": False,
        "original_modified": False,
        "safety_note": (
            "The patch has not been applied. Syntax validation alone "
            "does not establish migration correctness."
        ),
    }
