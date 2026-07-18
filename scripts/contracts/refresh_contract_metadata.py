#!/usr/bin/env python3
"""Deterministically refresh exact schema and documentation metadata.

The default mode is a read-only generated-drift check. ``--write`` constructs
and validates the complete output set before atomically replacing each stale
JSON document. The tool never discovers documentation mappings or fixture
expectations: those reviewed declarations remain explicit inputs.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import unquote, urlsplit

from bundle_profile import (
    MAX_BUNDLE_MEMBER_BYTES,
    BundleProfileError,
    portable_path_collision_key,
    validate_portable_path_set,
)
from contractlib import (
    REPOSITORY_ROOT,
    ContractToolError,
    canonical_digest,
    load_json,
    stable_file_digest,
    write_json,
)
from validate_schemas import (
    SCHEMA_INVENTORY_ENTRY_FIELDS,
    SCHEMA_INVENTORY_PROFILE,
    SCHEMA_INVENTORY_ROOT_FIELDS,
    fixture_schema_descriptor_error,
    stable_schema_id,
    validate_fixture_index_document,
)


SCHEMA_INVENTORY_PATH = "contracts/bundle/v1/schema-inventory.json"
FIXTURE_INDEX_PATH = "contracts/fixtures/schema/index.json"
DOCUMENTATION_MAP_PATH = "contracts/bundle/v1/documentation-map.json"
OPENAPI_PATH = "contracts/openapi/v1/agent-delivery.openapi.json"
ASYNCAPI_PATH = "contracts/asyncapi/v1/agent-delivery.asyncapi.json"
EVENT_TYPES_PATH = "contracts/events/v1/event-types.json"
EVENT_EXAMPLES_ROOT = "contracts/events/v1/examples"
SCHEMA_DESCRIPTOR_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/schema-descriptor/1.0.0"
)
EVENT_DATA_SCHEMA_ID = (
    "https://schemas.bytedesk.ai/agent-delivery/v1/event-data/1.0.0"
)
EXACT_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
ROOT_SCHEMA_DESCRIPTOR_FIELDS = {"id", "digest"}
SEMANTIC_SCHEMA_DENIALS = {"schema_id_mismatch", "schema_digest_mismatch"}
EVENT_TYPES_ROOT_FIELDS = {
    "$schema",
    "profile",
    "cloudEventsVersion",
    "delivery",
    "ordering",
    "authority",
    "eventTypes",
    "registryCompatibility",
    "resynchronization",
}
EVENT_TYPE_FIELDS = {
    "type",
    "aggregateType",
    "resourceSchemaId",
    "resourceSchemaDigest",
    "resourceUriTemplate",
    "resynchronizeOperationId",
    "redaction",
}
DOCUMENTATION_MAP_FIELDS = {"profile", "documents", "schemas", "projections"}
DOCUMENT_FIELDS = {"path", "digest"}
DOCUMENT_SCHEMA_FIELDS = {"id", "documents"}
PROJECTION_FIELDS = {"path", "source", "role"}
PROJECTION_ROLES = {
    "http-projection",
    "event-projection",
    "notification-registry",
}


@dataclass(frozen=True)
class SchemaRecord:
    schema_id: str
    relative_path: str
    path: Path
    document: dict[str, Any]
    digest: str


@dataclass(frozen=True)
class RefreshPlan:
    repository_root: Path
    outputs: dict[str, Any]
    current: dict[str, Any]
    schema_count: int
    indexed_fixture_count: int
    managed_fixture_count: int
    preserved_semantic_denial_count: int
    event_example_count: int
    documentation_count: int

    @property
    def stale_paths(self) -> list[str]:
        return sorted(
            path for path, expected in self.outputs.items() if self.current[path] != expected
        )


def _require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractToolError(f"{description} must be an object")
    return value


def _require_closed(value: Any, fields: set[str], description: str) -> dict[str, Any]:
    document = _require_object(value, description)
    unknown = sorted(set(document) - fields)
    missing = sorted(fields - set(document))
    if unknown or missing:
        raise ContractToolError(
            f"{description} is not closed: unknown={unknown} missing={missing}"
        )
    return document


def _resolve_declared_path(
    repository_root: Path,
    relative_path: str,
    description: str,
    *,
    directory_marker: bool = False,
) -> Path:
    if not isinstance(relative_path, str) or not relative_path or "\\" in relative_path:
        raise ContractToolError(f"{description} is not a non-empty repository path")
    stripped = relative_path.rstrip("/") if directory_marker else relative_path
    if not stripped or (directory_marker and relative_path != f"{stripped}/"):
        raise ContractToolError(f"{description} is not a canonical directory marker")
    try:
        portable_path_collision_key(stripped)
    except BundleProfileError as error:
        raise ContractToolError(f"{description} is not portable: {error}") from error

    candidate = repository_root / stripped
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ContractToolError(f"{description} is missing: {relative_path}") from error
    try:
        observed = resolved.relative_to(repository_root).as_posix()
    except ValueError as error:
        raise ContractToolError(f"{description} escapes the repository: {relative_path}") from error
    if observed != stripped or candidate.is_symlink():
        raise ContractToolError(f"{description} is not canonical: {relative_path}")
    if directory_marker:
        if not resolved.is_dir():
            raise ContractToolError(f"{description} is not a directory: {relative_path}")
    elif not resolved.is_file():
        raise ContractToolError(f"{description} is not a regular file: {relative_path}")
    return resolved


def _load_required_json(
    repository_root: Path, relative_path: str, description: str
) -> tuple[Path, Any]:
    path = _resolve_declared_path(repository_root, relative_path, description)
    return path, load_json(path)


def _discover_schemas(
    repository_root: Path,
) -> tuple[dict[str, SchemaRecord], dict[Path, SchemaRecord]]:
    schema_root = repository_root / "contracts" / "schemas" / "v1"
    try:
        resolved_root = schema_root.resolve(strict=True)
    except OSError as error:
        raise ContractToolError("contracts/schemas/v1 is missing") from error
    if resolved_root != schema_root or not resolved_root.is_dir():
        raise ContractToolError("contracts/schemas/v1 is not a canonical directory")

    records_by_id: dict[str, SchemaRecord] = {}
    records_by_path: dict[Path, SchemaRecord] = {}
    paths = sorted(schema_root.glob("*.schema.json"))
    if not paths:
        raise ContractToolError("no contracts/schemas/v1/*.schema.json files were found")
    for candidate in paths:
        relative = f"contracts/schemas/v1/{candidate.name}"
        path = _resolve_declared_path(
            repository_root, relative, "source schema path"
        )
        schema = _require_object(load_json(path), f"source schema {relative}")
        schema_id = schema.get("$id")
        if not stable_schema_id(schema_id):
            raise ContractToolError(f"source schema has a missing or invalid $id: {relative}")
        if schema_id in records_by_id:
            raise ContractToolError(f"duplicate source schema ID: {schema_id}")
        if path in records_by_path:
            raise ContractToolError(f"duplicate source schema path: {relative}")
        record = SchemaRecord(
            schema_id=schema_id,
            relative_path=relative,
            path=path,
            document=schema,
            digest=canonical_digest(schema),
        )
        records_by_id[schema_id] = record
        records_by_path[path] = record
    return records_by_id, records_by_path


def _expected_schema_inventory(
    current: Any, schemas: dict[str, SchemaRecord]
) -> dict[str, Any]:
    document = _require_closed(
        current, SCHEMA_INVENTORY_ROOT_FIELDS, "schema inventory"
    )
    if document["profile"] != SCHEMA_INVENTORY_PROFILE:
        raise ContractToolError("schema inventory has an unknown profile")
    entries = document["schemas"]
    if not isinstance(entries, list) or not entries:
        raise ContractToolError("schema inventory must contain a non-empty schemas array")
    live_by_path = {record.relative_path: record for record in schemas.values()}
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for position, value in enumerate(entries):
        entry = _require_closed(
            value, SCHEMA_INVENTORY_ENTRY_FIELDS, f"schema inventory entry {position}"
        )
        schema_id = entry["id"]
        schema_path = entry["path"]
        digest = entry["digest"]
        if not stable_schema_id(schema_id):
            raise ContractToolError(f"schema inventory entry {position} has an invalid ID")
        if (
            not isinstance(schema_path, str)
            or not schema_path.startswith("contracts/schemas/v1/")
            or not schema_path.endswith(".schema.json")
        ):
            raise ContractToolError(f"schema inventory entry {position} has an invalid path")
        if not isinstance(digest, str) or EXACT_SHA256.fullmatch(digest) is None:
            raise ContractToolError(f"schema inventory entry {position} has an invalid digest")
        if schema_id in seen_ids:
            raise ContractToolError(f"duplicate schema inventory ID: {schema_id}")
        if schema_path in seen_paths:
            raise ContractToolError(f"duplicate schema inventory path: {schema_path}")
        seen_ids.add(schema_id)
        seen_paths.add(schema_path)
        by_id = schemas.get(schema_id)
        by_path = live_by_path.get(schema_path)
        if by_id is None or by_path is None:
            raise ContractToolError(
                f"schema inventory contains an unknown ID or path: {schema_id} {schema_path}"
            )
        if by_id != by_path:
            raise ContractToolError(
                f"schema inventory ID/path binding differs: {schema_id} {schema_path}"
            )
    return {
        "profile": SCHEMA_INVENTORY_PROFILE,
        "schemas": [
            {
                "id": record.schema_id,
                "path": record.relative_path,
                "digest": record.digest,
            }
            for record in sorted(schemas.values(), key=lambda item: item.schema_id)
        ],
    }


def _exact_schema_descriptor(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == ROOT_SCHEMA_DESCRIPTOR_FIELDS
        and isinstance(value.get("id"), str)
        and isinstance(value.get("digest"), str)
    )


def _refresh_indexed_fixtures(
    repository_root: Path,
    index: Any,
    schemas: dict[str, SchemaRecord],
) -> tuple[dict[str, Any], int, int, int]:
    entries = validate_fixture_index_document(index)
    fixture_paths = [entry["path"] for entry in entries]
    try:
        validate_portable_path_set(fixture_paths, "fixture index")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error
    outputs: dict[str, Any] = {}
    seen_paths: set[str] = set()
    managed = 0
    preserved = 0
    for entry in entries:
        relative = entry["path"]
        if relative in seen_paths:
            raise ContractToolError(f"duplicate fixture path in index: {relative}")
        seen_paths.add(relative)
        schema_id = entry["schemaId"]
        record = schemas.get(schema_id)
        if record is None:
            raise ContractToolError(
                f"indexed fixture references unknown schema ID: {schema_id}"
            )
        path = _resolve_declared_path(
            repository_root, relative, "indexed fixture path"
        )
        fixture = load_json(path)
        expected_semantic_error = entry.get("expectedSemanticError")
        if expected_semantic_error is not None:
            if expected_semantic_error not in SEMANTIC_SCHEMA_DENIALS:
                raise ContractToolError(
                    f"indexed fixture has an unknown schema semantic denial: {relative}"
                )
            observed = fixture_schema_descriptor_error(
                fixture, schema_id, record.digest
            )
            if observed != expected_semantic_error:
                raise ContractToolError(
                    f"intentional schema semantic denial drift in {relative}: "
                    f"expected {expected_semantic_error}, observed {observed}"
                )
            preserved += 1
            continue

        expected = deepcopy(fixture)
        if isinstance(fixture, dict) and "schema" in fixture:
            if not _exact_schema_descriptor(fixture["schema"]):
                if entry["valid"]:
                    raise ContractToolError(
                        f"valid indexed fixture has a malformed root schema descriptor: {relative}"
                    )
            else:
                expected["schema"] = {"id": schema_id, "digest": record.digest}
                outputs[relative] = expected
                managed += 1
                continue

        if schema_id == SCHEMA_DESCRIPTOR_ID and entry["valid"]:
            if not _exact_schema_descriptor(fixture):
                raise ContractToolError(
                    f"valid schema-descriptor fixture is malformed: {relative}"
                )
            target_id = fixture["id"]
            target = schemas.get(target_id)
            if target is None:
                raise ContractToolError(
                    f"schema-descriptor fixture references unknown schema ID: {target_id}"
                )
            expected = {"id": target_id, "digest": target.digest}
            outputs[relative] = expected
            managed += 1
    return outputs, len(entries), managed, preserved


def _resolve_projection_schema(
    repository_root: Path,
    projection_path: Path,
    reference: Any,
    schemas_by_path: dict[Path, SchemaRecord],
) -> SchemaRecord:
    if not isinstance(reference, str) or not reference:
        raise ContractToolError("schema projection has a missing $ref")
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or parsed.query or not parsed.path:
        raise ContractToolError(f"schema projection has a non-local source path: {reference}")
    if unquote(parsed.path) != parsed.path or "\\" in parsed.path:
        raise ContractToolError(f"schema projection has an ambiguous source path: {reference}")
    try:
        target = (projection_path.parent / parsed.path).resolve(strict=True)
    except OSError as error:
        raise ContractToolError(f"schema projection source is missing: {reference}") from error
    try:
        target.relative_to(repository_root)
    except ValueError as error:
        raise ContractToolError(f"schema projection source escapes repository: {reference}") from error
    record = schemas_by_path.get(target)
    if record is None:
        raise ContractToolError(f"schema projection references an unknown schema path: {reference}")
    if parsed.fragment and not parsed.fragment.startswith("/"):
        raise ContractToolError(f"schema projection has an invalid JSON Pointer fragment: {reference}")
    return record


def _refresh_projection_components(
    repository_root: Path,
    relative_path: str,
    document: Any,
    schemas_by_path: dict[Path, SchemaRecord],
) -> dict[str, Any]:
    expected = deepcopy(_require_object(document, f"projection {relative_path}"))
    try:
        components = expected["components"]
        projected_schemas = components["schemas"]
    except (KeyError, TypeError) as error:
        raise ContractToolError(f"projection has no schema components: {relative_path}") from error
    if not isinstance(projected_schemas, dict) or not projected_schemas:
        raise ContractToolError(f"projection has no schema components: {relative_path}")
    projection_path = _resolve_declared_path(
        repository_root, relative_path, "schema projection path"
    )
    managed = 0
    for name, component in projected_schemas.items():
        if not isinstance(name, str) or not name or not isinstance(component, dict):
            raise ContractToolError(f"projection has an invalid schema component: {relative_path}")
        marker_fields = {
            "$ref",
            "x-bytedesk-schema-id",
            "x-bytedesk-schema-digest",
        }
        if not marker_fields.intersection(component):
            continue
        if set(component) != marker_fields:
            raise ContractToolError(
                f"schema projection component {name} is not a pure exact descriptor"
            )
        record = _resolve_projection_schema(
            repository_root,
            projection_path,
            component["$ref"],
            schemas_by_path,
        )
        component["x-bytedesk-schema-id"] = record.schema_id
        component["x-bytedesk-schema-digest"] = record.digest
        managed += 1
    if managed == 0:
        raise ContractToolError(f"projection has no exact schema descriptors: {relative_path}")
    return expected


def _refresh_named_schema_digest_pairs(
    value: Any,
    schemas: dict[str, SchemaRecord],
    *,
    description: str,
) -> int:
    refreshed = 0
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            has_id = "x-bytedesk-data-schema-id" in current
            has_digest = "x-bytedesk-data-schema-digest" in current
            if has_id != has_digest:
                raise ContractToolError(f"{description} has an incomplete data-schema binding")
            if has_id:
                schema_id = current["x-bytedesk-data-schema-id"]
                record = schemas.get(schema_id)
                if record is None:
                    raise ContractToolError(
                        f"{description} references unknown schema ID: {schema_id}"
                    )
                current["x-bytedesk-data-schema-digest"] = record.digest
                refreshed += 1
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return refreshed


def _refresh_event_registry(
    document: Any, schemas: dict[str, SchemaRecord]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    current = _require_closed(document, EVENT_TYPES_ROOT_FIELDS, "event type registry")
    if current["profile"] != "bytedesk.event-types/1":
        raise ContractToolError("event type registry has an unknown profile")
    entries = current["eventTypes"]
    if not isinstance(entries, list) or not entries:
        raise ContractToolError("event type registry has no event types")
    expected = deepcopy(current)
    by_type: dict[str, dict[str, Any]] = {}
    for position, entry_value in enumerate(expected["eventTypes"]):
        entry = _require_closed(
            entry_value, EVENT_TYPE_FIELDS, f"event type registry entry {position}"
        )
        event_type = entry["type"]
        schema_id = entry["resourceSchemaId"]
        if not isinstance(event_type, str) or not event_type:
            raise ContractToolError(f"event type registry entry {position} has an invalid type")
        if event_type in by_type:
            raise ContractToolError(f"duplicate event type: {event_type}")
        record = schemas.get(schema_id)
        if record is None:
            raise ContractToolError(
                f"event type registry references unknown schema ID: {schema_id}"
            )
        if not isinstance(entry["resourceUriTemplate"], str) or not isinstance(
            entry["resynchronizeOperationId"], str
        ):
            raise ContractToolError(f"event type registry entry {position} has invalid paths")
        entry["resourceSchemaDigest"] = record.digest
        by_type[event_type] = entry
    return expected, by_type


def _openapi_resource_descriptor(
    openapi: dict[str, Any], operation: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    try:
        response_reference = operation["responses"]["200"]["$ref"]
        response_prefix = "#/components/responses/"
        if not isinstance(response_reference, str) or not response_reference.startswith(
            response_prefix
        ):
            raise KeyError("response")
        response = openapi["components"]["responses"][
            response_reference.removeprefix(response_prefix)
        ]
        schema_reference = response["content"]["application/json"]["schema"]["$ref"]
        schema_prefix = "#/components/schemas/"
        if not isinstance(schema_reference, str) or not schema_reference.startswith(
            schema_prefix
        ):
            raise KeyError("schema")
        component = openapi["components"]["schemas"][
            schema_reference.removeprefix(schema_prefix)
        ]
        return {
            "id": component["x-bytedesk-schema-id"],
            "digest": component["x-bytedesk-schema-digest"],
        }
    except (KeyError, TypeError) as error:
        raise ContractToolError(
            f"event resynchronization operation has no exact schema: {operation_id}"
        ) from error


def _validate_event_openapi_bindings(
    event_types: dict[str, dict[str, Any]], openapi: Any
) -> None:
    document = _require_object(openapi, "OpenAPI projection")
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise ContractToolError("OpenAPI projection has no paths")
    operations: dict[str, tuple[str, dict[str, Any]]] = {}
    for template, path_item in paths.items():
        operation = path_item.get("get") if isinstance(path_item, dict) else None
        operation_id = operation.get("operationId") if isinstance(operation, dict) else None
        if isinstance(operation_id, str):
            if operation_id in operations:
                raise ContractToolError(f"duplicate OpenAPI GET operation ID: {operation_id}")
            operations[operation_id] = (template, operation)
    for event_type, entry in event_types.items():
        operation_id = entry["resynchronizeOperationId"]
        binding = operations.get(operation_id)
        if binding is None:
            raise ContractToolError(
                f"event type references unknown OpenAPI operation: {event_type}"
            )
        template, operation = binding
        if template != entry["resourceUriTemplate"]:
            raise ContractToolError(f"event resource path differs from OpenAPI: {event_type}")
        if not operation.get("security"):
            raise ContractToolError(f"event resource read is unauthenticated: {event_type}")
        if _openapi_resource_descriptor(document, operation, operation_id) != {
            "id": entry["resourceSchemaId"],
            "digest": entry["resourceSchemaDigest"],
        }:
            raise ContractToolError(f"event resource schema differs from OpenAPI: {event_type}")


def _replace_required_descriptor(
    parent: dict[str, Any],
    field: str,
    record: SchemaRecord,
    description: str,
) -> None:
    if field not in parent or not _exact_schema_descriptor(parent[field]):
        raise ContractToolError(f"{description} lacks exact {field} schema descriptor")
    parent[field] = {"id": record.schema_id, "digest": record.digest}


def _refresh_event_examples(
    repository_root: Path,
    schemas: dict[str, SchemaRecord],
    event_types: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    event_schema = schemas.get(EVENT_DATA_SCHEMA_ID)
    if event_schema is None:
        raise ContractToolError(f"event examples require schema ID {EVENT_DATA_SCHEMA_ID}")
    examples_root = repository_root / EVENT_EXAMPLES_ROOT
    try:
        resolved_root = examples_root.resolve(strict=True)
    except OSError as error:
        raise ContractToolError("event examples directory is missing") from error
    if resolved_root != examples_root or not resolved_root.is_dir():
        raise ContractToolError("event examples directory is not canonical")
    paths = sorted(examples_root.glob("*.json"))
    if not paths:
        raise ContractToolError("event examples directory has no JSON examples")
    outputs: dict[str, Any] = {}
    observed: set[str] = set()
    for candidate in paths:
        relative = candidate.relative_to(repository_root).as_posix()
        path = _resolve_declared_path(
            repository_root, relative, "event example path"
        )
        event = _require_object(load_json(path), f"event example {relative}")
        event_type = event.get("type")
        if event_type in observed:
            raise ContractToolError(f"duplicate event example type: {event_type}")
        registry_entry = event_types.get(event_type)
        if registry_entry is None:
            raise ContractToolError(f"event example references unknown event type: {event_type}")
        if event.get("dataschema") != EVENT_DATA_SCHEMA_ID:
            raise ContractToolError(f"event example has an unknown dataschema: {relative}")
        expected = deepcopy(event)
        data = expected.get("data")
        if not isinstance(data, dict):
            raise ContractToolError(f"event example has no data object: {relative}")
        _replace_required_descriptor(data, "schema", event_schema, relative)
        _replace_required_descriptor(data, "dataSchema", event_schema, relative)
        resource = data.get("resource")
        if not isinstance(resource, dict):
            raise ContractToolError(f"event example has no resource object: {relative}")
        projection = schemas[registry_entry["resourceSchemaId"]]
        _replace_required_descriptor(
            resource, "projectionSchema", projection, relative
        )
        outputs[relative] = expected
        observed.add(event_type)
    missing = sorted(set(event_types) - observed)
    if missing:
        raise ContractToolError(f"event registry types lack examples: {missing}")
    return outputs, len(paths)


def _refresh_documentation_map(
    repository_root: Path,
    document: Any,
    schemas: dict[str, SchemaRecord],
) -> tuple[dict[str, Any], int]:
    current = _require_closed(document, DOCUMENTATION_MAP_FIELDS, "documentation map")
    if current["profile"] != "bytedesk.contract-documentation-map/1":
        raise ContractToolError("documentation map has an unknown profile")
    documents = current["documents"]
    if not isinstance(documents, list) or not documents:
        raise ContractToolError("documentation map has no fixed documents")
    paths: list[str] = []
    expected_documents: list[dict[str, str]] = []
    for position, value in enumerate(documents):
        entry = _require_closed(
            value, DOCUMENT_FIELDS, f"documentation inventory entry {position}"
        )
        relative = entry["path"]
        digest = entry["digest"]
        if not isinstance(digest, str) or EXACT_SHA256.fullmatch(digest) is None:
            raise ContractToolError(
                f"documentation inventory entry {position} has an invalid digest"
            )
        path = _resolve_declared_path(
            repository_root, relative, "documentation inventory path"
        )
        observed_digest, _ = stable_file_digest(
            path,
            description=f"documentation inventory file {relative}",
            maximum_bytes=MAX_BUNDLE_MEMBER_BYTES,
        )
        paths.append(relative)
        expected_documents.append({"path": relative, "digest": observed_digest})
    if paths != sorted(set(paths)):
        raise ContractToolError("documentation inventory paths are not sorted and unique")
    try:
        validate_portable_path_set(paths, "documentation inventory")
    except BundleProfileError as error:
        raise ContractToolError(str(error)) from error

    mappings = current["schemas"]
    if not isinstance(mappings, list) or not mappings:
        raise ContractToolError("documentation map has no schema mappings")
    mapped_ids: set[str] = set()
    referenced_documents: set[str] = set()
    expected_mappings: list[dict[str, Any]] = []
    inventory_paths = set(paths)
    for position, value in enumerate(mappings):
        entry = _require_closed(
            value, DOCUMENT_SCHEMA_FIELDS, f"documentation schema entry {position}"
        )
        schema_id = entry["id"]
        listed = entry["documents"]
        if schema_id in mapped_ids:
            raise ContractToolError(f"documentation map has duplicate schema ID: {schema_id}")
        if schema_id not in schemas:
            raise ContractToolError(
                f"documentation map references unknown schema ID: {schema_id}"
            )
        if (
            not isinstance(listed, list)
            or not listed
            or not all(isinstance(path, str) and path for path in listed)
            or len(listed) != len(set(listed))
        ):
            raise ContractToolError(
                f"documentation map has invalid documents for schema ID: {schema_id}"
            )
        unknown_documents = sorted(set(listed) - inventory_paths)
        if unknown_documents:
            raise ContractToolError(
                f"documentation map schema ID {schema_id} references unknown paths: "
                f"{unknown_documents}"
            )
        mapped_ids.add(schema_id)
        referenced_documents.update(listed)
        expected_mappings.append({"id": schema_id, "documents": listed})
    missing_ids = sorted(set(schemas) - mapped_ids)
    if missing_ids:
        raise ContractToolError(
            f"documentation map lacks schema IDs: {missing_ids}"
        )
    if referenced_documents != inventory_paths:
        raise ContractToolError(
            "documentation map document reference closure differs: "
            f"unreferenced={sorted(inventory_paths - referenced_documents)}"
        )

    projections = current["projections"]
    if not isinstance(projections, list) or not projections:
        raise ContractToolError("documentation map has no projections")
    projection_paths: list[str] = []
    expected_projections: list[dict[str, str]] = []
    for position, value in enumerate(projections):
        entry = _require_closed(
            value, PROJECTION_FIELDS, f"documentation projection entry {position}"
        )
        projection_path = entry["path"]
        source = entry["source"]
        role = entry["role"]
        if role not in PROJECTION_ROLES:
            raise ContractToolError(f"documentation projection has an unknown role: {role}")
        _resolve_declared_path(
            repository_root, projection_path, "documentation projection path"
        )
        source_is_directory = isinstance(source, str) and source.endswith("/")
        _resolve_declared_path(
            repository_root,
            source,
            "documentation projection source",
            directory_marker=source_is_directory,
        )
        if not source.startswith("contracts/"):
            raise ContractToolError(
                f"documentation projection source is outside contracts: {source}"
            )
        projection_paths.append(projection_path)
        expected_projections.append(
            {"path": projection_path, "source": source, "role": role}
        )
    if len(projection_paths) != len(set(projection_paths)):
        raise ContractToolError("documentation map has duplicate projection paths")

    return (
        {
            "profile": "bytedesk.contract-documentation-map/1",
            "documents": expected_documents,
            "schemas": sorted(expected_mappings, key=lambda item: item["id"]),
            "projections": sorted(expected_projections, key=lambda item: item["path"]),
        },
        len(paths),
    )


def build_refresh_plan(repository_root: Path = REPOSITORY_ROOT) -> RefreshPlan:
    """Build and fully validate a deterministic metadata output plan."""

    try:
        root = repository_root.resolve(strict=True)
    except OSError as error:
        raise ContractToolError(f"repository root is missing: {repository_root}") from error
    if not root.is_dir():
        raise ContractToolError(f"repository root is not a directory: {root}")
    schemas, schemas_by_path = _discover_schemas(root)
    outputs: dict[str, Any] = {}
    current: dict[str, Any] = {}

    def add_output(relative: str, observed: Any, expected: Any) -> None:
        if relative in outputs:
            if outputs[relative] != expected or current[relative] != observed:
                raise ContractToolError(f"metadata path has conflicting projections: {relative}")
            return
        outputs[relative] = expected
        current[relative] = observed

    _, inventory = _load_required_json(root, SCHEMA_INVENTORY_PATH, "schema inventory path")
    add_output(
        SCHEMA_INVENTORY_PATH,
        inventory,
        _expected_schema_inventory(inventory, schemas),
    )

    _, fixture_index = _load_required_json(root, FIXTURE_INDEX_PATH, "fixture index path")
    fixture_outputs, fixture_count, managed_fixtures, preserved_denials = (
        _refresh_indexed_fixtures(root, fixture_index, schemas)
    )
    for relative, expected in fixture_outputs.items():
        add_output(relative, load_json(root / relative), expected)

    _, openapi = _load_required_json(root, OPENAPI_PATH, "OpenAPI projection path")
    expected_openapi = _refresh_projection_components(
        root, OPENAPI_PATH, openapi, schemas_by_path
    )
    add_output(OPENAPI_PATH, openapi, expected_openapi)

    _, asyncapi = _load_required_json(root, ASYNCAPI_PATH, "AsyncAPI projection path")
    expected_asyncapi = _refresh_projection_components(
        root, ASYNCAPI_PATH, asyncapi, schemas_by_path
    )
    if _refresh_named_schema_digest_pairs(
        expected_asyncapi,
        schemas,
        description="AsyncAPI projection",
    ) == 0:
        raise ContractToolError("AsyncAPI projection has no data-schema digest bindings")
    add_output(ASYNCAPI_PATH, asyncapi, expected_asyncapi)

    _, event_registry = _load_required_json(root, EVENT_TYPES_PATH, "event registry path")
    expected_event_registry, event_types = _refresh_event_registry(
        event_registry, schemas
    )
    _validate_event_openapi_bindings(event_types, expected_openapi)
    add_output(EVENT_TYPES_PATH, event_registry, expected_event_registry)

    example_outputs, example_count = _refresh_event_examples(
        root, schemas, event_types
    )
    for relative, expected in example_outputs.items():
        add_output(relative, load_json(root / relative), expected)

    _, documentation_map = _load_required_json(
        root, DOCUMENTATION_MAP_PATH, "documentation map path"
    )
    expected_documentation_map, documentation_count = _refresh_documentation_map(
        root, documentation_map, schemas
    )
    add_output(
        DOCUMENTATION_MAP_PATH, documentation_map, expected_documentation_map
    )

    return RefreshPlan(
        repository_root=root,
        outputs=outputs,
        current=current,
        schema_count=len(schemas),
        indexed_fixture_count=fixture_count,
        managed_fixture_count=managed_fixtures,
        preserved_semantic_denial_count=preserved_denials,
        event_example_count=example_count,
        documentation_count=documentation_count,
    )


def _evidence(
    plan: RefreshPlan,
    *,
    mode: str,
    changed_paths: list[str],
) -> dict[str, Any]:
    return {
        "profile": "bytedesk.contract-metadata-refresh/1",
        "mode": mode,
        "schemaCount": plan.schema_count,
        "indexedFixtureCount": plan.indexed_fixture_count,
        "managedFixtureCount": plan.managed_fixture_count,
        "preservedSemanticDenialCount": plan.preserved_semantic_denial_count,
        "eventExampleCount": plan.event_example_count,
        "documentationCount": plan.documentation_count,
        "managedFileCount": len(plan.outputs),
        "changedFileCount": len(changed_paths),
        "changedFiles": changed_paths,
        "staleFileCount": len(plan.stale_paths),
        "staleFiles": plan.stale_paths,
        "outcome": "pass",
    }


def execute_refresh(
    repository_root: Path = REPOSITORY_ROOT, *, write: bool = False
) -> dict[str, Any]:
    """Check metadata drift, or atomically rewrite every stale JSON document."""

    plan = build_refresh_plan(repository_root)
    stale = plan.stale_paths
    if not write:
        if stale:
            raise ContractToolError(f"contract metadata drift: {stale}")
        return _evidence(plan, mode="check", changed_paths=[])

    # No output is written until every declaration and relationship above has
    # been resolved. Each replacement then uses contractlib's fsync + rename
    # atomic writer rather than a predictable temporary path.
    for relative in stale:
        write_json(plan.repository_root / relative, plan.outputs[relative])
    verified = build_refresh_plan(plan.repository_root)
    if verified.stale_paths:
        raise ContractToolError(
            f"contract metadata remained stale after write: {verified.stale_paths}"
        )
    return _evidence(verified, mode="write", changed_paths=stale)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check generated drift (default)")
    mode.add_argument("--write", action="store_true", help="atomically refresh stale metadata")
    args = parser.parse_args()
    evidence = execute_refresh(REPOSITORY_ROOT, write=args.write)
    print(json.dumps(evidence, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"contract metadata refresh failed: {error}", file=sys.stderr)
        raise SystemExit(1)
