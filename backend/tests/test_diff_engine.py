import re
import pytest
from urllib.parse import urlparse
from app.diff_engine import compare_specs
from app.impact_analyzer import analyze_python_file, match_changes_to_calls


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



def test_analyzer_detects_http_calls(tmp_path):
    sample_file = tmp_path / "client.py"
    sample_file.write_text(
        'import requests\n'
        'requests.get("https://api.example.com/users/123")\n'
        'requests.post("https://api.example.com/users")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(sample_file)

    assert len(findings) == 2
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] == "https://api.example.com/users/123"
    assert findings[1]["method"] == "POST"


def test_matches_api_change_to_affected_call():
    changes = [
        {
            "type": "parameter_type_changed",
            "method": "GET",
            "path": "/users/{id}",
            "breaking": True,
            "evidence": {
                "parameter": "id",
                "in": "path",
                "old_type": "integer",
                "new_type": "string",
            },
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 2,
            "method": "GET",
            "url": "https://api.example.com/users/123",
            "call": "requests.get",
        },
        {
            "file": "client.py",
            "line": 3,
            "method": "POST",
            "url": "https://api.example.com/users",
            "call": "requests.post",
        },
    ]

    results = match_changes_to_calls(changes, findings)

    assert results[0]["potential_impact_count"] == 1
    assert results[0]["affected_calls"][0]["call"] == "requests.get"
    assert results[0]["potential_impact_count"] == 1

    affected_call = results[0]["affected_calls"][0]

    assert affected_call["match_evidence"]["http_method_matches"] is True
    assert affected_call["match_evidence"]["api_path"] == "/users/{id}"
    assert affected_call["match_evidence"]["matched_request_path"] == "/users/123"

    assert affected_call["parameter_evidence"]["parameter"] == "id"
    assert affected_call["parameter_evidence"]["location"] == "path"
    assert affected_call["parameter_evidence"]["old_type"] == "integer"
    assert affected_call["parameter_evidence"]["new_type"] == "string"



def test_detects_missing_required_query_parameter():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "old_parameter": None,
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 10,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123",
    }

    from app.impact_analyzer import match_changes_to_calls

    impacts = match_changes_to_calls([change], [finding])

    assert len(impacts) == 1
    assert impacts[0]["potential_impact_count"] == 1

    affected_call = impacts[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "include"
    assert affected_call["parameter_status"] == "missing_from_literal_url"
    assert affected_call["parameter_location"] == "query"



def test_detects_present_required_query_parameter():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 12,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123?include=orders",
    }

    from app.impact_analyzer import match_changes_to_calls

    impacts = match_changes_to_calls([change], [finding])

    affected_call = impacts[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "include"
    assert affected_call["parameter_status"] == "present"
    assert affected_call["parameter_source"] == "url_query"



def test_end_to_end_spec_diff_and_python_impact(tmp_path):
    from pathlib import Path
    from app.diff_engine import load_spec, compare_specs
    from app.impact_analyzer import (
        analyze_python_project,
        match_changes_to_calls,
    )

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

    assert len(findings) == 1
    assert len(impacts) == len(changes)

    include_impacts = [
        impact
        for impact in impacts
        if impact["change"].get("type") == "added_parameter"
        and impact["change"].get("evidence", {}).get("parameter") == "include"
    ]

    assert len(include_impacts) == 1

    affected_call = include_impacts[0]["affected_calls"][0]
    assert affected_call["parameter_status"] == "missing_from_literal_url"
    assert affected_call["required_parameter"] == "include"



def test_analyzer_resolves_url_constant(tmp_path):
    sample_file = tmp_path / "client.py"
    sample_file.write_text(
        'import requests\n'
        'BASE_URL = "https://api.example.com"\n'
        'requests.get(BASE_URL + "/users/123")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(sample_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] == "https://api.example.com/users/123"


def test_detects_required_query_parameter_in_params_dict():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 5,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123",
        "params": {"include": "orders"},
    }

    impacts = match_changes_to_calls([change], [finding])
    affected_call = impacts[0]["affected_calls"][0]

    assert affected_call["parameter_status"] == "present"
    assert affected_call["parameter_source"] == "params_dict"


def test_dynamic_url_is_not_reported_as_literal_url(tmp_path):
    sample_file = tmp_path / "client.py"
    sample_file.write_text(
        'import requests\n'
        'user_id = get_user_id()\n'
        'requests.get(f"https://api.example.com/users/{user_id}")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(sample_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] is None



def test_endpoint_matching_rejects_extra_path_segments():
    change = {
        "type": "parameter_type_changed",
        "method": "GET",
        "path": "/users/{id}",
        "breaking": True,
    }

    findings = [
        {
            "file": "client.py",
            "line": 2,
            "method": "GET",
            "url": "https://api.example.com/users/123",
            "call": "requests.get",
        },
        {
            "file": "client.py",
            "line": 3,
            "method": "GET",
            "url": "https://api.example.com/users/123/profile",
            "call": "requests.get",
        },
    ]

    results = match_changes_to_calls([change], findings)

    assert results[0]["potential_impact_count"] == 1
    assert results[0]["affected_calls"][0]["url"] == (
        "https://api.example.com/users/123"
    )


def test_dynamic_url_is_not_counted_as_affected_call():
    change = {
        "type": "parameter_type_changed",
        "method": "GET",
        "path": "/users/{id}",
        "breaking": True,
    }

    findings = [
        {
            "file": "client.py",
            "line": 10,
            "method": "GET",
            "url": None,
            "call": "requests.get",
        }
    ]

    results = match_changes_to_calls([change], findings)

    assert results[0]["potential_impact_count"] == 0
    assert results[0]["affected_calls"] == []


def test_endpoint_matching_handles_url_encoded_path_parameter():
    change = {
        "type": "parameter_type_changed",
        "method": "GET",
        "path": "/users/{id}",
        "breaking": True,
    }

    findings = [
        {
            "file": "client.py",
            "line": 5,
            "method": "GET",
            "url": "https://api.example.com/users/user%2042",
            "call": "requests.get",
        }
    ]

    results = match_changes_to_calls([change], findings)

    assert results[0]["potential_impact_count"] == 1
    assert results[0]["affected_calls"][0]["url"] == (
        "https://api.example.com/users/user%2042"
    )

def test_endpoint_matching_rejects_http_method_mismatch():
    change = {
        "type": "parameter_type_changed",
        "method": "GET",
        "path": "/users/{id}",
        "breaking": True,
    }

    findings = [
        {
            "file": "client.py",
            "line": 8,
            "method": "POST",
            "url": "https://api.example.com/users/123",
            "call": "requests.post",
        }
    ]

    results = match_changes_to_calls([change], findings)

    assert results[0]["potential_impact_count"] == 0
    assert results[0]["affected_calls"] == []

def test_missing_required_query_parameter_with_other_params():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 8,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123",
        "params": {"page": 2, "limit": 10},
    }

    results = match_changes_to_calls([change], [finding])

    assert results[0]["potential_impact_count"] == 1

    affected_call = results[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "include"
    assert affected_call["parameter_status"] == "missing_from_literal_url"


def test_query_parameter_matching_is_case_sensitive():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 9,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123?Include=orders",
    }

    results = match_changes_to_calls([change], [finding])

    assert results[0]["potential_impact_count"] == 1
    affected_call = results[0]["affected_calls"][0]
    assert affected_call["parameter_status"] == "missing_from_literal_url"


def test_detects_parameter_format_change():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "created_at",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
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
                            "name": "created_at",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "format": "date-time",
                            },
                        }
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "parameter_format_changed"
        and change["evidence"]["parameter"] == "created_at"
        and change["evidence"]["old_format"] is None
        and change["evidence"]["new_format"] == "date-time"
        for change in changes
    )



def test_detects_removed_enum_value():
    old_spec = {
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["pending", "active", "closed"],
                            },
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["pending", "active"],
                            },
                        }
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "parameter_enum_changed"
        and change["evidence"]["parameter"] == "status"
        and change["evidence"]["removed_values"] == ["closed"]
        for change in changes
    )



def test_detects_removed_enum_constraint():
    old_spec = {
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["active", "pending"],
                            },
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "parameter_enum_changed"
        and change["evidence"]["parameter"] == "status"
        and change["evidence"]["old_enum"] == ["active", "pending"]
        and change["evidence"]["new_enum"] is None
        for change in changes
    )


def test_detects_parameter_default_change():
    old_spec = {
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 10},
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 20},
                        }
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "parameter_default_changed"
        and change["evidence"]["parameter"] == "limit"
        and change["evidence"]["old_default"] == 10
        and change["evidence"]["new_default"] == 20
        for change in changes
    )


def test_detects_removed_request_body_property():
    old_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "request_body_property_removed"
        and change["method"] == "POST"
        and change["path"] == "/users"
        and change["evidence"]["property"] == "email"
        for change in changes
    )



def test_detects_removed_request_body_property():
    old_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "request_body_property_removed"
        and change["method"] == "POST"
        and change["path"] == "/users"
        and change["evidence"]["property"] == "email"
        for change in changes
    )


def test_detects_added_request_body_property():
    old_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "request_body_property_added"
        and change["evidence"]["property"] == "email"
        and change["breaking"] is False
        for change in changes
    )


def test_detects_request_body_property_type_change():
    old_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "age": {"type": "integer"},
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "age": {"type": "string"},
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "request_body_property_type_changed"
        and change["evidence"]["property"] == "age"
        and change["evidence"]["old_type"] == "integer"
        and change["evidence"]["new_type"] == "string"
        for change in changes
    )



def test_detects_removed_response_property():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "email": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "response_property_removed"
        and change["method"] == "GET"
        and change["path"] == "/users/{id}"
        and change["evidence"]["property"] == "email"
        and change["evidence"]["status_code"] == "200"
        for change in changes
    )



def test_detects_added_response_property():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "response_property_added"
        and change["evidence"]["property"] == "name"
        and change["evidence"]["status_code"] == "200"
        and change["breaking"] is False
        for change in changes
    )


def test_detects_response_property_type_change():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "response_property_type_changed"
        and change["evidence"]["property"] == "id"
        and change["evidence"]["old_type"] == "integer"
        and change["evidence"]["new_type"] == "string"
        and change["breaking"] is True
        for change in changes
    )



def test_detects_removed_response_status_code():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found"
                        },
                        "404": {
                            "description": "User not found"
                        },
                    }
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User found"
                        }
                    }
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "response_status_removed"
        and change["method"] == "GET"
        and change["path"] == "/users/{id}"
        and change["evidence"]["status_code"] == "404"
        and change["breaking"] is True
        for change in changes
    )



def test_load_spec_rejects_missing_paths(tmp_path):
    from app.diff_engine import load_spec

    spec_file = tmp_path / "invalid.yaml"
    spec_file.write_text(
        'openapi: "3.0.0"\ninfo:\n  title: Test API\n  version: "1.0"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected a paths object"):
        load_spec(spec_file)


def test_load_spec_rejects_invalid_yaml(tmp_path):
    from app.diff_engine import load_spec

    spec_file = tmp_path / "invalid.yaml"
    spec_file.write_text(
        "openapi: [this is not valid",
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        load_spec(spec_file)
