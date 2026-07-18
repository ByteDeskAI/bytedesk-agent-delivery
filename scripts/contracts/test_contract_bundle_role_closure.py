#!/usr/bin/env python3
"""Prove contract-bundle media and policy roles remain schema-closed."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable

from contractlib import ContractToolError, REPOSITORY_ROOT, SCHEMAS_ROOT, load_json, write_json


SCHEMA_PREFIX = "https://schemas.bytedesk.ai/agent-delivery/v1/"
COMMON_SCHEMA_ID = f"{SCHEMA_PREFIX}common/1.0.0"
CONTRACT_BUNDLE_SCHEMA_ID = f"{SCHEMA_PREFIX}contract-bundle/1.0.0"
CONTRACT_BUNDLE_MEDIA_TYPE = "application/vnd.bytedesk.agent.contract-bundle.v1+json"
LEGACY_CONTRACT_BUNDLE_MEDIA_TYPE = "application/vnd.bytedesk.agent.contract-bundle.v1+tar"
CONTRACT_BUNDLE_POLICY_ID = "contract-bundle-release-v1"
PRODUCT_POLICY_ID = "product-release-v1"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


ROLE_FIXTURES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "product-distribution",
        f"{SCHEMA_PREFIX}product-distribution-manifest/1.0.0",
        "contracts/fixtures/schema/positive/product-distribution-manifest__current.json",
        ("contractBundle",),
    ),
    (
        "product-release",
        f"{SCHEMA_PREFIX}product-release-manifest/1.0.0",
        "contracts/fixtures/schema/positive/product-release-manifest__current.json",
        ("contractBundle",),
    ),
    (
        "renderer-qualification-selection",
        f"{SCHEMA_PREFIX}renderer-qualification-selection/1.0.0",
        "contracts/fixtures/schema/positive/renderer-qualification-selection__native-amd64.json",
        ("contractBundle",),
    ),
    (
        "renderer-qualification-suite",
        f"{SCHEMA_PREFIX}renderer-qualification-suite/1.0.0",
        "contracts/fixtures/operations/renderer-cas/qualification-suite.json",
        ("contractBundle",),
    ),
    (
        "private-compilation-input",
        f"{SCHEMA_PREFIX}private-compilation-input/1.0.0",
        "contracts/fixtures/schema/positive/private-compilation-input__complete-lock.json",
        ("inputs", "contractBundle"),
    ),
    (
        "operational-readiness",
        f"{SCHEMA_PREFIX}operational-readiness-report/1.0.0",
        "contracts/fixtures/schema/positive/operational-readiness-report__ga-denied.json",
        ("contractBundle",),
    ),
)

CONTRACT_BUNDLE_FIXTURE = (
    "contracts/fixtures/schema/positive/contract-bundle__offline.json"
)
QUALIFICATION_SUBJECT_SCHEMA_ID = (
    f"{SCHEMA_PREFIX}release-qualification-predicate/1.0.0"
)
QUALIFICATION_SUBJECT_FIXTURE = (
    "contracts/fixtures/operations/renderer-cas/"
    "contract-bundle-contract-bundle-compatibility-predicate.json"
)


def reject_network_retrieval(uri: str) -> Resource[Any]:
    raise NoSuchResource(ref=uri)


def iter_references(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str):
                yield child
            else:
                yield from iter_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_references(child)


def build_offline_schema_registry() -> tuple[Registry[Any], dict[str, dict[str, Any]]]:
    resources: list[tuple[str, Resource[Any]]] = []
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMAS_ROOT.glob("*.schema.json")):
        schema = load_json(path)
        if not isinstance(schema, dict):
            raise ContractToolError(f"schema root is not an object: {path}")
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id.startswith(SCHEMA_PREFIX):
            raise ContractToolError(f"schema has no stable Agent Delivery ID: {path}")
        if schema_id in schemas:
            raise ContractToolError(f"duplicate schema ID: {schema_id}")
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
        except (SchemaError, ValueError) as error:
            raise ContractToolError(
                f"invalid Draft 2020-12 schema {schema_id}: {error}"
            ) from error
        schemas[schema_id] = schema
        resources.append((schema_id, resource))
    if not schemas:
        raise ContractToolError("no Agent Delivery schemas found")

    registry = Registry(retrieve=reject_network_retrieval).with_resources(resources)
    for schema_id, schema in schemas.items():
        resolver = registry.resolver(schema_id)
        try:
            for reference in iter_references(schema):
                resolver.lookup(reference)
        except (NoSuchResource, Unresolvable) as error:
            raise ContractToolError(
                f"offline schema reference from {schema_id} is unresolved: {error}"
            ) from error
    return registry, schemas


def validator_for(
    schema_id: str,
    registry: Registry[Any],
    schemas: dict[str, dict[str, Any]],
) -> Draft202012Validator:
    try:
        schema = schemas[schema_id]
    except KeyError as error:
        raise ContractToolError(f"required schema is absent: {schema_id}") from error
    return Draft202012Validator(
        schema,
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def fragment_validator(reference: str, registry: Registry[Any]) -> Draft202012Validator:
    return Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": reference,
        },
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def sorted_errors(
    validator: Draft202012Validator, instance: Any
) -> list[ValidationError]:
    return sorted(
        validator.iter_errors(instance),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )


def permit(
    cases: list[dict[str, str]],
    case_id: str,
    validator: Draft202012Validator,
    instance: Any,
) -> None:
    errors = sorted_errors(validator, instance)
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise ContractToolError(
            f"{case_id}: expected permit, rejected at {location}: {first.message}"
        )
    cases.append({"id": case_id, "outcome": "permitted"})


def deny(
    cases: list[dict[str, str]],
    case_id: str,
    validator: Draft202012Validator,
    instance: Any,
) -> None:
    errors = sorted_errors(validator, instance)
    if not errors:
        raise ContractToolError(f"{case_id}: expected denial, mutation was accepted")
    cases.append(
        {
            "id": case_id,
            "outcome": "denied",
            "keyword": str(errors[0].validator),
        }
    )


def at_path(document: Any, path: Sequence[str | int]) -> Any:
    current = document
    for part in path:
        try:
            current = current[part]
        except (KeyError, IndexError, TypeError) as error:
            rendered = "/".join(str(item) for item in path)
            raise ContractToolError(f"fixture is missing required path {rendered}") from error
    return current


def require_contract_bundle_descriptor(
    document: Any, path: Sequence[str | int], fixture_path: str
) -> dict[str, Any]:
    descriptor = at_path(document, path)
    if not isinstance(descriptor, dict):
        raise ContractToolError(f"fixture contractBundle is not an object: {fixture_path}")
    if descriptor.get("mediaType") != CONTRACT_BUNDLE_MEDIA_TYPE:
        raise ContractToolError(
            f"fixture contractBundle has stale media type: {fixture_path}"
        )
    trust_policy = descriptor.get("trustPolicy")
    if (
        not isinstance(trust_policy, dict)
        or trust_policy.get("id") != CONTRACT_BUNDLE_POLICY_ID
    ):
        raise ContractToolError(
            f"fixture contractBundle has stale trust policy: {fixture_path}"
        )
    return descriptor


def product_policy_substitution(document: Any, path: Sequence[str | int]) -> Any:
    mutated = deepcopy(document)
    descriptor = at_path(mutated, path)
    descriptor["trustPolicy"]["id"] = PRODUCT_POLICY_ID
    return mutated


def load_fixture(relative_path: str) -> dict[str, Any]:
    document = load_json(REPOSITORY_ROOT / relative_path)
    if not isinstance(document, dict):
        raise ContractToolError(f"fixture root is not an object: {relative_path}")
    return document


def artifact_descriptor(*, media_type: str, policy_id: str) -> dict[str, Any]:
    return {
        "repository": "registry.example/product/contracts",
        "digest": SHA_A,
        "mediaType": media_type,
        "size": 128,
        "trustPolicy": {"id": policy_id, "digest": SHA_B},
    }


def evidence_blob_descriptor(*, media_type: str) -> dict[str, Any]:
    return {
        "repository": "registry.example/product/contract-evidence",
        "digest": SHA_A,
        "mediaType": media_type,
        "size": 128,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    registry, schemas = build_offline_schema_registry()
    cases: list[dict[str, str]] = []

    generic_descriptor_validator = fragment_validator(
        f"{COMMON_SCHEMA_ID}#/$defs/artifactDescriptor", registry
    )
    canonical_descriptor = artifact_descriptor(
        media_type=CONTRACT_BUNDLE_MEDIA_TYPE,
        policy_id=CONTRACT_BUNDLE_POLICY_ID,
    )
    permit(
        cases,
        "common-artifact-contract-json-contract-policy",
        generic_descriptor_validator,
        canonical_descriptor,
    )
    deny(
        cases,
        "common-artifact-contract-json-product-policy",
        generic_descriptor_validator,
        artifact_descriptor(
            media_type=CONTRACT_BUNDLE_MEDIA_TYPE,
            policy_id=PRODUCT_POLICY_ID,
        ),
    )
    for policy_id, suffix in (
        (CONTRACT_BUNDLE_POLICY_ID, "contract-policy"),
        (PRODUCT_POLICY_ID, "product-policy"),
    ):
        deny(
            cases,
            f"common-artifact-legacy-contract-tar-{suffix}",
            generic_descriptor_validator,
            artifact_descriptor(
                media_type=LEGACY_CONTRACT_BUNDLE_MEDIA_TYPE,
                policy_id=policy_id,
            ),
        )
    deny(
        cases,
        "common-artifact-contract-policy-on-non-contract-media",
        generic_descriptor_validator,
        artifact_descriptor(
            media_type="application/vnd.dev.sigstore.bundle.v0.3+json",
            policy_id=CONTRACT_BUNDLE_POLICY_ID,
        ),
    )

    evidence_descriptor_validator = fragment_validator(
        f"{COMMON_SCHEMA_ID}#/$defs/evidenceBlobDescriptor", registry
    )
    signing_request_evidence = evidence_blob_descriptor(
        media_type="application/vnd.bytedesk.agent.signing-request.v1+json"
    )
    permit(
        cases,
        "evidence-blob-signing-request-positive",
        evidence_descriptor_validator,
        signing_request_evidence,
    )
    permit(
        cases,
        "evidence-blob-sigstore-bundle-positive",
        evidence_descriptor_validator,
        evidence_blob_descriptor(
            media_type="application/vnd.dev.sigstore.bundle.v0.3+json"
        ),
    )
    evidence_with_policy = deepcopy(signing_request_evidence)
    evidence_with_policy["trustPolicy"] = {
        "id": CONTRACT_BUNDLE_POLICY_ID,
        "digest": SHA_B,
    }
    deny(
        cases,
        "evidence-blob-trust-policy-smuggling",
        evidence_descriptor_validator,
        evidence_with_policy,
    )

    bundle = load_fixture(CONTRACT_BUNDLE_FIXTURE)
    if bundle.get("trustPolicy", {}).get("id") != CONTRACT_BUNDLE_POLICY_ID:
        raise ContractToolError(
            f"contract-bundle fixture has stale root trust policy: {CONTRACT_BUNDLE_FIXTURE}"
        )
    if not isinstance(bundle.get("schemas"), list) or not bundle["schemas"]:
        raise ContractToolError("contract-bundle fixture has no schema members")
    if bundle["schemas"][0].get("trustPolicy", {}).get("id") != CONTRACT_BUNDLE_POLICY_ID:
        raise ContractToolError(
            "contract-bundle fixture has stale schema-member trust policy: "
            f"{CONTRACT_BUNDLE_FIXTURE}"
        )
    bundle_validator = validator_for(CONTRACT_BUNDLE_SCHEMA_ID, registry, schemas)
    permit(cases, "contract-bundle-positive", bundle_validator, bundle)

    root_substitution = deepcopy(bundle)
    root_substitution["trustPolicy"]["id"] = PRODUCT_POLICY_ID
    deny(
        cases,
        "contract-bundle-root-product-policy-substitution",
        bundle_validator,
        root_substitution,
    )
    member_substitution = deepcopy(bundle)
    member_substitution["schemas"][0]["trustPolicy"]["id"] = PRODUCT_POLICY_ID
    deny(
        cases,
        "contract-bundle-schema-member-product-policy-substitution",
        bundle_validator,
        member_substitution,
    )

    fixture_paths = {CONTRACT_BUNDLE_FIXTURE}
    for role, schema_id, fixture_path, descriptor_path in ROLE_FIXTURES:
        fixture = load_fixture(fixture_path)
        require_contract_bundle_descriptor(fixture, descriptor_path, fixture_path)
        role_validator = validator_for(schema_id, registry, schemas)
        permit(cases, f"{role}-positive", role_validator, fixture)
        deny(
            cases,
            f"{role}-product-policy-substitution",
            role_validator,
            product_policy_substitution(fixture, descriptor_path),
        )
        fixture_paths.add(fixture_path)

    qualification_subject = load_fixture(QUALIFICATION_SUBJECT_FIXTURE)
    if qualification_subject.get("subjectRole") != "contract_bundle":
        raise ContractToolError(
            "qualification subject fixture is not the contract_bundle polymorphic role"
        )
    require_contract_bundle_descriptor(
        qualification_subject, ("subject",), QUALIFICATION_SUBJECT_FIXTURE
    )
    qualification_validator = validator_for(
        QUALIFICATION_SUBJECT_SCHEMA_ID, registry, schemas
    )
    permit(
        cases,
        "qualification-contract-bundle-subject-positive",
        qualification_validator,
        qualification_subject,
    )
    deny(
        cases,
        "qualification-contract-bundle-subject-product-policy-substitution",
        qualification_validator,
        product_policy_substitution(qualification_subject, ("subject",)),
    )
    fixture_paths.add(QUALIFICATION_SUBJECT_FIXTURE)

    result = {
        "profile": "bytedesk.contract-bundle-role-closure-conformance/1",
        "schemaCount": len(schemas),
        "fixtureCount": len(fixture_paths),
        "caseCount": len(cases),
        "cases": cases,
        "offlineReferenceResolution": "pass",
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
