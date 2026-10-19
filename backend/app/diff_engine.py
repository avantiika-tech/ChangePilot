
import yaml


HTTP_METHODS = {
    "get", "post", "put", "patch",
    "delete", "options", "head", "trace",
}


def load_spec(file_path):
    """Load and minimally validate an OpenAPI specification."""
    with open(file_path, "r", encoding="utf-8") as file:
        spec = yaml.safe_load(file)

    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        raise ValueError(
            "Invalid OpenAPI document: expected a paths object."
        )

    return spec


def get_operations(spec):
    """Extract HTTP operations, including path-level parameters."""
    operations = {}

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        path_parameters = path_item.get("parameters", [])
        if not isinstance(path_parameters, list):
            path_parameters = []

        for method, details in path_item.items():
            if (
                isinstance(method, str)
                and method.lower() in HTTP_METHODS
                and isinstance(details, dict)
            ):
                operations[(method.lower(), path)] = {
                    **details,
                    "_path_parameters": path_parameters,
                }

    return operations


def get_parameters(operation):
    """Combine path-level and operation-level parameters by location/name."""
    parameters = {}

    path_parameters = operation.get("_path_parameters", [])
    operation_parameters = operation.get("parameters", [])

    if not isinstance(path_parameters, list):
        path_parameters = []
    if not isinstance(operation_parameters, list):
        operation_parameters = []

    for parameter in path_parameters + operation_parameters:
        if not isinstance(parameter, dict):
            continue

        name = parameter.get("name")
        location = parameter.get("in")

        if name and location:
            # Operation-level entries override path-level entries with
            # the same (location, name), as OpenAPI specifies.
            parameters[(location, name)] = parameter

    return parameters


def add_change(
    changes,
    change_type,
    severity,
    method,
    path,
    message,
    evidence,
    breaking=True,
):
    """Append a consistently structured API change."""
    changes.append({
        "type": change_type,
        "severity": severity,
        "breaking": breaking,
        "method": method.upper(),
        "path": path,
        "message": message,
        "evidence": evidence,
    })


def get_schema(parameter):
    """Return a parameter's schema safely."""
    schema = parameter.get("schema", {})
    return schema if isinstance(schema, dict) else {}



def compare_object_properties(
    old_schema,
    new_schema,
    changes,
    method,
    path,
    media_type,
):
    """Detect top-level request-body property changes."""
    old_properties = old_schema.get("properties", {})
    new_properties = new_schema.get("properties", {})

    if not isinstance(old_properties, dict):
        return
    if not isinstance(new_properties, dict):
        return

    old_required = old_schema.get("required", [])
    new_required = new_schema.get("required", [])

    if not isinstance(old_required, list):
        old_required = []
    if not isinstance(new_required, list):
        new_required = []

    for name in sorted(old_properties.keys() - new_properties.keys()):
        add_change(
            changes,
            "request_body_property_removed",
            "high",
            method,
            path,
            f"Request body property '{name}' was removed.",
            {
                "property": name,
                "media_type": media_type,
                "old_schema": old_properties[name],
                "new_schema": None,
            },
            breaking=True,
        )

    for name in sorted(new_properties.keys() - old_properties.keys()):
        is_required = name in new_required

        add_change(
            changes,
            "request_body_property_added",
            "high" if is_required else "info",
            method,
            path,
            f"Request body property '{name}' was added.",
            {
                "property": name,
                "media_type": media_type,
                "old_schema": None,
                "new_schema": new_properties[name],
                "new_required": is_required,
            },
            breaking=is_required,
        )

    for name in sorted(old_properties.keys() & new_properties.keys()):
        old_property = old_properties[name]
        new_property = new_properties[name]

        if not isinstance(old_property, dict):
            continue
        if not isinstance(new_property, dict):
            continue

        old_type = old_property.get("type")
        new_type = new_property.get("type")

        if old_type and new_type and old_type != new_type:
            add_change(
                changes,
                "request_body_property_type_changed",
                "high",
                method,
                path,
                f"Request body property '{name}' type changed "
                f"from '{old_type}' to '{new_type}'.",
                {
                    "property": name,
                    "media_type": media_type,
                    "old_type": old_type,
                    "new_type": new_type,
                },
                breaking=True,
            )

        if name not in old_required and name in new_required:
            add_change(
                changes,
                "request_body_property_became_required",
                "high",
                method,
                path,
                f"Request body property '{name}' is now required.",
                {
                    "property": name,
                    "media_type": media_type,
                    "old_required": False,
                    "new_required": True,
                },
                breaking=True,
            )


def compare_response_properties(
    old_schema,
    new_schema,
    changes,
    method,
    path,
    status_code,
    media_type,
):
    """Compare top-level properties in an inline response object schema."""
    old_properties = old_schema.get("properties", {})
    new_properties = new_schema.get("properties", {})

    if not isinstance(old_properties, dict):
        return

    if not isinstance(new_properties, dict):
        return

    # A removed response field can break clients that rely on it.
    for property_name in sorted(old_properties.keys() - new_properties.keys()):
        changes.append({
            "type": "response_property_removed",
            "severity": "high",
            "breaking": True,
            "method": method.upper(),
            "path": path,
            "message": (
                f"Response property '{property_name}' was removed "
                f"from status {status_code}."
            ),
            "evidence": {
                "property": property_name,
                "status_code": str(status_code),
                "media_type": media_type,
                "old_schema": old_properties[property_name],
                "new_schema": None,
            },
        })

    # Adding a response field is normally backward-compatible.
    for property_name in sorted(new_properties.keys() - old_properties.keys()):
        changes.append({
            "type": "response_property_added",
            "severity": "low",
            "breaking": False,
            "method": method.upper(),
            "path": path,
            "message": (
                f"Response property '{property_name}' was added "
                f"to status {status_code}."
            ),
            "evidence": {
                "property": property_name,
                "status_code": str(status_code),
                "media_type": media_type,
                "old_schema": None,
                "new_schema": new_properties[property_name],
            },
        })

    # Changing an existing response property's type may break clients.
    for property_name in sorted(old_properties.keys() & new_properties.keys()):
        old_property_schema = old_properties[property_name]
        new_property_schema = new_properties[property_name]

        if not isinstance(old_property_schema, dict):
            continue

        if not isinstance(new_property_schema, dict):
            continue

        old_type = old_property_schema.get("type")
        new_type = new_property_schema.get("type")

        if old_type is not None and new_type is not None and old_type != new_type:
            changes.append({
                "type": "response_property_type_changed",
                "severity": "high",
                "breaking": True,
                "method": method.upper(),
                "path": path,
                "message": (
                    f"Response property '{property_name}' changed type "
                    f"from '{old_type}' to '{new_type}'."
                ),
                "evidence": {
                    "property": property_name,
                    "status_code": str(status_code),
                    "media_type": media_type,
                    "old_type": old_type,
                    "new_type": new_type,
                },
            })


def compare_specs(old_spec, new_spec):
    """
    Compare two OpenAPI specifications.

    Detects endpoint additions/removals, parameter additions/removals,
    requiredness changes, type changes, format changes, and enum changes.
    """
    old_operations = get_operations(old_spec)
    new_operations = get_operations(new_spec)

    changes = []

    # Removed endpoints
    for method, path in sorted(
        old_operations.keys() - new_operations.keys()
    ):
        add_change(
            changes,
            "removed_endpoint",
            "high",
            method,
            path,
            f"{method.upper()} {path} was removed.",
            {
                "old_endpoint": f"{method.upper()} {path}",
                "new_endpoint": None,
            },
        )

    # Added endpoints
    for method, path in sorted(
        new_operations.keys() - old_operations.keys()
    ):
        add_change(
            changes,
            "added_endpoint",
            "info",
            method,
            path,
            f"{method.upper()} {path} was added.",
            {
                "old_endpoint": None,
                "new_endpoint": f"{method.upper()} {path}",
            },
            breaking=False,
        )

    # Compare parameters on operations that exist in both specifications
    for method, path in sorted(
        old_operations.keys() & new_operations.keys()
    ):

        
        # Compare request-body object properties
        old_operation = old_operations[(method, path)]
        new_operation = new_operations[(method, path)]

        
        # Compare inline response object schemas for shared status codes
        # and media types.
        old_responses = old_operation.get("responses", {})
        new_responses = new_operation.get("responses", {})

        if isinstance(old_responses, dict) and isinstance(new_responses, dict):
            for status_code in sorted(
                old_responses.keys() & new_responses.keys(),
                key=str,
            ):
                old_response = old_responses[status_code]
                new_response = new_responses[status_code]

                if not isinstance(old_response, dict):
                    continue

                if not isinstance(new_response, dict):
                    continue

                old_content = old_response.get("content", {})
                new_content = new_response.get("content", {})

                if not isinstance(old_content, dict):
                    continue

                if not isinstance(new_content, dict):
                    continue

                for media_type in sorted(old_content.keys() & new_content.keys()):
                    old_media = old_content[media_type]
                    new_media = new_content[media_type]

                    if not isinstance(old_media, dict):
                        continue

                    if not isinstance(new_media, dict):
                        continue

                    old_schema = old_media.get("schema", {})
                    new_schema = new_media.get("schema", {})

                    if not isinstance(old_schema, dict):
                        continue

                    if not isinstance(new_schema, dict):
                        continue

                    if (
                        old_schema.get("type") == "object"
                        and new_schema.get("type") == "object"
                    ):
                        compare_response_properties(
                            old_schema,
                            new_schema,
                            changes,
                            method,
                            path,
                            status_code,
                            media_type,
                        )


        
        # Detect removed response status codes.
        old_responses = old_operation.get("responses", {})
        new_responses = new_operation.get("responses", {})

        if isinstance(old_responses, dict) and isinstance(new_responses, dict):
            removed_status_codes = (
                old_responses.keys() - new_responses.keys()
            )

            for status_code in sorted(removed_status_codes, key=str):
                add_change(
                    changes,
                    "response_status_removed",
                    "high",
                    method,
                    path,
                    f"Response status code '{status_code}' was removed.",
                    {
                        "status_code": str(status_code),
                    },
                )


        old_body = old_operation.get("requestBody", {})
        new_body = new_operation.get("requestBody", {})

        if isinstance(old_body, dict) and isinstance(new_body, dict):
            old_content = old_body.get("content", {})
            new_content = new_body.get("content", {})

            if isinstance(old_content, dict) and isinstance(new_content, dict):
                for media_type in sorted(
                    old_content.keys() & new_content.keys()
                ):
                    old_media = old_content[media_type]
                    new_media = new_content[media_type]

                    if not isinstance(old_media, dict):
                        continue
                    if not isinstance(new_media, dict):
                        continue

                    old_schema = old_media.get("schema", {})
                    new_schema = new_media.get("schema", {})

                    if (
                        isinstance(old_schema, dict)
                        and isinstance(new_schema, dict)
                        and old_schema.get("type") == "object"
                        and new_schema.get("type") == "object"
                    ):
                        compare_object_properties(
                            old_schema,
                            new_schema,
                            changes,
                            method,
                            path,
                            media_type,
                        )

        old_params = get_parameters(old_operations[(method, path)])
        new_params = get_parameters(new_operations[(method, path)])

        # Removed parameters
        for location, name in sorted(
            old_params.keys() - new_params.keys()
        ):
            old_param = old_params[(location, name)]
            was_required = old_param.get("required", False)

            add_change(
                changes,
                "removed_parameter",
                "high" if was_required else "medium",
                method,
                path,
                f"Parameter '{name}' in '{location}' was removed.",
                {
                    "parameter": name,
                    "in": location,
                    "old_required": was_required,
                    "new_parameter": None,
                },
                breaking=was_required,
            )

        # Added parameters
        for location, name in sorted(
            new_params.keys() - old_params.keys()
        ):
            new_param = new_params[(location, name)]
            is_required = new_param.get("required", False)

            add_change(
                changes,
                "added_parameter",
                "high" if is_required else "info",
                method,
                path,
                f"Parameter '{name}' in '{location}' was added.",
                {
                    "parameter": name,
                    "in": location,
                    "old_parameter": None,
                    "new_required": is_required,
                },
                breaking=is_required,
            )

        # Compare parameters present in both specifications
        for location, name in sorted(
            old_params.keys() & new_params.keys()
        ):
            old_param = old_params[(location, name)]
            new_param = new_params[(location, name)]

            old_required = old_param.get("required", False)
            new_required = new_param.get("required", False)

            # Optional -> required is breaking
            if not old_required and new_required:
                add_change(
                    changes,
                    "parameter_became_required",
                    "high",
                    method,
                    path,
                    f"Parameter '{name}' is now required.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_required": False,
                        "new_required": True,
                    },
                )

            old_schema = get_schema(old_param)
            new_schema = get_schema(new_param)

            old_default = old_schema.get("default")
            new_default = new_schema.get("default")

            if old_default != new_default and (
                "default" in old_schema or "default" in new_schema
            ):
                add_change(
                    changes,
                    "parameter_default_changed",
                    "medium",
                    method,
                    path,
                    f"Parameter '{name}' default value changed from "
                    f"'{old_default}' to '{new_default}'.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_default": old_default,
                        "new_default": new_default,
                    },
                    breaking=False,
                )

            old_type = old_schema.get("type")
            new_type = new_schema.get("type")

            # Parameter type changes
            if old_type and new_type and old_type != new_type:
                add_change(
                    changes,
                    "parameter_type_changed",
                    "high",
                    method,
                    path,
                    f"Parameter '{name}' type changed from "
                    f"'{old_type}' to '{new_type}'.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_type": old_type,
                        "new_type": new_type,
                    },
                )

            # Parameter format changes
            old_format = old_schema.get("format")
            new_format = new_schema.get("format")

            if old_format != new_format:
                add_change(
                    changes,
                    "parameter_format_changed",
                    "high",
                    method,
                    path,
                    f"Parameter '{name}' format changed from "
                    f"'{old_format}' to '{new_format}'.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_format": old_format,
                        "new_format": new_format,
                    },
                )

            # Parameter enum changes, including adding/removing the
            # entire enum constraint
            old_enum = old_schema.get("enum")
            new_enum = new_schema.get("enum")

            if old_enum != new_enum and (
                old_enum is not None or new_enum is not None
            ):
                old_values = old_enum if isinstance(old_enum, list) else []
                new_values = new_enum if isinstance(new_enum, list) else []

                removed_values = (
                    [value for value in old_values if value not in new_values]
                    if new_enum is not None
                    else []
                )
                added_values = (
                    [value for value in new_values if value not in old_values]
                    if old_enum is not None
                    else []
                )

                # Adding a restrictive enum where none existed can reject
                # values previously accepted by the API.
                adds_restriction = (
                    old_enum is None and new_enum is not None
                )
                is_breaking = bool(removed_values) or adds_restriction

                add_change(
                    changes,
                    "parameter_enum_changed",
                    "high" if is_breaking else "medium",
                    method,
                    path,
                    f"Parameter '{name}' allowed values changed.",
                    {
                        "parameter": name,
                        "in": location,
                        "old_enum": old_enum,
                        "new_enum": new_enum,
                        "removed_values": removed_values,
                        "added_values": added_values,
                    },
                    breaking=is_breaking,
                )

    return changes
