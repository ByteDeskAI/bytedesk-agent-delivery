#!/usr/bin/env python3
"""Closed, bounded, byte-exact OCI artifact graph construction and verification."""

from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable

import rfc8785


OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
OCI_EMPTY_CONFIG_MEDIA_TYPE = "application/vnd.oci.empty.v1+json"
OCI_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
OCI_WIRE_CHUNK_BYTES = 4_194_304
OCI_WIRE_BLOB_BYTES = 67_108_864
PUBLIC_RENDER_PUBLICATION_PAYLOAD_PROFILE = (
    "bytedesk.public-render-publication-payload/1"
)
EMPTY_CONFIG_BYTES = b"{}"
EMPTY_CONFIG_DIGEST = (
    "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)
LAYER_ROLE_ANNOTATION = "ai.bytedesk.agent-delivery.layer-role"
LAYER_ROLE_ORDER = (
    "portable-definition",
    "public-skills",
    "public-render",
    "private-customization",
    "approved-private-skills",
    "effective-private-render",
    "evidence",
)

# This is the executable counterpart of docs/standards/oci-media-types-v1.md.
# Values are semantic object roles; layer roles are separately registered below.
ARTIFACT_TYPE_ROLES = {
    "application/vnd.bytedesk.agent.contract-bundle.v1+json": "contract_bundle",
    "application/vnd.bytedesk.agent.product-distribution.v1+json": "product_distribution",
    "application/vnd.bytedesk.agent.product-release-manifest.v1+json": "product_release",
    "application/vnd.bytedesk.agent.renderer-allowlist.v1+json": "renderer_allowlist",
    "application/vnd.bytedesk.agent.renderer-release.v1+json": "renderer_release",
    "application/vnd.bytedesk.agent.release-qualification-policy.v1+json": "qualification_policy",
    "application/vnd.bytedesk.agent.renderer-qualification-suite.v1+json": "qualification_suite",
    "application/vnd.bytedesk.agent.renderer-qualification-selection.v1+json": "qualification_selection",
    "application/vnd.bytedesk.agent.renderer-qualification-attempt.v1+json": "qualification_attempt",
    "application/vnd.bytedesk.agent.renderer-qualification-attempt-authentication-evidence.v1+json": "qualification_attempt_authentication",
    "application/vnd.bytedesk.agent.renderer-qualification-evidence-tree.v1+json": "qualification_evidence_tree",
    "application/vnd.bytedesk.agent.renderer-qualification-receipt.v1+json": "qualification_receipt",
    "application/vnd.bytedesk.agent.renderer-qualification-receipt-authentication-evidence.v1+json": "qualification_receipt_authentication",
    "application/vnd.bytedesk.agent.release-qualification-evidence.v1+json": "qualification_evidence",
    "application/vnd.bytedesk.agent.release-qualification-finalization-matrix.v1+json": "qualification_finalization_matrix",
    "application/vnd.bytedesk.agent.release-qualification-predicate.v1+json": "qualification_predicate",
    "application/vnd.bytedesk.agent.release-qualification.v1+json": "qualification_decision",
    "application/vnd.bytedesk.agent.release-status.v1+json": "release_status",
    "application/vnd.bytedesk.agent.release-status-log-inclusion-proof.v1+json": "status_inclusion_proof",
    "application/vnd.bytedesk.agent.release-status-log-consistency-proof.v1+json": "status_consistency_proof",
    "application/vnd.bytedesk.agent.release-status-head-checkpoint.v1+json": "status_head_checkpoint",
    "application/vnd.bytedesk.agent.release-status-head-authentication-evidence.v1+json": "status_head_authentication",
    "application/vnd.bytedesk.agent.release-status-eligibility-evidence.v1+json": "release_status_eligibility",
    "application/vnd.bytedesk.agent.release-status-append-resolution.v1+json": "release_status_append_resolution",
    "application/vnd.bytedesk.agent.catalog.v1+json": "catalog_index",
    "application/vnd.bytedesk.agent.source.v1+json": "agent_source",
    "application/vnd.bytedesk.agent.skill.v1+json": "skill_package",
    "application/vnd.bytedesk.agent.renderer-selection.v1+json": "renderer_selection",
    "application/vnd.bytedesk.agent.renderer-attempt-authority.v1+json": "renderer_attempt_authority",
    "application/vnd.bytedesk.agent.renderer-attempt-authentication-evidence.v1+json": "renderer_attempt_authentication",
    "application/vnd.bytedesk.agent.renderer-execution-receipt.v1+json": "renderer_execution_receipt",
    "application/vnd.bytedesk.agent.renderer-execution-authentication-evidence.v1+json": "renderer_execution_authentication",
    "application/vnd.bytedesk.agent.render-manifest.v1+json": "render_manifest",
    "application/vnd.bytedesk.agent.render.v1+json": "harness_render",
    "application/vnd.bytedesk.agent.publication-evidence.v1+json": "publication_evidence",
    "application/vnd.bytedesk.agent.consumer-authority.v1+json": "consumer_authority",
    "application/vnd.bytedesk.agent.skill-approval.v1+json": "skill_approval",
    "application/vnd.bytedesk.agent.private-compilation-input.v1+json": "private_compilation_input",
    "application/vnd.bytedesk.agent.private-input-authentication.v1+json": "private_input_authentication",
    "application/vnd.bytedesk.agent.consumer-deployment.v1+json": "consumer_deployment",
    "application/vnd.bytedesk.agent.private-compilation-evidence.v1+json": "private_compilation_evidence",
    "application/vnd.bytedesk.agent.runtime-release.v1+json": "runtime_release",
    "application/vnd.bytedesk.agent.activation-authorization.v1+json": "activation_authorization",
    "application/vnd.bytedesk.agent.target-delivery-state.v1+json": "target_delivery_state",
    "application/vnd.bytedesk.agent.canary-plan.v1+json": "canary_plan",
    "application/vnd.bytedesk.agent.canary-evidence.v1+json": "canary_evidence",
    "application/vnd.bytedesk.agent.authorization-decision-proof.v1+json": "authorization_decision_proof",
    "application/vnd.bytedesk.agent.recovery-plan.v1+json": "recovery_plan",
    "application/vnd.bytedesk.agent.compatibility.v1+json": "compatibility_attestation",
    "application/vnd.bytedesk.agent.evaluation.v1+json": "evaluation_attestation",
    "application/vnd.bytedesk.agent.policy.v1+json": "policy_attestation",
    "application/vnd.bytedesk.agent.receipt.v1+json": "deployment_receipt",
    "application/vnd.bytedesk.agent.readiness.v1+json": "readiness_report",
}

_EVIDENCE_ONLY_TYPES = set(ARTIFACT_TYPE_ROLES)
ARTIFACT_LAYER_ROLES: dict[str, frozenset[str]] = {
    media_type: frozenset({"evidence"}) for media_type in _EVIDENCE_ONLY_TYPES
}
ARTIFACT_LAYER_ROLES.update(
    {
        "application/vnd.bytedesk.agent.contract-bundle.v1+json": frozenset(
            {"portable-definition", "evidence"}
        ),
        "application/vnd.bytedesk.agent.source.v1+json": frozenset(
            {"portable-definition", "public-skills", "evidence"}
        ),
        "application/vnd.bytedesk.agent.skill.v1+json": frozenset(
            {"public-skills", "approved-private-skills", "evidence"}
        ),
        "application/vnd.bytedesk.agent.render.v1+json": frozenset(
            {"portable-definition", "public-skills", "public-render", "evidence"}
        ),
        "application/vnd.bytedesk.agent.consumer-deployment.v1+json": frozenset(
            LAYER_ROLE_ORDER
        ),
    }
)


class OciGraphError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True)
class OciGraphLimits:
    maximum_depth: int = 32
    maximum_objects: int = 10_000
    maximum_manifest_bytes: int = 4_194_304
    maximum_blob_bytes: int = 67_108_864
    maximum_total_bytes: int = 1_073_741_824


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise OciGraphError(code, detail)


def raw_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_digest(value: Any) -> str:
    return raw_digest(rfc8785.dumps(value))


def encode_bounded_bytes(payload: bytes) -> str:
    """Encode exact wire bytes as canonical unpadded base64url."""

    _require(isinstance(payload, bytes), "oci_wire_bytes_invalid", "not bytes")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_bounded_bytes(value: str, *, maximum_bytes: int) -> bytes:
    """Decode the closed bounded-bytes wire profile and reject aliases."""

    _require(isinstance(value, str), "oci_wire_bytes_invalid", "not a string")
    _require("=" not in value, "oci_wire_bytes_noncanonical", "padding")
    try:
        payload = base64.b64decode(
            value + "=" * ((-len(value)) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as error:
        raise OciGraphError("oci_wire_bytes_invalid", "base64url") from error
    _require(
        len(payload) <= maximum_bytes,
        "oci_graph_limit_exceeded",
        "wire bytes",
    )
    _require(
        encode_bounded_bytes(payload) == value,
        "oci_wire_bytes_noncanonical",
        "base64url",
    )
    return payload


def build_oci_blob_stream(*, media_type: str, payload: bytes) -> dict[str, Any]:
    """Build one deterministic chunked OCI blob wire value.

    Chunk boundaries are transport-only and are deliberately excluded from the
    publication-payload authority digest.
    """

    _require(
        isinstance(media_type, str) and bool(media_type),
        "oci_blob_stream_invalid",
        "media type",
    )
    _require(
        isinstance(payload, bytes) and 0 < len(payload) <= OCI_WIRE_BLOB_BYTES,
        "oci_blob_stream_invalid",
        "payload size",
    )
    chunks: list[dict[str, Any]] = []
    for index, offset in enumerate(range(0, len(payload), OCI_WIRE_CHUNK_BYTES)):
        content = payload[offset : offset + OCI_WIRE_CHUNK_BYTES]
        chunks.append(
            {
                "index": index,
                "offset": offset,
                "size": len(content),
                "digest": raw_digest(content),
                "contentBase64url": encode_bounded_bytes(content),
            }
        )
    return {
        "digest": raw_digest(payload),
        "mediaType": media_type,
        "size": len(payload),
        "chunks": chunks,
    }


def decode_oci_blob_stream(stream: dict[str, Any]) -> bytes:
    """Validate and reconstruct one exact chunked OCI blob wire value."""

    _require(
        isinstance(stream, dict)
        and set(stream) == {"digest", "mediaType", "size", "chunks"}
        and isinstance(stream["mediaType"], str)
        and isinstance(stream["size"], int)
        and 0 < stream["size"] <= OCI_WIRE_BLOB_BYTES
        and isinstance(stream["chunks"], list)
        and 0 < len(stream["chunks"]) <= 1024,
        "oci_blob_stream_invalid",
        "root",
    )
    parts: list[bytes] = []
    expected_offset = 0
    for expected_index, chunk in enumerate(stream["chunks"]):
        _require(
            isinstance(chunk, dict)
            and set(chunk)
            == {"index", "offset", "size", "digest", "contentBase64url"}
            and chunk["index"] == expected_index
            and chunk["offset"] == expected_offset
            and isinstance(chunk["size"], int)
            and 0 < chunk["size"] <= OCI_WIRE_CHUNK_BYTES,
            "oci_blob_stream_invalid",
            f"chunk:{expected_index}",
        )
        content = decode_bounded_bytes(
            chunk["contentBase64url"], maximum_bytes=OCI_WIRE_CHUNK_BYTES
        )
        _require(
            len(content) == chunk["size"]
            and raw_digest(content) == chunk["digest"],
            "oci_blob_stream_chunk_mismatch",
            str(expected_index),
        )
        parts.append(content)
        expected_offset += len(content)
    payload = b"".join(parts)
    _require(
        len(payload) == stream["size"]
        and raw_digest(payload) == stream["digest"],
        "oci_blob_stream_digest_mismatch",
        stream["digest"],
    )
    return payload


def public_render_publication_payload_preimage(
    *,
    destination_repository: str,
    harness_render_descriptor: dict[str, Any],
    root_descriptor: dict[str, Any],
    manifest_bytes: bytes,
    blobs: list[dict[str, Any]],
    graph_digest: str,
) -> dict[str, Any]:
    """Return the exact finalizer-to-publisher payload authority preimage.

    The raw manifest and reconstructed non-root blob bytes are authoritative.
    Base64 text and chunk boundaries are transport projections and are not.
    """

    _require(
        root_descriptor.get("repository") == destination_repository
        and root_descriptor.get("digest") == raw_digest(manifest_bytes)
        and root_descriptor.get("size") == len(manifest_bytes),
        "public_render_publication_manifest_mismatch",
        str(root_descriptor.get("digest")),
    )
    descriptors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for blob in blobs:
        payload = decode_oci_blob_stream(blob)
        _require(
            blob["digest"] != root_descriptor["digest"]
            and blob["digest"] not in seen,
            "public_render_publication_blob_set_invalid",
            blob["digest"],
        )
        seen.add(blob["digest"])
        _require(
            raw_digest(payload) == blob["digest"],
            "public_render_publication_blob_set_invalid",
            blob["digest"],
        )
        descriptors.append(
            {
                "digest": blob["digest"],
                "mediaType": blob["mediaType"],
                "size": blob["size"],
            }
        )
    descriptors.sort(key=lambda value: value["digest"].encode("utf-8"))
    return {
        "profile": PUBLIC_RENDER_PUBLICATION_PAYLOAD_PROFILE,
        "destinationRepository": destination_repository,
        "harnessRenderDescriptor": deepcopy(harness_render_descriptor),
        "rootDescriptor": deepcopy(root_descriptor),
        "manifestDigest": raw_digest(manifest_bytes),
        "blobs": descriptors,
        "graphDigest": graph_digest,
    }


def public_render_publication_payload_digest(**arguments: Any) -> str:
    return canonical_digest(public_render_publication_payload_preimage(**arguments))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            raise OciGraphError("oci_duplicate_json_member", key)
        value[key] = member
    return value


def _jcs_object(payload: bytes, identity: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_strict_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                OciGraphError("oci_non_finite_number", token)
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OciGraphError("oci_manifest_json_invalid", identity) from error
    _require(isinstance(value, dict), "oci_manifest_json_invalid", identity)
    _require(rfc8785.dumps(value) == payload, "oci_manifest_not_jcs", identity)
    return value


def oci_descriptor(*, media_type: str, payload: bytes) -> dict[str, Any]:
    return {
        "mediaType": media_type,
        "digest": raw_digest(payload),
        "size": len(payload),
    }


def build_oci_manifest(
    *,
    repository: str,
    artifact_type: str,
    layers: list[tuple[str, bytes]],
    subject: dict[str, Any] | None = None,
    annotations: dict[str, str] | None = None,
) -> tuple[dict[str, Any], bytes, dict[tuple[str, str], bytes]]:
    """Build deterministic manifest bytes and a repository-scoped blob map."""

    _require(
        artifact_type in ARTIFACT_TYPE_ROLES,
        "oci_artifact_type_unregistered",
        artifact_type,
    )
    _require(bool(layers), "oci_layers_empty", artifact_type)
    descriptors: list[dict[str, Any]] = []
    blobs: dict[tuple[str, str], bytes] = {
        (repository, EMPTY_CONFIG_DIGEST): EMPTY_CONFIG_BYTES
    }
    for role, payload in layers:
        descriptor = oci_descriptor(media_type=OCI_LAYER_MEDIA_TYPE, payload=payload)
        descriptor["annotations"] = {LAYER_ROLE_ANNOTATION: role}
        descriptors.append(descriptor)
        blobs[(repository, descriptor["digest"])] = payload
    manifest: dict[str, Any] = {
        "schemaVersion": 2,
        "mediaType": OCI_MANIFEST_MEDIA_TYPE,
        "artifactType": artifact_type,
        "config": {
            "mediaType": OCI_EMPTY_CONFIG_MEDIA_TYPE,
            "digest": EMPTY_CONFIG_DIGEST,
            "size": 2,
        },
        "layers": descriptors,
    }
    if subject is not None:
        manifest["subject"] = deepcopy(subject)
    if annotations is not None:
        manifest["annotations"] = deepcopy(annotations)
    manifest_bytes = rfc8785.dumps(manifest)
    root = {
        "repository": repository,
        "digest": raw_digest(manifest_bytes),
        "mediaType": OCI_MANIFEST_MEDIA_TYPE,
        "artifactType": artifact_type,
        "size": len(manifest_bytes),
        "subjectDigest": None if subject is None else subject["digest"],
        "annotationsDigest": (
            None if annotations is None else canonical_digest(annotations)
        ),
    }
    blobs[(repository, root["digest"])] = manifest_bytes
    return root, manifest_bytes, blobs


class OciGraphVerifier:
    """Verify every reached manifest/config/layer/subject by exact bytes."""

    def __init__(
        self,
        *,
        fetch: Callable[[str, str], bytes],
        limits: OciGraphLimits | None = None,
        artifact_type_roles: dict[str, str] | None = None,
        artifact_layer_roles: dict[str, frozenset[str]] | None = None,
    ) -> None:
        self.fetch = fetch
        self.limits = limits or OciGraphLimits()
        self.artifact_type_roles = artifact_type_roles or ARTIFACT_TYPE_ROLES
        self.artifact_layer_roles = artifact_layer_roles or ARTIFACT_LAYER_ROLES

    def verify(
        self,
        root_descriptor: dict[str, Any],
        *,
        expected_repository: str,
        expected_artifact_type: str,
    ) -> dict[str, Any]:
        _require(
            set(root_descriptor)
            == {
                "repository",
                "digest",
                "mediaType",
                "artifactType",
                "size",
                "subjectDigest",
                "annotationsDigest",
            },
            "oci_root_descriptor_invalid",
            str(root_descriptor),
        )
        _require(
            root_descriptor["repository"] == expected_repository,
            "oci_repository_mismatch",
            root_descriptor["repository"],
        )
        _require(
            root_descriptor["mediaType"] == OCI_MANIFEST_MEDIA_TYPE
            and root_descriptor["artifactType"] == expected_artifact_type,
            "oci_root_type_mismatch",
            root_descriptor["digest"],
        )
        objects: dict[tuple[str, str], dict[str, Any]] = {}
        payload_records: dict[tuple[str, str], dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        visiting: set[tuple[str, str]] = set()
        total_bytes = 0
        observed_depth = 0

        def fetch_exact(
            repository: str,
            descriptor: dict[str, Any],
            *,
            manifest: bool,
            semantic_role: str,
        ) -> bytes:
            nonlocal total_bytes
            _require(
                set(descriptor) >= {"digest", "mediaType", "size"},
                "oci_descriptor_invalid",
                str(descriptor),
            )
            key = (repository, descriptor["digest"])
            existing = payload_records.get(key)
            if existing is not None:
                _require(
                    existing["mediaType"] == descriptor["mediaType"]
                    and existing["size"] == descriptor["size"],
                    "oci_descriptor_equivocation",
                    descriptor["digest"],
                )
            try:
                payload = self.fetch(repository, descriptor["digest"])
            except (KeyError, FileNotFoundError) as error:
                raise OciGraphError(
                    "oci_object_missing", descriptor["digest"]
                ) from error
            _require(isinstance(payload, bytes), "oci_object_not_bytes", descriptor["digest"])
            _require(raw_digest(payload) == descriptor["digest"], "oci_object_digest_mismatch", descriptor["digest"])
            _require(len(payload) == descriptor["size"], "oci_object_size_mismatch", descriptor["digest"])
            limit = (
                self.limits.maximum_manifest_bytes
                if manifest
                else self.limits.maximum_blob_bytes
            )
            _require(len(payload) <= limit, "oci_graph_limit_exceeded", descriptor["digest"])
            if existing is None:
                _require(
                    len(payload_records) < self.limits.maximum_objects,
                    "oci_graph_limit_exceeded",
                    "objects",
                )
                total_bytes += len(payload)
                _require(total_bytes <= self.limits.maximum_total_bytes, "oci_graph_limit_exceeded", "total bytes")
                payload_records[key] = {
                    "repository": repository,
                    "digest": descriptor["digest"],
                    "mediaType": descriptor["mediaType"],
                    "size": descriptor["size"],
                    "semanticRole": semantic_role,
                }
            return payload

        def visit_manifest(
            repository: str,
            descriptor: dict[str, Any],
            *,
            depth: int,
            expected_type: str | None,
            root: bool,
        ) -> dict[str, Any]:
            nonlocal observed_depth
            _require(depth <= self.limits.maximum_depth, "oci_graph_limit_exceeded", "depth")
            observed_depth = max(observed_depth, depth)
            key = (repository, descriptor["digest"])
            _require(key not in visiting, "oci_graph_cycle", descriptor["digest"])
            if key in objects:
                return objects[key]["manifest"]
            _require(len(objects) < self.limits.maximum_objects, "oci_graph_limit_exceeded", "objects")
            visiting.add(key)
            payload = fetch_exact(
                repository,
                descriptor,
                manifest=True,
                semantic_role="oci-manifest",
            )
            document = _jcs_object(payload, descriptor["digest"])
            required = {"schemaVersion", "mediaType", "artifactType", "config", "layers"}
            allowed = required | {"subject", "annotations"}
            _require(set(document).issubset(allowed) and required.issubset(document), "oci_manifest_shape_invalid", descriptor["digest"])
            _require(document["schemaVersion"] == 2 and document["mediaType"] == OCI_MANIFEST_MEDIA_TYPE, "oci_manifest_profile_mismatch", descriptor["digest"])
            artifact_type = document["artifactType"]
            _require(artifact_type in self.artifact_type_roles, "oci_artifact_type_unregistered", artifact_type)
            if expected_type is not None:
                _require(artifact_type == expected_type, "oci_artifact_type_mismatch", artifact_type)
            if root:
                _require(
                    root_descriptor["artifactType"] == artifact_type,
                    "oci_root_type_mismatch",
                    descriptor["digest"],
                )

            config = document["config"]
            _require(
                config
                == {
                    "mediaType": OCI_EMPTY_CONFIG_MEDIA_TYPE,
                    "digest": EMPTY_CONFIG_DIGEST,
                    "size": 2,
                },
                "oci_config_descriptor_invalid",
                descriptor["digest"],
            )
            config_payload = fetch_exact(
                repository,
                config,
                manifest=False,
                semantic_role="empty-config",
            )
            _require(config_payload == EMPTY_CONFIG_BYTES, "oci_config_bytes_invalid", descriptor["digest"])
            edges.append({"from": descriptor["digest"], "kind": "config", "index": 0, "to": config["digest"], "role": "empty-config"})

            layers = document["layers"]
            _require(isinstance(layers, list) and len(layers) > 0, "oci_layers_empty", descriptor["digest"])
            allowed_roles = self.artifact_layer_roles.get(artifact_type)
            _require(allowed_roles is not None, "oci_artifact_role_registry_missing", artifact_type)
            seen_roles: set[str] = set()
            seen_digests: set[str] = set()
            role_positions: list[int] = []
            for index, layer in enumerate(layers):
                _require(
                    isinstance(layer, dict)
                    and set(layer) == {"mediaType", "digest", "size", "annotations"}
                    and layer["mediaType"] == OCI_LAYER_MEDIA_TYPE
                    and layer["annotations"].keys() == {LAYER_ROLE_ANNOTATION},
                    "oci_layer_descriptor_invalid",
                    f"{descriptor['digest']}:{index}",
                )
                role = layer["annotations"][LAYER_ROLE_ANNOTATION]
                _require(
                    role in allowed_roles and role in LAYER_ROLE_ORDER,
                    "oci_media_role_unregistered",
                    f"{artifact_type}:{role}",
                )
                _require(role not in seen_roles and layer["digest"] not in seen_digests, "oci_layer_role_duplicate", role)
                seen_roles.add(role)
                seen_digests.add(layer["digest"])
                role_positions.append(LAYER_ROLE_ORDER.index(role))
                fetch_exact(
                    repository,
                    layer,
                    manifest=False,
                    semantic_role=f"layer:{role}",
                )
                edges.append({"from": descriptor["digest"], "kind": "layer", "index": index, "to": layer["digest"], "role": role})
            _require(role_positions == sorted(role_positions), "oci_layer_role_order_invalid", descriptor["digest"])

            subject = document.get("subject")
            if subject is not None:
                _require(
                    isinstance(subject, dict)
                    and set(subject) == {"mediaType", "digest", "size"}
                    and subject["mediaType"] == OCI_MANIFEST_MEDIA_TYPE,
                    "oci_subject_descriptor_invalid",
                    descriptor["digest"],
                )
                # OCI subject descriptors carry no repository.  Resolution in
                # the current repository is mandatory; a repository member is
                # rejected above rather than interpreted as cross-repository.
                edges.append({"from": descriptor["digest"], "kind": "subject", "index": 0, "to": subject["digest"], "role": "same-repository-subject"})
                visit_manifest(repository, subject, depth=depth + 1, expected_type=None, root=False)

            annotations = document.get("annotations")
            if annotations is not None:
                _require(
                    isinstance(annotations, dict)
                    and all(isinstance(k, str) and isinstance(v, str) for k, v in annotations.items()),
                    "oci_manifest_annotations_invalid",
                    descriptor["digest"],
                )
            if root:
                _require(
                    root_descriptor["subjectDigest"]
                    == (None if subject is None else subject["digest"])
                    and root_descriptor["annotationsDigest"]
                    == (None if annotations is None else canonical_digest(annotations)),
                    "oci_root_metadata_mismatch",
                    descriptor["digest"],
                )
            objects[key] = {
                "repository": repository,
                "digest": descriptor["digest"],
                "mediaType": OCI_MANIFEST_MEDIA_TYPE,
                "size": descriptor["size"],
                "artifactType": artifact_type,
                "semanticRole": self.artifact_type_roles[artifact_type],
                "manifest": document,
            }
            payload_records[key]["semanticRole"] = (
                f"artifact:{self.artifact_type_roles[artifact_type]}"
            )
            payload_records[key]["artifactType"] = artifact_type
            visiting.remove(key)
            return document

        visit_manifest(
            expected_repository,
            {
                "digest": root_descriptor["digest"],
                "mediaType": root_descriptor["mediaType"],
                "size": root_descriptor["size"],
            },
            depth=0,
            expected_type=expected_artifact_type,
            root=True,
        )
        object_records = [deepcopy(value) for value in payload_records.values()]
        object_records.sort(key=lambda value: (value["repository"].encode("utf-8"), value["digest"]))
        edges.sort(key=lambda value: (value["from"], value["kind"], value["index"], value["to"], value["role"]))
        graph_digest = canonical_digest(
            {
                "profile": "bytedesk.oci-recursive-graph/1",
                "root": root_descriptor,
                "objects": object_records,
                "edges": edges,
            }
        )
        root_manifest = objects[(expected_repository, root_descriptor["digest"])]["manifest"]
        return {
            "rootDescriptor": deepcopy(root_descriptor),
            "configDescriptor": deepcopy(root_manifest["config"]),
            "layerDescriptors": deepcopy(root_manifest["layers"]),
            "artifactType": root_manifest["artifactType"],
            "subject": deepcopy(root_manifest.get("subject")),
            "graphDigest": graph_digest,
            "objectCount": len(payload_records),
            "totalBytes": total_bytes,
            "maximumDepthObserved": observed_depth,
        }
