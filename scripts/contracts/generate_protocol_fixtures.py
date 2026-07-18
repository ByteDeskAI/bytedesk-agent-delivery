#!/usr/bin/env python3
"""Generate deterministic executable OCI, evidence, and capability fixtures."""

from __future__ import annotations

import argparse
import base64
import binascii
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any, Callable
import zlib

import rfc8785


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "contracts" / "ports" / "v1" / "protocol-fixtures.json"
SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/protocol-fixtures/1.0.0"
CANARY_SCHEMA = ROOT / "contracts" / "schemas" / "v1" / "canary-evidence.schema.json"
AUTHORIZATION_SCHEMA = ROOT / "contracts" / "schemas" / "v1" / "authorization-decision-proof.schema.json"
AUTHORIZATION_FIXTURE = ROOT / "contracts" / "fixtures" / "schema" / "positive" / "authorization-decision-proof__policy-denied.json"
CAPABILITY_FIXTURE = ROOT / "contracts" / "fixtures" / "schema" / "positive" / "canary-evidence__capability.json"

OCI_CONFIG_MEDIA_TYPE = "application/vnd.oci.empty.v1+json"
OCI_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
OCI_ARTIFACT_TYPE = "application/vnd.bytedesk.agent.source.v1+json"
SAMPLE_TIME = "2026-07-17T12:01:00Z"
RECEIVED_TIME = "2026-07-17T12:02:00Z"
EXPIRES_TIME = "2026-07-17T12:05:00Z"
ZERO = "sha256:" + "0" * 64
ONE = "sha256:" + "1" * 64
SPDX_LICENSE_LIST_VERSION = "3.28.0"
SPDX_LICENSE_LIST_DIGEST = "sha256:f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee"
SPDX_EXCEPTION_LIST_DIGEST = "sha256:bd145bb558f44432fcd6f0d7e956ed0124dff72af7641a7cfcb1b557dc390a5b"
SPDX_EXPRESSION_PARSER_PROFILE = "spdx-license-expression-2.3-strict/1"


class GenerationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GenerationError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot load {path.relative_to(ROOT)}: {error}") from error
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} root must be an object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def fixture_entry(
    fixture_id: str,
    kind: str,
    media_type: str,
    payload: bytes,
) -> dict[str, Any]:
    return {
        "fixtureId": fixture_id,
        "kind": kind,
        "mediaType": media_type,
        "digest": digest_bytes(payload),
        "size": len(payload),
        "contentBase64url": encoded(payload),
    }


def json_fixture(
    fixture_id: str,
    kind: str,
    media_type: str,
    value: dict[str, Any],
) -> dict[str, Any]:
    return fixture_entry(fixture_id, kind, media_type, canonical_bytes(value))


def decode_fixture(entry: dict[str, Any]) -> bytes:
    value = entry["contentBase64url"]
    return base64.urlsafe_b64decode(value + "=" * ((-len(value)) % 4))


def decode_json_fixture(entry: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(decode_fixture(entry))
    require(isinstance(value, dict), "JSON fixture root must be an object")
    return value


def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def output_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def octal_field(value: int, width: int) -> bytes:
    rendered = f"{value:0{width - 1}o}".encode("ascii") + b"\0"
    require(len(rendered) == width, "ustar numeric field overflow")
    return rendered


def ustar_header(name: str, size: int, mode: int) -> bytes:
    name_bytes = name.encode("utf-8")
    require(0 < len(name_bytes) <= 100, f"fixture path is not ustar-safe: {name}")
    header = bytearray(512)
    header[0 : len(name_bytes)] = name_bytes
    header[100:108] = octal_field(mode, 8)
    header[108:116] = octal_field(0, 8)
    header[116:124] = octal_field(0, 8)
    header[124:136] = octal_field(size, 12)
    header[136:148] = octal_field(0, 12)
    header[148:156] = b" " * 8
    header[156:157] = b"0"
    header[257:263] = b"ustar\0"
    header[263:265] = b"00"
    checksum = sum(header)
    header[148:156] = f"{checksum:06o}".encode("ascii") + b"\0 "
    return bytes(header)


def build_tar(members: list[tuple[str, bytes, int]]) -> bytes:
    output = bytearray()
    for name, payload, mode in sorted(members, key=lambda item: item[0]):
        output.extend(ustar_header(name, len(payload), mode))
        output.extend(payload)
        output.extend(b"\0" * ((-len(payload)) % 512))
    output.extend(b"\0" * 1024)
    return bytes(output)


def deterministic_gzip(payload: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(payload) + compressor.flush()
    header = b"\x1f\x8b\x08\x00" + struct.pack("<I", 0) + b"\x02\xff"
    trailer = struct.pack("<II", binascii.crc32(payload) & 0xFFFFFFFF, len(payload) & 0xFFFFFFFF)
    return header + compressed + trailer


def material_entry(
    material_id: str,
    kind: str,
    value: dict[str, Any],
) -> dict[str, Any]:
    payload = canonical_bytes(value)
    return {
        "materialId": material_id,
        "kind": kind,
        "uri": f"https://materials.bytedesk.example.invalid/{material_id}/1",
        "mediaType": "application/json",
        "digest": digest_bytes(payload),
        "size": len(payload),
        "contentBase64url": encoded(payload),
    }


def build_materials() -> list[dict[str, Any]]:
    specifications: list[tuple[str, str, dict[str, Any]]] = [
        ("source-commit-and-tree", "source-commit-and-tree", {"commit": "a" * 40, "treeDigest": ZERO}),
        ("builder-distribution", "builder", {"distribution": "agent-delivery-builder", "imageDigest": ONE}),
        ("workflow", "workflow", {"workflow": "build-agent", "workflowDigest": ZERO}),
        ("toolchain", "toolchain", {"componentLockDigest": ONE, "runtime": "python-3.13"}),
        ("component-lock", "component-lock", {"contract": "bytedesk.component-lock/1", "digest": ZERO}),
        ("renderer-release", "renderer-release", {"rendererId": "native", "releaseDigest": ONE}),
        ("public-skill", "public-skill", {"skillId": "public-skill", "packageDigest": ZERO}),
        ("private-skill", "private-skill", {"skillId": "private-skill", "packageDigest": ONE}),
        ("policy-binding", "policy-binding", {"policyId": "consumer-policy", "policyDigest": ZERO}),
        ("customization", "customization", {"customizationId": "consumer-functional-delta", "digest": ONE}),
        ("test-evidence", "test-evidence", {"suite": "protocol-golden", "evidenceDigest": ZERO}),
    ]
    return [material_entry(material_id, kind, value) for material_id, kind, value in specifications]


def build_spdx(layer_members: list[tuple[str, bytes, int]]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    sha1_values: list[str] = []
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package-Agent",
        }
    ]
    for index, (name, payload, _) in enumerate(sorted(layer_members), start=1):
        sha1 = hashlib.sha1(payload).hexdigest()
        sha256 = hashlib.sha256(payload).hexdigest()
        sha1_values.append(sha1)
        spdx_id = f"SPDXRef-File-{index}"
        files.append(
            {
                "SPDXID": spdx_id,
                "fileName": f"./{name}",
                "checksums": [
                    {"algorithm": "SHA1", "checksumValue": sha1},
                    {"algorithm": "SHA256", "checksumValue": sha256},
                ],
                "licenseConcluded": "Apache-2.0",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package-Agent",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": spdx_id,
            }
        )
    verification_code = hashlib.sha1("".join(sorted(sha1_values)).encode("ascii")).hexdigest()
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "name": "bytedesk-agent-delivery-golden",
        "documentNamespace": "https://spdx.bytedesk.example.invalid/documents/agent-delivery-golden-1",
        "creationInfo": {
            "created": SAMPLE_TIME,
            "creators": ["Tool: bytedesk-agent-delivery-protocol-fixture-generator/1"],
        },
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-Agent",
                "name": "golden-agent",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "packageVerificationCode": {
                    "packageVerificationCodeValue": verification_code
                },
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "copyrightText": "NOASSERTION",
            }
        ],
        "files": files,
        "relationships": relationships,
    }


def build_slsa(
    subject_digest: str,
    materials: list[dict[str, Any]],
) -> dict[str, Any]:
    dependencies = [
        {
            "uri": material["uri"],
            "digest": {"sha256": material["digest"].removeprefix("sha256:")},
            "annotations": {
                "ai.bytedesk.material-kind": material["kind"],
                "ai.bytedesk.material-id": material["materialId"],
            },
        }
        for material in materials
    ]
    builder = next(item for item in materials if item["materialId"] == "builder-distribution")
    external_parameters_digest = digest_json(
        {
            "profile": "bytedesk.agent-delivery-build/1",
            "subjectDigest": subject_digest,
        }
    )
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": "registry.example.invalid/agent-delivery/golden-agent",
                "digest": {"sha256": subject_digest.removeprefix("sha256:")},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://build.bytedesk.example.invalid/types/agent-delivery/v1",
                "externalParameters": {"digest": external_parameters_digest},
                "resolvedDependencies": dependencies,
            },
            "runDetails": {
                "builder": {"id": builder["uri"]},
                "metadata": {
                    "invocationId": "protocol-fixture-build-1",
                    "startedOn": "2026-07-17T12:00:00Z",
                    "finishedOn": SAMPLE_TIME,
                },
            },
        },
    }


def build_blob_stream(payload: bytes) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    offset = 0
    chunk_size = 64
    for index in range(0, len(payload), chunk_size):
        part = payload[index : index + chunk_size]
        chunks.append(
            {
                "index": len(chunks),
                "offset": offset,
                "size": len(part),
                "digest": digest_bytes(part),
                "contentBase64url": encoded(part),
            }
        )
        offset += len(part)
    require(len(chunks) >= 2, "golden OCI blob must exercise multiple chunks")
    return {
        "mediaType": OCI_LAYER_MEDIA_TYPE,
        "digest": digest_bytes(payload),
        "size": len(payload),
        "chunks": chunks,
    }


def mutate_json_fixture(
    entry: dict[str, Any],
    mutate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    value = decode_json_fixture(entry)
    mutate(value)
    return json_fixture(entry["fixtureId"], entry["kind"], entry["mediaType"], value)


def mutation(
    mutation_id: str,
    base_fixture_id: str,
    rejecting_operation: str,
    expected_problem_code: str,
    mutated_fixture: dict[str, Any],
    *,
    chain_role: str | None = None,
    chain_id: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "mutationId": mutation_id,
        "baseFixtureId": base_fixture_id,
        "rejectingOperation": rejecting_operation,
        "expectedProblemCode": expected_problem_code,
        "mutatedFixture": mutated_fixture,
    }
    if chain_role is not None:
        value["chainRole"] = chain_role
        require(chain_id is not None, "chain mutation requires an exact chain ID")
        value["chainId"] = chain_id
    else:
        require(chain_id is None, "non-chain mutation cannot name a chain ID")
    return value


def build_catalog() -> dict[str, Any]:
    agent_bytes = canonical_bytes(
        {"contract": "bytedesk.agent-source/1", "name": "golden-agent", "version": 1}
    )
    skill_bytes = b"#!/bin/sh\nprintf '%s\\n' 'golden skill'\n"
    layer_members = [
        ("agent.json", agent_bytes, 0o644),
        ("skills/run.sh", skill_bytes, 0o755),
    ]
    tar_payload = build_tar(layer_members)
    layer_payload = deterministic_gzip(tar_payload)

    config = fixture_entry("oci-empty-config", "oci-config", OCI_CONFIG_MEDIA_TYPE, b"{}")
    layer = fixture_entry("oci-deterministic-layer", "oci-layer", OCI_LAYER_MEDIA_TYPE, layer_payload)
    blob_stream = json_fixture(
        "oci-chunked-layer-blob",
        "oci-blob-stream",
        "application/vnd.bytedesk.oci-blob-stream.v1+json",
        build_blob_stream(layer_payload),
    )
    manifest_value = {
        "schemaVersion": 2,
        "mediaType": OCI_MANIFEST_MEDIA_TYPE,
        "artifactType": OCI_ARTIFACT_TYPE,
        "config": {
            "mediaType": config["mediaType"],
            "digest": config["digest"],
            "size": config["size"],
        },
        "layers": [
            {
                "mediaType": layer["mediaType"],
                "digest": layer["digest"],
                "size": layer["size"],
                "annotations": {
                    "ai.bytedesk.agent-delivery.layer-role": "portable-definition"
                },
            }
        ],
    }
    manifest = json_fixture(
        "oci-artifact-manifest", "oci-manifest", OCI_MANIFEST_MEDIA_TYPE, manifest_value
    )

    materials = build_materials()
    material_map = {item["materialId"]: item for item in materials}
    spdx = json_fixture(
        "spdx-2.3-document",
        "spdx-document",
        "application/spdx+json",
        build_spdx(layer_members),
    )
    slsa = json_fixture(
        "slsa-v1.2-provenance",
        "slsa-provenance",
        "application/vnd.in-toto+json",
        build_slsa(manifest["digest"], materials),
    )

    vulnerability = json_fixture(
        "vulnerability-report",
        "vulnerability-report",
        "application/vnd.bytedesk.scan.v1+json",
        {
            "artifactDigest": manifest["digest"],
            "sbomDigest": spdx["digest"],
            "scannerImageDigest": material_map["toolchain"]["digest"],
            "scannerRulesDigest": material_map["workflow"]["digest"],
            "advisorySnapshotDigest": material_map["component-lock"]["digest"],
            "severityPolicyDigest": material_map["policy-binding"]["digest"],
            "scanTime": SAMPLE_TIME,
            "outcome": "pass",
            "coverageComplete": True,
            "findings": [],
        },
    )
    malware = json_fixture(
        "malware-report",
        "malware-report",
        "application/vnd.bytedesk.malware-scan.v1+json",
        {
            "artifactDigest": manifest["digest"],
            "scannerImageDigest": material_map["toolchain"]["digest"],
            "signatureDatabaseDigest": material_map["component-lock"]["digest"],
            "sandboxProfileDigest": material_map["policy-binding"]["digest"],
            "scanTime": SAMPLE_TIME,
            "outcome": "pass",
            "coverageComplete": True,
            "findings": [],
        },
    )
    secret = json_fixture(
        "secret-scan-report",
        "secret-scan-report",
        "application/vnd.bytedesk.secret-scan.v1+json",
        {
            "artifactDigest": manifest["digest"],
            "scannerImageDigest": material_map["toolchain"]["digest"],
            "rulesetDigest": material_map["workflow"]["digest"],
            "allowlistDigest": material_map["policy-binding"]["digest"],
            "scanTime": SAMPLE_TIME,
            "outcome": "pass",
            "coverageComplete": True,
            "findings": [],
        },
    )
    completeness = json_fixture(
        "scan-completeness-report",
        "scan-completeness-report",
        "application/vnd.bytedesk.scan-completeness.v1+json",
        {
            "artifactDigest": manifest["digest"],
            "inventoryDigest": digest_bytes(tar_payload),
            "vulnerabilityReportDigest": vulnerability["digest"],
            "malwareReportDigest": malware["digest"],
            "secretScanReportDigest": secret["digest"],
            "evaluatorImageDigest": material_map["toolchain"]["digest"],
            "evaluatedAt": SAMPLE_TIME,
            "outcome": "pass",
            "complete": True,
        },
    )
    license_report = json_fixture(
        "license-report",
        "license-report",
        "application/vnd.bytedesk.license.v1+json",
        {
            "sbomDigest": spdx["digest"],
            "licensePolicyId": "consumer-license-policy-1",
            "licensePolicyDigest": material_map["policy-binding"]["digest"],
            "evaluatorImageDigest": material_map["toolchain"]["digest"],
            "expressionParserProfile": SPDX_EXPRESSION_PARSER_PROFILE,
            "licenseListVersion": SPDX_LICENSE_LIST_VERSION,
            "licenseListDigest": SPDX_LICENSE_LIST_DIGEST,
            "exceptionListDigest": SPDX_EXCEPTION_LIST_DIGEST,
            "evaluationTime": SAMPLE_TIME,
            "outcome": "pass",
            "expressions": [
                {
                    "packageId": "SPDXRef-Package-Agent",
                    "expression": "Apache-2.0",
                    "disposition": "allowed",
                }
            ],
        },
    )

    spdx_value = decode_json_fixture(spdx)
    slsa_value = decode_json_fixture(slsa)
    vulnerability_value = decode_json_fixture(vulnerability)
    malware_value = decode_json_fixture(malware)
    secret_value = decode_json_fixture(secret)
    completeness_value = decode_json_fixture(completeness)
    license_value = decode_json_fixture(license_report)
    spdx_unknown_value = deepcopy(spdx_value)
    spdx_unknown_value["name"] = "bytedesk-agent-delivery-golden-unknown-license"
    spdx_unknown_value["documentNamespace"] = (
        "https://spdx.bytedesk.example.invalid/documents/agent-delivery-golden-unknown-license-1"
    )
    for package in spdx_unknown_value["packages"]:
        package["licenseConcluded"] = "NOASSERTION"
        package["licenseDeclared"] = "NOASSERTION"
    spdx_unknown = json_fixture(
        "spdx-2.3-document-unknown-license",
        "spdx-document",
        "application/spdx+json",
        spdx_unknown_value,
    )
    license_deny_value = deepcopy(license_value)
    license_deny_value["outcome"] = "deny"
    license_deny_value["expressions"][0]["disposition"] = "denied"
    license_deny = json_fixture(
        "license-report-deny",
        "license-report",
        "application/vnd.bytedesk.license.v1+json",
        license_deny_value,
    )
    license_indeterminate_value = deepcopy(license_value)
    license_indeterminate_value["sbomDigest"] = spdx_unknown["digest"]
    license_indeterminate_value["outcome"] = "indeterminate"
    license_indeterminate_value["expressions"][0]["expression"] = "NOASSERTION"
    license_indeterminate_value["expressions"][0]["disposition"] = "unknown"
    license_indeterminate = json_fixture(
        "license-report-indeterminate",
        "license-report",
        "application/vnd.bytedesk.license.v1+json",
        license_indeterminate_value,
    )
    slsa_definition = slsa_value["predicate"]["buildDefinition"]
    slsa_metadata = slsa_value["predicate"]["runDetails"]["metadata"]

    supply_wrappers: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
        "generate-sbom": (
            {
                "artifactDigest": manifest["digest"],
                "generatorImageDigest": material_map["toolchain"]["digest"],
                "componentLockDigest": material_map["component-lock"]["digest"],
            },
            {
                "sbomDigest": spdx["digest"],
                "sbomDescriptor": {
                    "specification": "SPDX-2.3",
                    "interoperabilityProfile": "agent-delivery-v1-spdx-2.3-json",
                    "documentNamespace": spdx_value["documentNamespace"],
                    "documentDigest": spdx["digest"],
                    "artifactDigest": manifest["digest"],
                    "mediaType": "application/spdx+json",
                    "packageCount": len(spdx_value["packages"]),
                    "fileCount": len(spdx_value["files"]),
                    "relationshipCount": len(spdx_value["relationships"]),
                    "generatedAt": spdx_value["creationInfo"]["created"],
                },
            },
        ),
        "generate-provenance": (
            {
                "subjectDigest": manifest["digest"],
                "buildType": slsa_definition["buildType"],
                "builderId": slsa_value["predicate"]["runDetails"]["builder"]["id"],
                "invocationId": slsa_metadata["invocationId"],
                "externalParametersDigest": slsa_definition["externalParameters"]["digest"],
                "resolvedDependencies": slsa_definition["resolvedDependencies"],
                "startedOn": slsa_metadata["startedOn"],
                "finishedOn": slsa_metadata["finishedOn"],
            },
            {"provenanceDigest": slsa["digest"], "provenance": slsa_value},
        ),
        "scan-vulnerabilities": (
            {key: vulnerability_value[key] for key in (
                "artifactDigest", "sbomDigest", "scannerImageDigest", "scannerRulesDigest",
                "advisorySnapshotDigest", "severityPolicyDigest", "scanTime"
            )},
            {"reportDigest": vulnerability["digest"], "report": vulnerability_value},
        ),
        "scan-malware": (
            {key: malware_value[key] for key in (
                "artifactDigest", "scannerImageDigest", "signatureDatabaseDigest",
                "sandboxProfileDigest", "scanTime"
            )},
            {"reportDigest": malware["digest"], "report": malware_value},
        ),
        "scan-secrets": (
            {key: secret_value[key] for key in (
                "artifactDigest", "scannerImageDigest", "rulesetDigest", "allowlistDigest", "scanTime"
            )},
            {"reportDigest": secret["digest"], "report": secret_value},
        ),
        "attest-scan-completeness": (
            {
                "artifactDigest": completeness_value["artifactDigest"],
                "inventoryDigest": completeness_value["inventoryDigest"],
                "vulnerabilityReportDigest": completeness_value["vulnerabilityReportDigest"],
                "malwareReportDigest": completeness_value["malwareReportDigest"],
                "secretScanReportDigest": completeness_value["secretScanReportDigest"],
                "evaluatorImageDigest": completeness_value["evaluatorImageDigest"],
                "evaluationTime": completeness_value["evaluatedAt"],
            },
            {"reportDigest": completeness["digest"], "report": completeness_value},
        ),
        "evaluate-licenses": (
            {
                "sbomDigest": license_value["sbomDigest"],
                "licensePolicyId": license_value["licensePolicyId"],
                "licensePolicyDigest": license_value["licensePolicyDigest"],
                "evaluatorImageDigest": license_value["evaluatorImageDigest"],
                "expressionParserProfile": license_value["expressionParserProfile"],
                "licenseListVersion": license_value["licenseListVersion"],
                "licenseListDigest": license_value["licenseListDigest"],
                "exceptionListDigest": license_value["exceptionListDigest"],
                "evaluationTime": license_value["evaluationTime"],
            },
            {"evaluationDigest": license_report["digest"], "report": license_value},
        ),
    }
    supply_wrapper_fixtures: dict[str, dict[str, Any]] = {}
    for operation_id, (request_value, result_value) in supply_wrappers.items():
        request_id = f"supply-{operation_id}-request"
        result_id = f"supply-{operation_id}-result"
        supply_wrapper_fixtures[request_id] = json_fixture(
            request_id, "supply-chain-request", "application/json", request_value
        )
        supply_wrapper_fixtures[result_id] = json_fixture(
            result_id, "supply-chain-result", "application/json", result_value
        )
    for variant, report_entry, report_value in (
        ("deny", license_deny, license_deny_value),
        ("indeterminate", license_indeterminate, license_indeterminate_value),
    ):
        request_value = deepcopy(supply_wrappers["evaluate-licenses"][0])
        request_value["sbomDigest"] = report_value["sbomDigest"]
        request_id = f"supply-evaluate-licenses-request-{variant}"
        result_id = f"supply-evaluate-licenses-result-{variant}"
        supply_wrapper_fixtures[request_id] = json_fixture(
            request_id, "supply-chain-request", "application/json", request_value
        )
        supply_wrapper_fixtures[result_id] = json_fixture(
            result_id,
            "supply-chain-result",
            "application/json",
            {"evaluationDigest": report_entry["digest"], "report": report_value},
        )

    check_profile_digest = material_map["policy-binding"]["digest"]

    authorization_schema_digest = digest_json(load_json(AUTHORIZATION_SCHEMA))
    base_proof = load_json(AUTHORIZATION_FIXTURE)

    def build_decision_proof(
        proof_id: str,
        capability_id: str,
        capability_digest: str,
        decision_class: str,
        decision_code: str,
    ) -> dict[str, Any]:
        proof = deepcopy(base_proof)
        proof["schema"]["digest"] = authorization_schema_digest
        proof["proofId"] = proof_id
        proof["candidateDigest"] = manifest["digest"]
        proof["capability"] = {
            "id": capability_id,
            "digest": capability_digest,
        }
        proof["decision"] = {"class": decision_class, "code": decision_code}
        proof["issuedAt"] = SAMPLE_TIME
        proof["expiresAt"] = EXPIRES_TIME
        proof["transport"]["responseDigest"] = digest_json(
            {
                "proofId": proof_id,
                "candidateDigest": manifest["digest"],
                "decision": proof["decision"],
            }
        )
        return proof

    dispatch_proof = build_decision_proof(
        "capability-dispatch-authorization-1",
        "capability.dispatch",
        check_profile_digest,
        "permitted",
        "capability_dispatch_permitted",
    )
    permitted_proof = build_decision_proof(
        "capability-permitted-decision-1",
        "capability.required",
        material_map["public-skill"]["digest"],
        "permitted",
        "capability_check_permitted",
    )
    denied_proof = build_decision_proof(
        "capability-denied-sentinel-decision-1",
        "capability.denied-sentinel",
        material_map["private-skill"]["digest"],
        "policy_denied",
        "sentinel_denied",
    )
    dispatch_proof_entry = json_fixture(
        "capability-dispatch-authorization-proof",
        "capability-authorization-proof",
        "application/json",
        dispatch_proof,
    )
    permitted_proof_entry = json_fixture(
        "capability-permitted-decision-proof",
        "capability-authorization-proof",
        "application/json",
        permitted_proof,
    )
    denied_proof_entry = json_fixture(
        "capability-denied-sentinel-decision-proof",
        "capability-authorization-proof",
        "application/json",
        denied_proof,
    )
    request_value = {
        "consumerId": dispatch_proof["consumerId"],
        "targetId": dispatch_proof["targetId"],
        "candidateDigest": manifest["digest"],
        "checkProfileDigest": check_profile_digest,
        "dispatchNonce": dispatch_proof["nonce"],
        "authorizationDecisionProof": dispatch_proof,
        "authorizationDecisionDigest": dispatch_proof_entry["digest"],
        "issuedAt": SAMPLE_TIME,
        "expiresAt": EXPIRES_TIME,
    }
    request = json_fixture(
        "capability-dispatch-request",
        "capability-dispatch-request",
        "application/json",
        request_value,
    )
    receipt_value = {
        "checkId": "capability-check-1",
        "requestDigest": request["digest"],
        "consumerId": request_value["consumerId"],
        "targetId": request_value["targetId"],
        "candidateDigest": request_value["candidateDigest"],
        "checkProfileDigest": request_value["checkProfileDigest"],
        "nonce": request_value["dispatchNonce"],
        "authorizationDecisionDigest": request_value["authorizationDecisionDigest"],
        "endpoint": "https://consumer.example.invalid/capability/checks/1",
        "coordinatorFencingToken": 1,
        "issuedAt": request_value["issuedAt"],
        "expiresAt": request_value["expiresAt"],
    }
    receipt = json_fixture(
        "capability-dispatch-receipt",
        "capability-dispatch-receipt",
        "application/json",
        receipt_value,
    )
    dispatch_result_value = {
        "dispatchReceipt": receipt_value,
        "dispatchReceiptDigest": receipt["digest"],
    }
    dispatch_result = json_fixture(
        "capability-dispatch-result",
        "capability-dispatch-result",
        "application/json",
        dispatch_result_value,
    )
    evidence_value = load_json(CAPABILITY_FIXTURE)
    evidence_value["schema"]["digest"] = digest_json(load_json(CANARY_SCHEMA))
    evidence_value["evidenceId"] = "capability-evidence-golden-1"
    evidence_value["consumerId"] = request_value["consumerId"]
    evidence_value["targetId"] = request_value["targetId"]
    evidence_value["candidateDigest"] = request_value["candidateDigest"]
    evidence_value["nonce"] = request_value["dispatchNonce"]
    for field in (
        "planDigest",
        "subjectId",
        "releaseDigest",
        "deploymentDigest",
        "policyDigest",
        "grantSetDigest",
        "workloadIdentityDigest",
    ):
        evidence_value[field] = dispatch_proof[field]
    evidence_value["issuedAt"] = request_value["issuedAt"]
    evidence_value["expiresAt"] = request_value["expiresAt"]
    evidence_value["capabilityDispatch"] = {
        "requestDigest": request["digest"],
        "receiptDigest": receipt["digest"],
        "checkProfileDigest": request_value["checkProfileDigest"],
        "authorizationDecisionDigest": request_value["authorizationDecisionDigest"],
    }
    evidence_value["results"] = {
        "mode": "required",
        "workload_login": {
            "actual": "passed",
            "trace": evidence_value["results"]["workload_login"]["trace"],
        },
        "permitted_capability": {
            "outcome": "decision",
            "decisionClass": permitted_proof["decision"]["class"],
            "decisionCode": permitted_proof["decision"]["code"],
            "authorizationDecisionProofDigest": permitted_proof_entry["digest"],
        },
        "denied_sentinel": {
            "outcome": "decision",
            "decisionClass": denied_proof["decision"]["class"],
            "decisionCode": denied_proof["decision"]["code"],
            "authorizationDecisionProofDigest": denied_proof_entry["digest"],
        },
    }
    evidence = json_fixture(
        "capability-evidence",
        "capability-evidence",
        "application/json",
        evidence_value,
    )

    def authenticated_record(
        record_id: str,
        subject_kind: str,
        subject: dict[str, Any],
        signer_identity: str,
        signer_policy: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "recordId": record_id,
            "subjectKind": subject_kind,
            "subjectDigest": digest_json(subject),
            "verificationMethod": "detached-signature",
            "verifiedSignerIdentity": signer_identity,
            "verifiedSignerPolicy": signer_policy,
            "verificationEvidenceDigest": material_map["test-evidence"]["digest"],
            "verifiedAt": RECEIVED_TIME,
            "validUntil": subject["expiresAt"],
        }

    authenticated_evidence = {
        "mode": "required",
        "dispatchAuthorization": authenticated_record(
            "authenticated-dispatch-authorization-1",
            "dispatch-authorization-proof",
            dispatch_proof,
            dispatch_proof["signerIdentity"],
            dispatch_proof["signerPolicy"],
        ),
        "requiredCapability": authenticated_record(
            "authenticated-required-capability-1",
            "required-capability-decision-proof",
            permitted_proof,
            permitted_proof["signerIdentity"],
            permitted_proof["signerPolicy"],
        ),
        "deniedSentinel": authenticated_record(
            "authenticated-denied-sentinel-1",
            "denied-sentinel-decision-proof",
            denied_proof,
            denied_proof["signerIdentity"],
            denied_proof["signerPolicy"],
        ),
        "capabilityEvidence": authenticated_record(
            "authenticated-capability-evidence-1",
            "capability-evidence",
            evidence_value,
            evidence_value["actorIdentity"],
            evidence_value["signerPolicy"],
        ),
    }
    verification_request_value = {
        "dispatchReceipt": receipt_value,
        "dispatchReceiptDigest": receipt["digest"],
        "capabilityEvidence": evidence_value,
        "verificationProofs": {
            "mode": "required",
            "dispatchAuthorization": dispatch_proof,
            "permittedCapability": permitted_proof,
            "deniedSentinel": denied_proof,
        },
        "authenticatedEvidence": authenticated_evidence,
        "expectations": {
            "mode": "required",
            "consumerId": evidence_value["consumerId"],
            "subjectId": evidence_value["subjectId"],
            "targetId": evidence_value["targetId"],
            "candidateDigest": evidence_value["candidateDigest"],
            "checkProfileDigest": check_profile_digest,
            "planDigest": evidence_value["planDigest"],
            "desiredRevisionDigest": evidence_value["desiredRevisionDigest"],
            "releaseDigest": evidence_value["releaseDigest"],
            "deploymentDigest": evidence_value["deploymentDigest"],
            "authorityDigest": evidence_value["authorityDigest"],
            "policyDigest": evidence_value["policyDigest"],
            "grantSetDigest": evidence_value["grantSetDigest"],
            "workloadIdentityDigest": evidence_value["workloadIdentityDigest"],
            "permittedCapability": permitted_proof["capability"],
            "deniedSentinelCapability": denied_proof["capability"],
            "authorizationSignerIdentity": dispatch_proof["signerIdentity"],
            "authorizationSignerPolicy": dispatch_proof["signerPolicy"],
            "capabilityVerifierIdentity": evidence_value["actorIdentity"],
            "capabilityVerifierVersion": evidence_value["actorVersion"],
            "capabilityEvidenceSignerPolicy": evidence_value["signerPolicy"],
            "authorizationProofSchemaDigest": authorization_schema_digest,
            "canaryEvidenceSchemaDigest": digest_json(load_json(CANARY_SCHEMA)),
        },
        "receivedAt": RECEIVED_TIME,
    }
    verification_request = json_fixture(
        "capability-verification-request",
        "capability-verification-request",
        "application/json",
        verification_request_value,
    )
    accepted = json_fixture(
        "capability-accepted-result",
        "capability-accepted-result",
        "application/json",
        {
            "acceptedEvidenceDigest": evidence["digest"],
            "policyOutcome": "permitted",
            "freshUntil": evidence_value["expiresAt"],
        },
    )

    required_denied_proof = deepcopy(permitted_proof)
    required_denied_proof["proofId"] = "capability-required-denied-decision-1"
    required_denied_proof["decision"] = {
        "class": "policy_denied",
        "code": "capability_required_denied",
    }
    required_denied_proof["transport"]["responseDigest"] = digest_json(
        {
            "proofId": required_denied_proof["proofId"],
            "candidateDigest": manifest["digest"],
            "decision": required_denied_proof["decision"],
        }
    )
    required_denied_proof_entry = json_fixture(
        "capability-required-denied-decision-proof",
        "capability-authorization-proof",
        "application/json",
        required_denied_proof,
    )
    denied_evidence_value = deepcopy(evidence_value)
    denied_evidence_value["evidenceId"] = "capability-evidence-denied-golden-1"
    denied_evidence_value["results"]["permitted_capability"] = {
        "outcome": "decision",
        "decisionClass": required_denied_proof["decision"]["class"],
        "decisionCode": required_denied_proof["decision"]["code"],
        "authorizationDecisionProofDigest": required_denied_proof_entry["digest"],
    }
    denied_evidence = json_fixture(
        "capability-evidence-denied",
        "capability-evidence",
        "application/json",
        denied_evidence_value,
    )
    denied_verification_request_value = deepcopy(verification_request_value)
    denied_verification_request_value["capabilityEvidence"] = denied_evidence_value
    denied_verification_request_value["verificationProofs"][
        "permittedCapability"
    ] = required_denied_proof
    denied_verification_request_value["authenticatedEvidence"][
        "requiredCapability"
    ] = authenticated_record(
        "authenticated-required-capability-denied-1",
        "required-capability-decision-proof",
        required_denied_proof,
        required_denied_proof["signerIdentity"],
        required_denied_proof["signerPolicy"],
    )
    denied_verification_request_value["authenticatedEvidence"][
        "capabilityEvidence"
    ] = authenticated_record(
        "authenticated-capability-evidence-denied-1",
        "capability-evidence",
        denied_evidence_value,
        denied_evidence_value["actorIdentity"],
        denied_evidence_value["signerPolicy"],
    )
    denied_verification_request = json_fixture(
        "capability-verification-request-denied",
        "capability-verification-request",
        "application/json",
        denied_verification_request_value,
    )
    denied_accepted = json_fixture(
        "capability-accepted-result-denied",
        "capability-accepted-result",
        "application/json",
        {
            "acceptedEvidenceDigest": denied_evidence["digest"],
            "policyOutcome": "denied",
            "freshUntil": denied_evidence_value["expiresAt"],
        },
    )

    certification_value = {
        "certificationId": "capability-not-applicable-certification-1",
        "outcome": "not_applicable",
        "consumerId": evidence_value["consumerId"],
        "subjectId": evidence_value["subjectId"],
        "targetId": evidence_value["targetId"],
        "candidateDigest": evidence_value["candidateDigest"],
        "checkProfileDigest": check_profile_digest,
        "planDigest": evidence_value["planDigest"],
        "desiredRevisionDigest": evidence_value["desiredRevisionDigest"],
        "releaseDigest": evidence_value["releaseDigest"],
        "deploymentDigest": evidence_value["deploymentDigest"],
        "authorityDigest": evidence_value["authorityDigest"],
        "policyDigest": evidence_value["policyDigest"],
        "grantSetDigest": evidence_value["grantSetDigest"],
        "workloadIdentityDigest": evidence_value["workloadIdentityDigest"],
        "signerIdentity": "spiffe://consumer.example/not-applicable-certifier",
        "signerPolicy": {
            "id": "consumer-not-applicable-certification-v1",
            "digest": material_map["policy-binding"]["digest"],
        },
        "signatureEvidenceDigest": material_map["test-evidence"]["digest"],
        "issuedAt": SAMPLE_TIME,
        "expiresAt": EXPIRES_TIME,
    }
    certification = json_fixture(
        "capability-not-applicable-certification",
        "capability-not-applicable-certification",
        "application/json",
        certification_value,
    )
    not_applicable_evidence_value = deepcopy(evidence_value)
    not_applicable_evidence_value["evidenceId"] = (
        "capability-evidence-not-applicable-golden-1"
    )
    not_applicable_evidence_value["results"] = {
        "mode": "certified_not_applicable",
        "certified_not_applicable": {
            "actual": "not_applicable",
            "certificationDigest": certification["digest"],
            "certificationPolicy": certification_value["signerPolicy"],
            "trace": evidence_value["results"]["workload_login"]["trace"],
        },
    }
    not_applicable_evidence = json_fixture(
        "capability-evidence-not-applicable",
        "capability-evidence",
        "application/json",
        not_applicable_evidence_value,
    )
    not_applicable_verification_request_value = deepcopy(
        verification_request_value
    )
    not_applicable_verification_request_value["capabilityEvidence"] = (
        not_applicable_evidence_value
    )
    not_applicable_verification_request_value["verificationProofs"] = {
        "mode": "certified_not_applicable",
        "dispatchAuthorization": dispatch_proof,
        "certification": certification_value,
    }
    not_applicable_verification_request_value["authenticatedEvidence"] = {
        "mode": "certified_not_applicable",
        "dispatchAuthorization": authenticated_evidence["dispatchAuthorization"],
        "notApplicableCertification": authenticated_record(
            "authenticated-not-applicable-certification-1",
            "not-applicable-certification",
            certification_value,
            certification_value["signerIdentity"],
            certification_value["signerPolicy"],
        ),
        "capabilityEvidence": authenticated_record(
            "authenticated-capability-evidence-not-applicable-1",
            "capability-evidence",
            not_applicable_evidence_value,
            not_applicable_evidence_value["actorIdentity"],
            not_applicable_evidence_value["signerPolicy"],
        ),
    }
    not_applicable_expectations = deepcopy(
        not_applicable_verification_request_value["expectations"]
    )
    not_applicable_expectations["mode"] = "certified_not_applicable"
    not_applicable_expectations.pop("permittedCapability")
    not_applicable_expectations.pop("deniedSentinelCapability")
    not_applicable_expectations["notApplicableCertificationSignerIdentity"] = (
        certification_value["signerIdentity"]
    )
    not_applicable_expectations["notApplicableCertificationPolicy"] = (
        certification_value["signerPolicy"]
    )
    not_applicable_verification_request_value["expectations"] = (
        not_applicable_expectations
    )
    not_applicable_verification_request = json_fixture(
        "capability-verification-request-not-applicable",
        "capability-verification-request",
        "application/json",
        not_applicable_verification_request_value,
    )
    not_applicable_accepted = json_fixture(
        "capability-accepted-result-not-applicable",
        "capability-accepted-result",
        "application/json",
        {
            "acceptedEvidenceDigest": not_applicable_evidence["digest"],
            "policyOutcome": "permitted",
            "freshUntil": not_applicable_evidence_value["expiresAt"],
        },
    )

    fixtures = [
        config,
        layer,
        blob_stream,
        manifest,
        spdx,
        slsa,
        vulnerability,
        malware,
        secret,
        completeness,
        license_report,
        spdx_unknown,
        license_deny,
        license_indeterminate,
        *supply_wrapper_fixtures.values(),
        dispatch_proof_entry,
        permitted_proof_entry,
        denied_proof_entry,
        request,
        receipt,
        dispatch_result,
        evidence,
        verification_request,
        accepted,
        required_denied_proof_entry,
        denied_evidence,
        denied_verification_request,
        denied_accepted,
        certification,
        not_applicable_evidence,
        not_applicable_verification_request,
        not_applicable_accepted,
    ]

    oci_verify = "bytedesk.port.oci-registry/1#verify-artifact-graph"
    oci_push = "bytedesk.port.oci-registry/1#push-artifact"
    supply = "bytedesk.port.supply-chain-evidence/1#"
    capability = "bytedesk.port.capability-verifier/1#verify-capability-result"
    permitted_chain_id = "capability-required-permitted"
    denied_chain_id = "capability-required-denied"
    not_applicable_chain_id = "capability-certified-not-applicable"
    mutations: list[dict[str, Any]] = []

    mutations.append(
        mutation(
            "OCI-003-empty-config-digest-mismatch",
            config["fixtureId"],
            oci_verify,
            "digest_mismatch",
            fixture_entry(config["fixtureId"], config["kind"], config["mediaType"], b'{"drift":true}'),
        )
    )
    drifted_layer = bytearray(layer_payload)
    drifted_layer[4] = 1
    mutations.append(
        mutation(
            "OCI-004-layer-profile-drift",
            layer["fixtureId"],
            oci_verify,
            "artifact_unsafe",
            fixture_entry(layer["fixtureId"], layer["kind"], layer["mediaType"], bytes(drifted_layer)),
        )
    )
    mutations.append(
        mutation(
            "OCI-006-manifest-config-binding-mismatch",
            manifest["fixtureId"],
            oci_verify,
            "digest_mismatch",
            mutate_json_fixture(manifest, lambda value: value["config"].__setitem__("digest", ZERO)),
        )
    )

    def mutate_stream(mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        return mutate_json_fixture(blob_stream, mutator)

    mutations.extend(
        [
            mutation(
                "OCI-007-chunk-offset-gap", blob_stream["fixtureId"], oci_push,
                "invalid_request", mutate_stream(lambda value: value["chunks"][1].__setitem__("offset", value["chunks"][1]["offset"] + 1)),
            ),
            mutation(
                "OCI-008-chunk-offset-overlap", blob_stream["fixtureId"], oci_push,
                "invalid_request", mutate_stream(lambda value: value["chunks"][1].__setitem__("offset", value["chunks"][1]["offset"] - 1)),
            ),
            mutation(
                "OCI-009-chunk-order-mismatch", blob_stream["fixtureId"], oci_push,
                "invalid_request", mutate_stream(lambda value: value["chunks"].__setitem__(slice(0, 2), [value["chunks"][1], value["chunks"][0]])),
            ),
            mutation(
                "OCI-010-chunk-digest-mismatch", blob_stream["fixtureId"], oci_push,
                "digest_mismatch", mutate_stream(lambda value: value["chunks"][0].__setitem__("digest", ZERO)),
            ),
            mutation(
                "OCI-011-aggregate-digest-mismatch", blob_stream["fixtureId"], oci_push,
                "digest_mismatch", mutate_stream(lambda value: value.__setitem__("digest", ZERO)),
            ),
        ]
    )

    supply_result_problem = {
        "generate-sbom": "artifact_unsafe",
        "generate-provenance": "evidence_invalid",
        "scan-vulnerabilities": "artifact_unsafe",
        "scan-malware": "artifact_unsafe",
        "scan-secrets": "artifact_unsafe",
        "attest-scan-completeness": "evidence_invalid",
        "evaluate-licenses": "evidence_invalid",
    }
    result_digest_field = {
        "generate-sbom": "sbomDigest",
        "generate-provenance": "provenanceDigest",
        "scan-vulnerabilities": "reportDigest",
        "scan-malware": "reportDigest",
        "scan-secrets": "reportDigest",
        "attest-scan-completeness": "reportDigest",
        "evaluate-licenses": "evaluationDigest",
    }
    for index, operation_id in enumerate(supply_wrappers, start=8):
        base = supply_wrapper_fixtures[f"supply-{operation_id}-result"]
        mutations.append(
            mutation(
                f"EVIDENCE-{index:03d}-{operation_id}-result-digest-mismatch",
                base["fixtureId"],
                supply + operation_id,
                supply_result_problem[operation_id],
                mutate_json_fixture(
                    base,
                    lambda value, field=result_digest_field[operation_id]: value.__setitem__(field, ZERO),
                ),
            )
        )
    mutations.extend(
        [
            mutation(
                "EVIDENCE-015-license-deny-false-pass",
                license_deny["fixtureId"],
                supply + "evaluate-licenses",
                "evidence_invalid",
                mutate_json_fixture(
                    license_deny,
                    lambda value: value.__setitem__("outcome", "pass"),
                ),
            ),
            mutation(
                "EVIDENCE-016-license-indeterminate-false-pass",
                license_indeterminate["fixtureId"],
                supply + "evaluate-licenses",
                "evidence_invalid",
                mutate_json_fixture(
                    license_indeterminate,
                    lambda value: value.__setitem__("outcome", "pass"),
                ),
            ),
            mutation(
                "EVIDENCE-017-license-expression-invalid",
                license_report["fixtureId"],
                supply + "evaluate-licenses",
                "evidence_invalid",
                mutate_json_fixture(
                    license_report,
                    lambda value: value["expressions"][0].__setitem__(
                        "expression", "Apache-2.0 AND"
                    ),
                ),
            ),
            mutation(
                "EVIDENCE-018-license-list-unpinned",
                license_report["fixtureId"],
                supply + "evaluate-licenses",
                "external_input_unpinned",
                mutate_json_fixture(
                    license_report,
                    lambda value: value.__setitem__("licenseListDigest", ZERO),
                ),
            ),
            mutation(
                "EVIDENCE-019-exception-list-unpinned",
                license_report["fixtureId"],
                supply + "evaluate-licenses",
                "external_input_unpinned",
                mutate_json_fixture(
                    license_report,
                    lambda value: value.__setitem__("exceptionListDigest", ZERO),
                ),
            ),
            mutation(
                "EVIDENCE-020-license-parser-profile-unpinned",
                license_report["fixtureId"],
                supply + "evaluate-licenses",
                "external_input_unpinned",
                mutate_json_fixture(
                    license_report,
                    lambda value: value.__setitem__(
                        "expressionParserProfile", "spdx-license-expression-current"
                    ),
                ),
            ),
            mutation(
                "EVIDENCE-021-license-list-version-unpinned",
                license_report["fixtureId"],
                supply + "evaluate-licenses",
                "external_input_unpinned",
                mutate_json_fixture(
                    license_report,
                    lambda value: value.__setitem__("licenseListVersion", "current"),
                ),
            ),
        ]
    )

    mutations.extend(
        [
            mutation(
                "EVIDENCE-001-incomplete-required-sbom", spdx["fixtureId"], supply + "generate-sbom",
                "artifact_unsafe", mutate_json_fixture(spdx, lambda value: value["files"].pop()),
            ),
            mutation(
                "EVIDENCE-002-provenance-builder-mismatch", slsa["fixtureId"], supply + "generate-provenance",
                "evidence_invalid", mutate_json_fixture(slsa, lambda value: value["predicate"]["runDetails"]["builder"].__setitem__("id", "https://untrusted.example.invalid/builder")),
            ),
            mutation(
                "EVIDENCE-003-unpinned-scan-snapshot", vulnerability["fixtureId"], supply + "scan-vulnerabilities",
                "external_input_unpinned", mutate_json_fixture(vulnerability, lambda value: value.pop("advisorySnapshotDigest")),
            ),
            mutation(
                "EVIDENCE-004-malware-coverage-incomplete-pass", malware["fixtureId"], supply + "scan-malware",
                "artifact_unsafe", mutate_json_fixture(malware, lambda value: value.__setitem__("coverageComplete", False)),
            ),
            mutation(
                "EVIDENCE-005-secret-coverage-incomplete-pass", secret["fixtureId"], supply + "scan-secrets",
                "artifact_unsafe", mutate_json_fixture(secret, lambda value: value.__setitem__("coverageComplete", False)),
            ),
            mutation(
                "EVIDENCE-006-scan-completeness-false-pass", completeness["fixtureId"], supply + "attest-scan-completeness",
                "evidence_invalid", mutate_json_fixture(completeness, lambda value: value.__setitem__("complete", False)),
            ),
            mutation(
                "EVIDENCE-007-license-input-mismatch", license_report["fixtureId"], supply + "evaluate-licenses",
                "evidence_invalid", mutate_json_fixture(license_report, lambda value: value.__setitem__("sbomDigest", ZERO)),
            ),
        ]
    )

    capability_mutations: list[
        tuple[str, dict[str, Any], str, str, Callable[[dict[str, Any]], None]]
    ] = [
        ("CAP-004-consumer-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("consumerId", "other-consumer")),
        ("CAP-004-target-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("targetId", "other-target")),
        ("CAP-004-candidate-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("candidateDigest", ZERO)),
        ("CAP-004-check-profile-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("checkProfileDigest", ZERO)),
        ("CAP-004-nonce-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("nonce", "nonce_ffffffffffffffff")),
        ("CAP-004-authorization-decision-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("authorizationDecisionDigest", ZERO)),
        ("CAP-004-issued-at-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("issuedAt", "2026-07-17T12:02:00Z")),
        ("CAP-004-expires-at-mismatch", receipt, "dispatch-receipt", "evidence_invalid", lambda value: value.__setitem__("expiresAt", "2026-07-17T12:06:00Z")),
        ("CAP-004-dispatch-proof-candidate-mismatch", dispatch_proof_entry, "dispatch-authorization-proof", "evidence_invalid", lambda value: value.__setitem__("candidateDigest", ZERO)),
        ("CAP-004-dispatch-proof-profile-mismatch", dispatch_proof_entry, "dispatch-authorization-proof", "evidence_invalid", lambda value: value["capability"].__setitem__("digest", ZERO)),
        ("CAP-004-dispatch-proof-window-mismatch", dispatch_proof_entry, "dispatch-authorization-proof", "evidence_invalid", lambda value: value.__setitem__("expiresAt", "2026-07-17T12:06:00Z")),
        ("CAP-004-dispatch-result-digest-mismatch", dispatch_result, "dispatch-result", "evidence_invalid", lambda value: value.__setitem__("dispatchReceiptDigest", ZERO)),
        ("CAP-004-request-digest-mismatch", evidence, "capability-evidence", "evidence_invalid", lambda value: value["capabilityDispatch"].__setitem__("requestDigest", ZERO)),
        ("CAP-004-receipt-digest-mismatch", evidence, "capability-evidence", "evidence_invalid", lambda value: value["capabilityDispatch"].__setitem__("receiptDigest", ZERO)),
        ("CAP-004-evidence-issued-at-mismatch", evidence, "capability-evidence", "evidence_invalid", lambda value: value.__setitem__("issuedAt", "2026-07-17T12:00:00Z")),
        ("CAP-004-evidence-expires-at-mismatch", evidence, "capability-evidence", "evidence_invalid", lambda value: value.__setitem__("expiresAt", "2026-07-17T12:06:00Z")),
        ("CAP-004-evidence-authority-context-mismatch", evidence, "capability-evidence", "evidence_invalid", lambda value: value.__setitem__("subjectId", "other-subject")),
        ("CAP-004-permitted-proof-digest-mismatch", evidence, "capability-evidence", "evidence_invalid", lambda value: value["results"]["permitted_capability"].__setitem__("authorizationDecisionProofDigest", ZERO)),
        ("CAP-004-verification-receipt-object-mismatch", verification_request, "verification-request", "evidence_invalid", lambda value: value["dispatchReceipt"].__setitem__("checkId", "other-check")),
        ("CAP-004-verification-receipt-digest-mismatch", verification_request, "verification-request", "evidence_invalid", lambda value: value.__setitem__("dispatchReceiptDigest", ZERO)),
        ("CAP-004-verification-evidence-object-mismatch", verification_request, "verification-request", "evidence_invalid", lambda value: value["capabilityEvidence"].__setitem__("evidenceId", "other-evidence")),
        ("CAP-004-received-before-issued", verification_request, "verification-request", "evidence_invalid", lambda value: value.__setitem__("receivedAt", "2026-07-17T12:00:00Z")),
        ("CAP-004-received-at-expiry", verification_request, "verification-request", "evidence_invalid", lambda value: value.__setitem__("receivedAt", EXPIRES_TIME)),
        ("CAP-004-evidence-digest-mismatch", accepted, "accepted-result", "evidence_invalid", lambda value: value.__setitem__("acceptedEvidenceDigest", ZERO)),
        ("CAP-004-fresh-until-mismatch", accepted, "accepted-result", "evidence_invalid", lambda value: value.__setitem__("freshUntil", "2026-07-17T12:06:00Z")),
        ("CAP-002-denied-proof-digest-mismatch", evidence, "capability-evidence", "capability_denial_not_proven", lambda value: value["results"]["denied_sentinel"].__setitem__("authorizationDecisionProofDigest", ZERO)),
        ("CAP-002-false-denial-outcome", accepted, "accepted-result", "capability_denial_not_proven", lambda value: value.__setitem__("policyOutcome", "denied")),
    ]
    for mutation_id, base, role, problem_code, mutator in capability_mutations:
        mutations.append(
            mutation(
                mutation_id,
                base["fixtureId"],
                capability,
                problem_code,
                mutate_json_fixture(base, mutator),
                chain_role=role,
                chain_id=permitted_chain_id,
            )
        )

    denied_chain_mutations: list[
        tuple[str, dict[str, Any], str, str, Callable[[dict[str, Any]], None]]
    ] = [
        (
            "CAP-006-false-permit-outcome",
            denied_accepted,
            "accepted-result",
            "capability_denial_not_proven",
            lambda value: value.__setitem__("policyOutcome", "permitted"),
        ),
        (
            "CAP-006-required-denial-proof-digest-mismatch",
            denied_evidence,
            "capability-evidence",
            "evidence_invalid",
            lambda value: value["results"]["permitted_capability"].__setitem__(
                "authorizationDecisionProofDigest", ZERO
            ),
        ),
    ]
    for mutation_id, base, role, problem_code, mutator in denied_chain_mutations:
        mutations.append(
            mutation(
                mutation_id,
                base["fixtureId"],
                capability,
                problem_code,
                mutate_json_fixture(base, mutator),
                chain_role=role,
                chain_id=denied_chain_id,
            )
        )

    not_applicable_mutations: list[
        tuple[str, dict[str, Any], str, str, Callable[[dict[str, Any]], None]]
    ] = [
        (
            "CAP-005-certification-digest-mismatch",
            not_applicable_evidence,
            "capability-evidence",
            "evidence_invalid",
            lambda value: value["results"]["certified_not_applicable"].__setitem__(
                "certificationDigest", ZERO
            ),
        ),
        (
            "CAP-005-certification-policy-mismatch",
            not_applicable_evidence,
            "capability-evidence",
            "trust_verification_failed",
            lambda value: value["results"]["certified_not_applicable"][
                "certificationPolicy"
            ].__setitem__("digest", ZERO),
        ),
        (
            "CAP-005-certification-context-mismatch",
            certification,
            "not-applicable-certification",
            "evidence_invalid",
            lambda value: value.__setitem__("subjectId", "other-subject"),
        ),
        (
            "CAP-005-certification-signer-mismatch",
            certification,
            "not-applicable-certification",
            "trust_verification_failed",
            lambda value: value.__setitem__(
                "signerIdentity", "spiffe://consumer.example/untrusted-certifier"
            ),
        ),
        (
            "CAP-005-certification-expired",
            certification,
            "not-applicable-certification",
            "evidence_invalid",
            lambda value: value.__setitem__("expiresAt", RECEIVED_TIME),
        ),
        (
            "CAP-005-not-applicable-failed",
            not_applicable_evidence,
            "capability-evidence",
            "evidence_invalid",
            lambda value: value["results"]["certified_not_applicable"].__setitem__(
                "actual", "failed"
            ),
        ),
        (
            "CAP-005-false-denial-outcome",
            not_applicable_accepted,
            "accepted-result",
            "evidence_invalid",
            lambda value: value.__setitem__("policyOutcome", "denied"),
        ),
    ]
    for mutation_id, base, role, problem_code, mutator in not_applicable_mutations:
        mutations.append(
            mutation(
                mutation_id,
                base["fixtureId"],
                capability,
                problem_code,
                mutate_json_fixture(base, mutator),
                chain_role=role,
                chain_id=not_applicable_chain_id,
            )
        )

    authenticated_record_mutations: list[
        tuple[str, dict[str, Any], str, str, str, Callable[[dict[str, Any]], None]]
    ] = [
        (
            "CAP-009-evidence-auth-subject-mismatch",
            verification_request,
            permitted_chain_id,
            "verification-request",
            "trust_verification_failed",
            lambda value: value["authenticatedEvidence"]["capabilityEvidence"].__setitem__(
                "subjectDigest", ZERO
            ),
        ),
        (
            "CAP-009-proof-auth-signer-mismatch",
            verification_request,
            permitted_chain_id,
            "verification-request",
            "trust_verification_failed",
            lambda value: value["authenticatedEvidence"]["requiredCapability"].__setitem__(
                "verifiedSignerIdentity", "spiffe://consumer.example/untrusted"
            ),
        ),
        (
            "CAP-009-proof-auth-policy-mismatch",
            verification_request,
            permitted_chain_id,
            "verification-request",
            "trust_verification_failed",
            lambda value: value["authenticatedEvidence"]["deniedSentinel"][
                "verifiedSignerPolicy"
            ].__setitem__("digest", ZERO),
        ),
        (
            "CAP-009-auth-evidence-absent",
            verification_request,
            permitted_chain_id,
            "verification-request",
            "trust_verification_failed",
            lambda value: value["authenticatedEvidence"]["dispatchAuthorization"].__setitem__(
                "verificationEvidenceDigest", ZERO
            ),
        ),
        (
            "CAP-009-auth-verified-after-receipt",
            verification_request,
            permitted_chain_id,
            "verification-request",
            "evidence_invalid",
            lambda value: value["authenticatedEvidence"]["capabilityEvidence"].__setitem__(
                "verifiedAt", "2026-07-17T12:03:00Z"
            ),
        ),
        (
            "CAP-009-certification-auth-subject-mismatch",
            not_applicable_verification_request,
            not_applicable_chain_id,
            "verification-request",
            "trust_verification_failed",
            lambda value: value["authenticatedEvidence"][
                "notApplicableCertification"
            ].__setitem__("subjectDigest", ZERO),
        ),
    ]
    for mutation_id, base, chain_id, role, problem_code, mutator in authenticated_record_mutations:
        mutations.append(
            mutation(
                mutation_id,
                base["fixtureId"],
                capability,
                problem_code,
                mutate_json_fixture(base, mutator),
                chain_role=role,
                chain_id=chain_id,
            )
        )

    return {
        "$schema": SCHEMA_ID,
        "profile": "bytedesk.protocol-fixtures/1",
        "version": 1,
        "fixtures": fixtures,
        "materials": materials,
        "chains": [
            {
                "chainId": permitted_chain_id,
                "documents": [
                    {"role": "dispatch-authorization-proof", "fixtureId": dispatch_proof_entry["fixtureId"]},
                    {"role": "dispatch-request", "fixtureId": request["fixtureId"]},
                    {"role": "dispatch-receipt", "fixtureId": receipt["fixtureId"]},
                    {"role": "dispatch-result", "fixtureId": dispatch_result["fixtureId"]},
                    {"role": "required-capability-decision-proof", "fixtureId": permitted_proof_entry["fixtureId"]},
                    {"role": "denied-sentinel-decision-proof", "fixtureId": denied_proof_entry["fixtureId"]},
                    {"role": "capability-evidence", "fixtureId": evidence["fixtureId"]},
                    {"role": "verification-request", "fixtureId": verification_request["fixtureId"]},
                    {"role": "accepted-result", "fixtureId": accepted["fixtureId"]},
                ],
            },
            {
                "chainId": denied_chain_id,
                "documents": [
                    {"role": "dispatch-authorization-proof", "fixtureId": dispatch_proof_entry["fixtureId"]},
                    {"role": "dispatch-request", "fixtureId": request["fixtureId"]},
                    {"role": "dispatch-receipt", "fixtureId": receipt["fixtureId"]},
                    {"role": "dispatch-result", "fixtureId": dispatch_result["fixtureId"]},
                    {"role": "required-capability-decision-proof", "fixtureId": required_denied_proof_entry["fixtureId"]},
                    {"role": "denied-sentinel-decision-proof", "fixtureId": denied_proof_entry["fixtureId"]},
                    {"role": "capability-evidence", "fixtureId": denied_evidence["fixtureId"]},
                    {"role": "verification-request", "fixtureId": denied_verification_request["fixtureId"]},
                    {"role": "accepted-result", "fixtureId": denied_accepted["fixtureId"]},
                ],
            },
            {
                "chainId": not_applicable_chain_id,
                "documents": [
                    {"role": "dispatch-authorization-proof", "fixtureId": dispatch_proof_entry["fixtureId"]},
                    {"role": "dispatch-request", "fixtureId": request["fixtureId"]},
                    {"role": "dispatch-receipt", "fixtureId": receipt["fixtureId"]},
                    {"role": "dispatch-result", "fixtureId": dispatch_result["fixtureId"]},
                    {"role": "not-applicable-certification", "fixtureId": certification["fixtureId"]},
                    {"role": "capability-evidence", "fixtureId": not_applicable_evidence["fixtureId"]},
                    {"role": "verification-request", "fixtureId": not_applicable_verification_request["fixtureId"]},
                    {"role": "accepted-result", "fixtureId": not_applicable_accepted["fixtureId"]},
                ],
            },
        ],
        "mutations": mutations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        catalog = build_catalog()
        payload = output_bytes(catalog)
        if args.check:
            require(OUTPUT.is_file(), f"generated catalog is missing: {OUTPUT.relative_to(ROOT)}")
            require(OUTPUT.read_bytes() == payload, f"generated catalog drift: {OUTPUT.relative_to(ROOT)}")
        else:
            write_atomic(OUTPUT, payload)
    except (GenerationError, KeyError, TypeError, ValueError) as error:
        print(f"protocol fixture generation failed: {error}", file=sys.stderr)
        return 1
    action = "verified" if args.check else "generated"
    print(
        f"protocol fixtures {action}: {len(catalog['fixtures'])} protocol documents, "
        f"{len(catalog['materials'])} materials, {len(catalog['mutations'])} mutations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
