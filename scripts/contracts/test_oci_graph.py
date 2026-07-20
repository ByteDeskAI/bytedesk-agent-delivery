#!/usr/bin/env python3
"""Focused recursive OCI graph verification cases."""

from __future__ import annotations

from copy import deepcopy
import hashlib

import rfc8785

import oci_graph
from oci_graph import (
    ARTIFACT_TYPE_ROLES,
    EMPTY_CONFIG_BYTES,
    EMPTY_CONFIG_DIGEST,
    LAYER_ROLE_ANNOTATION,
    OCI_EMPTY_CONFIG_MEDIA_TYPE,
    OCI_LAYER_MEDIA_TYPE,
    OCI_MANIFEST_MEDIA_TYPE,
    OciGraphError,
    OciGraphLimits,
    OciGraphVerifier,
    build_oci_manifest,
    raw_digest,
)


REPOSITORY = "registry.example/public/renders"
HARNESS_RENDER = "application/vnd.bytedesk.agent.render.v1+json"
STATUS_ELIGIBILITY = (
    "application/vnd.bytedesk.agent."
    "release-status-eligibility-evidence.v1+json"
)


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)


def expect(code: str, operation, detail: str) -> None:
    try:
        operation()
    except OciGraphError as error:
        require(error.code == code, f"{detail}: expected {code}, got {error.code}")
    else:
        raise AssertionError(f"{detail}: denial was accepted")


def merge(*stores: dict[tuple[str, str], bytes]) -> dict[tuple[str, str], bytes]:
    result: dict[tuple[str, str], bytes] = {}
    for store in stores:
        for key, payload in store.items():
            if key in result:
                require(result[key] == payload, f"conflicting blob {key}")
            result[key] = payload
    return result


def verifier(
    store: dict[tuple[str, str], bytes],
    *,
    limits: OciGraphLimits | None = None,
) -> OciGraphVerifier:
    return OciGraphVerifier(fetch=lambda repository, digest: store[(repository, digest)], limits=limits)


def run() -> dict[str, int | str]:
    required_new_types = {
        "application/vnd.bytedesk.agent.release-status-log-inclusion-proof.v1+json",
        STATUS_ELIGIBILITY,
        "application/vnd.bytedesk.agent.release-status-append-resolution.v1+json",
        "application/vnd.bytedesk.agent.publication-evidence.v1+json",
        "application/vnd.bytedesk.agent.activation-authorization.v1+json",
    }
    require(required_new_types.issubset(ARTIFACT_TYPE_ROLES), "new media types missing")

    subject_root, _, subject_store = build_oci_manifest(
        repository=REPOSITORY,
        artifact_type=STATUS_ELIGIBILITY,
        layers=[("evidence", b"fresh-publication-eligibility")],
    )
    subject = {
        "mediaType": subject_root["mediaType"],
        "digest": subject_root["digest"],
        "size": subject_root["size"],
    }
    root, _, root_store = build_oci_manifest(
        repository=REPOSITORY,
        artifact_type=HARNESS_RENDER,
        layers=[
            ("portable-definition", b"agent-source"),
            ("public-render", b"render-output"),
            ("evidence", b"finalization-evidence"),
        ],
        subject=subject,
        annotations={"org.opencontainers.artifact.created": "2026-07-17T12:00:08Z"},
    )
    store = merge(subject_store, root_store)
    result = verifier(store).verify(
        root,
        expected_repository=REPOSITORY,
        expected_artifact_type=HARNESS_RENDER,
    )
    require(result["objectCount"] == 7, "transitive object count drift")
    require(result["maximumDepthObserved"] == 1, "subject depth not traversed")

    missing_root_store = dict(store)
    del missing_root_store[(REPOSITORY, root["digest"])]
    expect(
        "oci_object_missing",
        lambda: verifier(missing_root_store).verify(
            root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "direct missing root",
    )
    missing_transitive_store = dict(store)
    subject_layer_digest = next(
        digest
        for (repository, digest), payload in subject_store.items()
        if repository == REPOSITORY
        and digest not in {subject_root["digest"], EMPTY_CONFIG_DIGEST}
    )
    del missing_transitive_store[(REPOSITORY, subject_layer_digest)]
    expect(
        "oci_object_missing",
        lambda: verifier(missing_transitive_store).verify(
            root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "transitive missing layer",
    )
    tampered_store = dict(store)
    tampered_store[(REPOSITORY, subject_layer_digest)] = b"tampered"
    expect(
        "oci_object_digest_mismatch",
        lambda: verifier(tampered_store).verify(
            root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "transitive tamper",
    )

    duplicate_root, _, duplicate_store = build_oci_manifest(
        repository=REPOSITORY,
        artifact_type=HARNESS_RENDER,
        layers=[("evidence", b"one"), ("evidence", b"two")],
    )
    expect(
        "oci_layer_role_duplicate",
        lambda: verifier(duplicate_store).verify(
            duplicate_root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "duplicate role",
    )
    unknown_root, _, unknown_store = build_oci_manifest(
        repository=REPOSITORY,
        artifact_type=HARNESS_RENDER,
        layers=[("tenant-secrets", b"forbidden")],
    )
    expect(
        "oci_media_role_unregistered",
        lambda: verifier(unknown_store).verify(
            unknown_root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "unregistered media-role pair",
    )
    substituted_subject = deepcopy(root)
    substituted_subject["subjectDigest"] = "sha256:" + ("77" * 32)
    expect(
        "oci_root_metadata_mismatch",
        lambda: verifier(store).verify(
            substituted_subject,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "subject substitution",
    )
    cross_repository_subject = deepcopy(subject)
    cross_repository_subject["repository"] = "registry.example/other"
    cross_root, _, cross_store = build_oci_manifest(
        repository=REPOSITORY,
        artifact_type=HARNESS_RENDER,
        layers=[("evidence", b"cross-repository")],
        subject=cross_repository_subject,
    )
    expect(
        "oci_subject_descriptor_invalid",
        lambda: verifier(merge(cross_store, subject_store)).verify(
            cross_root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "cross-repository subject",
    )
    expect(
        "oci_graph_limit_exceeded",
        lambda: verifier(
            store,
            limits=OciGraphLimits(maximum_objects=3),
        ).verify(
            root,
            expected_repository=REPOSITORY,
            expected_artifact_type=HARNESS_RENDER,
        ),
        "bounded traversal",
    )

    # A content-addressed SHA-256 cycle requires a collision/fixed point.  This
    # test models that adversarial condition by pinning the raw-digest oracle to
    # two exact colliding fixture identifiers, proving the explicit DFS cycle
    # guard fails closed even if the digest assumption is defeated.
    fake_a = "sha256:" + ("aa" * 32)
    fake_b = "sha256:" + ("bb" * 32)
    layer_payload = b"cycle-evidence"
    layer = {
        "mediaType": OCI_LAYER_MEDIA_TYPE,
        "digest": raw_digest(layer_payload),
        "size": len(layer_payload),
        "annotations": {LAYER_ROLE_ANNOTATION: "evidence"},
    }

    def cycle_manifest(subject_digest: str) -> bytes:
        return rfc8785.dumps(
            {
                "schemaVersion": 2,
                "mediaType": OCI_MANIFEST_MEDIA_TYPE,
                "artifactType": STATUS_ELIGIBILITY,
                "config": {
                    "mediaType": OCI_EMPTY_CONFIG_MEDIA_TYPE,
                    "digest": EMPTY_CONFIG_DIGEST,
                    "size": 2,
                },
                "layers": [layer],
                "subject": {
                    "mediaType": OCI_MANIFEST_MEDIA_TYPE,
                    "digest": subject_digest,
                    "size": 0,
                },
            }
        )

    a_payload = cycle_manifest(fake_b)
    b_payload = cycle_manifest(fake_a)
    a_document = oci_graph._jcs_object(a_payload, fake_a)
    b_document = oci_graph._jcs_object(b_payload, fake_b)
    a_document["subject"]["size"] = len(b_payload)
    b_document["subject"]["size"] = len(a_payload)
    a_payload = rfc8785.dumps(a_document)
    b_payload = rfc8785.dumps(b_document)
    # Sizes influence one another but stabilize because both digests have fixed
    # width and JSON integer widths converge in one additional pass.
    for _ in range(3):
        a_document = oci_graph._jcs_object(a_payload, fake_a)
        b_document = oci_graph._jcs_object(b_payload, fake_b)
        a_document["subject"]["size"] = len(b_payload)
        b_document["subject"]["size"] = len(a_payload)
        a_payload = rfc8785.dumps(a_document)
        b_payload = rfc8785.dumps(b_document)
    cycle_store = {
        (REPOSITORY, fake_a): a_payload,
        (REPOSITORY, fake_b): b_payload,
        (REPOSITORY, EMPTY_CONFIG_DIGEST): EMPTY_CONFIG_BYTES,
        (REPOSITORY, layer["digest"]): layer_payload,
    }
    original_raw_digest = oci_graph.raw_digest
    fake_by_payload = {a_payload: fake_a, b_payload: fake_b}
    oci_graph.raw_digest = lambda payload: fake_by_payload.get(
        payload, original_raw_digest(payload)
    )
    try:
        cycle_root = {
            "repository": REPOSITORY,
            "digest": fake_a,
            "mediaType": OCI_MANIFEST_MEDIA_TYPE,
            "artifactType": STATUS_ELIGIBILITY,
            "size": len(a_payload),
            "subjectDigest": fake_b,
            "annotationsDigest": None,
        }
        expect(
            "oci_graph_cycle",
            lambda: verifier(cycle_store).verify(
                cycle_root,
                expected_repository=REPOSITORY,
                expected_artifact_type=STATUS_ELIGIBILITY,
            ),
            "content-addressed cycle",
        )
    finally:
        oci_graph.raw_digest = original_raw_digest

    return {
        "profile": "bytedesk.oci-recursive-graph-focused-tests/1",
        "positiveCases": 1,
        "denialCases": 9,
    }


if __name__ == "__main__":
    print(run())
