#!/usr/bin/env python3
"""Exercise fail-closed official OpenAPI and AsyncAPI validator boundaries."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable

from contractlib import ContractToolError, load_json, write_json
from lint_projections import (
    ASYNCAPI_OFFICIAL_SCHEMA_ID,
    ASYNCAPI_OFFICIAL_SCHEMA_PATH,
    ASYNCAPI_PATH,
    EVENT_TYPES_PATH,
    OPENAPI_DOCUMENT_URI,
    OPENAPI_OFFICIAL_SCHEMA_ID,
    OPENAPI_OFFICIAL_SCHEMA_PATH,
    OPENAPI_PATH,
    PINNED_VENDOR_FILES,
    check_asyncapi_topology,
    check_event_registry_bindings,
    check_openapi_topology,
    load_pinned_projection_schema,
    projection_schema_resources,
    require_offline_projection_references,
    validate_official_asyncapi,
    validate_official_openapi,
)
from referencing.jsonschema import DRAFT7


def expect_denial(
    cases: list[dict[str, str]],
    case_id: str,
    operation: Callable[[], Any],
    expected_message: str,
) -> None:
    try:
        operation()
    except ContractToolError as error:
        if expected_message not in str(error):
            raise ContractToolError(
                f"unexpected official projection denial for {case_id}: {error}"
            ) from error
        cases.append({"id": case_id, "outcome": "denied"})
    else:
        raise ContractToolError(
            f"official projection denial unexpectedly passed: {case_id}"
        )


def network_reference_probe() -> None:
    schema = load_pinned_projection_schema(
        ASYNCAPI_OFFICIAL_SCHEMA_PATH,
        PINNED_VENDOR_FILES[ASYNCAPI_OFFICIAL_SCHEMA_PATH],
        ASYNCAPI_OFFICIAL_SCHEMA_ID,
        "AsyncAPI",
    )
    mutated = deepcopy(schema)
    mutated.setdefault("allOf", []).append(
        {"$ref": "https://network.invalid/forbidden-projection-schema.json"}
    )
    registry, _ = projection_schema_resources(mutated, DRAFT7, "AsyncAPI probe")
    require_offline_projection_references(
        mutated, registry, ASYNCAPI_OFFICIAL_SCHEMA_ID, "AsyncAPI probe"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    openapi = load_json(OPENAPI_PATH)
    asyncapi = load_json(ASYNCAPI_PATH)
    validate_official_openapi(openapi)
    validate_official_asyncapi(asyncapi)
    check_openapi_topology(openapi)
    check_asyncapi_topology(asyncapi)
    cases = [
        {"id": "official-openapi-baseline", "outcome": "permitted"},
        {"id": "official-asyncapi-baseline", "outcome": "permitted"},
    ]

    mutated_openapi = deepcopy(openapi)
    mutated_openapi["authority"] = "smuggled"
    expect_denial(
        cases,
        "official-openapi-unknown-root-field",
        lambda: validate_official_openapi(mutated_openapi),
        "official OpenAPI schema rejected projection",
    )

    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["$self"] = OPENAPI_DOCUMENT_URI
    expect_denial(
        cases,
        "official-asyncapi-rejects-openapi-self",
        lambda: validate_official_asyncapi(mutated_asyncapi),
        "official AsyncAPI schema rejected projection",
    )

    expect_denial(
        cases,
        "official-openapi-corrupt-vendor-digest",
        lambda: load_pinned_projection_schema(
            OPENAPI_OFFICIAL_SCHEMA_PATH,
            "sha256:" + "0" * 64,
            OPENAPI_OFFICIAL_SCHEMA_ID,
            "OpenAPI",
        ),
        "official schema digest mismatch",
    )
    expect_denial(
        cases,
        "official-schema-network-retrieval",
        network_reference_probe,
        "forbidden network retrieval",
    )

    mutated_openapi = deepcopy(openapi)
    del mutated_openapi["paths"]["/v1/commands"]
    expect_denial(
        cases,
        "openapi-commands-path-removal",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI path/method topology drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/command-submissions"] = mutated_openapi["paths"].pop(
        "/v1/commands"
    )
    expect_denial(
        cases,
        "openapi-commands-path-rename",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI path/method topology drift",
    )
    mutated_openapi = deepcopy(openapi)
    del mutated_openapi["paths"]["/v1/targets/{targetId}/observations"]
    expect_denial(
        cases,
        "openapi-append-observation-removal",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI path/method topology drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/targets/{targetId}/observations"]["post"][
        "operationId"
    ] = "appendTargetEvidence"
    expect_denial(
        cases,
        "openapi-append-observation-operation-rename",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation identity drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/actions/{actionId}"]["get"]["security"] = []
    expect_denial(
        cases,
        "openapi-operation-security-drift",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation security drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["servers"][0]["url"] = "https://alternate.invalid"
    expect_denial(
        cases,
        "openapi-root-server-drift",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI server topology drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/actions/{actionId}"]["get"]["servers"] = [
        {"url": "https://alternate.invalid"}
    ]
    expect_denial(
        cases,
        "openapi-operation-server-override",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation semantic topology drift for getAction",
    )
    mutated_openapi = deepcopy(openapi)
    del mutated_openapi["paths"]["/v1/commands"]["post"]["responses"]["202"]
    expect_denial(
        cases,
        "openapi-operation-response-drift",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation response topology drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/commands"]["post"]["responses"]["202"] = {
        "$ref": "#/components/responses/Problem"
    }
    expect_denial(
        cases,
        "openapi-operation-response-reference-drift",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation response topology drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["securitySchemes"]["consumerBearer"][
        "type"
    ] = "apiKey"
    expect_denial(
        cases,
        "openapi-security-scheme-drift",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI security scheme topology drift",
    )

    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["schemas"]["Action"] = deepcopy(
        openapi["components"]["schemas"]["Candidate"]
    )
    expect_denial(
        cases,
        "openapi-schema-component-identity-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI schema component topology drift for Action",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/actions/{actionId}"]["get"]["parameters"][0] = {
        "$ref": "#/components/parameters/CandidateId"
    }
    expect_denial(
        cases,
        "openapi-operation-parameter-reference-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation parameter topology drift for getAction",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/actions/{actionId}"]["parameters"] = [
        {"$ref": "#/components/parameters/CandidateId"}
    ]
    expect_denial(
        cases,
        "openapi-path-level-parameter-added",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI path item topology drift at /v1/actions/{actionId}",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/commands"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"] = {"$ref": "#/components/schemas/Observation"}
    expect_denial(
        cases,
        "openapi-operation-request-schema-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation request body topology drift for submitCommand",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/commands"]["post"]["requestBody"][
        "required"
    ] = False
    expect_denial(
        cases,
        "openapi-operation-request-required-drift",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation request body topology drift for submitCommand",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["responses"]["Action"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/Candidate"}
    expect_denial(
        cases,
        "openapi-response-component-schema-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI response component topology drift for Action",
    )
    mutated_openapi = deepcopy(openapi)
    action_content = mutated_openapi["components"]["responses"]["Action"]["content"]
    action_content["application/problem+json"] = action_content.pop("application/json")
    expect_denial(
        cases,
        "openapi-response-component-media-type-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI response component topology drift for Action",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["responses"]["Action"]["headers"]["ETag"] = {
        "$ref": "#/components/headers/Location"
    }
    expect_denial(
        cases,
        "openapi-response-component-header-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI response component topology drift for Action",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["parameters"]["ActionId"] = deepcopy(
        openapi["components"]["parameters"]["CandidateId"]
    )
    expect_denial(
        cases,
        "openapi-parameter-component-identity-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI parameter component topology drift for ActionId",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["headers"]["ETag"]["schema"] = deepcopy(
        openapi["components"]["headers"]["Location"]["schema"]
    )
    expect_denial(
        cases,
        "openapi-header-component-schema-substitution",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI header component topology drift for ETag",
    )

    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/targets/{targetId}/state"]["get"][
        "parameters"
    ].append({"$ref": "#/components/parameters/LastEventId"})
    expect_denial(
        cases,
        "openapi-last-event-id-on-ordinary-state-get",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation parameter topology drift for getTargetDeliveryState",
    )
    mutated_openapi = deepcopy(openapi)
    stream_content = mutated_openapi["components"]["responses"][
        "TargetEventStream"
    ]["content"]
    stream_content["application/json"] = stream_content.pop("text/event-stream")
    expect_denial(
        cases,
        "openapi-target-watch-not-sse",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI response component topology drift for TargetEventStream",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/targets/{targetId}/events"]["get"][
        "x-bytedesk-sse"
    ]["durableActionDisconnect"] = "cancel-action"
    expect_denial(
        cases,
        "openapi-sse-disconnect-cancels-durable-action",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI target event SSE profile drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/targets/{targetId}/capability-evidence"][
        "post"
    ]["security"] = [{"targetReconcilerBearer": []}]
    expect_denial(
        cases,
        "openapi-capability-evidence-wrong-mtls-identity",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI operation security drift for appendCapabilityEvidence",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["paths"]["/v1/targets/{targetId}/capability-evidence"][
        "post"
    ]["x-bytedesk-authority"]["promotionAuthority"] = True
    expect_denial(
        cases,
        "openapi-capability-evidence-promotion-authority",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI capability evidence authority boundary drift",
    )
    mutated_openapi = deepcopy(openapi)
    mutated_openapi["components"]["schemas"]["CapabilityEvidenceIntake"][
        "additionalProperties"
    ] = True
    expect_denial(
        cases,
        "openapi-capability-evidence-request-opened",
        lambda: check_openapi_topology(mutated_openapi),
        "OpenAPI protocol schema component topology drift for CapabilityEvidenceIntake",
    )
    mutated_event_types = deepcopy(load_json(EVENT_TYPES_PATH))
    mutated_event_types["eventTypes"][0]["resourceSchemaDigest"] = "sha256:" + "0" * 64
    expect_denial(
        cases,
        "event-registry-stale-resource-schema-digest",
        lambda: check_event_registry_bindings(mutated_event_types, openapi),
        "event type resource schema digest drift",
    )

    mutated_asyncapi = deepcopy(asyncapi)
    del mutated_asyncapi["servers"]["consumerWebhook"]
    expect_denial(
        cases,
        "asyncapi-consumer-webhook-removal",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI server topology drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["servers"]["renamedWebhook"] = mutated_asyncapi["servers"].pop(
        "consumerWebhook"
    )
    expect_denial(
        cases,
        "asyncapi-consumer-webhook-rename",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI server topology drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["servers"]["consumerWebhook"]["security"] = [
        {"$ref": "#/components/securitySchemes/consumerBearer"}
    ]
    expect_denial(
        cases,
        "asyncapi-consumer-webhook-security-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI server security drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["channels"]["notifications"]["address"] = "/v1/renamed-events"
    expect_denial(
        cases,
        "asyncapi-notification-channel-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI channel topology drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["channels"]["notifications"]["servers"] = [
        {"$ref": "#/servers/consumerFeed"}
    ]
    expect_denial(
        cases,
        "asyncapi-notification-channel-server-removal",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI channel topology drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    del mutated_asyncapi["operations"]["receiveNotifications"]
    expect_denial(
        cases,
        "asyncapi-notification-operation-removal",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI operation topology drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["operations"]["renamedNotifications"] = mutated_asyncapi[
        "operations"
    ].pop("receiveNotifications")
    expect_denial(
        cases,
        "asyncapi-notification-operation-rename",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI operation topology drift",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["components"]["securitySchemes"]["mutualTLS"]["type"] = "apiKey"
    expect_denial(
        cases,
        "asyncapi-security-scheme-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI security scheme topology drift",
    )

    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["components"]["schemas"]["EventDataEnvelope"] = deepcopy(
        openapi["components"]["schemas"]["Action"]
    )
    expect_denial(
        cases,
        "asyncapi-schema-component-identity-substitution",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI schema component topology drift for EventDataEnvelope",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["payload"]["properties"]["data"] = {
        "$ref": "../../schemas/v1/action.schema.json"
    }
    expect_denial(
        cases,
        "asyncapi-message-data-schema-substitution",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["payload"]["properties"]["specversion"]["const"] = "1.1"
    expect_denial(
        cases,
        "asyncapi-message-specversion-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["payload"]["properties"]["dataschema"][
        "const"
    ] = "https://schemas.bytedesk.ai/agent-delivery/v1/action/1.0.0"
    expect_denial(
        cases,
        "asyncapi-message-dataschema-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["payload"]["properties"]["type"]["enum"] = message["payload"][
        "properties"
    ]["type"]["enum"][:-1]
    expect_denial(
        cases,
        "asyncapi-message-event-type-enum-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["payload"]["required"].remove("data")
    expect_denial(
        cases,
        "asyncapi-message-required-envelope-member-removal",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["x-bytedesk-data-schema-digest"] = "sha256:" + "0" * 64
    expect_denial(
        cases,
        "asyncapi-message-schema-metadata-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["contentType"] = "application/json"
    expect_denial(
        cases,
        "asyncapi-message-content-type-drift",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    message = mutated_asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    message["payload"]["additionalProperties"] = True
    expect_denial(
        cases,
        "asyncapi-message-envelope-opened",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift for AgentDeliveryNotification",
    )
    mutated_asyncapi = deepcopy(asyncapi)
    mutated_asyncapi["components"]["messages"]["AlternativeNotification"] = deepcopy(
        asyncapi["components"]["messages"]["AgentDeliveryNotification"]
    )
    expect_denial(
        cases,
        "asyncapi-message-component-added",
        lambda: check_asyncapi_topology(mutated_asyncapi),
        "AsyncAPI message component topology drift",
    )

    result = {
        "profile": "bytedesk.official-projection-validator-conformance/1",
        "caseCount": len(cases),
        "cases": cases,
        "outcome": "pass",
    }
    if args.evidence:
        write_json(args.evidence, result)
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractToolError as error:
        print(f"official projection validator conformance failed: {error}", file=sys.stderr)
        raise SystemExit(1)
