
import ast
from pathlib import Path
from typing import Any


HTTP_METHODS = {
    "get", "post", "put", "patch",
    "delete", "options", "head",
}


def _get_call_name(node: ast.AST) -> str:
    """Return a readable name for a function call."""
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _get_call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr

    return ""


def _get_string_value(node: ast.AST) -> str | None:
    """Extract a literal string from a Python AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    return None


def analyze_python_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Find likely HTTP API calls and return their source locations."""
    path = Path(file_path)

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return [{
            "file": str(path),
            "error": str(exc),
        }]

    findings = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        call_name = _get_call_name(node.func)
        method = None

        # requests.get(...), httpx.post(...), etc.
        if call_name.split(".")[-1].lower() in HTTP_METHODS:
            method = call_name.split(".")[-1].upper()

        # session.request("GET", ...) or client.request(...)
        elif call_name.split(".")[-1].lower() == "request":
            if node.args:
                first_arg = _get_string_value(node.args[0])
                if first_arg and first_arg.lower() in HTTP_METHODS:
                    method = first_arg.upper()

            if method is None:
                for keyword in node.keywords:
                    if keyword.arg == "method":
                        value = _get_string_value(keyword.value)
                        if value and value.lower() in HTTP_METHODS:
                            method = value.upper()

        if method is None:
            continue

        url = None

        # Find URLs supplied as positional arguments or url=...
        for arg in node.args:
            value = _get_string_value(arg)
            if value and (
                value.startswith("/")
                or "://" in value
            ):
                url = value
                break

        if url is None:
            for keyword in node.keywords:
                if keyword.arg in {"url", "uri"}:
                    url = _get_string_value(keyword.value)
                    if url:
                        break

        findings.append({
            "file": str(path),
            "line": node.lineno,
            "method": method,
            "url": url,
            "call": call_name,
        })

    return sorted(findings, key=lambda item: item.get("line", 0))


def analyze_python_project(
    project_path: str | Path,
) -> list[dict[str, Any]]:
    """Analyze Python files under a project directory."""
    root = Path(project_path)

    if not root.exists() or not root.is_dir():
        raise ValueError(f"Not a valid project directory: {root}")

    findings = []
    ignored_dirs = {
        ".git", ".venv", "venv", "__pycache__",
        "node_modules", ".pytest_cache",
    }

    for file_path in root.rglob("*.py"):
        if any(part in ignored_dirs for part in file_path.parts):
            continue
        findings.extend(analyze_python_file(file_path))

    return findings
