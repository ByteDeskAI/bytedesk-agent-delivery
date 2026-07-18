#!/usr/bin/env python3
"""Create exact, conformance-only evidence for one built contract bundle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from typing import Any

from contractlib import (
    ContractToolError,
    canonical_json,
    load_json_bytes,
    sha256_bytes,
    stable_read_bytes,
    strict_json_bytes,
    write_bytes,
)
from release_evidence import (
    ATTESTATION_FILENAME,
    RELEASE_EVIDENCE_IDS,
    SOURCE_EVIDENCE,
    build_executed_distribution_report,
    build_license_report,
    build_scan_completeness_report,
    build_scan_report,
    build_slsa_provenance,
    build_spdx_document,
    evaluation_schema_descriptor,
    evidence_filename,
    expected_evidence_tree_paths,
    expected_test_evaluator,
    release_evidence_subject,
    source_descriptor,
)
from verify_bundle import MANIFEST_ARCHIVE_PATH, read_archive_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--trust-policy", type=Path, required=True)
    parser.add_argument("--verification-evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    snapshot = read_archive_snapshot(args.bundle.resolve())
    manifest_bytes = snapshot.members[MANIFEST_ARCHIVE_PATH]
    manifest = strict_json_bytes(manifest_bytes, MANIFEST_ARCHIVE_PATH)
    if not isinstance(manifest, dict):
        raise ContractToolError("contract-bundle manifest is not an object")
    _, detached_manifest_bytes = load_json_bytes(args.manifest.resolve())
    if detached_manifest_bytes != manifest_bytes:
        raise ContractToolError("detached manifest differs from the release-evidence subject")
    policy, policy_bytes = load_json_bytes(args.trust_policy.resolve())
    if not isinstance(policy, dict) or policy_bytes != canonical_json(policy):
        raise ContractToolError("test trust policy is not exact RFC 8785 bytes")
    policy_ref = {"id": policy["policyId"], "digest": sha256_bytes(policy_bytes)}
    if set(policy.get("requiredEvidence", [])) != set(RELEASE_EVIDENCE_IDS):
        raise ContractToolError("test policy does not require the exact release-evidence set")
    subject = release_evidence_subject(
        repository=args.repository,
        digest=snapshot.digest,
        size=snapshot.size,
        trust_policy=policy_ref,
    )
    evaluator = expected_test_evaluator(repo_root)

    verification_evidence_dir = args.verification_evidence_dir.resolve()
    source_payloads: dict[str, bytes] = {}
    source_descriptors: dict[str, list[dict[str, Any]]] = {}
    for group, specifications in SOURCE_EVIDENCE.items():
        descriptors: list[dict[str, Any]] = []
        for source_id, filename, profile, outcome_field in specifications:
            source_path = verification_evidence_dir / filename
            try:
                if source_path.is_symlink() or not source_path.is_file():
                    raise ContractToolError(
                        f"required verification evidence is not a regular file: {filename}"
                    )
                payload = stable_read_bytes(
                    source_path,
                    description=f"verification evidence {filename}",
                    maximum_bytes=64 * 1024 * 1024,
                )
            except OSError as error:
                raise ContractToolError(f"required verification evidence is absent: {filename}") from error
            source = strict_json_bytes(payload, f"verification evidence {filename}")
            if not isinstance(source, dict) or source.get("profile") != profile:
                raise ContractToolError(f"verification evidence has the wrong profile: {filename}")
            if source.get(outcome_field) != "pass":
                raise ContractToolError(f"verification evidence did not pass: {filename}")
            source_payloads[filename] = payload
            descriptors.append(
                source_descriptor(
                    source_id=source_id,
                    filename=filename,
                    profile=profile,
                    outcome_field=outcome_field,
                    payload=payload,
                )
            )
        source_descriptors[group] = descriptors

    fixture_path = manifest["fixtureIndex"]["path"]
    fixture_index = strict_json_bytes(snapshot.members[fixture_path], fixture_path)
    if not isinstance(fixture_index, dict) or not isinstance(fixture_index.get("fixtures"), list):
        raise ContractToolError("bundle fixture index is invalid")
    compatibility_path = manifest["compatibility"]["path"]
    compatibility = strict_json_bytes(
        snapshot.members[compatibility_path], compatibility_path
    )
    if not isinstance(compatibility, dict):
        raise ContractToolError("bundle compatibility document is invalid")

    documents: dict[str, dict[str, Any]] = {}
    documents["schema"] = {
        "profile": "bytedesk.contract-release-schema-evidence/1",
        "subject": subject,
        "policy": policy_ref,
        "manifestDigest": sha256_bytes(manifest_bytes),
        "schemaInventory": manifest["schemaInventory"],
        "schemaCount": len(manifest["schemas"]),
        "fixtureCount": len(fixture_index["fixtures"]),
        "sources": source_descriptors["schema"],
        "outcome": "pass",
        "authorityIssued": False,
    }
    documents["compatibility"] = {
        "profile": "bytedesk.contract-release-compatibility-evidence/1",
        "subject": subject,
        "policy": policy_ref,
        "document": manifest["compatibility"],
        "bundleMajor": compatibility["bundleMajor"],
        "schemaDialect": compatibility["schemaDialect"],
        "canonicalization": compatibility["canonicalization"],
        "outcome": "pass",
        "authorityIssued": False,
    }
    documents["conformance"] = {
        "profile": "bytedesk.contract-release-conformance-evidence/1",
        "subject": subject,
        "policy": policy_ref,
        "sources": source_descriptors["conformance"],
        "sourceCount": len(source_descriptors["conformance"]),
        "outcome": "pass",
        "authorityIssued": False,
    }
    documents["determinism"] = {
        "profile": "bytedesk.contract-release-determinism-evidence/1",
        "subject": subject,
        "policy": policy_ref,
        "manifestDigest": sha256_bytes(manifest_bytes),
        "source": source_descriptors["determinism"][0],
        "outcome": "pass",
        "authorityIssued": False,
    }
    documents["sbom"] = build_spdx_document(
        subject=subject,
        policy=policy_ref,
        manifest=manifest,
        members=snapshot.members,
        created_at=args.evaluated_at,
    )
    sbom_digest = sha256_bytes(canonical_json(documents["sbom"]))
    documents["provenance"] = build_slsa_provenance(
        subject=subject,
        policy=policy_ref,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        evaluator=evaluator,
        evaluated_at=args.evaluated_at,
    )
    for evidence_id in ("vulnerability", "malware", "secret_scan"):
        documents[evidence_id] = build_scan_report(
            evidence_id=evidence_id,
            subject=subject,
            policy=policy_ref,
            sbom_digest=sbom_digest,
            members=snapshot.members,
            evaluated_at=args.evaluated_at,
        )
    documents["license"] = build_license_report(
        subject=subject,
        policy=policy_ref,
        sbom_digest=sbom_digest,
        evaluated_at=args.evaluated_at,
    )
    report_digests = {
        evidence_id: sha256_bytes(canonical_json(documents[evidence_id]))
        for evidence_id in ("vulnerability", "malware", "secret_scan")
    }
    documents["scan_completeness"] = build_scan_completeness_report(
        subject=subject,
        policy=policy_ref,
        sbom_digest=sbom_digest,
        report_digests=report_digests,
        members=snapshot.members,
        evaluated_at=args.evaluated_at,
    )
    documents["executed_distribution"] = build_executed_distribution_report(
        repo_root=repo_root,
        subject=subject,
        policy=policy_ref,
        evaluator=evaluator,
    )

    document_bytes = {
        evidence_id: canonical_json(documents[evidence_id])
        for evidence_id in RELEASE_EVIDENCE_IDS
    }
    attestation = {
        "contract": "bytedesk.evaluation-attestation/1",
        "schema": evaluation_schema_descriptor(repo_root),
        "subject": subject,
        "policy": policy_ref,
        "result": "passed",
        "checks": [
            {
                "id": evidence_id,
                "result": "passed",
                "evidenceDigest": sha256_bytes(document_bytes[evidence_id]),
            }
            for evidence_id in RELEASE_EVIDENCE_IDS
        ],
        "evaluatedAt": args.evaluated_at,
        "evaluator": evaluator,
        "trustPolicy": policy_ref,
    }

    output_dir = args.output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=f".{output_dir.name}.", dir=output_dir.parent
    ) as temporary:
        staged = Path(temporary) / "tree"
        (staged / "sources").mkdir(parents=True)
        write_bytes(staged / ATTESTATION_FILENAME, canonical_json(attestation))
        for evidence_id, payload in document_bytes.items():
            write_bytes(staged / evidence_filename(evidence_id), payload)
        for filename, payload in source_payloads.items():
            write_bytes(staged / "sources" / filename, payload)
        observed = {
            path.relative_to(staged).as_posix()
            for path in staged.rglob("*")
            if path.is_file()
        }
        if observed != expected_evidence_tree_paths():
            raise ContractToolError("generated release-evidence tree is incomplete")
        if output_dir.exists():
            if output_dir.is_symlink() or not output_dir.is_dir():
                raise ContractToolError("release-evidence output exists and is not a directory")
            shutil.rmtree(output_dir)
        os.replace(staged, output_dir)

    result = {
        "profile": "bytedesk.contract-release-evidence-creation/1",
        "subject": subject,
        "attestationDigest": sha256_bytes(canonical_json(attestation)),
        "evidenceCount": len(document_bytes),
        "requiredEvidence": list(RELEASE_EVIDENCE_IDS),
        "evaluator": evaluator,
        "attestationAuthenticated": False,
        "authorityIssued": False,
        "outcome": "pass",
    }
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError) as error:
        print(f"test release-evidence creation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
