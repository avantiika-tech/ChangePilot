
import yaml


HTTP_METHODS = {
    "get", "post", "put", "patch",
    "delete", "options", "head", "trace",
}


def load_spec(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        spec = yaml.safe_load(file)

    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        raise ValueError("Invalid OpenAPI document: expected a paths object.")

    return spec


def get_operations(spec):
    operations = {}

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        path_parameters = path_item.get("parameters", [])
        if not isinstance(path_parameters, list):
            path_parameters = []

        for method, details in path_item.items():
            if method.lower() in HTTP_METHODS and isinstance(details, dict):
                operations[(method.lower(), path)] = {
                    **details,
                    "_path_parameters": path_parameters,
                }

    return operations


def get_parameters(operation):
    parameters = {}

    combined = (
        operation.get("_path_parameters", [])
        + operation.get("parameters", [])
    )

    for parameter in combined:
        if not isinstance(parameter, dict):
            continue

        name = parameter.get("name")
        location = parameter.get("in")

        if name and location:
            parameters[(location, name)] = parameter

    return parameters


def add_change(changes, change_type, severity, method, path,
               message, evidence, breaking=True):
    changes.append({
        "type": change_type,
        "severity": severity,
        "breaking": breaking,
        "method": method.upper(),
        "path": path,
        "message": message,
        "evidence": evidence,
    })


def compare_specs(old_spec, new_spec):
    old_operations = get_operations(old_spec)
    new_operations = get_operations(new_spec)

    changes = []

    for method, path in sorted(old_operations.keys() - new_operations.keys()):
        add_change(
            changes, "removed_endpoint", "high", method, path,
            f"{method.upper()} {path} was removed.",
            {"old_endpoint": f"{method.upper()} {path}",
             "new_endpoint": None},
        )

    for method, path in sorted(new_operations.keys() - old_operations.keys()):
        add_change(
            changes, "added_endpoint", "info", method, path,
            f"{method.upper()} {path} was added.",
            {"old_endpoint": None,
             "new_endpoint": f"{method.upper()} {path}"},
            breaking=False,
        )

    for method, path in sorted(old_operations.keys() & new_operations.keys()):
        old_params = get_parameters(old_operations[(method, path)])
        new_params = get_parameters(new_operations[(method, path)])

        for location, name in sorted(old_params.keys() - new_params.keys()):
            old_param = old_params[(location, name)]
            was_required = old_param.get("required", False)

            add_change(
                changes,
                "removed_parameter",
                "high" if was_required else "medium",
                method, path,
                f"Parameter '{name}' in '{location}' was removed.",
                {
                    "parameter": name,
                    "in": location,
                    "old_required": was_required,
                    "new_parameter": None,
                },
                breaking=was_required,
            )

        for location, name in sorted(new_params.keys() - old_params.keys()):
            new_param = new_params[(location, name)]
            is_required = new_param.get("required", False)

            add_change(
                changes,
                "added_parameter",
                "high" if is_required else "info",
                method, path,
                f"Parameter '{name}' in '{location}' was added.",
                {
                    "parameter": name,
                    "in": location,
                    "old_parameter": None,
                    "new_required": is_required,
                },
                breaking=is_required,
            )

        for location, name in sorted(old_params.keys() & new_params.keys()):
            old_param = old_params[(location, name)]
            new_param = new_params[(location, name)]

            old_required = old_param.get("required", False)
            new_required = new_param.get("required", False)

            if not old_required and new_required:
                add_change(
                    changes,
                    "parameter_became_required",
                    "high", method, path,
                    f"Parameter '{name}' is now required.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_required": False,
                        "new_required": True,
                    },
                )

            old_type = old_param.get("schema", {}).get("type")
            new_type = new_param.get("schema", {}).get("type")

            if old_type and new_type and old_type != new_type:
                add_change(
                    changes,
                    "parameter_type_changed",
                    "high", method, path,
                    f"Parameter '{name}' type changed from "
                    f"'{old_type}' to '{new_type}'.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_type": old_type,
                        "new_type": new_type,
                    },
                )

    return changes



from pathlib import Path
from app.impact_analyzer import analyze_python_project


def test_end_to_end_spec_diff_and_python_impact(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    old_spec = load_spec(project_root / "samples" / "v1.yaml")
    new_spec = load_spec(project_root / "samples" / "v2.yaml")

    changes = compare_specs(old_spec, new_spec)

    client_file = tmp_path / "client.py"
    client_file.write_text(
        'import requests\n'
        'requests.get("https://api.example.com/users/123")\n',
        encoding="utf-8",
    )

    findings = analyze_python_project(tmp_path)
    impacts = match_changes_to_calls(changes, findings)

    assert isinstance(changes, list)
    assert isinstance(findings, list)
    assert isinstance(impacts, list)
    assert len(impacts) == len(changes)
