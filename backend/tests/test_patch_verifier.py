from app.patch_verifier import verify_python_patch


def test_valid_python_patch():
    result = verify_python_patch("response = requests.get('/users')")

    assert result["valid"] is True
    assert result["status"] == "syntax_valid"
    assert result["error"] is None


def test_invalid_python_patch():
    result = verify_python_patch("def broken(:")

    assert result["valid"] is False
    assert result["status"] == "syntax_error"
    assert result["error"] is not None
    assert result["line"] == 1


def test_empty_source_is_valid_python():
    result = verify_python_patch("")

    assert result["valid"] is True
