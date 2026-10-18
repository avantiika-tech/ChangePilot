
from app.patch_policy import check_patch_policy


def test_valid_patch_is_allowed_for_review():
    result = check_patch_policy(
        {
            "filename": "client.py",
            "status": "ready_for_review",
            "patch": "-old_call()\n+new_call()\n",
            "applied": False,
            "original_modified": False,
            "verification": {"valid": True},
        },
        expected_filename="client.py",
    )

    assert result["allowed_for_review"] is True
    assert result["errors"] == []
    assert result["semantic_correctness_verified"] is False


def test_wrong_filename_is_blocked():
    result = check_patch_policy(
        {
            "filename": "other.py",
            "status": "ready_for_review",
            "patch": "-old_call()\n+new_call()\n",
            "applied": False,
            "original_modified": False,
            "verification": {"valid": True},
        },
        expected_filename="client.py",
    )

    assert result["allowed_for_review"] is False
    assert any("filename" in error.lower() for error in result["errors"])


def test_invalid_syntax_is_blocked():
    result = check_patch_policy(
        {
            "filename": "client.py",
            "status": "rejected_invalid_syntax",
            "patch": "-old_call()\n+def broken(\n",
            "applied": False,
            "original_modified": False,
            "verification": {"valid": False},
        },
        expected_filename="client.py",
    )

    assert result["allowed_for_review"] is False
    assert len(result["errors"]) > 0


def test_already_applied_patch_is_blocked():
    result = check_patch_policy(
        {
            "filename": "client.py",
            "status": "ready_for_review",
            "patch": "-old_call()\n+new_call()\n",
            "applied": True,
            "original_modified": False,
            "verification": {"valid": True},
        },
        expected_filename="client.py",
    )

    assert result["allowed_for_review"] is False
