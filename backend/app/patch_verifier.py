import ast
from typing import Any


def verify_python_patch(
    source_code: str,
    filename: str = "<proposed_patch>",
) -> dict[str, Any]:
    """Check proposed Python code for syntax errors without executing it."""
    try:
        ast.parse(source_code, filename=filename)
    except SyntaxError as exc:
        return {
            "valid": False,
            "status": "syntax_error",
            "filename": filename,
            "error": exc.msg,
            "line": exc.lineno,
            "column": exc.offset,
        }

    return {
        "valid": True,
        "status": "syntax_valid",
        "filename": filename,
        "error": None,
        "line": None,
        "column": None,
    }
