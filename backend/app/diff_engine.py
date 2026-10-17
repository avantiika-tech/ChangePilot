
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

        for method, details in path_item.items():
            if method.lower() in HTTP_METHODS and isinstance(details, dict):
                operations[(method.lower(), path)] = details

    return operations


def compare_specs(old_spec, new_spec):
    old_operations = get_operations(old_spec)
    new_operations = get_operations(new_spec)

    changes = []

    for method, path in sorted(old_operations.keys() - new_operations.keys()):
        changes.append({
            "type": "removed_endpoint",
            "severity": "high",
            "method": method.upper(),
            "path": path,
            "message": f"{method.upper()} {path} was removed.",
        })

    for method, path in sorted(new_operations.keys() - old_operations.keys()):
        changes.append({
            "type": "added_endpoint",
            "severity": "info",
            "method": method.upper(),
            "path": path,
            "message": f"{method.upper()} {path} was added.",
        })

    return changes
