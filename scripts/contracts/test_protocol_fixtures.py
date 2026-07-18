#!/usr/bin/env python3
"""Validate executable OCI, supply-chain, and capability protocol fixtures."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
from typing import Any
import zlib

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
import rfc8785


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "contracts" / "ports" / "v1" / "protocol-fixtures.json"
SCHEMA_PATH = ROOT / "contracts" / "schemas" / "v1" / "protocol-fixtures.schema.json"
PROFILE_PATH = ROOT / "contracts" / "ports" / "v1" / "protocol-profiles.json"
REGISTRY_PATH = ROOT / "contracts" / "ports" / "v1" / "port-registry.json"
TYPE_CATALOG_PATH = ROOT / "contracts" / "ports" / "v1" / "type-catalog.json"
CONFORMANCE_PATH = ROOT / "contracts" / "ports" / "v1" / "conformance-cases.json"

EXPECTED_FIXTURES = {
    "oci-empty-config",
    "oci-deterministic-layer",
    "oci-chunked-layer-blob",
    "oci-artifact-manifest",
    "spdx-2.3-document",
    "slsa-v1.2-provenance",
    "vulnerability-report",
    "malware-report",
    "secret-scan-report",
    "scan-completeness-report",
    "license-report",
    "capability-dispatch-authorization-proof",
    "capability-permitted-decision-proof",
    "capability-denied-sentinel-decision-proof",
    "capability-dispatch-request",
    "capability-dispatch-receipt",
    "capability-dispatch-result",
    "capability-evidence",
    "capability-verification-request",
    "capability-accepted-result",
    "capability-required-denied-decision-proof",
    "capability-evidence-denied",
    "capability-verification-request-denied",
    "capability-accepted-result-denied",
    "capability-not-applicable-certification",
    "capability-evidence-not-applicable",
    "capability-verification-request-not-applicable",
    "capability-accepted-result-not-applicable",
    "supply-generate-sbom-request",
    "supply-generate-sbom-result",
    "supply-generate-provenance-request",
    "supply-generate-provenance-result",
    "supply-scan-vulnerabilities-request",
    "supply-scan-vulnerabilities-result",
    "supply-scan-malware-request",
    "supply-scan-malware-result",
    "supply-scan-secrets-request",
    "supply-scan-secrets-result",
    "supply-attest-scan-completeness-request",
    "supply-attest-scan-completeness-result",
    "supply-evaluate-licenses-request",
    "supply-evaluate-licenses-result",
    "spdx-2.3-document-unknown-license",
    "license-report-deny",
    "license-report-indeterminate",
    "supply-evaluate-licenses-request-deny",
    "supply-evaluate-licenses-result-deny",
    "supply-evaluate-licenses-request-indeterminate",
    "supply-evaluate-licenses-result-indeterminate",
}

EXPECTED_MATERIALS = {
    "source-commit-and-tree",
    "builder-distribution",
    "workflow",
    "toolchain",
    "component-lock",
    "renderer-release",
    "public-skill",
    "private-skill",
    "policy-binding",
    "customization",
    "test-evidence",
}

EXPECTED_MUTATIONS = {
    "OCI-003-empty-config-digest-mismatch",
    "OCI-004-layer-profile-drift",
    "OCI-006-manifest-config-binding-mismatch",
    "OCI-007-chunk-offset-gap",
    "OCI-008-chunk-offset-overlap",
    "OCI-009-chunk-order-mismatch",
    "OCI-010-chunk-digest-mismatch",
    "OCI-011-aggregate-digest-mismatch",
    "EVIDENCE-001-incomplete-required-sbom",
    "EVIDENCE-002-provenance-builder-mismatch",
    "EVIDENCE-003-unpinned-scan-snapshot",
    "EVIDENCE-004-malware-coverage-incomplete-pass",
    "EVIDENCE-005-secret-coverage-incomplete-pass",
    "EVIDENCE-006-scan-completeness-false-pass",
    "EVIDENCE-007-license-input-mismatch",
    "CAP-004-consumer-mismatch",
    "CAP-004-target-mismatch",
    "CAP-004-candidate-mismatch",
    "CAP-004-check-profile-mismatch",
    "CAP-004-nonce-mismatch",
    "CAP-004-authorization-decision-mismatch",
    "CAP-004-issued-at-mismatch",
    "CAP-004-expires-at-mismatch",
    "CAP-004-request-digest-mismatch",
    "CAP-004-receipt-digest-mismatch",
    "CAP-004-evidence-digest-mismatch",
    "CAP-004-dispatch-proof-candidate-mismatch",
    "CAP-004-dispatch-proof-profile-mismatch",
    "CAP-004-dispatch-proof-window-mismatch",
    "CAP-004-dispatch-result-digest-mismatch",
    "CAP-004-evidence-issued-at-mismatch",
    "CAP-004-evidence-expires-at-mismatch",
    "CAP-004-evidence-authority-context-mismatch",
    "CAP-004-permitted-proof-digest-mismatch",
    "CAP-004-verification-receipt-object-mismatch",
    "CAP-004-verification-receipt-digest-mismatch",
    "CAP-004-verification-evidence-object-mismatch",
    "CAP-004-received-before-issued",
    "CAP-004-received-at-expiry",
    "CAP-004-fresh-until-mismatch",
    "CAP-002-denied-proof-digest-mismatch",
    "CAP-002-false-denial-outcome",
    "CAP-006-false-permit-outcome",
    "CAP-006-required-denial-proof-digest-mismatch",
    "CAP-005-certification-digest-mismatch",
    "CAP-005-certification-policy-mismatch",
    "CAP-005-certification-context-mismatch",
    "CAP-005-certification-signer-mismatch",
    "CAP-005-certification-expired",
    "CAP-005-not-applicable-failed",
    "CAP-005-false-denial-outcome",
    "CAP-009-evidence-auth-subject-mismatch",
    "CAP-009-proof-auth-signer-mismatch",
    "CAP-009-proof-auth-policy-mismatch",
    "CAP-009-auth-evidence-absent",
    "CAP-009-auth-verified-after-receipt",
    "CAP-009-certification-auth-subject-mismatch",
    "EVIDENCE-008-generate-sbom-result-digest-mismatch",
    "EVIDENCE-009-generate-provenance-result-digest-mismatch",
    "EVIDENCE-010-scan-vulnerabilities-result-digest-mismatch",
    "EVIDENCE-011-scan-malware-result-digest-mismatch",
    "EVIDENCE-012-scan-secrets-result-digest-mismatch",
    "EVIDENCE-013-attest-scan-completeness-result-digest-mismatch",
    "EVIDENCE-014-evaluate-licenses-result-digest-mismatch",
    "EVIDENCE-015-license-deny-false-pass",
    "EVIDENCE-016-license-indeterminate-false-pass",
    "EVIDENCE-017-license-expression-invalid",
    "EVIDENCE-018-license-list-unpinned",
    "EVIDENCE-019-exception-list-unpinned",
    "EVIDENCE-020-license-parser-profile-unpinned",
    "EVIDENCE-021-license-list-version-unpinned",
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
MAX_OCI_CHUNK_BYTES = 4 * 1024 * 1024
MAX_OCI_BLOB_BYTES = 64 * 1024 * 1024
MAX_OCI_MEMBER_BYTES = 16 * 1024 * 1024
MAX_OCI_MEMBERS = 20000
MAX_CATALOG_BYTES = 128 * 1024 * 1024
EXPECTED_EVALUATION_TIME = "2026-07-17T12:01:00Z"
SPDX_LICENSE_LIST_VERSION = "3.28.0"
SPDX_LICENSE_LIST_DIGEST = "sha256:f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee"
SPDX_EXCEPTION_LIST_DIGEST = "sha256:bd145bb558f44432fcd6f0d7e956ed0124dff72af7641a7cfcb1b557dc390a5b"
SPDX_EXPRESSION_PARSER_PROFILE = "spdx-license-expression-2.3-strict/1"


class ProtocolError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def load_json(path: Path, *, maximum_bytes: int | None = None) -> dict[str, Any]:
    try:
        if maximum_bytes is not None:
            require(path.stat().st_size <= maximum_bytes, f"{path.relative_to(ROOT)} exceeds bounded document size")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"cannot load {path.relative_to(ROOT)}: {error}") from error
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} root must be an object")
    return value


def build_schema_registry(
    type_catalog: dict[str, Any],
) -> tuple[Registry, dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    schemas: dict[str, dict[str, Any]] = {}
    schema_refs: dict[str, str] = {}
    contract_ids: dict[str, str] = {}

    def add_schema(schema: Any, label: str) -> str:
        require(isinstance(schema, dict), f"{label} schema is not an object")
        schema_id = schema.get("$id")
        require(isinstance(schema_id, str), f"{label} schema has no $id")
        require(schema_id not in schemas, f"duplicate executable schema ID: {schema_id}")
        Draft202012Validator.check_schema(schema)
        schemas[schema_id] = schema
        return schema_id

    for path in sorted((ROOT / "contracts" / "schemas" / "v1").glob("*.schema.json")):
        add_schema(load_json(path), str(path.relative_to(ROOT)))
    for index, entry in enumerate(type_catalog["baseTypes"]):
        schema_id = add_schema(entry["schema"], f"baseTypes[{index}]")
        schema_ref = entry["schemaRef"]
        require(schema_ref not in schema_refs, f"duplicate base schema ref: {schema_ref}")
        schema_refs[schema_ref] = schema_id
    for index, entry in enumerate(type_catalog["types"]):
        add_schema(entry["schema"], f"types[{index}]")
    for index, entry in enumerate(type_catalog["contracts"]):
        schema_id = add_schema(entry["schema"], f"contracts[{index}]")
        contract_id = entry["contractId"]
        require(contract_id not in contract_ids, f"duplicate port contract ID: {contract_id}")
        contract_ids[contract_id] = schema_id
    registry = Registry().with_resources(
        (schema_id, Resource.from_contents(schema))
        for schema_id, schema in schemas.items()
    )
    return registry, schemas, schema_refs, contract_ids


def validate_schema_instance(
    instance: Any,
    schema_id: str,
    *,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    label: str,
) -> None:
    require(schema_id in schemas, f"{label} references unknown schema: {schema_id}")
    errors = sorted(
        Draft202012Validator(
            schemas[schema_id],
            registry=registry,
            format_checker=FormatChecker(),
        ).iter_errors(instance),
        key=lambda error: (list(error.absolute_path), error.validator or ""),
    )
    if errors:
        first = errors[0]
        path = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise ProtocolError(
            f"{label} fails {schema_id} at {path}: {first.message}"
        )


def parse_time(value: Any, label: str) -> datetime:
    require(isinstance(value, str), f"{label} is not a timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProtocolError(f"{label} is not RFC 3339 date-time") from error
    require(parsed.tzinfo is not None, f"{label} has no offset")
    return parsed.astimezone(timezone.utc)


def digest_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(rfc8785.dumps(value))


def decode_payload(entry: dict[str, Any]) -> bytes:
    entry_id = entry.get("fixtureId", entry.get("materialId", "payload"))
    encoded = entry["contentBase64url"]
    require(isinstance(encoded, str), f"{entry_id} payload is not text")
    require("=" not in encoded, f"{entry_id} base64url is padded")
    try:
        payload = base64.b64decode(
            encoded + "=" * ((-len(encoded)) % 4), altchars=b"-_", validate=True
        )
    except ValueError as error:
        raise ProtocolError(f"{entry_id} base64url is invalid") from error
    canonical = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    require(canonical == encoded, f"{entry_id} base64url is noncanonical")
    require(len(payload) == entry["size"], f"{entry_id} size mismatch")
    require(digest_bytes(payload) == entry["digest"], f"{entry_id} digest mismatch")
    return payload


def decode_json(entry: dict[str, Any]) -> dict[str, Any]:
    payload = decode_payload(entry)
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"{entry.get('fixtureId', entry.get('materialId', 'payload'))} is not JSON") from error
    entry_id = entry.get("fixtureId", entry.get("materialId", "payload"))
    require(isinstance(value, dict), f"{entry_id} JSON root must be an object")
    require(rfc8785.dumps(value) == payload, f"{entry_id} is not exact JCS JSON")
    return value


def validate_tar(payload: bytes) -> list[tuple[str, bytes, int]]:
    require(len(payload) <= MAX_OCI_BLOB_BYTES, "expanded tar exceeds aggregate bound")
    require(len(payload) % 512 == 0 and payload.endswith(b"\0" * 1024), "tar framing drift")
    entries: list[tuple[str, bytes, int]] = []
    offset = 0
    names: list[str] = []
    while payload[offset : offset + 512] != b"\0" * 512:
        require(len(entries) < MAX_OCI_MEMBERS, "tar member count exceeds bound")
        header = payload[offset : offset + 512]
        require(len(header) == 512, "truncated tar header")
        require(header[257:263] == b"ustar\0" and header[263:265] == b"00", "non-ustar layer")
        require(header[156:157] in {b"0", b"\0"}, "non-regular tar member")
        require(header[157:257].rstrip(b"\0") == b"", "tar link target is forbidden")
        name = header[0:100].split(b"\0", 1)[0].decode("utf-8")
        mode = int(header[100:108].rstrip(b"\0 ") or b"0", 8)
        uid = int(header[108:116].rstrip(b"\0 ") or b"0", 8)
        gid = int(header[116:124].rstrip(b"\0 ") or b"0", 8)
        size = int(header[124:136].rstrip(b"\0 ") or b"0", 8)
        require(size <= MAX_OCI_MEMBER_BYTES, f"tar member exceeds byte bound: {name}")
        mtime = int(header[136:148].rstrip(b"\0 ") or b"0", 8)
        require(uid == gid == mtime == 0, f"nondeterministic tar metadata: {name}")
        require(mode in {0o644, 0o755}, f"unsafe tar mode: {name}")
        require(header[265:297].rstrip(b"\0") == b"", f"tar uname is not empty: {name}")
        require(header[297:329].rstrip(b"\0") == b"", f"tar gname is not empty: {name}")
        checksum_header = bytearray(header)
        checksum_header[148:156] = b" " * 8
        claimed = int(header[148:156].rstrip(b"\0 ") or b"0", 8)
        require(sum(checksum_header) == claimed, f"tar checksum mismatch: {name}")
        offset += 512
        data = payload[offset : offset + size]
        require(len(data) == size, f"truncated tar data: {name}")
        entries.append((name, data, mode))
        names.append(name)
        offset += ((size + 511) // 512) * 512
    require(names == sorted(names) and len(names) == len(set(names)), "tar paths are not unique sorted paths")
    require(offset + 1024 == len(payload), "tar has trailing records")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        require([member.name for member in archive.getmembers()] == names, "independent tar parser disagrees")
    return entries


def validate_layer(entry: dict[str, Any]) -> bytes:
    payload = decode_payload(entry)
    require(len(payload) <= MAX_OCI_BLOB_BYTES, "compressed OCI layer exceeds blob bound")
    require(payload[:4] == b"\x1f\x8b\x08\x00", "gzip header or flags drift")
    require(payload[4:8] == b"\0\0\0\0", "gzip mtime is not zero")
    require(payload[8] == 2 and payload[9] == 255, "gzip XFL/OS profile drift")
    decoder = zlib.decompressobj(wbits=31)
    tar_payload = decoder.decompress(payload, MAX_OCI_BLOB_BYTES + 1)
    require(len(tar_payload) <= MAX_OCI_BLOB_BYTES, "expanded OCI layer exceeds aggregate bound")
    require(not decoder.unconsumed_tail, "expanded OCI layer exceeds bounded decompression")
    remaining = MAX_OCI_BLOB_BYTES - len(tar_payload) + 1
    tar_payload += decoder.flush(remaining)
    require(len(tar_payload) <= MAX_OCI_BLOB_BYTES, "expanded OCI layer exceeds aggregate bound")
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, "concatenated or trailing gzip data")
    entries = validate_tar(tar_payload)
    require([name for name, _, _ in entries] == ["agent.json", "skills/run.sh"], "layer inventory drift")
    return tar_payload


def validate_spdx(document: dict[str, Any], fixtures: dict[str, dict[str, Any]]) -> None:
    required = {"SPDXID", "spdxVersion", "dataLicense", "name", "documentNamespace", "creationInfo", "packages", "files", "relationships"}
    require(required <= set(document), "SPDX required section missing")
    require(document["SPDXID"] == "SPDXRef-DOCUMENT" and document["spdxVersion"] == "SPDX-2.3", "SPDX identity drift")
    require(document["dataLicense"] == "CC0-1.0", "SPDX data license drift")
    require(document["packages"] and document["files"] and document["relationships"], "SPDX coverage is empty")
    layer_tar = validate_layer(fixtures["oci-deterministic-layer"])
    layer_members = {f"./{name}": payload for name, payload, _ in validate_tar(layer_tar)}
    file_ids: set[str] = set()
    sha1_by_file: dict[str, str] = {}
    described_files: set[str] = set()
    for file_entry in document["files"]:
        file_ids.add(file_entry["SPDXID"])
        file_name = file_entry.get("fileName")
        require(file_name in layer_members, f"SPDX file is absent from OCI layer: {file_name}")
        require(file_name not in described_files, f"SPDX file is duplicated: {file_name}")
        described_files.add(file_name)
        file_bytes = layer_members[file_name]
        checksums = file_entry.get("checksums", [])
        require(
            any(
                check.get("algorithm") == "SHA256"
                and check.get("checksumValue") == hashlib.sha256(file_bytes).hexdigest()
                for check in checksums
            ),
            "SPDX file SHA256 does not match OCI layer bytes",
        )
        sha1_values = [
            check["checksumValue"]
            for check in checksums
            if check.get("algorithm") == "SHA1"
            and HEX40.fullmatch(check.get("checksumValue", ""))
        ]
        require(len(sha1_values) == 1, "SPDX file must have one SHA1 for package verification")
        require(sha1_values[0] == hashlib.sha1(file_bytes).hexdigest(), "SPDX file SHA1 does not match OCI layer bytes")
        sha1_by_file[file_entry["SPDXID"]] = sha1_values[0]
    require(described_files == set(layer_members), "SPDX file inventory does not exactly cover the OCI layer")
    for package in document["packages"]:
        require(package.get("filesAnalyzed") is True, "SPDX package files are not analyzed")
        verification = package.get("packageVerificationCode", {})
        claimed = verification.get("packageVerificationCodeValue", "")
        require(HEX40.fullmatch(claimed) is not None, "SPDX package verification code missing")
        excluded = set(verification.get("packageVerificationCodeExcludedFiles", []))
        require(not excluded, "golden SPDX package may not exclude layer files")
        included_sha1s = sorted(
            checksum
            for file_id, checksum in sha1_by_file.items()
            if file_id not in excluded
        )
        expected = hashlib.sha1("".join(included_sha1s).encode("ascii")).hexdigest()
        require(claimed == expected, "SPDX package verification code does not match included file SHA1 values")
    contained = {item["relatedSpdxElement"] for item in document["relationships"] if item.get("relationshipType") == "CONTAINS"}
    require(file_ids <= contained, "SPDX relationship coverage is incomplete")


def validate_slsa(
    statement: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    materials: dict[str, dict[str, Any]],
) -> None:
    require(set(statement) == {"_type", "subject", "predicateType", "predicate"}, "in-toto Statement members drift")
    require(statement["_type"] == "https://in-toto.io/Statement/v1", "in-toto statement type drift")
    require(statement["predicateType"] == "https://slsa.dev/provenance/v1", "SLSA predicate type drift")
    require(len(statement["subject"]) == 1 and all(HEX64.fullmatch(item["digest"]["sha256"]) for item in statement["subject"]), "SLSA subject digest missing")
    require(
        statement["subject"][0]["digest"]["sha256"]
        == fixtures["oci-artifact-manifest"]["digest"].removeprefix("sha256:"),
        "SLSA subject is not bound to the exact OCI manifest",
    )
    predicate = statement["predicate"]
    require(set(predicate) == {"buildDefinition", "runDetails"}, "SLSA predicate shape drift")
    definition = predicate["buildDefinition"]
    require({"buildType", "externalParameters", "resolvedDependencies"} <= set(definition), "SLSA build definition incomplete")
    expected_external_parameters_digest = digest_json(
        {
            "profile": "bytedesk.agent-delivery-build/1",
            "subjectDigest": fixtures["oci-artifact-manifest"]["digest"],
        }
    )
    require(
        definition["externalParameters"]
        == {"digest": expected_external_parameters_digest},
        "SLSA external-parameters digest is not bound to the exact output",
    )
    dependencies = definition["resolvedDependencies"]
    require(dependencies, "SLSA resolved dependencies are empty")
    kinds: set[str] = set()
    referenced_materials: set[str] = set()
    for dependency in dependencies:
        require({"uri", "digest", "annotations"} <= set(dependency), "SLSA ResourceDescriptor is incomplete")
        require(HEX64.fullmatch(dependency["digest"].get("sha256", "")) is not None, "SLSA material SHA256 is missing")
        annotations = dependency["annotations"]
        kind = annotations.get("ai.bytedesk.material-kind")
        material_id = annotations.get("ai.bytedesk.material-id")
        require(isinstance(kind, str) and kind, "SLSA material kind annotation is missing")
        require(material_id in materials, "SLSA material binding is unknown")
        material = materials[material_id]
        require(kind == material["kind"], f"SLSA material kind is not bound to {material_id}")
        require(dependency["uri"] == material["uri"], f"SLSA material URI is not bound to {material_id}")
        require(
            dependency["digest"]["sha256"] == material["digest"].removeprefix("sha256:"),
            f"SLSA material digest is not bound to {material_id}",
        )
        kinds.add(kind)
        require(material_id not in referenced_materials, f"SLSA material is duplicated: {material_id}")
        referenced_materials.add(material_id)
    required_kinds = {"source-commit-and-tree", "builder", "workflow", "toolchain", "component-lock", "renderer-release", "public-skill", "private-skill", "policy-binding", "customization", "test-evidence"}
    require(required_kinds <= kinds, "SLSA required material class missing")
    require(referenced_materials == set(materials), "SLSA resolved dependencies do not exactly cover golden materials")
    run = predicate["runDetails"]
    require(
        run["builder"]["id"] == materials["builder-distribution"]["uri"],
        "SLSA builder identity is not bound to the golden builder distribution",
    )
    metadata = run["metadata"]
    require({"invocationId", "startedOn", "finishedOn"} <= set(metadata), "SLSA run metadata incomplete")


def validate_blob_stream(entry: dict[str, Any], fixtures: dict[str, dict[str, Any]]) -> None:
    stream = decode_json(entry)
    require(set(stream) == {"mediaType", "digest", "size", "chunks"}, "OCI blob stream is not closed")
    require(isinstance(stream["chunks"], list) and stream["chunks"], "OCI blob stream has no chunks")
    reconstructed = bytearray()
    expected_offset = 0
    for expected_index, chunk in enumerate(stream["chunks"]):
        require(
            set(chunk) == {"index", "offset", "size", "digest", "contentBase64url"},
            "OCI blob chunk is not closed",
        )
        require(chunk["index"] == expected_index, "OCI blob chunk order/index mismatch")
        require(chunk["offset"] == expected_offset, "OCI blob chunk offset is not contiguous")
        encoded = chunk["contentBase64url"]
        require(isinstance(encoded, str) and "=" not in encoded, "OCI blob chunk base64url is padded")
        try:
            payload = base64.b64decode(
                encoded + "=" * ((-len(encoded)) % 4), altchars=b"-_", validate=True
            )
        except ValueError as error:
            raise ProtocolError("OCI blob chunk base64url is invalid") from error
        require(
            base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii") == encoded,
            "OCI blob chunk base64url is noncanonical",
        )
        require(0 < len(payload) <= MAX_OCI_CHUNK_BYTES, "OCI blob chunk exceeds bounded wire size")
        require(chunk["size"] == len(payload), "OCI blob chunk size mismatch")
        require(chunk["digest"] == digest_bytes(payload), "OCI blob chunk digest mismatch")
        reconstructed.extend(payload)
        expected_offset += len(payload)
    require(len(reconstructed) <= MAX_OCI_BLOB_BYTES, "OCI blob exceeds maximum aggregate size")
    require(stream["size"] == len(reconstructed), "OCI blob aggregate size mismatch")
    require(stream["digest"] == digest_bytes(reconstructed), "OCI blob aggregate digest mismatch")
    layer = fixtures["oci-deterministic-layer"]
    require(stream["mediaType"] == layer["mediaType"], "OCI blob stream media type mismatch")
    require(stream["size"] == layer["size"], "OCI blob stream does not bind the layer size")
    require(stream["digest"] == layer["digest"], "OCI blob stream does not bind the layer digest")
    require(bytes(reconstructed) == decode_payload(layer), "OCI blob stream does not reconstruct the layer bytes")


def validate_spdx_expression_syntax(expression: str) -> None:
    require(isinstance(expression, str) and expression, "SPDX expression is empty")
    token_pattern = re.compile(
        r"\s*(\(|\)|\+|AND\b|OR\b|WITH\b|(?:DocumentRef-[A-Za-z0-9.-]+:)?LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9][A-Za-z0-9.-]*)"
    )
    tokens: list[str] = []
    offset = 0
    while offset < len(expression):
        match = token_pattern.match(expression, offset)
        require(match is not None, "SPDX expression contains an invalid token")
        tokens.append(match.group(1))
        offset = match.end()
    require(offset == len(expression), "SPDX expression has trailing invalid bytes")
    position = 0

    def parse_atom() -> None:
        nonlocal position
        require(position < len(tokens), "SPDX expression ends before an operand")
        if tokens[position] == "(":
            position += 1
            parse_or()
            require(position < len(tokens) and tokens[position] == ")", "SPDX expression has an unclosed group")
            position += 1
            return
        require(tokens[position] not in {"AND", "OR", "WITH", ")", "+"}, "SPDX expression operand is invalid")
        position += 1
        if position < len(tokens) and tokens[position] == "+":
            position += 1

    def parse_with() -> None:
        nonlocal position
        parse_atom()
        if position < len(tokens) and tokens[position] == "WITH":
            position += 1
            require(position < len(tokens), "SPDX WITH lacks an exception")
            require(tokens[position] not in {"AND", "OR", "WITH", "(", ")", "+"}, "SPDX exception identifier is invalid")
            position += 1

    def parse_and() -> None:
        nonlocal position
        parse_with()
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            parse_with()

    def parse_or() -> None:
        nonlocal position
        parse_and()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            parse_and()

    parse_or()
    require(position == len(tokens), "SPDX expression has trailing operators or operands")


def validate_report(
    kind: str,
    report: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    materials: dict[str, dict[str, Any]],
) -> None:
    required_by_kind = {
        "vulnerability-report": {"artifactDigest", "sbomDigest", "scannerImageDigest", "scannerRulesDigest", "advisorySnapshotDigest", "severityPolicyDigest", "scanTime", "outcome", "coverageComplete", "findings"},
        "malware-report": {"artifactDigest", "scannerImageDigest", "signatureDatabaseDigest", "sandboxProfileDigest", "scanTime", "outcome", "coverageComplete", "findings"},
        "secret-scan-report": {"artifactDigest", "scannerImageDigest", "rulesetDigest", "allowlistDigest", "scanTime", "outcome", "coverageComplete", "findings"},
        "scan-completeness-report": {"artifactDigest", "inventoryDigest", "vulnerabilityReportDigest", "malwareReportDigest", "secretScanReportDigest", "evaluatorImageDigest", "evaluatedAt", "outcome", "complete"},
        "license-report": {"sbomDigest", "licensePolicyId", "licensePolicyDigest", "evaluatorImageDigest", "expressionParserProfile", "licenseListVersion", "licenseListDigest", "exceptionListDigest", "evaluationTime", "outcome", "expressions"},
    }
    require(required_by_kind[kind] <= set(report), f"{kind} pinned field missing")
    require(report["outcome"] in {"pass", "deny", "indeterminate"}, f"{kind} outcome drift")
    if kind in {"vulnerability-report", "malware-report", "secret-scan-report"}:
        require(not (report["outcome"] == "pass" and report["coverageComplete"] is not True), f"{kind} passes incomplete coverage")
    if kind == "scan-completeness-report":
        require(not (report["outcome"] == "pass" and report["complete"] is not True), "scan completeness passes incomplete evidence")
    manifest_digest = fixtures["oci-artifact-manifest"]["digest"]
    sbom_digest = fixtures["spdx-2.3-document"]["digest"]
    if "artifactDigest" in report:
        require(report["artifactDigest"] == manifest_digest, f"{kind} artifact binding mismatch")
    if "sbomDigest" in report:
        accepted_sbom_digests = (
            {
                entry["digest"]
                for entry in fixtures.values()
                if entry["kind"] == "spdx-document"
            }
            if kind == "license-report"
            else {sbom_digest}
        )
        require(report["sbomDigest"] in accepted_sbom_digests, f"{kind} SBOM binding mismatch")
    if kind == "vulnerability-report":
        require(report["scannerImageDigest"] == materials["toolchain"]["digest"], "vulnerability scanner pin mismatch")
        require(report["scannerRulesDigest"] == materials["workflow"]["digest"], "vulnerability rules pin mismatch")
        require(report["advisorySnapshotDigest"] == materials["component-lock"]["digest"], "vulnerability advisory pin mismatch")
        require(report["severityPolicyDigest"] == materials["policy-binding"]["digest"], "vulnerability policy pin mismatch")
        require(report["scanTime"] == EXPECTED_EVALUATION_TIME, "vulnerability scan time mismatch")
    elif kind == "malware-report":
        require(report["scannerImageDigest"] == materials["toolchain"]["digest"], "malware scanner pin mismatch")
        require(report["signatureDatabaseDigest"] == materials["component-lock"]["digest"], "malware signature database pin mismatch")
        require(report["sandboxProfileDigest"] == materials["policy-binding"]["digest"], "malware sandbox profile pin mismatch")
        require(report["scanTime"] == EXPECTED_EVALUATION_TIME, "malware scan time mismatch")
    elif kind == "secret-scan-report":
        require(report["scannerImageDigest"] == materials["toolchain"]["digest"], "secret scanner pin mismatch")
        require(report["rulesetDigest"] == materials["workflow"]["digest"], "secret rules pin mismatch")
        require(report["allowlistDigest"] == materials["policy-binding"]["digest"], "secret allowlist pin mismatch")
        require(report["scanTime"] == EXPECTED_EVALUATION_TIME, "secret scan time mismatch")
    elif kind == "scan-completeness-report":
        expected_inventory = digest_bytes(validate_layer(fixtures["oci-deterministic-layer"]))
        require(report["inventoryDigest"] == expected_inventory, "completeness inventory binding mismatch")
        require(report["vulnerabilityReportDigest"] == fixtures["vulnerability-report"]["digest"], "completeness vulnerability binding mismatch")
        require(report["malwareReportDigest"] == fixtures["malware-report"]["digest"], "completeness malware binding mismatch")
        require(report["secretScanReportDigest"] == fixtures["secret-scan-report"]["digest"], "completeness secret binding mismatch")
        require(report["evaluatorImageDigest"] == materials["toolchain"]["digest"], "completeness evaluator pin mismatch")
        require(report["evaluatedAt"] == EXPECTED_EVALUATION_TIME, "completeness evaluation time mismatch")
    elif kind == "license-report":
        require(report["licensePolicyId"] == "consumer-license-policy-1", "license policy ID mismatch")
        require(report["licensePolicyDigest"] == materials["policy-binding"]["digest"], "license policy pin mismatch")
        require(report["evaluatorImageDigest"] == materials["toolchain"]["digest"], "license evaluator pin mismatch")
        require(report["expressionParserProfile"] == SPDX_EXPRESSION_PARSER_PROFILE, "license expression parser profile mismatch")
        require(report["licenseListVersion"] == SPDX_LICENSE_LIST_VERSION, "SPDX License List version mismatch")
        require(report["licenseListDigest"] == SPDX_LICENSE_LIST_DIGEST, "SPDX license-list digest mismatch")
        require(report["exceptionListDigest"] == SPDX_EXCEPTION_LIST_DIGEST, "SPDX exception-list digest mismatch")
        require(report["evaluationTime"] == EXPECTED_EVALUATION_TIME, "license evaluation time mismatch")
        spdx_candidates = [
            entry
            for entry in fixtures.values()
            if entry["kind"] == "spdx-document"
            and entry["digest"] == report["sbomDigest"]
        ]
        require(len(spdx_candidates) == 1, "license report does not bind one exact SPDX document")
        spdx = decode_json(spdx_candidates[0])
        package_licenses = {
            package["SPDXID"]: package.get("licenseDeclared")
            for package in spdx["packages"]
        }
        expressions = report["expressions"]
        require(
            len(expressions) == len({entry["packageId"] for entry in expressions}),
            "license report duplicates a package",
        )
        require(
            {entry["packageId"] for entry in expressions} == set(package_licenses),
            "license report does not exactly cover SBOM packages",
        )
        for entry in expressions:
            expression = entry["expression"]
            disposition = entry["disposition"]
            validate_spdx_expression_syntax(expression)
            require(
                expression == package_licenses[entry["packageId"]],
                "license report expression differs from the bound SBOM",
            )
            if expression in {"NOASSERTION", "NONE"}:
                require(disposition == "unknown", "unknown SPDX license is not indeterminate")
            else:
                require(disposition in {"allowed", "denied"}, "known SPDX license has unknown disposition")
        derived_outcome = (
            "deny"
            if any(entry["disposition"] == "denied" for entry in expressions)
            else "indeterminate"
            if any(entry["disposition"] == "unknown" for entry in expressions)
            else "pass"
        )
        require(
            report["outcome"] == derived_outcome,
            "license report outcome differs from its exact dispositions",
        )


SUPPLY_OPERATIONS = (
    "generate-sbom",
    "generate-provenance",
    "scan-vulnerabilities",
    "scan-malware",
    "scan-secrets",
    "attest-scan-completeness",
    "evaluate-licenses",
)


def expected_supply_wrappers(
    fixtures: dict[str, dict[str, Any]],
    materials: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    manifest_digest = fixtures["oci-artifact-manifest"]["digest"]
    spdx_entry = fixtures["spdx-2.3-document"]
    spdx = decode_json(spdx_entry)
    slsa_entry = fixtures["slsa-v1.2-provenance"]
    slsa = decode_json(slsa_entry)
    vulnerability_entry = fixtures["vulnerability-report"]
    vulnerability = decode_json(vulnerability_entry)
    malware_entry = fixtures["malware-report"]
    malware = decode_json(malware_entry)
    secret_entry = fixtures["secret-scan-report"]
    secret = decode_json(secret_entry)
    completeness_entry = fixtures["scan-completeness-report"]
    completeness = decode_json(completeness_entry)
    license_entry = fixtures["license-report"]
    license_report = decode_json(license_entry)
    definition = slsa["predicate"]["buildDefinition"]
    run = slsa["predicate"]["runDetails"]
    wrappers: dict[str, dict[str, Any]] = {
        "supply-generate-sbom-request": {
            "artifactDigest": manifest_digest,
            "generatorImageDigest": materials["toolchain"]["digest"],
            "componentLockDigest": materials["component-lock"]["digest"],
        },
        "supply-generate-sbom-result": {
            "sbomDigest": spdx_entry["digest"],
            "sbomDescriptor": {
                "specification": "SPDX-2.3",
                "interoperabilityProfile": "agent-delivery-v1-spdx-2.3-json",
                "documentNamespace": spdx["documentNamespace"],
                "documentDigest": spdx_entry["digest"],
                "artifactDigest": manifest_digest,
                "mediaType": "application/spdx+json",
                "packageCount": len(spdx["packages"]),
                "fileCount": len(spdx["files"]),
                "relationshipCount": len(spdx["relationships"]),
                "generatedAt": spdx["creationInfo"]["created"],
            },
        },
        "supply-generate-provenance-request": {
            "subjectDigest": manifest_digest,
            "buildType": definition["buildType"],
            "builderId": run["builder"]["id"],
            "invocationId": run["metadata"]["invocationId"],
            "externalParametersDigest": definition["externalParameters"]["digest"],
            "resolvedDependencies": definition["resolvedDependencies"],
            "startedOn": run["metadata"]["startedOn"],
            "finishedOn": run["metadata"]["finishedOn"],
        },
        "supply-generate-provenance-result": {
            "provenanceDigest": slsa_entry["digest"],
            "provenance": slsa,
        },
        "supply-scan-vulnerabilities-request": {
            key: vulnerability[key]
            for key in (
                "artifactDigest",
                "sbomDigest",
                "scannerImageDigest",
                "scannerRulesDigest",
                "advisorySnapshotDigest",
                "severityPolicyDigest",
                "scanTime",
            )
        },
        "supply-scan-vulnerabilities-result": {
            "reportDigest": vulnerability_entry["digest"],
            "report": vulnerability,
        },
        "supply-scan-malware-request": {
            key: malware[key]
            for key in (
                "artifactDigest",
                "scannerImageDigest",
                "signatureDatabaseDigest",
                "sandboxProfileDigest",
                "scanTime",
            )
        },
        "supply-scan-malware-result": {
            "reportDigest": malware_entry["digest"],
            "report": malware,
        },
        "supply-scan-secrets-request": {
            key: secret[key]
            for key in (
                "artifactDigest",
                "scannerImageDigest",
                "rulesetDigest",
                "allowlistDigest",
                "scanTime",
            )
        },
        "supply-scan-secrets-result": {
            "reportDigest": secret_entry["digest"],
            "report": secret,
        },
        "supply-attest-scan-completeness-request": {
            "artifactDigest": completeness["artifactDigest"],
            "inventoryDigest": completeness["inventoryDigest"],
            "vulnerabilityReportDigest": completeness["vulnerabilityReportDigest"],
            "malwareReportDigest": completeness["malwareReportDigest"],
            "secretScanReportDigest": completeness["secretScanReportDigest"],
            "evaluatorImageDigest": completeness["evaluatorImageDigest"],
            "evaluationTime": completeness["evaluatedAt"],
        },
        "supply-attest-scan-completeness-result": {
            "reportDigest": completeness_entry["digest"],
            "report": completeness,
        },
        "supply-evaluate-licenses-request": {
            key: license_report[key]
            for key in (
                "sbomDigest",
                "licensePolicyId",
                "licensePolicyDigest",
                "evaluatorImageDigest",
                "expressionParserProfile",
                "licenseListVersion",
                "licenseListDigest",
                "exceptionListDigest",
                "evaluationTime",
            )
        },
        "supply-evaluate-licenses-result": {
            "evaluationDigest": license_entry["digest"],
            "report": license_report,
        },
    }
    for variant, report_fixture_id in (
        ("deny", "license-report-deny"),
        ("indeterminate", "license-report-indeterminate"),
    ):
        report_entry = fixtures[report_fixture_id]
        report = decode_json(report_entry)
        request = dict(wrappers["supply-evaluate-licenses-request"])
        request["sbomDigest"] = report["sbomDigest"]
        wrappers[f"supply-evaluate-licenses-request-{variant}"] = request
        wrappers[f"supply-evaluate-licenses-result-{variant}"] = {
            "evaluationDigest": report_entry["digest"],
            "report": report,
        }
    return wrappers


def validate_fixture(
    entry: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    materials: dict[str, dict[str, Any]],
    *,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    schema_refs: dict[str, str],
    contract_ids: dict[str, str],
) -> None:
    kind = entry["kind"]
    if kind == "oci-config":
        require(decode_payload(entry) == b"{}", "OCI config is not exact two-byte empty JSON")
    elif kind == "oci-layer":
        validate_layer(entry)
    elif kind == "oci-blob-stream":
        validate_blob_stream(entry, fixtures)
    elif kind == "oci-manifest":
        manifest = decode_json(entry)
        require(set(manifest) == {"schemaVersion", "mediaType", "artifactType", "config", "layers"}, "OCI manifest is not closed")
        require(manifest["schemaVersion"] == 2 and manifest["mediaType"] == "application/vnd.oci.image.manifest.v1+json", "OCI manifest header drift")
        config = fixtures["oci-empty-config"]
        layer = fixtures["oci-deterministic-layer"]
        require(manifest["config"] == {"mediaType": config["mediaType"], "digest": config["digest"], "size": config["size"]}, "OCI config descriptor mismatch")
        require(manifest["layers"] == [{"mediaType": layer["mediaType"], "digest": layer["digest"], "size": layer["size"], "annotations": {"ai.bytedesk.agent-delivery.layer-role": "portable-definition"}}], "OCI layer descriptor mismatch")
    elif kind == "spdx-document":
        validate_spdx(decode_json(entry), fixtures)
    elif kind == "slsa-provenance":
        value = decode_json(entry)
        validate_slsa(value, fixtures, materials)
        validate_schema_instance(
            value,
            schema_refs["bytedesk.port.intoto-provenance/1"],
            registry=registry,
            schemas=schemas,
            label=entry["fixtureId"],
        )
    elif kind in {"vulnerability-report", "malware-report", "secret-scan-report", "scan-completeness-report", "license-report"}:
        value = decode_json(entry)
        validate_report(kind, value, fixtures, materials)
        report_refs = {
            "vulnerability-report": "bytedesk.port.vulnerability-report/1",
            "malware-report": "bytedesk.port.malware-report/1",
            "secret-scan-report": "bytedesk.port.secret-scan-report/1",
            "scan-completeness-report": "bytedesk.port.scan-completeness-report/1",
            "license-report": "bytedesk.port.license-report/1",
        }
        validate_schema_instance(
            value,
            schema_refs[report_refs[kind]],
            registry=registry,
            schemas=schemas,
            label=entry["fixtureId"],
        )
    elif kind in {"supply-chain-request", "supply-chain-result"}:
        value = decode_json(entry)
        expected = expected_supply_wrappers(fixtures, materials)
        fixture_id = entry["fixtureId"]
        require(fixture_id in expected, f"unknown supply-chain wrapper: {fixture_id}")
        direction = "request" if kind == "supply-chain-request" else "result"
        operation_id = next(
            operation
            for operation in SUPPLY_OPERATIONS
            if fixture_id == f"supply-{operation}-{direction}"
            or fixture_id.startswith(f"supply-{operation}-{direction}-")
        )
        contract_id = (
            f"bytedesk.port.supply-chain-evidence.{operation_id}.{direction}/1"
        )
        validate_schema_instance(
            value,
            contract_ids[contract_id],
            registry=registry,
            schemas=schemas,
            label=fixture_id,
        )
        require(value == expected[fixture_id], f"{fixture_id} is not the exact operation envelope")
    elif kind.startswith("capability-"):
        value = decode_json(entry)
        capability_schemas = {
            "capability-authorization-proof": "https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0",
            "capability-dispatch-request": contract_ids["bytedesk.port.capability-verifier.dispatch-capability-check.request/1"],
            "capability-dispatch-receipt": schema_refs["bytedesk.port.capability-dispatch-receipt/1"],
            "capability-dispatch-result": contract_ids["bytedesk.port.capability-verifier.dispatch-capability-check.result/1"],
            "capability-evidence": "https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0",
            "capability-verification-request": contract_ids["bytedesk.port.capability-verifier.verify-capability-result.request/1"],
            "capability-accepted-result": contract_ids["bytedesk.port.capability-verifier.verify-capability-result.result/1"],
        }
        if kind == "capability-not-applicable-certification":
            expected_fields = {
                "certificationId",
                "outcome",
                "consumerId",
                "subjectId",
                "targetId",
                "candidateDigest",
                "checkProfileDigest",
                "planDigest",
                "desiredRevisionDigest",
                "releaseDigest",
                "deploymentDigest",
                "authorityDigest",
                "policyDigest",
                "grantSetDigest",
                "workloadIdentityDigest",
                "signerIdentity",
                "signerPolicy",
                "signatureEvidenceDigest",
                "issuedAt",
                "expiresAt",
            }
            require(set(value) == expected_fields, "not-applicable certification is not closed")
            require(value["outcome"] == "not_applicable", "certification outcome drift")
            return
        require(kind in capability_schemas, f"unknown capability fixture kind: {kind}")
        validate_schema_instance(
            value,
            capability_schemas[kind],
            registry=registry,
            schemas=schemas,
            label=entry["fixtureId"],
        )
    else:
        raise ProtocolError(f"unknown protocol fixture kind: {kind}")


def validate_capability_chain(
    catalog: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    materials: dict[str, dict[str, Any]],
    *,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    schema_refs: dict[str, str],
    contract_ids: dict[str, str],
    require_complete_catalog: bool = True,
) -> int:
    check_count = 0

    def check(condition: bool, message: str) -> None:
        nonlocal check_count
        require(condition, message)
        check_count += 1

    chains = {entry["chainId"]: entry for entry in catalog["chains"]}
    require(len(chains) == len(catalog["chains"]), "duplicate capability chain ID")
    expected_outcomes = {
        "capability-required-permitted": "permitted",
        "capability-required-denied": "denied",
        "capability-certified-not-applicable": "permitted",
    }
    if require_complete_catalog:
        require(set(chains) == set(expected_outcomes), "capability golden chain set drift")
    else:
        require(set(chains) <= set(expected_outcomes), "unknown capability mutation chain")

    material_digests = {entry["digest"] for entry in materials.values()}
    common_roles = {
        "dispatch-authorization-proof",
        "dispatch-request",
        "dispatch-receipt",
        "dispatch-result",
        "capability-evidence",
        "verification-request",
        "accepted-result",
    }
    proof_context_fields = (
        "consumerId",
        "subjectId",
        "targetId",
        "candidateDigest",
        "planDigest",
        "releaseDigest",
        "deploymentDigest",
        "policyDigest",
        "grantSetDigest",
        "workloadIdentityDigest",
        "nonce",
        "issuedAt",
        "expiresAt",
    )
    expectation_fields = (
        "consumerId",
        "subjectId",
        "targetId",
        "candidateDigest",
        "planDigest",
        "desiredRevisionDigest",
        "releaseDigest",
        "deploymentDigest",
        "authorityDigest",
        "policyDigest",
        "grantSetDigest",
        "workloadIdentityDigest",
    )

    for chain_id, chain in chains.items():
        roles = {item["role"]: item["fixtureId"] for item in chain["documents"]}
        require(len(roles) == len(chain["documents"]), f"{chain_id} roles are not unique")
        required_mode = chain_id != "capability-certified-not-applicable"
        expected_roles = common_roles | (
            {
                "required-capability-decision-proof",
                "denied-sentinel-decision-proof",
            }
            if required_mode
            else {"not-applicable-certification"}
        )
        require(set(roles) == expected_roles, f"{chain_id} roles incomplete")
        for role, fixture_id in roles.items():
            require(fixture_id in fixtures, f"{chain_id} fixture is unknown: {role}")
            validate_fixture(
                fixtures[fixture_id],
                fixtures,
                materials,
                registry=registry,
                schemas=schemas,
                schema_refs=schema_refs,
                contract_ids=contract_ids,
            )

        dispatch_proof = decode_json(fixtures[roles["dispatch-authorization-proof"]])
        request = decode_json(fixtures[roles["dispatch-request"]])
        receipt = decode_json(fixtures[roles["dispatch-receipt"]])
        dispatch_result = decode_json(fixtures[roles["dispatch-result"]])
        evidence = decode_json(fixtures[roles["capability-evidence"]])
        verification_request = decode_json(fixtures[roles["verification-request"]])
        accepted = decode_json(fixtures[roles["accepted-result"]])
        expectations = verification_request["expectations"]

        check(request["authorizationDecisionProof"] == dispatch_proof, f"{chain_id} request proof bytes differ")
        check(request["authorizationDecisionDigest"] == digest_json(dispatch_proof), f"{chain_id} dispatch proof digest mismatch")
        for request_name, proof_name in {
            "consumerId": "consumerId",
            "targetId": "targetId",
            "candidateDigest": "candidateDigest",
            "dispatchNonce": "nonce",
            "issuedAt": "issuedAt",
            "expiresAt": "expiresAt",
        }.items():
            check(request[request_name] == dispatch_proof[proof_name], f"{chain_id} dispatch {request_name} binding mismatch")
        check(request["checkProfileDigest"] == dispatch_proof["capability"]["digest"], f"{chain_id} profile proof binding mismatch")
        check(dispatch_proof["decision"]["class"] == "permitted", f"{chain_id} dispatch is not authorized")
        check(receipt["requestDigest"] == digest_json(request), f"{chain_id} request digest mismatch")
        for request_name, receipt_name in {
            "consumerId": "consumerId",
            "targetId": "targetId",
            "candidateDigest": "candidateDigest",
            "checkProfileDigest": "checkProfileDigest",
            "dispatchNonce": "nonce",
            "authorizationDecisionDigest": "authorizationDecisionDigest",
            "issuedAt": "issuedAt",
            "expiresAt": "expiresAt",
        }.items():
            check(request[request_name] == receipt[receipt_name], f"{chain_id} receipt {receipt_name} mismatch")
        receipt_digest = digest_json(receipt)
        check(
            dispatch_result == {"dispatchReceipt": receipt, "dispatchReceiptDigest": receipt_digest},
            f"{chain_id} dispatch result does not bind exact receipt",
        )
        check(verification_request["dispatchReceipt"] == receipt, f"{chain_id} verification receipt differs")
        check(verification_request["dispatchReceiptDigest"] == receipt_digest, f"{chain_id} verification receipt digest differs")
        check(verification_request["capabilityEvidence"] == evidence, f"{chain_id} verification evidence differs")

        dispatch = evidence["capabilityDispatch"]
        check(dispatch["requestDigest"] == receipt["requestDigest"], f"{chain_id} evidence request mismatch")
        check(dispatch["receiptDigest"] == receipt_digest, f"{chain_id} evidence receipt mismatch")
        check(dispatch["checkProfileDigest"] == receipt["checkProfileDigest"], f"{chain_id} evidence profile mismatch")
        check(dispatch["authorizationDecisionDigest"] == receipt["authorizationDecisionDigest"], f"{chain_id} evidence authorization mismatch")
        for field in ("consumerId", "targetId", "candidateDigest", "nonce"):
            check(evidence[field] == receipt[field], f"{chain_id} evidence {field} mismatch")
        check(evidence["issuedAt"] == receipt["issuedAt"], f"{chain_id} evidence issuance mismatch")
        check(evidence["expiresAt"] == receipt["expiresAt"], f"{chain_id} evidence expiry mismatch")
        check(evidence["actor"] == "consumer_capability_verifier", f"{chain_id} host evidence was accepted")

        for field in expectation_fields:
            check(expectations[field] == evidence[field], f"{chain_id} trusted {field} mismatch")
        check(expectations["checkProfileDigest"] == receipt["checkProfileDigest"], f"{chain_id} trusted profile mismatch")
        check(expectations["capabilityVerifierIdentity"] == evidence["actorIdentity"], f"{chain_id} verifier identity mismatch")
        check(expectations["capabilityVerifierVersion"] == evidence["actorVersion"], f"{chain_id} verifier version mismatch")
        check(expectations["capabilityEvidenceSignerPolicy"] == evidence["signerPolicy"], f"{chain_id} evidence signer policy mismatch")
        authorization_schema_id = "https://schemas.bytedesk.ai/agent-delivery/v1/authorization-decision-proof/1.0.0"
        canary_schema_id = "https://schemas.bytedesk.ai/agent-delivery/v1/canary-evidence/1.0.0"
        check(expectations["authorizationProofSchemaDigest"] == digest_json(schemas[authorization_schema_id]), f"{chain_id} authorization schema pin mismatch")
        check(expectations["canaryEvidenceSchemaDigest"] == digest_json(schemas[canary_schema_id]), f"{chain_id} canary schema pin mismatch")

        authenticated = verification_request["authenticatedEvidence"]
        expected_auth_records: dict[str, tuple[str, dict[str, Any], str, dict[str, Any]]]
        expiry_objects: list[tuple[str, dict[str, Any]]] = [
            ("dispatch receipt", receipt),
            ("capability evidence", evidence),
            ("dispatch authorization", dispatch_proof),
        ]
        decision_proofs = verification_request["verificationProofs"]

        if required_mode:
            required_proof = decode_json(fixtures[roles["required-capability-decision-proof"]])
            denied_proof = decode_json(fixtures[roles["denied-sentinel-decision-proof"]])
            check(
                decision_proofs == {
                    "mode": "required",
                    "dispatchAuthorization": dispatch_proof,
                    "permittedCapability": required_proof,
                    "deniedSentinel": denied_proof,
                },
                f"{chain_id} proof set differs from exact chain",
            )
            check(expectations["mode"] == "required", f"{chain_id} expectation mode drift")
            for label, proof in (
                ("dispatch authorization", dispatch_proof),
                ("required capability", required_proof),
                ("denied sentinel", denied_proof),
            ):
                for field in proof_context_fields:
                    check(proof[field] == evidence[field], f"{chain_id} {label} {field} mismatch")
                check(proof["signerIdentity"] == expectations["authorizationSignerIdentity"], f"{chain_id} {label} signer mismatch")
                check(proof["signerPolicy"] == expectations["authorizationSignerPolicy"], f"{chain_id} {label} policy mismatch")
            check(required_proof["capability"] == expectations["permittedCapability"], f"{chain_id} required capability mismatch")
            check(denied_proof["capability"] == expectations["deniedSentinelCapability"], f"{chain_id} sentinel capability mismatch")
            results = evidence["results"]
            check(results["mode"] == "required", f"{chain_id} evidence mode drift")
            for label, result, proof in (
                ("required capability", results["permitted_capability"], required_proof),
                ("denied sentinel", results["denied_sentinel"], denied_proof),
            ):
                check(result["outcome"] == "decision", f"{chain_id} {label} is not a decision")
                check(result["decisionClass"] == proof["decision"]["class"], f"{chain_id} {label} class mismatch")
                check(result["decisionCode"] == proof["decision"]["code"], f"{chain_id} {label} code mismatch")
                check(result["authorizationDecisionProofDigest"] == digest_json(proof), f"{chain_id} {label} digest mismatch")
            derived_outcome = (
                "permitted"
                if results["workload_login"]["actual"] == "passed"
                and required_proof["decision"]["class"] == "permitted"
                and denied_proof["decision"]["class"] == "policy_denied"
                else "denied"
            )
            expected_auth_records = {
                "dispatchAuthorization": ("dispatch-authorization-proof", dispatch_proof, dispatch_proof["signerIdentity"], dispatch_proof["signerPolicy"]),
                "requiredCapability": ("required-capability-decision-proof", required_proof, required_proof["signerIdentity"], required_proof["signerPolicy"]),
                "deniedSentinel": ("denied-sentinel-decision-proof", denied_proof, denied_proof["signerIdentity"], denied_proof["signerPolicy"]),
                "capabilityEvidence": ("capability-evidence", evidence, evidence["actorIdentity"], evidence["signerPolicy"]),
            }
            check(authenticated["mode"] == "required", f"{chain_id} authenticated-set mode drift")
            expiry_objects.extend([("required capability", required_proof), ("denied sentinel", denied_proof)])
        else:
            certification = decode_json(fixtures[roles["not-applicable-certification"]])
            check(
                decision_proofs == {
                    "mode": "certified_not_applicable",
                    "dispatchAuthorization": dispatch_proof,
                    "certification": certification,
                },
                f"{chain_id} certification proof set differs from exact chain",
            )
            check(expectations["mode"] == "certified_not_applicable", f"{chain_id} expectation mode drift")
            for field in expectation_fields:
                check(certification[field] == expectations[field], f"{chain_id} certification {field} mismatch")
            check(certification["checkProfileDigest"] == expectations["checkProfileDigest"], f"{chain_id} certification profile mismatch")
            check(certification["signerIdentity"] == expectations["notApplicableCertificationSignerIdentity"], f"{chain_id} certification signer mismatch")
            check(certification["signerPolicy"] == expectations["notApplicableCertificationPolicy"], f"{chain_id} certification policy mismatch")
            result = evidence["results"]["certified_not_applicable"]
            check(evidence["results"]["mode"] == "certified_not_applicable", f"{chain_id} evidence mode drift")
            check(result["certificationDigest"] == digest_json(certification), f"{chain_id} certification digest mismatch")
            check(result["certificationPolicy"] == certification["signerPolicy"], f"{chain_id} certification policy binding mismatch")
            derived_outcome = "permitted" if result["actual"] == "not_applicable" else "denied"
            expected_auth_records = {
                "dispatchAuthorization": ("dispatch-authorization-proof", dispatch_proof, dispatch_proof["signerIdentity"], dispatch_proof["signerPolicy"]),
                "notApplicableCertification": ("not-applicable-certification", certification, certification["signerIdentity"], certification["signerPolicy"]),
                "capabilityEvidence": ("capability-evidence", evidence, evidence["actorIdentity"], evidence["signerPolicy"]),
            }
            check(authenticated["mode"] == "certified_not_applicable", f"{chain_id} authenticated-set mode drift")
            expiry_objects.append(("not-applicable certification", certification))

        check(set(authenticated) == {"mode", *expected_auth_records}, f"{chain_id} authenticated record set drift")
        record_ids: set[str] = set()
        for record_name, (subject_kind, subject, signer_identity, signer_policy) in expected_auth_records.items():
            record = authenticated[record_name]
            check(
                set(record) == {
                    "recordId",
                    "subjectKind",
                    "subjectDigest",
                    "verificationMethod",
                    "verifiedSignerIdentity",
                    "verifiedSignerPolicy",
                    "verificationEvidenceDigest",
                    "verifiedAt",
                    "validUntil",
                },
                f"{chain_id} {record_name} authentication record is not closed",
            )
            check(record["recordId"] not in record_ids, f"{chain_id} duplicate authentication record ID")
            record_ids.add(record["recordId"])
            check(record["subjectKind"] == subject_kind, f"{chain_id} {record_name} subject kind mismatch")
            check(record["subjectDigest"] == digest_json(subject), f"{chain_id} {record_name} subject digest mismatch")
            check(record["verificationMethod"] in {"detached-signature", "mutual-tls-channel", "workload-identity-channel"}, f"{chain_id} {record_name} method drift")
            check(record["verifiedSignerIdentity"] == signer_identity, f"{chain_id} {record_name} verified signer mismatch")
            check(record["verifiedSignerPolicy"] == signer_policy, f"{chain_id} {record_name} verified policy mismatch")
            check(record["verificationEvidenceDigest"] in material_digests, f"{chain_id} {record_name} verification evidence is absent")
            check(record["validUntil"] == subject["expiresAt"], f"{chain_id} {record_name} validity mismatch")

        received_at = parse_time(verification_request["receivedAt"], f"{chain_id}.receivedAt")
        issued_times = [parse_time(value["issuedAt"], f"{chain_id}.{label}.issuedAt") for label, value in expiry_objects]
        expiry_values = [value["expiresAt"] for _, value in expiry_objects]
        expiry_times = [parse_time(value, f"{chain_id}.expiry") for value in expiry_values]
        check(received_at >= max(issued_times), f"{chain_id} received before issuance")
        check(received_at < min(expiry_times), f"{chain_id} received at or after expiry")
        for record_name in expected_auth_records:
            record = authenticated[record_name]
            verified_at = parse_time(record["verifiedAt"], f"{chain_id}.{record_name}.verifiedAt")
            check(max(issued_times) <= verified_at <= received_at, f"{chain_id} {record_name} verification time is invalid")
            check(verified_at < parse_time(record["validUntil"], f"{chain_id}.{record_name}.validUntil"), f"{chain_id} {record_name} was verified after validity")

        check(accepted["acceptedEvidenceDigest"] == digest_json(evidence), f"{chain_id} accepted digest mismatch")
        check(accepted["policyOutcome"] == derived_outcome, f"{chain_id} aggregate outcome contradicts authenticated inputs")
        check(accepted["policyOutcome"] == expected_outcomes[chain_id], f"{chain_id} golden outcome drift")
        freshest_expiry = min(expiry_values, key=lambda value: parse_time(value, f"{chain_id}.freshness"))
        check(accepted["freshUntil"] == freshest_expiry, f"{chain_id} freshness is not earliest expiry")

    return check_count


def validate_mutations(
    catalog: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    materials: dict[str, dict[str, Any]],
    *,
    registry: Registry,
    schemas: dict[str, dict[str, Any]],
    schema_refs: dict[str, str],
    contract_ids: dict[str, str],
) -> int:
    mutations = {entry["mutationId"]: entry for entry in catalog["mutations"]}
    require(len(mutations) == len(catalog["mutations"]), "duplicate protocol mutation ID")
    require(set(mutations) == EXPECTED_MUTATIONS, f"protocol mutation set drift: {sorted(set(mutations) ^ EXPECTED_MUTATIONS)}")
    chains = {entry["chainId"]: entry for entry in catalog["chains"]}
    rejected = 0
    for mutation_id, mutation in mutations.items():
        require(mutation["baseFixtureId"] in fixtures, f"protocol mutation base is unknown: {mutation_id}")
        mutated = mutation["mutatedFixture"]
        require(mutated["fixtureId"] == mutation["baseFixtureId"], f"protocol mutation changes fixture identity: {mutation_id}")
        decode_payload(mutated)
        try:
            if mutation.get("chainRole"):
                chain_id = mutation.get("chainId")
                require(chain_id in chains, f"protocol mutation chain is unknown: {mutation_id}")
                chain = chains[chain_id]
                base_roles = {item["role"]: item["fixtureId"] for item in chain["documents"]}
                require(mutation["chainRole"] in base_roles, f"protocol mutation role is absent: {mutation_id}")
                require(
                    base_roles[mutation["chainRole"]] == mutation["baseFixtureId"],
                    f"protocol mutation base does not match chain role: {mutation_id}",
                )
                temporary = dict(fixtures)
                temporary[mutation["baseFixtureId"]] = mutated
                mutated_chain = dict(catalog)
                mutated_chain["chains"] = [{
                    "chainId": chain["chainId"],
                    "documents": chain["documents"],
                }]
                validate_capability_chain(
                    mutated_chain,
                    temporary,
                    materials,
                    registry=registry,
                    schemas=schemas,
                    schema_refs=schema_refs,
                    contract_ids=contract_ids,
                    require_complete_catalog=False,
                )
            else:
                temporary = dict(fixtures)
                temporary[mutated["fixtureId"]] = mutated
                validate_fixture(
                    mutated,
                    temporary,
                    materials,
                    registry=registry,
                    schemas=schemas,
                    schema_refs=schema_refs,
                    contract_ids=contract_ids,
                )
        except ProtocolError:
            rejected += 1
            continue
        raise ProtocolError(f"protocol mutation was accepted: {mutation_id}")
    return rejected


def operation_errors(operation: dict[str, Any]) -> set[str]:
    return {
        error["code"] if isinstance(error, dict) else error
        for error in operation["errors"]
    }


def validate_conformance_links(
    catalog: dict[str, Any],
    conformance: dict[str, Any],
    registry: dict[str, Any],
) -> int:
    fixtures = {entry["fixtureId"] for entry in catalog["fixtures"]}
    mutations = {entry["mutationId"]: entry for entry in catalog["mutations"]}
    ports = {port["portId"]: port for port in registry["ports"]}
    mutation_links: dict[str, list[dict[str, Any]]] = {mutation_id: [] for mutation_id in mutations}
    referenced_fixtures: set[str] = set()
    for case in conformance["cases"]:
        link = case["fixture"]
        if "protocolMutationIds" not in link:
            continue
        unknown_fixtures = set(link["protocolFixtureIds"]) - fixtures
        unknown_mutations = set(link["protocolMutationIds"]) - set(mutations)
        require(not unknown_fixtures, f"conformance case references unknown protocol fixtures: {case['caseId']}/{sorted(unknown_fixtures)}")
        require(not unknown_mutations, f"conformance case references unknown protocol mutations: {case['caseId']}/{sorted(unknown_mutations)}")
        referenced_fixtures.update(link["protocolFixtureIds"])
        rejecting = link["rejectingOperation"]
        port_id, operation_id = rejecting.split("#", 1)
        require(port_id in ports, f"conformance rejecting port is unknown: {rejecting}")
        operations = {operation["operationId"]: operation for operation in ports[port_id]["operations"]}
        require(operation_id in operations, f"conformance rejecting operation is unknown: {rejecting}")
        expected_code = case["expected"]["problemCode"]
        require(expected_code in operation_errors(operations[operation_id]), f"conformance problem is undeclared by rejecting operation: {case['caseId']}/{expected_code}")
        covered = {
            f"{coverage['portId']}#{coverage['operationId']}"
            for coverage in case["covers"]
        }
        require(rejecting in covered, f"conformance rejecting operation is not covered: {case['caseId']}")
        for mutation_id in link["protocolMutationIds"]:
            mutation = mutations[mutation_id]
            require(mutation["rejectingOperation"] == rejecting, f"protocol rejecting operation drift: {mutation_id}")
            require(mutation["expectedProblemCode"] == expected_code, f"protocol expected problem drift: {mutation_id}")
            require(mutation["baseFixtureId"] in link["protocolFixtureIds"], f"protocol base fixture is not named by conformance case: {mutation_id}")
            mutation_links[mutation_id].append(case)
    unlinked = sorted(mutation_id for mutation_id, links in mutation_links.items() if len(links) != 1)
    require(not unlinked, f"protocol mutations must have exactly one conformance case: {unlinked}")
    require(referenced_fixtures == fixtures, f"protocol fixtures are not completely referenced by conformance cases: {sorted(fixtures ^ referenced_fixtures)}")
    return len(mutation_links)


def validate_registry_profile_alignment(registry: dict[str, Any], profiles: dict[str, Any]) -> None:
    ports = {port["portId"]: port for port in registry["ports"]}
    supply = {op["operationId"]: op for op in ports["bytedesk.port.supply-chain-evidence/1"]["operations"]}
    require(set(supply) == {"generate-sbom", "generate-provenance", "scan-vulnerabilities", "scan-malware", "scan-secrets", "attest-scan-completeness", "evaluate-licenses"}, "supply-chain operation set drift")
    requirements = next(profile["requirements"] for profile in profiles["profiles"] if profile["profileId"] == "bytedesk.signing-evidence-profile/1")
    expected_fields = {
        "scan-vulnerabilities": requirements["vulnerabilityScan"]["requiredInputs"],
        "scan-malware": requirements["malwareScan"]["requiredInputs"],
        "scan-secrets": requirements["secretScan"]["requiredInputs"],
        "evaluate-licenses": requirements["licenseEvaluation"]["requiredInputs"],
    }
    for operation_id, fields in expected_fields.items():
        require([field["name"] for field in supply[operation_id]["requestFields"]] == fields, f"{operation_id} pinned inputs differ from profile")
    capability = ports["bytedesk.port.capability-verifier/1"]
    require("contracts/schemas/v1/verification-result.schema.json" not in capability["contractPaths"], "stale capability verification-result contract path")
    capability_requirements = next(
        profile["requirements"]
        for profile in profiles["profiles"]
        if profile["profileId"] == "bytedesk.capability-verification/1"
    )
    verify_operation = next(
        operation
        for operation in capability["operations"]
        if operation["operationId"] == "verify-capability-result"
    )
    request_fields = [field["name"] for field in verify_operation["requestFields"]]
    require(
        capability_requirements["chainBindings"]["verificationRequestFields"]
        == request_fields,
        "capability verification request fields differ from profile",
    )
    expected_required_rows = {
        (workload, required, sentinel): (
            "permitted"
            if (workload, required, sentinel)
            == ("passed", "permitted", "policy_denied")
            else "denied"
        )
        for workload in ("passed", "failed")
        for required in ("permitted", "policy_denied")
        for sentinel in ("permitted", "policy_denied")
    }
    actual_required_rows: dict[tuple[str, str, str], str] = {}
    actual_not_applicable_rows: dict[str, str] = {}
    for row in capability_requirements["outcomeDerivation"]:
        if row["mode"] == "required":
            key = (
                row["workloadLogin"],
                row["requiredCapability"],
                row["deniedSentinel"],
            )
            require(key not in actual_required_rows, "duplicate required capability truth-table row")
            actual_required_rows[key] = row["outcome"]
        else:
            key = row["certifiedResult"]
            require(key not in actual_not_applicable_rows, "duplicate not-applicable truth-table row")
            actual_not_applicable_rows[key] = row["outcome"]
    require(actual_required_rows == expected_required_rows, "required capability outcome truth table is not closed")
    require(
        actual_not_applicable_rows
        == {"not_applicable": "permitted", "failed": "denied"},
        "not-applicable outcome truth table is not closed",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        catalog = load_json(CATALOG_PATH, maximum_bytes=MAX_CATALOG_BYTES)
        schema = load_json(SCHEMA_PATH)
        errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(catalog), key=lambda error: list(error.absolute_path))
        require(not errors, f"protocol fixture catalog schema failure: {errors[0].message if errors else ''}")
        fixtures = {entry["fixtureId"]: entry for entry in catalog["fixtures"]}
        require(len(fixtures) == len(catalog["fixtures"]), "duplicate protocol fixture ID")
        require(set(fixtures) == EXPECTED_FIXTURES, f"protocol fixture set drift: {sorted(set(fixtures) ^ EXPECTED_FIXTURES)}")
        materials = {entry["materialId"]: entry for entry in catalog["materials"]}
        require(len(materials) == len(catalog["materials"]), "duplicate protocol material ID")
        require(set(materials) == EXPECTED_MATERIALS, f"protocol material set drift: {sorted(set(materials) ^ EXPECTED_MATERIALS)}")
        for material in materials.values():
            decode_json(material)
        require(len({entry["uri"] for entry in materials.values()}) == len(materials), "protocol material URIs are not distinct")
        require(len({entry["digest"] for entry in materials.values()}) == len(materials), "protocol material digests are not distinct")
        type_catalog = load_json(TYPE_CATALOG_PATH, maximum_bytes=MAX_CATALOG_BYTES)
        schema_registry, schemas, schema_refs, contract_ids = build_schema_registry(type_catalog)
        for fixture in fixtures.values():
            validate_fixture(
                fixture,
                fixtures,
                materials,
                registry=schema_registry,
                schemas=schemas,
                schema_refs=schema_refs,
                contract_ids=contract_ids,
            )
        chain_checks = validate_capability_chain(
            catalog,
            fixtures,
            materials,
            registry=schema_registry,
            schemas=schemas,
            schema_refs=schema_refs,
            contract_ids=contract_ids,
        )
        mutation_count = validate_mutations(
            catalog,
            fixtures,
            materials,
            registry=schema_registry,
            schemas=schemas,
            schema_refs=schema_refs,
            contract_ids=contract_ids,
        )
        registry = load_json(REGISTRY_PATH)
        validate_registry_profile_alignment(registry, load_json(PROFILE_PATH))
        conformance_links = validate_conformance_links(
            catalog,
            load_json(CONFORMANCE_PATH),
            registry,
        )
        evidence = {
            "profile": "bytedesk.protocol-fixture-validation-evidence/1",
            "result": "pass",
            "counts": {"goldenFixtures": len(fixtures) + len(materials), "protocolDocuments": len(fixtures), "materials": len(materials), "mutations": mutation_count, "capabilityBindingChecks": chain_checks, "conformanceLinks": conformance_links},
            "catalogDigest": digest_json(catalog),
            "checks": ["digest-indexed-canonical-payloads", "oci-manifest-config-layer-archive", "spdx-2.3-document", "slsa-v1.2-provenance", "pinned-supply-chain-reports", "chunked-oci-wire-profile", "capability-exact-binding-chain", "executable-protocol-mutations"],
        }
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ProtocolError, KeyError, TypeError, ValueError, UnicodeError, OSError) as error:
        print(f"protocol fixture validation failed: {error}", file=sys.stderr)
        return 1
    print(f"protocol fixture validation passed: {len(fixtures)} fixtures, {mutation_count} mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
