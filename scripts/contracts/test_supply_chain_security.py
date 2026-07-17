#!/usr/bin/env python3
"""Focused denial, concurrency, and external-Adapter supply-chain tests."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Callable

import bundle_profile
import contractlib
from bundle_profile import (
    MAX_BUNDLE_MEMBER_BYTES,
    BundleProfileError,
    normalized_member_payload,
    portable_path_collision_key,
    validate_portable_path_set,
    write_deterministic_tar,
)
from contractlib import (
    ContractToolError,
    canonical_json,
    load_json_bytes,
    sha256_bytes,
    stable_read_bytes,
    strict_json_bytes,
    write_bytes,
    write_json,
)
from verify_bundle import (
    MANIFEST_ARCHIVE_PATH,
    build_bundle_registry,
    consume_replay_ledger,
    evaluate_trust_policy,
    load_canonical_request,
    load_canonical_trust_policy,
    preflight_trust_policy,
    read_archive_snapshot,
    verify_sigstore_signature,
)


def expect_denial(case_id: str, operation: Callable[[], Any]) -> dict[str, str]:
    try:
        operation()
    except (BundleProfileError, ContractToolError, OSError) as error:
        return {"id": case_id, "outcome": "denied", "reason": str(error)}
    raise ContractToolError(f"supply-chain denial case unexpectedly passed: {case_id}")


def mutation_denial(
    case_id: str,
    policy: dict[str, Any],
    request: dict[str, Any],
    manifest: dict[str, Any],
    verification_time: str,
    mutate: Callable[[dict[str, Any]], None],
) -> dict[str, str]:
    candidate = deepcopy(policy)
    mutate(candidate)
    payload = canonical_json(candidate)
    expected = {"id": candidate["policyId"], "digest": sha256_bytes(payload)}
    return expect_denial(
        case_id,
        lambda: preflight_trust_policy(
            candidate,
            payload,
            expected_policy=expected,
            request=request,
            manifest=manifest,
            verification_time=verification_time,
            available_evidence={"schema", "compatibility"},
        ),
    )


def fake_cosign_script(
    *,
    request_bytes: bytes,
    identity: str,
    issuer: str,
    source_repository: str,
    source_ref: str,
    source_commit: str,
) -> bytes:
    expected = [
        "verify-blob",
        "--bundle",
        "__BUNDLE__",
        "--trusted-root",
        "__ROOT__",
        "--certificate-identity",
        identity,
        "--certificate-oidc-issuer",
        issuer,
        "--certificate-github-workflow-repository",
        source_repository,
        "--certificate-github-workflow-ref",
        source_ref,
        "--certificate-github-workflow-sha",
        source_commit,
        "--certificate-github-workflow-trigger",
        "workflow_dispatch",
        "-",
    ]
    checks = ["[ \"$#\" -eq 18 ]"]
    for position, value in enumerate(expected, start=1):
        if value == "__BUNDLE__":
            checks.append(
                f"[ \"$(/usr/bin/basename \"${{{position}}}\")\" = signature.sigstore.json ]"
            )
        elif value == "__ROOT__":
            checks.append(
                f"[ \"$(/usr/bin/basename \"${{{position}}}\")\" = trusted-root.json ]"
            )
        else:
            checks.append(f"[ \"${{{position}}}\" = {shlex.quote(value)} ]")
    expected_request_digest = sha256_bytes(request_bytes).removeprefix("sha256:")
    return (
        "#!/bin/sh\n"
        "set -eu\n"
        + "\n".join(checks)
        + "\nactual=$(/usr/bin/sha256sum | /usr/bin/cut -d' ' -f1)\n"
        + f"[ \"$actual\" = {expected_request_digest} ]\n"
        + "echo fake-cosign-adapter-conformance-pass\n"
    ).encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trust-policy", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-id", required=True)
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--expected-purpose", required=True)
    parser.add_argument("--expected-key-version", required=True)
    parser.add_argument("--expected-nonce", required=True)
    parser.add_argument("--expected-issued-at", required=True)
    parser.add_argument("--expected-expires-at", required=True)
    parser.add_argument("--verification-time", required=True)
    parser.add_argument("--expected-trust-policy-id", required=True)
    parser.add_argument("--expected-trust-policy-digest", required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    snapshot = read_archive_snapshot(args.bundle.absolute())
    manifest_bytes = snapshot.members[MANIFEST_ARCHIVE_PATH]
    manifest = strict_json_bytes(manifest_bytes, MANIFEST_ARCHIVE_PATH)
    _, detached_manifest_bytes = load_json_bytes(args.manifest.absolute())
    if detached_manifest_bytes != manifest_bytes:
        raise ContractToolError("test detached manifest differs from archive snapshot")
    policy, policy_bytes = load_canonical_trust_policy(args.trust_policy.absolute())
    request, request_bytes = load_canonical_request(args.request.absolute())
    expected_policy = {
        "id": args.expected_trust_policy_id,
        "digest": args.expected_trust_policy_digest,
    }
    expected_request = {
        "requestId": args.expected_request_id,
        "repository": args.expected_repository,
        "purpose": args.expected_purpose,
        "keyVersion": args.expected_key_version,
        "nonce": args.expected_nonce,
        "issuedAt": args.expected_issued_at,
        "expiresAt": args.expected_expires_at,
        "trustPolicy": expected_policy,
    }
    evaluation = preflight_trust_policy(
        policy,
        policy_bytes,
        expected_policy=expected_policy,
        request=request,
        manifest=manifest,
        verification_time=args.verification_time,
        available_evidence={"schema", "compatibility"},
    )
    registry, schemas = build_bundle_registry(manifest, snapshot.members, expected_policy)
    if evaluate_trust_policy(
        policy,
        policy_bytes,
        expected_policy=expected_policy,
        request=request,
        manifest=manifest,
        verification_time=args.verification_time,
        available_evidence={"schema", "compatibility"},
        registry=registry,
        schemas=schemas,
    ) != evaluation:
        raise ContractToolError("baseline trust-policy preflight/full results differ")

    cases: list[dict[str, str]] = [
        {"id": "baseline-independent-trust-policy", "outcome": "pass"}
    ]

    path_denials = {
        "path-parent-segment": "contracts/../manifest.json",
        "path-not-nfc": "contracts/cafe\u0301.json",
        "path-format-control": "contracts/release\u200d.json",
        "path-windows-device": "contracts/CON.json",
        "path-windows-trailing-dot": "contracts/release./manifest.json",
    }
    for case_id, value in path_denials.items():
        cases.append(expect_denial(case_id, lambda value=value: portable_path_collision_key(value)))
    cases.append(
        expect_denial(
            "path-casefold-collision",
            lambda: validate_portable_path_set(
                ["contracts/Manifest.json", "contracts/manifest.json"], "test"
            ),
        )
    )
    presentation_a = b'{ "states": ["one", "two"], "profile": "example" }\n'
    presentation_b = b'{"profile":"example","states":["one","two"]}'
    control_path = "contracts/lifecycle/presentation-variance.v1.json"
    normalized_a = normalized_member_payload(control_path, presentation_a)
    normalized_b = normalized_member_payload(control_path, presentation_b)
    if normalized_a != normalized_b or sha256_bytes(normalized_a) != sha256_bytes(normalized_b):
        raise ContractToolError("structured-control presentation changed semantic identity")
    raw_path = "contracts/vendor/example/raw-presentation.json"
    if (
        normalized_member_payload(raw_path, presentation_a) != presentation_a
        or normalized_member_payload(raw_path, presentation_b) != presentation_b
    ):
        raise ContractToolError("raw vendor payload was presentation-normalized")
    cases.append(
        {
            "id": "structured-control-presentation-invariant-raw-payload-exact",
            "outcome": "pass",
        }
    )
    cases.append(
        expect_denial(
            "archive-member-over-size",
            lambda: write_deterministic_tar(
                io.BytesIO(),
                {MANIFEST_ARCHIVE_PATH: b"x" * (MAX_BUNDLE_MEMBER_BYTES + 1)},
            ),
        )
    )
    original_archive_limit = bundle_profile.MAX_BUNDLE_BYTES
    bundle_profile.MAX_BUNDLE_BYTES = 1024
    try:
        cases.append(
            expect_denial(
                "archive-total-byte-limit-before-publication",
                lambda: write_deterministic_tar(
                    io.BytesIO(),
                    {MANIFEST_ARCHIVE_PATH: b"{}"},
                ),
            )
        )
    finally:
        bundle_profile.MAX_BUNDLE_BYTES = original_archive_limit

    with TemporaryDirectory(prefix="bytedesk-archive-profile-") as directory:
        archive = Path(directory) / "minimal.tar"
        with archive.open("wb") as target:
            write_deterministic_tar(target, {MANIFEST_ARCHIVE_PATH: b"{}"})
        if read_archive_snapshot(archive).digest != sha256_bytes(archive.read_bytes()):
            raise ContractToolError("shared archive writer/verifier digest differs")
        cases.append({"id": "shared-archive-profile-round-trip", "outcome": "pass"})

    with TemporaryDirectory(prefix="bytedesk-stable-read-") as directory:
        target = Path(directory) / "input.bin"
        write_bytes(target, b"a" * (2 * 1024 * 1024))
        original_read = contractlib.os.read
        mutated = False

        def mutating_read(descriptor: int, size: int) -> bytes:
            nonlocal mutated
            block = original_read(descriptor, size)
            if not mutated and block:
                mutated = True
                with target.open("r+b", buffering=0) as source:
                    source.seek(1024 * 1024)
                    source.write(b"b")
                    source.flush()
                    os.fsync(source.fileno())
            return block

        contractlib.os.read = mutating_read
        try:
            cases.append(
                expect_denial(
                    "descriptor-stable-read-detects-in-place-change",
                    lambda: stable_read_bytes(
                        target,
                        description="concurrently changed input",
                        maximum_bytes=4 * 1024 * 1024,
                    ),
                )
            )
        finally:
            contractlib.os.read = original_read

        absent_output = Path(directory) / "atomic.out"

        def publish(value: bytes) -> str:
            write_bytes(absent_output, value, require_absent=True)
            return "published"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(publish, value) for value in (b"a", b"b")]
        published = 0
        denied = 0
        for future in futures:
            try:
                future.result()
                published += 1
            except ContractToolError:
                denied += 1
        if (published, denied) != (1, 1):
            raise ContractToolError("exclusive atomic publication did not select exactly one winner")
        cases.append({"id": "exclusive-atomic-publication-concurrency", "outcome": "pass"})

    request_digest = sha256_bytes(request_bytes)
    with TemporaryDirectory(prefix="bytedesk-replay-ledger-") as directory:
        ledger = Path(directory) / "ledger.jsonl"

        def consume() -> str:
            return consume_replay_ledger(
                ledger,
                request_id=args.expected_request_id,
                nonce=args.expected_nonce,
                request_digest=request_digest,
                verified_at=args.verification_time,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(consume) for _ in range(2)]
        permitted = 0
        replay_denied = 0
        for future in futures:
            try:
                future.result()
                permitted += 1
            except ContractToolError:
                replay_denied += 1
        if (permitted, replay_denied) != (1, 1):
            raise ContractToolError("local replay concurrency did not select exactly one winner")
        cases.append({"id": "test-local-replay-concurrency", "outcome": "pass"})

        malformed = Path(directory) / "malformed.jsonl"
        write_bytes(malformed, b"not-json\n")
        before = malformed.read_bytes()
        cases.append(expect_denial("malformed-replay-ledger", lambda: consume_replay_ledger(
            malformed,
            request_id="different-request",
            nonce="different-nonce",
            request_digest="sha256:" + "f" * 64,
            verified_at=args.verification_time,
        )))
        if malformed.read_bytes() != before:
            raise ContractToolError("malformed replay ledger was changed after denial")

    cases.extend(
        [
            mutation_denial(
                "trust-policy-unpinned-reusable-workflow",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["signers"][0]["claims"].update(
                    {"workflow": ".github/workflows/contract-release-signer.yml"}
                ),
            ),
            mutation_denial(
                "trust-policy-caller-ref-not-tag",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["signers"][0]["claims"].update(
                    {"ref": "refs/heads/main"}
                ),
            ),
            mutation_denial(
                "trust-policy-out-of-scope-repository",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["scope"].update(
                    {"repositories": ["registry.example.invalid/other/contracts"]}
                ),
            ),
            mutation_denial(
                "trust-policy-revoked-key-version",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["revocations"]["keyVersions"].append(
                    args.expected_key_version
                ),
            ),
            mutation_denial(
                "trust-policy-missing-required-evidence",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["requiredEvidence"].append("provenance"),
            ),
            mutation_denial(
                "trust-policy-revoked-manifest",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["revocations"]["digests"].append(
                    sha256_bytes(canonical_json(manifest))
                ),
            ),
            mutation_denial(
                "trust-policy-revoked-schema",
                policy,
                request,
                manifest,
                args.verification_time,
                lambda candidate: candidate["revocations"]["schemas"].append(
                    manifest["schemas"][0]["digest"]
                ),
            ),
        ]
    )

    wrong_descriptor = deepcopy(policy)
    wrong_descriptor["schema"]["digest"] = "sha256:" + "f" * 64
    wrong_descriptor_bytes = canonical_json(wrong_descriptor)
    cases.append(
        expect_denial(
            "trust-policy-stale-schema-descriptor",
            lambda: evaluate_trust_policy(
                wrong_descriptor,
                wrong_descriptor_bytes,
                expected_policy={
                    "id": wrong_descriptor["policyId"],
                    "digest": sha256_bytes(wrong_descriptor_bytes),
                },
                request=request,
                manifest=manifest,
                verification_time=args.verification_time,
                available_evidence={"schema", "compatibility"},
                registry=registry,
                schemas=schemas,
            ),
        )
    )

    source_commit = "2" * 40
    with TemporaryDirectory(prefix="bytedesk-external-adapter-") as directory:
        root = Path(directory)
        fake_cosign = root / "cosign"
        sigstore_bundle = root / "input.sigstore.json"
        trusted_root = root / "input.trusted-root.json"
        write_bytes(sigstore_bundle, b'{"test":"sigstore-bundle"}')
        write_bytes(trusted_root, b'{"test":"trusted-root"}')
        write_bytes(
            fake_cosign,
            fake_cosign_script(
                request_bytes=request_bytes,
                identity=evaluation.certificate_identity,
                issuer=evaluation.certificate_oidc_issuer,
                source_repository=evaluation.source_repository,
                source_ref=evaluation.source_ref,
                source_commit=source_commit,
            ),
        )
        fake_cosign.chmod(0o700)
        old_path = os.environ.get("PATH")
        os.environ["PATH"] = f"{root}:{old_path or ''}"
        try:
            adapter_defaults = {
                "expected_trusted_root_digest": sha256_bytes(trusted_root.read_bytes()),
                "expected_cosign_digest": sha256_bytes(fake_cosign.read_bytes()),
                "expected_certificate_identity": evaluation.certificate_identity,
                "expected_certificate_oidc_issuer": evaluation.certificate_oidc_issuer,
                "expected_certificate_audience": evaluation.certificate_audience,
                "expected_workload_identity": evaluation.workload_identity,
                "expected_source_repository": evaluation.source_repository,
                "expected_source_ref": evaluation.source_ref,
                "expected_source_commit": source_commit,
            }

            def invoke_adapter(**overrides: str) -> tuple[dict[str, str], bytes, bytes]:
                selected = dict(adapter_defaults)
                selected.update(overrides)
                return verify_sigstore_signature(
                    request,
                    request_bytes,
                    sigstore_bundle,
                    trusted_root,
                    manifest_bytes,
                    expected_request,
                    args.verification_time,
                    **selected,
                )

            adapter_result, _, adapter_output = invoke_adapter()
            if (
                adapter_result["requestDigest"] != sha256_bytes(request_bytes)
                or adapter_output != b"fake-cosign-adapter-conformance-pass\n"
            ):
                raise ContractToolError("external Adapter baseline evidence differs")
            cases.append({"id": "hermetic-external-adapter-no-private-key", "outcome": "pass"})
            cases.append(
                expect_denial(
                    "external-adapter-caller-ref-substitution",
                    lambda: invoke_adapter(
                        expected_source_ref="refs/tags/v9.9.9-substituted"
                    ),
                )
            )
            cases.append(
                expect_denial(
                    "external-adapter-source-commit-substitution",
                    lambda: invoke_adapter(expected_source_commit="3" * 40),
                )
            )
            substitution_cases = {
                "external-adapter-caller-repository-substitution": {
                    "expected_source_repository": "OtherOrg/other-repository"
                },
                "external-adapter-called-workflow-san-substitution": {
                    "expected_certificate_identity": (
                        "https://github.com/ByteDeskAI/bytedesk-agent-delivery/"
                        ".github/workflows/other-signer.yml@" + "4" * 40
                    )
                },
                "external-adapter-issuer-substitution": {
                    "expected_certificate_oidc_issuer": "https://issuer.example.invalid"
                },
                "external-adapter-trusted-root-digest-substitution": {
                    "expected_trusted_root_digest": "sha256:" + "5" * 64
                },
                "external-adapter-cosign-digest-substitution": {
                    "expected_cosign_digest": "sha256:" + "6" * 64
                },
            }
            for case_id, overrides in substitution_cases.items():
                cases.append(
                    expect_denial(
                        case_id,
                        lambda overrides=overrides: invoke_adapter(**overrides),
                    )
                )

            cli_evidence = root / "external-cli-evidence.json"
            cli_input = root / "external-cli-verification-input.json"
            cli_output = root / "external-cli-cosign-output.txt"
            cli_ledger = root / "external-cli-replay-ledger.jsonl"
            cli_command = [
                sys.executable,
                str(Path(__file__).with_name("verify_bundle.py")),
                "--bundle",
                str(args.bundle.absolute()),
                "--manifest",
                str(args.manifest.absolute()),
                "--expected-trust-policy-id",
                args.expected_trust_policy_id,
                "--expected-trust-policy-digest",
                args.expected_trust_policy_digest,
                "--trust-policy",
                str(args.trust_policy.absolute()),
                "--external-signing-request",
                str(args.request.absolute()),
                "--sigstore-bundle",
                str(sigstore_bundle),
                "--sigstore-trusted-root",
                str(trusted_root),
                "--expected-sigstore-trusted-root-digest",
                adapter_defaults["expected_trusted_root_digest"],
                "--expected-cosign-digest",
                adapter_defaults["expected_cosign_digest"],
                "--expected-source-commit",
                source_commit,
                "--verification-input-output",
                str(cli_input),
                "--cosign-verification-output",
                str(cli_output),
                "--external-adapter-conformance",
                "--expected-request-id",
                args.expected_request_id,
                "--expected-repository",
                args.expected_repository,
                "--expected-purpose",
                args.expected_purpose,
                "--expected-key-version",
                args.expected_key_version,
                "--expected-nonce",
                args.expected_nonce,
                "--expected-issued-at",
                args.expected_issued_at,
                "--expected-expires-at",
                args.expected_expires_at,
                "--verification-time",
                args.verification_time,
                "--replay-ledger",
                str(cli_ledger),
                "--allow-test-local-replay-ledger",
                "--evidence",
                str(cli_evidence),
            ]
            completed = subprocess.run(
                cli_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                env=dict(os.environ),
                timeout=180,
            )
            if completed.returncode != 0:
                raise ContractToolError(
                    f"external Adapter CLI baseline failed (exit {completed.returncode})"
                )
            cli_result, _ = load_json_bytes(cli_evidence)
            expected_cli_evidence = {
                "verificationMode": "external_adapter_conformance",
                "signatureAuthenticated": True,
                "authorityIssued": False,
                "authorityOutcome": "not_issued",
                "verificationResultDigest": None,
                "outcome": "adapter_conformance_pass",
            }
            if any(cli_result.get(key) != value for key, value in expected_cli_evidence.items()):
                raise ContractToolError("external Adapter CLI authority evidence is ambiguous")
            if not cli_input.is_file() or not cli_output.is_file():
                raise ContractToolError("external Adapter CLI omitted conformance outputs")
            cases.append(
                {
                    "id": "external-adapter-cli-mode-and-authority-boundary",
                    "outcome": "pass",
                }
            )

            forbidden_result = root / "forbidden-verification-result.json"
            forbidden_command = list(cli_command)
            evidence_position = forbidden_command.index("--evidence")
            del forbidden_command[evidence_position : evidence_position + 2]
            replacements = {
                str(cli_input): str(root / "forbidden-verification-input.json"),
                str(cli_output): str(root / "forbidden-cosign-output.txt"),
                str(cli_ledger): str(root / "forbidden-result-ledger.jsonl"),
            }
            forbidden_command = [replacements.get(value, value) for value in forbidden_command]
            forbidden_command.extend(
                ["--verification-result-output", str(forbidden_result)]
            )
            denied = subprocess.run(
                forbidden_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                env=dict(os.environ),
                timeout=180,
            )
            if (
                denied.returncode == 0
                or forbidden_result.exists()
                or b"cannot mint a production verification result" not in denied.stdout
            ):
                raise ContractToolError("repository CLI minted a forbidden verification result")
            cases.append(
                {"id": "external-adapter-cli-forbids-authority-result", "outcome": "denied"}
            )
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path

    result = {
        "profile": "bytedesk.contract-supply-chain-security-conformance/1",
        "caseCount": len(cases),
        "cases": cases,
        "externalVerifierPrivateKeyUsed": False,
        "localReplayAuthority": "test-only-non-global",
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BundleProfileError, ContractToolError, OSError) as error:
        print(f"supply-chain security conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
