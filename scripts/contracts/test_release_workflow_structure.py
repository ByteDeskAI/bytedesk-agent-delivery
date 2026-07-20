#!/usr/bin/env python3
"""Freeze the privilege and sealed-tool boundary of contract release workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable

from contractlib import ContractToolError, REPOSITORY_ROOT, write_json


CALLER = REPOSITORY_ROOT / ".github" / "workflows" / "contract-release.yml"
SIGNER = REPOSITORY_ROOT / ".github" / "workflows" / "contract-release-signer.yml"
CONTRACTS_CI = REPOSITORY_ROOT / ".github" / "workflows" / "contracts.yml"
ZERO_PIN = "0" * 40


def reusable_workflow_pin(caller: str) -> str:
    match = re.search(
        r"uses: ByteDeskAI/bytedesk-agent-delivery/\.github/workflows/"
        r"contract-release-signer\.yml@([0-9a-f]{40})",
        caller,
    )
    if match is None:
        raise ContractToolError("release caller does not use an exact reusable-workflow SHA")
    return match.group(1)


def shell_run_blocks(workflow: str) -> str:
    """Return literal shell bodies without treating action inputs as YAML."""

    lines = workflow.splitlines()
    bodies: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)run:\s*\|\s*$", lines[index])
        if match is None:
            index += 1
            continue
        base_indent = len(match.group(1))
        index += 1
        while index < len(lines):
            line = lines[index]
            indentation = len(line) - len(line.lstrip())
            if line.strip() and indentation <= base_indent:
                break
            bodies.append(line)
            index += 1
    return "\n".join(bodies)


def validate_full_history_checkout(workflow: str, workflow_name: str) -> None:
    if workflow.count("uses: actions/checkout@") != 1:
        raise ContractToolError(f"{workflow_name} must have exactly one source checkout")
    if "persist-credentials: false\n          fetch-depth: 0" not in workflow:
        raise ContractToolError(
            f"{workflow_name} must fetch full history for reusable-workflow pin verification"
        )


def validate_release_workflows(
    caller: str,
    signer: str,
    *,
    verify_activated_pin_bytes: bool = True,
) -> None:
    validate_full_history_checkout(caller, "release caller")
    pin = reusable_workflow_pin(caller)
    if pin != ZERO_PIN and verify_activated_pin_bytes:
        completed = subprocess.run(
            ["git", "show", f"{pin}:.github/workflows/contract-release-signer.yml"],
            cwd=REPOSITORY_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0 or completed.stdout.decode() != signer:
            raise ContractToolError(
                "activated reusable-workflow SHA does not contain the reviewed signer bytes"
            )
    if "secrets: inherit" in caller:
        raise ContractToolError("release caller exposes ambient secrets to the reusable signer")
    try:
        build_job = caller.split("  build-candidate:\n", 1)[1].split(
            "  sign-candidate:\n", 1
        )[0]
        sign_call = caller.split("  sign-candidate:\n", 1)[1]
    except IndexError as error:
        raise ContractToolError("release caller jobs are not structurally separated") from error
    if "id-token: write" in build_job:
        raise ContractToolError("candidate build job has OIDC signing permission")
    if "steps:" in sign_call:
        raise ContractToolError("privileged caller job can execute candidate-controlled steps")
    if "id-token: write" not in sign_call:
        raise ContractToolError("reusable signer call was not delegated OIDC permission")

    required_signer_fragments = (
        "workflow_call:",
        "environment: contract-release",
        "id-token: write",
        "CALLER_ARTIFACT_NAME: ${{ inputs.artifact-name }}",
        "CALLER_SOURCE_COMMIT: ${{ inputs.source-commit }}",
        "CALLER_SOURCE_REF: ${{ inputs.source-ref }}",
        "SCM_READ_TOKEN: ${{ github.token }}",
        '"https://api.github.com/repos/$GITHUB_REPOSITORY/git/commits/$CALLER_SOURCE_COMMIT"',
        '"https://api.github.com/repos/$GITHUB_REPOSITORY/tarball/$CALLER_SOURCE_COMMIT"',
        'EXPECTED_SNAPSHOT_URL="https://codeload.github.com/$GITHUB_REPOSITORY/legacy.tar.gz/$CALLER_SOURCE_COMMIT"',
        "--max-filesize 4194304",
        "--max-filesize 67108864",
        "CONTRACT_RELEASE_VERIFIER_IMAGE: ${{ vars.CONTRACT_RELEASE_VERIFIER_IMAGE }}",
        r"^ghcr\.io/bytedesk/agent-delivery-contract-release-tool@sha256:[a-f0-9]{64}$",
        "docker pull \"$CONTRACT_RELEASE_VERIFIER_IMAGE\"",
        "certify-contract-release-v1",
        "finalize-contract-release-v1",
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--expected-builder-digest \"$VERIFIER_DIGEST\"",
        "--expected-credential-kind sigstore_keyless",
        "--expected-signer-identity-digest \"$CONTRACT_RELEASE_SIGNER_IDENTITY_DIGEST\"",
        "--expected-trusted-root-digest \"$CONTRACT_RELEASE_SIGSTORE_TRUSTED_ROOT_DIGEST\"",
        '.purpose == "contract-bundle-release-v1"',
        ".preSignCertificationDigest == $certificationDigest",
        "(has(\"keyVersion\") | not)",
        "--expected-cosign-digest \"$CONTRACT_RELEASE_COSIGN_DIGEST\"",
        "--certificate-github-workflow-repository \"$GITHUB_REPOSITORY\"",
        "--certificate-github-workflow-ref \"$CALLER_SOURCE_REF\"",
        "--certificate-github-workflow-sha \"$CALLER_SOURCE_COMMIT\"",
        "--certificate-github-workflow-trigger workflow_dispatch",
        "require_regular_bounded candidate/agent-delivery-contracts-v1.manifest.sha256 256",
        "require_regular_bounded signed/agent-delivery-contracts-v1.sigstore.json 67108864",
        "--source-archive /source/source.tar.gz",
        "--source-commit-metadata /source/commit-metadata.json",
        "--expected-source-tree \"$SOURCE_TREE\"",
        "--expected-source-archive-digest \"$SOURCE_ARCHIVE_DIGEST\"",
        "--expected-source-metadata-digest \"$SOURCE_METADATA_DIGEST\"",
        "--source-archive-max-bytes 67108864",
        "--source-member-max-bytes 16777216",
        "--source-expanded-max-bytes 67108864",
        "--source-member-max-count 20000",
        "--source-path-profile bytedesk.portable-path/1",
        "--reject-source-links-and-special-files",
        "--require-source-metadata-match-before-extraction",
        "--require-source-tree-object-match",
        "--require-trusted-source-rebuild-match",
        "--mount type=bind,src=\"$PWD/signed\",dst=/signed,readonly",
        "require_regular_bounded final/release-signing-evidence.json 4194304",
        '.profile == "bytedesk.contract-bundle-release-signing-evidence/1"',
        '.verificationMode == "sigstore_contract_bundle_release"',
        ".contractBundleSignatureIssued == true",
        ".sourceLineage == {commit:$commit,tree:$tree,snapshotDigest:$snapshotDigest,commitMetadataDigest:$metadataDigest,safeExtractionProfile:\"bytedesk.portable-path/1\",treeObjectMatch:true,rebuildBundleDigest:$bundleDigest,rebuildManifestDigest:$manifestDigest,byteForByteCandidateMatch:true}",
        ".sourceLineageVerified == true",
        ".byteForByteSourceRebuildMatch == true",
        '.fullBundleNativeSemantics == true',
        ".consumerPermitIssued == false",
    )
    missing = [fragment for fragment in required_signer_fragments if fragment not in signer]
    if missing:
        raise ContractToolError(f"trusted signer workflow lacks sealed-boundary fragments: {missing}")
    forbidden_signer_fragments = (
        "actions/checkout@",
        "unsigned-structure-verification.json",
        "scripts/contracts/",
        "make verify",
        "uv run",
        "sigstore_product_release",
        "productReleaseSignatureIssued",
        "go run",
        "python ",
        "jq -cnS",
        "tar -x",
        "unzip ",
        "git clone",
        "git checkout",
        "--location",
        "--location-trusted",
        "CONTRACT_RELEASE_VERIFIER_IMAGE: ${{ inputs.",
    )
    present = [fragment for fragment in forbidden_signer_fragments if fragment in signer]
    if present:
        raise ContractToolError(
            f"trusted signer can execute candidate code or trust caller evidence: {present}"
        )
    if "${{ inputs." in shell_run_blocks(signer):
        raise ContractToolError(
            "trusted signer interpolates reusable-workflow input directly into shell"
        )
    if signer.count("docker run --rm") != 2:
        raise ContractToolError("trusted signer must use the sealed tool for pre/post signature phases")
    if signer.count("--network none") != 2 or signer.count("--read-only") != 2:
        raise ContractToolError("one sealed verifier phase is not hermetic/read-only")
    if signer.count('src="$PWD/source",dst=/source,readonly') != 2:
        raise ContractToolError("exact source snapshot is not read-only in both sealed phases")
    if signer.count("--require-trusted-source-rebuild-match") != 2:
        raise ContractToolError("trusted source rebuild equality is not required twice")
    if signer.count("--require-source-metadata-match-before-extraction") != 2:
        raise ContractToolError("source commit metadata is not checked before both rebuilds")
    if signer.count("--require-source-tree-object-match") != 2:
        raise ContractToolError("source tree identity is not recomputed in both sealed phases")
    if signer.count("--expected-credential-kind sigstore_keyless") != 2:
        raise ContractToolError("both sealed phases must require the keyless credential kind")
    if signer.count(
        '--expected-signer-identity-digest "$CONTRACT_RELEASE_SIGNER_IDENTITY_DIGEST"'
    ) != 2:
        raise ContractToolError("both sealed phases must pin the signer identity digest")
    if signer.count(
        '--expected-trusted-root-digest "$CONTRACT_RELEASE_SIGSTORE_TRUSTED_ROOT_DIGEST"'
    ) != 2:
        raise ContractToolError("both sealed phases must pin the trusted-root digest")
    if re.search(
        r"CONTRACT_RELEASE_VERIFIER_IMAGE.*(?:^|:)latest(?:$|\s)", signer, re.MULTILINE
    ):
        raise ContractToolError("trusted release verifier image is tag-selected")


def expect_denial(
    case_id: str,
    caller: str,
    signer: str,
    mutation: Callable[[str, str], tuple[str, str]],
) -> dict[str, str]:
    mutated_caller, mutated_signer = mutation(caller, signer)
    try:
        # The baseline separately binds the activated pin to the reviewed signer
        # bytes. Mutation cases disable that outer binding check so each sealed
        # boundary invariant is exercised instead of being masked by the first
        # byte mismatch.
        validate_release_workflows(
            mutated_caller,
            mutated_signer,
            verify_activated_pin_bytes=False,
        )
    except ContractToolError as error:
        return {"id": case_id, "outcome": "denied", "reason": str(error)}
    raise ContractToolError(f"release workflow mutation unexpectedly passed: {case_id}")


def expect_ci_denial(
    case_id: str,
    workflow: str,
    mutation: Callable[[str], str],
) -> dict[str, str]:
    try:
        validate_full_history_checkout(mutation(workflow), "contracts CI")
    except ContractToolError as error:
        return {"id": case_id, "outcome": "denied", "reason": str(error)}
    raise ContractToolError(f"contracts workflow mutation unexpectedly passed: {case_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    caller = CALLER.read_text(encoding="utf-8")
    signer = SIGNER.read_text(encoding="utf-8")
    contracts_ci = CONTRACTS_CI.read_text(encoding="utf-8")
    validate_release_workflows(caller, signer)
    validate_full_history_checkout(contracts_ci, "contracts CI")
    initial_pin = reusable_workflow_pin(caller)
    activation_state = "bootstrap_fail_closed" if initial_pin == ZERO_PIN else "activated"
    cases: list[dict[str, str]] = [
        {
            "id": f"baseline-{activation_state.replace('_', '-')}-pin-and-sealed-signer",
            "outcome": "pass",
        },
        expect_ci_denial(
            "contracts-ci-shallow-checkout",
            contracts_ci,
            lambda value: value.replace("fetch-depth: 0", "fetch-depth: 1", 1),
        ),
    ]
    cases.extend(
        [
            expect_denial(
                "caller-unpinned-reusable-workflow",
                caller,
                signer,
                lambda c, s: (c.replace(initial_pin, "main", 1), s),
            ),
            expect_denial(
                "release-caller-shallow-checkout",
                caller,
                signer,
                lambda c, s: (c.replace("fetch-depth: 0", "fetch-depth: 1", 1), s),
            ),
            expect_denial(
                "candidate-build-gains-oidc",
                caller,
                signer,
                lambda c, s: (
                    c.replace("      contents: read\n    env:", "      contents: read\n      id-token: write\n    env:", 1),
                    s,
                ),
            ),
            expect_denial(
                "signer-checks-out-candidate-repository",
                caller,
                signer,
                lambda c, s: (c, s + "\n      - uses: actions/checkout@deadbeef\n"),
            ),
            expect_denial(
                "signer-trusts-caller-evidence",
                caller,
                signer,
                lambda c, s: (c, s + "\n# unsigned-structure-verification.json\n"),
            ),
            expect_denial(
                "signer-verifier-image-can-use-tag",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        r"^ghcr\.io/bytedesk/agent-delivery-contract-release-tool@sha256:[a-f0-9]{64}$",
                        r"^ghcr\.io/bytedesk/agent-delivery-contract-release-tool:latest$",
                    ),
                ),
            ),
            expect_denial(
                "sealed-pre-sign-network-enabled",
                caller,
                signer,
                lambda c, s: (c, s.replace("            --network none \\\n", "", 1)),
            ),
            expect_denial(
                "full-bundle-native-certifier-bypassed",
                caller,
                signer,
                lambda c, s: (c, s.replace("            certify-contract-release-v1 \\\n", "", 1)),
            ),
            expect_denial(
                "builder-digest-conflated-with-cosign",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        '--expected-builder-digest "$VERIFIER_DIGEST"',
                        '--expected-builder-digest "$CONTRACT_RELEASE_COSIGN_DIGEST"',
                    ),
                ),
            ),
            expect_denial(
                "contract-bundle-signing-purpose-not-bound",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        '.purpose == "contract-bundle-release-v1"',
                        "true",
                        1,
                    ),
                ),
            ),
            expect_denial(
                "keyless-request-allows-kms-key-version",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace('(has("keyVersion") | not)', "true", 1),
                ),
            ),
            expect_denial(
                "pre-sign-certification-not-bound-into-request",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        ".preSignCertificationDigest == $certificationDigest",
                        "true",
                        1,
                    ),
                ),
            ),
            expect_denial(
                "keyless-signer-identity-unpinned",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        '--expected-signer-identity-digest "$CONTRACT_RELEASE_SIGNER_IDENTITY_DIGEST"',
                        "--expected-signer-identity-digest unchecked",
                    ),
                ),
            ),
            expect_denial(
                "caller-sha-certificate-extension-unchecked",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        '--certificate-github-workflow-sha "$CALLER_SOURCE_COMMIT"',
                        "--certificate-github-workflow-sha unchecked",
                    ),
                ),
            ),
            expect_denial(
                "reusable-input-direct-shell-interpolation",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        '[[ "$CALLER_SOURCE_COMMIT" == "$GITHUB_SHA" ]]',
                        '[[ "${{ inputs.source-commit }}" == "$GITHUB_SHA" ]]',
                        1,
                    ),
                ),
            ),
            expect_denial(
                "trusted-source-rebuild-bypassed",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        "            --require-trusted-source-rebuild-match \\\n",
                        "",
                        1,
                    ),
                ),
            ),
            expect_denial(
                "source-snapshot-extracted-on-oidc-host",
                caller,
                signer,
                lambda c, s: (c, s + "\n# tar -xf source/source.tar.gz\n"),
            ),
            expect_denial(
                "source-tree-object-check-bypassed",
                caller,
                signer,
                lambda c, s: (
                    c,
                    s.replace(
                        "            --require-source-tree-object-match \\\n",
                        "",
                        1,
                    ),
                ),
            ),
            expect_denial(
                "authenticated-scm-redirect-followed",
                caller,
                signer,
                lambda c, s: (c, s + "\n# curl --location with bearer token\n"),
            ),
        ]
    )

    result = {
        "profile": "bytedesk.contract-release-workflow-boundary/1",
        "caseCount": len(cases),
        "cases": cases,
        "reusableWorkflowPin": initial_pin,
        "activationState": activation_state,
        "signerCheckout": False,
        "candidateEvidenceIsAuthority": False,
        "sealedVerifierPhases": 2,
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
        print(f"release workflow boundary conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
