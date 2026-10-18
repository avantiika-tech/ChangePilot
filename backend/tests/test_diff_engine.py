
from app.diff_engine import compare_specs


def test_detects_added_required_parameter():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "include",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "added_parameter"
        and change["evidence"]["parameter"] == "include"
        and change["breaking"] is True
        for change in changes
    )


def test_detects_parameter_type_change():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "parameter_type_changed"
        and change["evidence"]["old_type"] == "integer"
        and change["evidence"]["new_type"] == "string"
        for change in changes
    )
