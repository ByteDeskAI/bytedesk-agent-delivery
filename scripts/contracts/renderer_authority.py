#!/usr/bin/env python3
"""Schema-owned renderer authority preimages shared by all contract tooling."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RENDERER_SELECTION_SCHEMA_PATH = (
    REPOSITORY_ROOT / "contracts/schemas/v1/renderer-selection.schema.json"
)


def _selection_authority_contract() -> tuple[str, tuple[str, ...]]:
    schema = json.loads(RENDERER_SELECTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    authority = schema.get("x-bytedesk-digestAuthority")
    if not isinstance(authority, dict):
        raise ValueError("renderer-selection schema lacks x-bytedesk-digestAuthority")
    profile = authority.get("profile")
    fields = authority.get("fields")
    if not isinstance(profile, str) or not isinstance(fields, list):
        raise ValueError("renderer-selection digest authority metadata is invalid")
    if not fields or len(fields) != len(set(fields)) or not all(
        isinstance(field, str) for field in fields
    ):
        raise ValueError("renderer-selection digest authority fields are not unique strings")
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    if any(field not in properties or field not in required for field in fields):
        raise ValueError("renderer-selection digest authority field is not required by schema")
    excluded = {"contract", "schema", "selectionDigest"}
    if set(fields) != required - excluded:
        raise ValueError(
            "renderer-selection digest authority must bind every required semantic field"
        )
    return profile, tuple(fields)


RENDERER_SELECTION_PROFILE, RENDERER_SELECTION_AUTHORITY_FIELDS = (
    _selection_authority_contract()
)


def renderer_selection_preimage(selection: dict[str, Any]) -> dict[str, Any]:
    """Return the exact schema-owned renderer-selection digest preimage."""

    missing = [
        field for field in RENDERER_SELECTION_AUTHORITY_FIELDS if field not in selection
    ]
    if missing:
        raise KeyError(f"renderer selection is missing authority fields: {missing}")
    return {
        "profile": RENDERER_SELECTION_PROFILE,
        **{
            field: deepcopy(selection[field])
            for field in RENDERER_SELECTION_AUTHORITY_FIELDS
        },
    }


def inline_authority_preimage(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Return a closed schema-owned inline-signature authority preimage."""

    authority = schema.get("x-bytedesk-digestAuthority")
    if not isinstance(authority, dict):
        raise ValueError("schema lacks x-bytedesk-digestAuthority")
    profile = authority.get("profile")
    excluded = authority.get("exclude")
    expected_excluded = ["contract", "schema", "authorityDigest", "signingResult"]
    if not isinstance(profile, str) or excluded != expected_excluded:
        raise ValueError("inline authority metadata has an invalid profile or exclusion set")
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValueError("inline authority schema is not a closed object contract")
    if not all(field in properties and field in required for field in excluded):
        raise ValueError("inline authority exclusion field is not required by schema")
    if schema.get("additionalProperties") is not False:
        raise ValueError("inline authority schema must reject additional properties")
    missing = [field for field in required if field not in document]
    if missing:
        raise KeyError(f"inline authority document is missing required fields: {missing}")
    unknown = [field for field in document if field not in properties]
    if unknown:
        raise KeyError(f"inline authority document has undeclared fields: {unknown}")
    return {
        "profile": profile,
        **{
            field: deepcopy(value)
            for field, value in document.items()
            if field not in excluded
        },
    }


def schema_field_authority_preimage(
    document: dict[str, Any],
    schema: dict[str, Any],
    digest_field: str,
) -> dict[str, Any]:
    """Return an exact fields-list authority preimage declared by a schema."""

    authority = schema.get("x-bytedesk-digestAuthority")
    if not isinstance(authority, dict):
        raise ValueError("schema lacks x-bytedesk-digestAuthority")
    profile = authority.get("profile")
    fields = authority.get("fields")
    if not isinstance(profile, str) or not isinstance(fields, list):
        raise ValueError("schema fields authority metadata is invalid")
    if not fields or len(fields) != len(set(fields)) or not all(
        isinstance(field, str) for field in fields
    ):
        raise ValueError("schema fields authority entries are not unique strings")
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    excluded = {"contract", "schema", digest_field}
    if set(fields) != required - excluded:
        raise ValueError("schema fields authority does not bind every semantic field")
    if any(field not in properties for field in fields) or digest_field not in properties:
        raise ValueError("schema fields authority names an undeclared property")
    missing = [field for field in fields if field not in document]
    if missing:
        raise KeyError(f"authority document is missing fields: {missing}")
    return {
        "profile": profile,
        **{field: deepcopy(document[field]) for field in fields},
    }
