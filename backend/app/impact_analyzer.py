
import ast
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse


HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
}


def _get_call_name(node: ast.AST) -> str:
    """Return the dotted name of a function or method call."""
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = _get_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr

    return ""


def _get_string_value(node: ast.AST) -> str | None:
    """Return a string literal's value, if available."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    return None


def _resolve_string(
    node: ast.AST,
    constants: dict[str, str],
) -> str | None:
    """Resolve string literals, known constants, concatenation, and static f-strings."""
    literal = _get_string_value(node)
    if literal is not None:
        return literal

    if isinstance(node, ast.Name):
        return constants.get(node.id)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_string(node.left, constants)
        right = _resolve_string(node.right, constants)

        if left is not None and right is not None:
            return left + right

    if isinstance(node, ast.JoinedStr):
        parts = []

        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(
                value.value, str
            ):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                if isinstance(value.value, ast.Name):
                    resolved = constants.get(value.value.id)
                    if resolved is None:
                        return None
                    parts.append(resolved)
                else:
                    return None
            else:
                return None

        return "".join(parts)

    return None


def _collect_string_constants(tree: ast.AST) -> dict[str, str]:
    """Collect statically resolvable simple string assignments in source order."""
    constants: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        else:
            targets = [node.target]
            value = node.value

        if value is None:
            continue

        resolved = _resolve_string(value, constants)
        if resolved is None:
            continue

        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = resolved

    return constants


def _extract_url(
    node: ast.Call,
    constants: dict[str, str],
) -> str | None:
    """Extract a statically resolvable URL from a common HTTP call."""
    call_name = _get_call_name(node.func)
    method_name = call_name.rsplit(".", 1)[-1].lower()

    if method_name == "request":
        # Example: requests.request("GET", url)
        if len(node.args) >= 2:
            return _resolve_string(node.args[1], constants)

        # Example: requests.request(method="GET", url=url)
        for keyword in node.keywords:
            if keyword.arg in {"url", "uri"}:
                return _resolve_string(keyword.value, constants)

        return None

    if method_name in HTTP_METHODS:
        if node.args:
            return _resolve_string(node.args[0], constants)

        for keyword in node.keywords:
            if keyword.arg in {"url", "uri"}:
                return _resolve_string(keyword.value, constants)

    return None


def _extract_http_method(node: ast.Call) -> str | None:
    """Extract the HTTP method represented by a common HTTP call."""
    call_name = _get_call_name(node.func)
    method_name = call_name.rsplit(".", 1)[-1].lower()

    if method_name in HTTP_METHODS:
        return method_name.upper()

    if method_name == "request":
        if node.args:
            method = _get_string_value(node.args[0])
            if method:
                return method.upper()

        for keyword in node.keywords:
            if keyword.arg == "method":
                method = _get_string_value(keyword.value)
                if method:
                    return method.upper()

    return None


def _extract_static_params(
    node: ast.Call,
    constants: dict[str, str],
) -> dict[str, Any] | None:
    """Extract a statically defined params dictionary from an HTTP call."""
    for keyword in node.keywords:
        if keyword.arg != "params":
            continue

        try:
            value = ast.literal_eval(keyword.value)
        except (ValueError, TypeError, SyntaxError):
            return None

        if isinstance(value, dict):
            return value

        return None

    return None


def analyze_python_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Analyze a Python file and find statically identifiable HTTP calls."""
    path = Path(file_path)

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []

    constants = _collect_string_constants(tree)
    findings: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        method = _extract_http_method(node)
        if method is None:
            continue

        url = _extract_url(node, constants)

        finding = {
            "file": str(path),
            "line": node.lineno,
            "method": method,
            "url": url,
            "call": _get_call_name(node.func),
        }


        params = _extract_static_params(node, constants)
        if params is not None:
            finding["params"] = params

        findings.append(finding)

    return findings


def analyze_python_project(
    project_path: str | Path,
) -> list[dict[str, Any]]:
    """Analyze Python files throughout a project, skipping common generated folders."""
    root = Path(project_path)
    findings: list[dict[str, Any]] = []

    if not root.exists():
        return findings

    for file_path in root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in file_path.parts):
            continue

        findings.extend(analyze_python_file(file_path))

    return findings


def match_changes_to_calls(
    changes: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match API changes to Python calls using method, path, and query parameters."""
    results = []

    for change in changes:
        method = change.get("method", "").upper()
        api_path = change.get("path", "")
        evidence = change.get("evidence", {})

        escaped_path = re.escape(api_path)
        pattern = re.sub(r"\\\{[^/]+\\\}", r"[^/]+", escaped_path)
        pattern = f"^{pattern.rstrip('/')}/?$"

        affected_calls = []

        for finding in findings:
            if finding.get("method", "").upper() != method:
                continue

            url = finding.get("url")
            if not isinstance(url, str) or not url:
                continue

            parsed_url = urlparse(url)

            if not re.match(pattern, parsed_url.path):
                continue

            
            affected_call = {
                "file": finding.get("file"),
                "line": finding.get("line"),
                "call": finding.get("call"),
                "url": url,
                "match_evidence": {
                    "http_method_matches": True,
                    "api_path": api_path,
                    "matched_request_path": parsed_url.path,
                },
            }

            parameter_evidence = change.get("evidence", {})

            if parameter_evidence.get("in") == "path":
                affected_call["parameter_evidence"] = {
                    "parameter": parameter_evidence.get("parameter"),
                    "location": "path",
                    "old_type": parameter_evidence.get("old_type"),
                    "new_type": parameter_evidence.get("new_type"),
                }

            # Check whether a newly required query parameter is supplied.
            if (
                change.get("type") == "added_parameter"
                and evidence.get("in") == "query"
                and evidence.get(
                    "required",
                    evidence.get("new_required"),
                ) is True
            ):
                parameter_name = evidence.get("parameter")

                present_names = {
                    name
                    for name, _ in parse_qsl(
                        parsed_url.query,
                        keep_blank_values=True,
                    )
                }

                params = finding.get("params")
                if isinstance(params, dict):
                    present_names.update(
                        key for key in params if isinstance(key, str)
                    )

                if isinstance(parameter_name, str) and parameter_name:
                    affected_call["required_parameter"] = parameter_name
                    affected_call["parameter_location"] = evidence.get("in", "query")

                    if parameter_name in present_names:
                        affected_call["parameter_status"] = "present"
                        affected_call["parameter_source"] = (
                            "params_dict"
                            if isinstance(params, dict) and parameter_name in params
                            else "url_query"
                        )
                    else:
                        affected_call["parameter_status"] = "missing_from_literal_url"
                        affected_call["parameter_source"] = None

            affected_calls.append(affected_call)

        results.append(
            {
                "change": change,
                "affected_calls": affected_calls,
                "potential_impact_count": len(affected_calls),
            }
        )

    return results
