
from app.patch_generator import create_patch_preview


def test_valid_patch_generates_diff():
    original = "response = requests.get('/v1/users')\n"
    proposed = "response = requests.get('/v2/users')\n"

    result = create_patch_preview(
        original,
        proposed,
        "client.py",
    )

    assert result["status"] == "ready_for_review"
    assert result["changed"] is True
    assert "--- a/client.py" in result["patch"]
    assert "+++ b/client.py" in result["patch"]
    assert "-response = requests.get('/v1/users')" in result["patch"]
    assert "+response = requests.get('/v2/users')" in result["patch"]
    assert result["applied"] is False
    assert result["original_modified"] is False


def test_invalid_python_patch_is_rejected():
    original = "response = 1\n"
    proposed = "def broken(\n"

    result = create_patch_preview(
        original,
        proposed,
        "client.py",
    )

    assert result["status"] == "rejected_invalid_syntax"
    assert result["verification"]["valid"] is False
    assert result["applied"] is False


def test_identical_code_returns_no_changes():
    source = "response = requests.get('/v1/users')\n"

    result = create_patch_preview(
        source,
        source,
        "client.py",
    )

    assert result["status"] == "no_changes"
    assert result["patch"] == ""
    assert result["changed"] is False
