#!/usr/bin/env python3
"""Adversarial conformance tests for contract-bundle release evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from typing import Any, Callable

from contractlib import (
    ContractToolError,
    canonical_json,
    load_json,
    load_json_bytes,
    sha256_bytes,
    strict_json_bytes,
    write_bytes,
    write_json,
)
from release_evidence import (
    ATTESTATION_FILENAME,
    PRODUCT_RELEASE_POLICY_PATH,
    RELEASE_EVIDENCE_IDS,
    TEST_EVALUATOR_MEDIA_TYPE,
    TEST_EVALUATOR_REPOSITORY,
    conformance_builder_tools,
    evidence_filename,
    executed_distribution_tools,
    expected_test_evaluator,
    release_evidence_subject,
    validate_release_evidence,
)
from verify_bundle import MANIFEST_ARCHIVE_PATH, read_archive_snapshot


def expect_denial(case_id: str, operation: Callable[[], Any]) -> dict[str, str]:
    try:
        operation()
    except (ContractToolError, OSError) as error:
        return {"id": case_id, "outcome": "denied", "reason": str(error)}
    raise ContractToolError(f"release-evidence denial case unexpectedly passed: {case_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trust-policy", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--release-evidence-dir", type=Path, required=True)
    parser.add_argument("--verification-time", required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    executed_paths = {
        tool["path"] for tool in executed_distribution_tools(repo_root)
    }
    builder_paths = {
        tool["path"] for tool in conformance_builder_tools(repo_root)
    }
    policy_orchestration_paths = {
        "Makefile",
        ".github/workflows/contracts.yml",
    }
    if not policy_orchestration_paths.issubset(executed_paths):
        raise ContractToolError(
            "executed-distribution evidence omits policy-bearing orchestration"
        )
    if policy_orchestration_paths & builder_paths:
        raise ContractToolError(
            "conformance builder inventory is circular through policy-bearing orchestration"
        )
    snapshot = read_archive_snapshot(args.bundle.resolve())
    manifest_bytes = snapshot.members[MANIFEST_ARCHIVE_PATH]
    manifest = strict_json_bytes(manifest_bytes, MANIFEST_ARCHIVE_PATH)
    _, detached_manifest_bytes = load_json_bytes(args.manifest.resolve())
    if detached_manifest_bytes != manifest_bytes:
        raise ContractToolError("release-evidence test manifest differs from bundle")
    policy, policy_bytes = load_json_bytes(args.trust_policy.resolve())
    if not isinstance(policy, dict) or policy_bytes != canonical_json(policy):
        raise ContractToolError("release-evidence test policy is not canonical")
    policy_ref = {"id": policy["policyId"], "digest": sha256_bytes(policy_bytes)}
    subject = release_evidence_subject(
        repository=args.repository,
        digest=snapshot.digest,
        size=snapshot.size,
        trust_policy=policy_ref,
    )

    def validate(directory: Path) -> Any:
        return validate_release_evidence(
            directory / ATTESTATION_FILENAME,
            directory,
            repo_root=repo_root,
            subject=subject,
            policy=policy,
            policy_bytes=policy_bytes,
            expected_policy=policy_ref,
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            members=snapshot.members,
            verification_time=args.verification_time,
        )

    baseline = validate(args.release_evidence_dir.resolve())
    if set(baseline.available_evidence) != set(RELEASE_EVIDENCE_IDS):
        raise ContractToolError("baseline did not derive the complete release-evidence set")
    if baseline.authority_issued:
        raise ContractToolError("conformance-only release evidence issued authority")
    if baseline.evaluator["trustPolicy"] == policy_ref:
        raise ContractToolError(
            "evaluator inherited the evaluated subject trust policy"
        )
    if baseline.evaluator != expected_test_evaluator(repo_root):
        raise ContractToolError("baseline evaluator is not independently product-pinned")

    def validate_policy_object(candidate: dict[str, Any]) -> Any:
        return validate_release_evidence(
            args.release_evidence_dir.resolve() / ATTESTATION_FILENAME,
            args.release_evidence_dir.resolve(),
            repo_root=repo_root,
            subject=subject,
            policy=candidate,
            policy_bytes=policy_bytes,
            expected_policy=policy_ref,
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            members=snapshot.members,
            verification_time=args.verification_time,
        )

    cases: list[dict[str, str]] = [
        {"id": "baseline-exact-release-evidence", "outcome": "pass"}
    ]
    evaluator_policy = load_json(repo_root / PRODUCT_RELEASE_POLICY_PATH)
    if not isinstance(evaluator_policy, dict):
        raise ContractToolError("test evaluator product-release policy is invalid")
    with TemporaryDirectory(prefix="bytedesk-evaluator-policy-test-") as temporary:
        temporary_root = Path(temporary)
        temporary_policy_path = temporary_root / PRODUCT_RELEASE_POLICY_PATH
        temporary_policy_path.parent.mkdir(parents=True)

        def evaluator_policy_denial(
            case_id: str, mutate: Callable[[dict[str, Any]], None]
        ) -> dict[str, str]:
            candidate = deepcopy(evaluator_policy)
            mutate(candidate)
            write_bytes(temporary_policy_path, canonical_json(candidate))
            return expect_denial(
                case_id, lambda: expected_test_evaluator(temporary_root)
            )

        cases.extend(
            [
                evaluator_policy_denial(
                    "evaluator-product-policy-repository-out-of-scope",
                    lambda value: value["scope"].update(
                        {
                            "repositories": [
                                item
                                for item in value["scope"]["repositories"]
                                if item != TEST_EVALUATOR_REPOSITORY
                            ]
                        }
                    ),
                ),
                evaluator_policy_denial(
                    "evaluator-product-policy-media-type-out-of-scope",
                    lambda value: value["scope"].update(
                        {
                            "mediaTypes": [
                                item
                                for item in value["scope"]["mediaTypes"]
                                if item != TEST_EVALUATOR_MEDIA_TYPE
                            ]
                        }
                    ),
                ),
                evaluator_policy_denial(
                    "evaluator-product-policy-purpose-substitution",
                    lambda value: value["scope"].update(
                        {"purposes": [policy_ref["id"]]}
                    ),
                ),
            ]
        )
    malformed_required = deepcopy(policy)
    malformed_required["requiredEvidence"].append({"not": "a string"})
    cases.append(
        expect_denial(
            "malformed-policy-required-evidence-type",
            lambda: validate_policy_object(malformed_required),
        )
    )
    malformed_rules = deepcopy(policy)
    malformed_rules["rules"] = []
    cases.append(
        expect_denial(
            "malformed-policy-rules-type",
            lambda: validate_policy_object(malformed_rules),
        )
    )

    with TemporaryDirectory(prefix="bytedesk-release-evidence-test-") as temporary:
        temporary_root = Path(temporary)

        def variant(name: str) -> Path:
            target = temporary_root / name
            shutil.copytree(args.release_evidence_dir.resolve(), target)
            return target

        def load_attestation(directory: Path) -> dict[str, Any]:
            value, _ = load_json_bytes(directory / ATTESTATION_FILENAME)
            if not isinstance(value, dict):
                raise ContractToolError("test attestation is not an object")
            return value

        def write_attestation(directory: Path, value: dict[str, Any]) -> None:
            write_bytes(directory / ATTESTATION_FILENAME, canonical_json(value))

        def mutate_attestation(
            name: str, mutate: Callable[[dict[str, Any]], None]
        ) -> Path:
            directory = variant(name)
            attestation = load_attestation(directory)
            mutate(attestation)
            write_attestation(directory, attestation)
            return directory

        def mutate_evidence(
            name: str,
            evidence_id: str,
            mutate: Callable[[dict[str, Any]], None],
            *,
            rebind: bool = True,
        ) -> Path:
            directory = variant(name)
            evidence_path = directory / evidence_filename(evidence_id)
            evidence_document, _ = load_json_bytes(evidence_path)
            if not isinstance(evidence_document, dict):
                raise ContractToolError("test evidence document is not an object")
            mutate(evidence_document)
            evidence_bytes = canonical_json(evidence_document)
            write_bytes(evidence_path, evidence_bytes)
            if rebind:
                attestation = load_attestation(directory)
                check = next(item for item in attestation["checks"] if item["id"] == evidence_id)
                check["evidenceDigest"] = sha256_bytes(evidence_bytes)
                write_attestation(directory, attestation)
            return directory

        missing = variant("missing-check-file")
        (missing / evidence_filename("malware")).unlink()
        cases.append(expect_denial("missing-evidence-file", lambda: validate(missing)))

        duplicate = mutate_attestation(
            "duplicate-check-id",
            lambda value: value["checks"].append(deepcopy(value["checks"][0])),
        )
        cases.append(expect_denial("duplicate-check-id", lambda: validate(duplicate)))

        missing_check = mutate_attestation(
            "missing-check",
            lambda value: value["checks"].pop(),
        )
        cases.append(expect_denial("missing-required-check", lambda: validate(missing_check)))

        failed = mutate_attestation(
            "failed-check",
            lambda value: value["checks"][0].update({"result": "failed"}),
        )
        cases.append(expect_denial("failed-check", lambda: validate(failed)))

        not_applicable = mutate_attestation(
            "not-applicable-check",
            lambda value: value["checks"][0].update({"result": "not_applicable"}),
        )
        cases.append(
            expect_denial("not-applicable-required-check", lambda: validate(not_applicable))
        )

        wrong_subject = mutate_attestation(
            "wrong-subject",
            lambda value: value["subject"].update({"digest": "sha256:" + "f" * 64}),
        )
        cases.append(expect_denial("wrong-subject", lambda: validate(wrong_subject)))

        wrong_size = mutate_attestation(
            "wrong-subject-size",
            lambda value: value["subject"].update({"size": value["subject"]["size"] + 1}),
        )
        cases.append(expect_denial("wrong-subject-size", lambda: validate(wrong_size)))

        wrong_repository = mutate_attestation(
            "wrong-subject-repository",
            lambda value: value["subject"].update(
                {"repository": "registry.example.invalid/other/contracts"}
            ),
        )
        cases.append(
            expect_denial("wrong-subject-repository", lambda: validate(wrong_repository))
        )

        wrong_media_type = mutate_attestation(
            "wrong-subject-media-type",
            lambda value: value["subject"].update(
                {"mediaType": "application/vnd.oci.image.manifest.v1+json"}
            ),
        )
        cases.append(
            expect_denial("wrong-subject-media-type", lambda: validate(wrong_media_type))
        )

        wrong_policy = mutate_attestation(
            "wrong-policy",
            lambda value: value["policy"].update({"digest": "sha256:" + "e" * 64}),
        )
        cases.append(expect_denial("wrong-policy", lambda: validate(wrong_policy)))

        tampered = variant("tampered-evidence-bytes")
        with (tampered / evidence_filename("schema")).open("ab") as stream:
            stream.write(b"\n")
        cases.append(expect_denial("tampered-evidence-bytes", lambda: validate(tampered)))

        incomplete_sbom = mutate_evidence(
            "incomplete-spdx",
            "sbom",
            lambda value: value["files"].pop(),
        )
        cases.append(expect_denial("incomplete-spdx", lambda: validate(incomplete_sbom)))

        wrong_provenance_subject = mutate_evidence(
            "wrong-provenance-subject",
            "provenance",
            lambda value: value["subject"][0]["digest"].update({"sha256": "f" * 64}),
        )
        cases.append(
            expect_denial(
                "wrong-provenance-subject", lambda: validate(wrong_provenance_subject)
            )
        )

        incomplete_provenance = mutate_evidence(
            "incomplete-provenance-materials",
            "provenance",
            lambda value: value["predicate"]["buildDefinition"][
                "resolvedDependencies"
            ].pop(),
        )
        cases.append(
            expect_denial(
                "incomplete-provenance-materials", lambda: validate(incomplete_provenance)
            )
        )

        incomplete_scan = mutate_evidence(
            "incomplete-vulnerability-scan",
            "vulnerability",
            lambda value: value["coverage"].update(
                {"scannedFileCount": value["coverage"]["scannedFileCount"] - 1}
            ),
        )
        cases.append(
            expect_denial("incomplete-vulnerability-scan", lambda: validate(incomplete_scan))
        )

        wrong_scan_binding = mutate_evidence(
            "wrong-scan-binding",
            "scan_completeness",
            lambda value: value["reports"].update(
                {"malware": "sha256:" + "d" * 64}
            ),
        )
        cases.append(
            expect_denial("wrong-scan-cross-binding", lambda: validate(wrong_scan_binding))
        )

        wrong_license_binding = mutate_evidence(
            "wrong-license-sbom",
            "license",
            lambda value: value.update({"sbomDigest": "sha256:" + "c" * 64}),
        )
        cases.append(
            expect_denial("wrong-license-sbom-binding", lambda: validate(wrong_license_binding))
        )

        unknown_license = mutate_evidence(
            "unknown-license-false-pass",
            "license",
            lambda value: value["packages"][0].update(
                {"concluded": "NOASSERTION"}
            ),
        )
        cases.append(
            expect_denial("unknown-license-false-pass", lambda: validate(unknown_license))
        )

        unpinned_evaluator = mutate_attestation(
            "unpinned-evaluator",
            lambda value: value["evaluator"].update({"digest": "sha256:" + "b" * 64}),
        )
        cases.append(
            expect_denial("unpinned-evaluator", lambda: validate(unpinned_evaluator))
        )

        subject_policy_evaluator = mutate_attestation(
            "subject-policy-substituted-evaluator",
            lambda value: value["evaluator"].update(
                {"trustPolicy": deepcopy(policy_ref)}
            ),
        )
        cases.append(
            expect_denial(
                "subject-policy-substituted-evaluator",
                lambda: validate(subject_policy_evaluator),
            )
        )

        wrong_distribution = mutate_evidence(
            "wrong-executed-distribution",
            "executed_distribution",
            lambda value: value["tools"][0].update({"digest": "sha256:" + "a" * 64}),
        )
        cases.append(
            expect_denial(
                "wrong-executed-distribution", lambda: validate(wrong_distribution)
            )
        )

        wrong_builder = mutate_evidence(
            "wrong-executed-builder",
            "executed_distribution",
            lambda value: value["builder"].update(
                {"digest": "sha256:" + "b" * 64}
            ),
        )
        cases.append(
            expect_denial(
                "wrong-executed-builder", lambda: validate(wrong_builder)
            )
        )

        false_builder_authority = mutate_evidence(
            "false-builder-execution-authority",
            "executed_distribution",
            lambda value: value.update({"builderExecutionAuthenticated": True}),
        )
        cases.append(
            expect_denial(
                "false-builder-execution-authority",
                lambda: validate(false_builder_authority),
            )
        )

    result = {
        "profile": "bytedesk.contract-release-evidence-conformance/1",
        "caseCount": len(cases),
        "cases": cases,
        "requiredEvidence": list(RELEASE_EVIDENCE_IDS),
        "attestationAuthenticated": False,
        "authorityIssued": False,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractToolError, OSError) as error:
        print(f"release-evidence conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
