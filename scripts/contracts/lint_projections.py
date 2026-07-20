#!/usr/bin/env python3
"""Fail-closed structural and offline-reference lint for API/event projections."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urljoin

from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable
from referencing.jsonschema import DRAFT7, DRAFT202012, Specification

from contractlib import (
    CONTRACTS_ROOT,
    REPOSITORY_ROOT,
    SCHEMAS_ROOT,
    ContractToolError,
    canonical_digest,
    file_digest,
    load_json,
    repository_path,
    validation_error_key,
    write_json,
)
from validate_schemas import build_registry


OPENAPI_PATH = CONTRACTS_ROOT / "openapi" / "v1" / "agent-delivery.openapi.json"
ASYNCAPI_PATH = CONTRACTS_ROOT / "asyncapi" / "v1" / "agent-delivery.asyncapi.json"
EVENT_TYPES_PATH = CONTRACTS_ROOT / "events" / "v1" / "event-types.json"
EVENT_CASES_PATH = CONTRACTS_ROOT / "events" / "v1" / "conformance-cases.json"
EVENT_EXAMPLES_ROOT = CONTRACTS_ROOT / "events" / "v1" / "examples"
EVENT_DATA_SCHEMA_ID = "https://schemas.bytedesk.ai/agent-delivery/v1/event-data/1.0.0"
OPENAPI_OFFICIAL_SCHEMA_PATH = (
    CONTRACTS_ROOT / "vendor" / "openapi" / "3.2.0" / "schema-2025-11-23.json"
)
ASYNCAPI_OFFICIAL_SCHEMA_PATH = (
    CONTRACTS_ROOT
    / "vendor"
    / "asyncapi"
    / "3.1.0"
    / "schema-e609fc2341007395d75df5756fc6fccf662c2087.json"
)
OPENAPI_OFFICIAL_SCHEMA_ID = "https://spec.openapis.org/oas/3.2/schema/2025-11-23"
ASYNCAPI_OFFICIAL_SCHEMA_ID = "http://asyncapi.com/definitions/3.1.0/asyncapi.json"
PINNED_VENDOR_FILES = {
    OPENAPI_OFFICIAL_SCHEMA_PATH: (
        "sha256:7d48f01f37eeae4799041b371ad5f533f9f533fd2b0caa1011a8ba27c5b48b70"
    ),
    CONTRACTS_ROOT / "vendor" / "openapi" / "3.2.0" / "LICENSE": (
        "sha256:4948367c65e1ce06690e2cadc6e86fce1a6a6db55ef874ce4b78c0f472ce5f13"
    ),
    ASYNCAPI_OFFICIAL_SCHEMA_PATH: (
        "sha256:51d3274899ad2875f25c18fd1aef4d5512f0a97be785d519740bde55a4162f61"
    ),
    CONTRACTS_ROOT / "vendor" / "asyncapi" / "3.1.0" / "LICENSE": (
        "sha256:43070e2d4e532684de521b885f385d0841030efa2b1a20bafb76133a5e1379c1"
    ),
    CONTRACTS_ROOT / "vendor" / "asyncapi" / "3.1.0" / "NOTICE": (
        "sha256:4f0425a69113106423aa95eded6c30811cb65898743b8da6dedf5b331e23a599"
    ),
}
EVENT_TYPE_ROOT_FIELDS = {
    "$schema",
    "profile",
    "cloudEventsVersion",
    "delivery",
    "ordering",
    "authority",
    "eventTypes",
    "registryCompatibility",
    "resynchronization",
}
EVENT_TYPE_ENTRY_FIELDS = {
    "type",
    "aggregateType",
    "resourceSchemaId",
    "resourceSchemaDigest",
    "resourceUriTemplate",
    "resynchronizeOperationId",
    "redaction",
}
EVENT_REGISTRY_COMPATIBILITY = (
    "Event type, resource schema ID and digest, URI template, redaction class, and "
    "resynchronization operation are immutable within v1."
)
EVENT_REGISTRY_RESYNCHRONIZATION = {
    "authority": "authenticated-api-read",
    "on": [
        "unknown-event-type",
        "unknown-schema-id-or-digest",
        "aggregate-sequence-gap",
        "etag-mismatch",
    ],
    "resumeAfter": "exact-resource-schema-and-etag-verified",
}
EVENT_REDACTION_CLASSES = {"consumer-private", "restricted"}
AGENT_DELIVERY_EVENT_TYPE_ENUM = [
    "ai.bytedesk.agent-delivery.installation.changed.v1",
    "ai.bytedesk.agent-delivery.action.changed.v1",
    "ai.bytedesk.agent-delivery.candidate.changed.v1",
    "ai.bytedesk.agent-delivery.rollout.changed.v1",
    "ai.bytedesk.agent-delivery.target-delivery-state.changed.v1",
    "ai.bytedesk.agent-delivery.observation.appended.v1",
    "ai.bytedesk.agent-delivery.receipt.appended.v1",
]
COMMAND_AUTHORIZATION_PROFILE = {
    "discriminator": "command",
    "publicPurposeCommands": ["source_validate", "render"],
    "privateDefault": "require-exact-consumer-and-operation-scope",
    "unknownCommand": "deny",
}
COMMAND_CONDITIONAL_REQUEST_PROFILE = {
    "discriminator": "precondition.kind",
    "notApplicableCommands": ["source_validate", "render"],
    "absent": {
        "requiredHeader": "If-None-Match",
        "requiredValue": "*",
        "forbiddenHeader": "If-Match",
    },
    "match": {
        "requiredHeader": "If-Match",
        "requiredValueFrom": "precondition.digest",
        "forbiddenHeader": "If-None-Match",
    },
    "missingOrConflicting": "deny",
}
OBSERVATION_CONDITIONAL_REQUEST_PROFILE = {
    "requiredHeader": "If-Match",
    "requiredValueFrom": "requestBody.desiredRevisionDigest",
    "valueEncoding": "quoted-strong-etag",
    "missingOrMismatch": "deny",
}
CAPABILITY_EVIDENCE_CONDITIONAL_REQUEST_PROFILE = {
    "requiredHeader": "If-None-Match",
    "requiredValue": "*",
    "forbiddenHeader": "If-Match",
    "missingOrMismatch": "deny",
}
CAPABILITY_EVIDENCE_AUTHORITY_PROFILE = {
    "profile": "bytedesk.capability-evidence-intake/1",
    "effect": "append-only-evidence",
    "desiredStateWrite": False,
    "promotionAuthority": False,
    "capabilityGrantAuthority": False,
    "absenceOrTransportFailureIsDenial": False,
}
TARGET_EVENT_SSE_PROFILE = {
    "profile": "bytedesk.target-events-sse/1",
    "itemMediaType": "application/cloudevents+json",
    "delivery": "at-least-once",
    "ordering": "per-aggregate-sequence",
    "resumeHeader": "Last-Event-ID",
    "eventId": "CloudEvent.id",
    "heartbeat": "comment-frame",
    "initialGap": "409-event_sequence_gap",
    "streamGap": "close-and-resynchronize",
    "resynchronizeOperationId": "resynchronizeTargetEvents",
    "authority": "notification-only",
    "durableActionDisconnect": "continues-until-terminal-or-explicit-cancel-command",
}
TARGET_EVENT_RESYNCHRONIZATION_PROFILE = {
    "profile": "bytedesk.target-event-resynchronization/1",
    "triggers": ["event_sequence_gap", "unknown_schema", "resume_token_rejected"],
    "result": "authoritative-target-state-plus-sequence-and-resume-token",
    "resume": "reconnect-watchTargetEvents-with-returned-token",
    "authority": "read-only",
}
ACCEPTED_ACTION_HEADERS = {
    "ETag",
    "Location",
    "RateLimit-Limit",
    "RateLimit-Remaining",
    "RateLimit-Reset",
}
OPENAPI_ROOT_FIELDS = {
    "openapi",
    "$self",
    "info",
    "jsonSchemaDialect",
    "servers",
    "paths",
    "webhooks",
    "components",
    "security",
    "tags",
    "externalDocs",
}
ASYNCAPI_ROOT_FIELDS = {
    "asyncapi",
    "id",
    "info",
    "servers",
    "defaultContentType",
    "channels",
    "operations",
    "components",
}
OPENAPI_DOCUMENT_URI = (
    "https://contracts.bytedesk.ai/agent-delivery/openapi/v1/agent-delivery.openapi.json"
)
ASYNCAPI_DOCUMENT_URI = (
    "https://contracts.bytedesk.ai/agent-delivery/asyncapi/v1/agent-delivery.asyncapi.json"
)
EXTENSION_FIELD_PATTERN = re.compile(r"^x-[A-Za-z0-9][A-Za-z0-9._-]*$")
HEADER_OBJECT_FIELDS = {
    "description",
    "required",
    "deprecated",
    "example",
    "examples",
    "style",
    "explode",
    "schema",
    "content",
}
REFERENCE_OBJECT_FIELDS = {"$ref", "summary", "description"}
OPENAPI_HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
    "query",
}
OPENAPI_OPERATION_TOPOLOGY = {
    ("/v1/catalogs/{catalogId}/releases/{revision}", "get"): {
        "operationId": "getCatalogRelease",
        "security": [],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/CatalogIndex",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/sources/{sourceDigest}", "get"): {
        "operationId": "getAgentSource",
        "security": [],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/AgentSource",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/renderers/{rendererId}/releases/{rendererDigest}", "get"): {
        "operationId": "getRendererRelease",
        "security": [],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/RendererRelease",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/renders/{renderDigest}", "get"): {
        "operationId": "getHarnessRender",
        "security": [],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/HarnessRender",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/actions/{actionId}", "get"): {
        "operationId": "getAction",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/Action",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/installations/{installationId}", "get"): {
        "operationId": "getInstallation",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/Installation",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/candidates/{candidateId}", "get"): {
        "operationId": "getCandidate",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/Candidate",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/state", "get"): {
        "operationId": "getTargetDeliveryState",
        "security": [{"targetReconcilerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/TargetDeliveryState",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/events", "get"): {
        "operationId": "watchTargetEvents",
        "security": [{"targetReconcilerBearer": []}],
        "responses": {"200", "409", "default"},
        "responseRefs": {
            "200": "#/components/responses/TargetEventStream",
            "409": "#/components/responses/Problem",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/events/resync", "get"): {
        "operationId": "resynchronizeTargetEvents",
        "security": [{"targetReconcilerBearer": []}],
        "responses": {"200", "default"},
        "responseRefs": {
            "200": "#/components/responses/TargetEventResynchronization",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/capability-evidence", "post"): {
        "operationId": "appendCapabilityEvidence",
        "security": [{"capabilityVerifierMtls": []}],
        "responses": {"201", "default"},
        "responseRefs": {
            "201": "#/components/responses/CapabilityEvidenceReceipt",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/rollouts/{rolloutId}", "get"): {
        "operationId": "getRollout",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/Rollout",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/commands", "post"): {
        "operationId": "submitCommand",
        "security": [{"consumerBearer": []}],
        "responses": {"202", "default"},
        "responseRefs": {
            "202": "#/components/responses/AcceptedAction",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/observations", "post"): {
        "operationId": "appendObservation",
        "security": [{"targetReconcilerBearer": []}],
        "responses": {"201", "default"},
        "responseRefs": {
            "201": "#/components/responses/Observation",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/targets/{targetId}/observations/{observationId}", "get"): {
        "operationId": "getObservation",
        "security": [
            {"consumerBearer": []},
            {"targetReconcilerBearer": []},
        ],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/Observation",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/deployments/{deploymentDigest}", "get"): {
        "operationId": "getConsumerDeployment",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/ConsumerDeployment",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/receipts/{receiptId}", "get"): {
        "operationId": "getDeploymentReceipt",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/DeploymentReceipt",
            "default": "#/components/responses/Problem",
        },
    },
    ("/v1/verifications/{verificationId}", "get"): {
        "operationId": "getVerificationResult",
        "security": [{"consumerBearer": []}],
        "responses": {"200", "304", "default"},
        "responseRefs": {
            "200": "#/components/responses/VerificationResult",
            "default": "#/components/responses/Problem",
        },
    },
}
OPENAPI_OPERATION_INPUT_TOPOLOGY = {
    "getCatalogRelease": {
        "parameters": [
            "#/components/parameters/CatalogId",
            "#/components/parameters/Revision",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getAgentSource": {
        "parameters": [
            "#/components/parameters/SourceDigest",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getRendererRelease": {
        "parameters": [
            "#/components/parameters/RendererId",
            "#/components/parameters/RendererDigest",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getHarnessRender": {
        "parameters": [
            "#/components/parameters/RenderDigest",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getAction": {
        "parameters": [
            "#/components/parameters/ActionId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getInstallation": {
        "parameters": [
            "#/components/parameters/InstallationId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getCandidate": {
        "parameters": [
            "#/components/parameters/CandidateId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getTargetDeliveryState": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "watchTargetEvents": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/LastEventId",
        ],
        "requestSchema": None,
    },
    "resynchronizeTargetEvents": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/KnownAggregateSequence",
        ],
        "requestSchema": None,
    },
    "appendCapabilityEvidence": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/RequiredIfNoneMatch",
            "#/components/parameters/IdempotencyKey",
            "#/components/parameters/CanonicalRequestDigest",
        ],
        "requestSchema": "#/components/schemas/CapabilityEvidenceIntake",
    },
    "getRollout": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/RolloutId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "submitCommand": {
        "parameters": [
            "#/components/parameters/IfMatch",
            "#/components/parameters/IfNoneMatch",
            "#/components/parameters/IdempotencyKey",
            "#/components/parameters/CanonicalRequestDigest",
        ],
        "requestSchema": "#/components/schemas/CommandRequest",
    },
    "appendObservation": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/RequiredIfMatch",
            "#/components/parameters/IdempotencyKey",
            "#/components/parameters/CanonicalRequestDigest",
        ],
        "requestSchema": "#/components/schemas/Observation",
    },
    "getObservation": {
        "parameters": [
            "#/components/parameters/TargetId",
            "#/components/parameters/ObservationId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getConsumerDeployment": {
        "parameters": [
            "#/components/parameters/DeploymentDigest",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getDeploymentReceipt": {
        "parameters": [
            "#/components/parameters/ReceiptId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
    "getVerificationResult": {
        "parameters": [
            "#/components/parameters/VerificationId",
            "#/components/parameters/IfNoneMatch",
        ],
        "requestSchema": None,
    },
}
OPENAPI_IDENTIFIER_PATTERN = "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
OPENAPI_IDENTIFIER_SCHEMA = {"type": "string", "pattern": OPENAPI_IDENTIFIER_PATTERN}
OPENAPI_DIGEST_SCHEMA = {"$ref": "#/components/schemas/Sha256Digest"}
OPENAPI_ETAG_SCHEMA = {"type": "string", "pattern": '^"sha256:[a-f0-9]{64}"$'}
OPENAPI_PARAMETER_COMPONENT_TOPOLOGY = {
    "ActionId": ("actionId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "CandidateId": ("candidateId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "CatalogId": ("catalogId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "InstallationId": ("installationId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "ObservationId": ("observationId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "ReceiptId": ("receiptId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "RendererId": ("rendererId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "RolloutId": ("rolloutId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "TargetId": ("targetId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "VerificationId": ("verificationId", "path", True, OPENAPI_IDENTIFIER_SCHEMA),
    "Revision": (
        "revision",
        "path",
        True,
        {"type": "integer", "minimum": 1, "maximum": 9007199254740991},
    ),
    "SourceDigest": ("sourceDigest", "path", True, OPENAPI_DIGEST_SCHEMA),
    "RendererDigest": ("rendererDigest", "path", True, OPENAPI_DIGEST_SCHEMA),
    "RenderDigest": ("renderDigest", "path", True, OPENAPI_DIGEST_SCHEMA),
    "DeploymentDigest": ("deploymentDigest", "path", True, OPENAPI_DIGEST_SCHEMA),
    "IfMatch": ("If-Match", "header", False, OPENAPI_ETAG_SCHEMA),
    "RequiredIfMatch": ("If-Match", "header", True, OPENAPI_ETAG_SCHEMA),
    "IfNoneMatch": (
        "If-None-Match",
        "header",
        False,
        {
            "type": "string",
            "pattern": '^(?:\\*|"sha256:[a-f0-9]{64}")$',
        },
    ),
    "IdempotencyKey": (
        "Idempotency-Key",
        "header",
        True,
        {"type": "string", "minLength": 16, "maxLength": 128},
    ),
    "CanonicalRequestDigest": (
        "X-Canonical-Request-Digest",
        "header",
        True,
        OPENAPI_DIGEST_SCHEMA,
    ),
    "RequiredIfNoneMatch": (
        "If-None-Match",
        "header",
        True,
        {"const": "*"},
    ),
    "KnownAggregateSequence": (
        "knownAggregateSequence",
        "query",
        True,
        {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991,
        },
    ),
    "LastEventId": (
        "Last-Event-ID",
        "header",
        False,
        {"type": "string", "minLength": 1, "maxLength": 256},
    ),
}
OPENAPI_HEADER_COMPONENT_TOPOLOGY = {
    "ETag": (True, OPENAPI_ETAG_SCHEMA),
    "Location": (
        True,
        {
            "type": "string",
            "format": "uri-reference",
            "pattern": "^/v1/actions/[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
            "maxLength": 256,
        },
    ),
    "RateLimitLimit": (
        True,
        {"type": "integer", "minimum": 0, "maximum": 9007199254740991},
    ),
    "RateLimitRemaining": (
        True,
        {"type": "integer", "minimum": 0, "maximum": 9007199254740991},
    ),
    "RateLimitReset": (
        True,
        {"type": "integer", "minimum": 0, "maximum": 9007199254740991},
    ),
}
OPENAPI_SCHEMA_COMPONENT_TOPOLOGY = {
    "Action": (
        "../../schemas/v1/action.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/action/1.0.0",
        "sha256:ddf0e484b8d35195f984204e130c9f3e88b5e347581722437aa763e28b2c346a",
    ),
    "AgentSource": (
        "../../schemas/v1/agent-source.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/agent-source/1.0.0",
        "sha256:44fa5624b641e046f04365c5230c83028d29396c596f6ab894526e28fc8328c8",
    ),
    "Candidate": (
        "../../schemas/v1/candidate.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/candidate/1.0.0",
        "sha256:07964d57f89136a95950250c8790179a8765fd54788d81a7d1148d0cc8b8c2e5",
    ),
    "CatalogIndex": (
        "../../schemas/v1/catalog-index.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/catalog-index/1.0.0",
        "sha256:f7bdca8523a7c8c3de3dcc9909857217959ace7744550d35c4e5b3b429bded62",
    ),
    "CommandRequest": (
        "../../schemas/v1/command-request.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/command-request/1.0.0",
        "sha256:fdb077eb05d7943580f299461e91360c3630075e95bd68918e4bb600b5dd02fd",
    ),
    "EventDataEnvelope": (
        "../../schemas/v1/event-data-envelope.schema.json",
        EVENT_DATA_SCHEMA_ID,
        "sha256:b89b2091b29798a62b147da8132cde46bc42aae4beacf6709a03474bc6c90243",
    ),
    "ConsumerDeployment": (
        "../../schemas/v1/consumer-deployment.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/consumer-deployment/1.0.0",
        "sha256:24c4e7aecf25d16cf7d3aa768fe09ca9508e6db667e0a282b95c9dd68370fea0",
    ),
    "DeploymentReceipt": (
        "../../schemas/v1/deployment-receipt.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/deployment-receipt/1.0.0",
        "sha256:a32cd43cf6e566da849f23f0d0a8ef6cec269f60387b8d019bcdfece4c36bd1a",
    ),
    "HarnessRender": (
        "../../schemas/v1/harness-render.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/harness-render/1.0.0",
        "sha256:68fe1a718f9e5210c0ba4d10095f049983499243b69ae565a826155b949525cf",
    ),
    "Installation": (
        "../../schemas/v1/installation.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/installation/1.0.0",
        "sha256:af01882c9dc8dbf80fc753f148a35fd916d4bdbe5d93b6a8938c0b10f58ff8dc",
    ),
    "Observation": (
        "../../schemas/v1/observation.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/observation/1.0.0",
        "sha256:61cec89f0502071956315db65fabc3c0e7bb7c97b563711cfdb935987a3d5c92",
    ),
    "ProblemDetails": (
        "../../schemas/v1/problem-details.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/problem-details/1.0.0",
        "sha256:73c47dbc705fa5c7b19f51d012711ef5f9d82f67ef87defe7c751172767131b1",
    ),
    "RecoveryPlan": (
        "../../schemas/v1/recovery-plan.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/recovery-plan/1.0.0",
        "sha256:15c95ed8c5f31982fe76e92bfef675830dcba98e4078261b961679e515c76829",
    ),
    "RendererRelease": (
        "../../schemas/v1/renderer-release.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/renderer-release/1.0.0",
        "sha256:fec8fe534d7d51129cca211fa12583410c58bc47c9c1b90ec00b77299a64e80b",
    ),
    "Rollout": (
        "../../schemas/v1/rollout.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/rollout/1.0.0",
        "sha256:a3fef06c3c2b3967279f4e572dfb0730dea1dac953d2e672d1bd8c2f146eb200",
    ),
    "Sha256Digest": (
        "../../schemas/v1/common.schema.json#/$defs/sha256",
        "https://schemas.bytedesk.ai/agent-delivery/v1/common/1.0.0",
        "sha256:088eb2aa7604a5ae581595d931dd539ee84c0ce4d4b7413c5c4400619f3ebb4d",
    ),
    "TargetDeliveryState": (
        "../../schemas/v1/target-delivery-state.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/target-delivery-state/1.0.0",
        "sha256:5ea7f494cd955eb19f1a89c6e640ed963426b40eaf3eab42b6f58f446d7b64b6",
    ),
    "VerificationResult": (
        "../../schemas/v1/verification-result.schema.json",
        "https://schemas.bytedesk.ai/agent-delivery/v1/verification-result/1.0.0",
        "sha256:0acdbdbfeb5c84af9ab26a32b9d5a5e49dba4a1dd45189ac1e82a635bb5ab9b6",
    ),
}
OPENAPI_PROTOCOL_SCHEMA_COMPONENT_TOPOLOGY = {
    "AgentDeliveryCloudEvent": {
        "type": "object",
        "required": [
            "specversion",
            "id",
            "source",
            "type",
            "subject",
            "time",
            "datacontenttype",
            "dataschema",
            "data",
        ],
        "properties": {
            "specversion": {"const": "1.0"},
            "id": {"type": "string", "minLength": 1, "maxLength": 256},
            "source": {
                "type": "string",
                "format": "uri-reference",
                "maxLength": 2048,
            },
            "type": {"type": "string", "enum": AGENT_DELIVERY_EVENT_TYPE_ENUM},
            "subject": {"type": "string", "minLength": 1, "maxLength": 256},
            "time": {"type": "string", "format": "date-time"},
            "datacontenttype": {"const": "application/json"},
            "dataschema": {"const": EVENT_DATA_SCHEMA_ID},
            "data": {"$ref": "../../schemas/v1/event-data-envelope.schema.json"},
        },
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "x-bytedesk-cloudevents-version": "1.0.2",
        "x-bytedesk-data-schema-id": EVENT_DATA_SCHEMA_ID,
        "x-bytedesk-data-schema-digest": (
            "sha256:b89b2091b29798a62b147da8132cde46bc42aae4beacf6709a03474bc6c90243"
        ),
    },
    "CapabilityEvidenceIntake": {
        "type": "object",
        "required": [
            "verificationResult",
            "dispatchNonce",
            "authorizationDecisionDigest",
        ],
        "properties": {
            "verificationResult": {
                "$ref": "../../schemas/v1/verification-result.schema.json"
            },
            "dispatchNonce": {
                "$ref": "../../schemas/v1/common.schema.json#/$defs/nonce"
            },
            "authorizationDecisionDigest": {
                "$ref": "../../schemas/v1/common.schema.json#/$defs/sha256"
            },
        },
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "x-bytedesk-port-contract": (
            "bytedesk.port.control-plane-api-events."
            "append-capability-evidence.request/1"
        ),
    },
    "CapabilityEvidenceReceipt": {
        "type": "object",
        "required": ["evidenceDigest", "acceptedAt"],
        "properties": {
            "evidenceDigest": {
                "$ref": "../../schemas/v1/common.schema.json#/$defs/sha256"
            },
            "acceptedAt": {
                "$ref": "../../schemas/v1/common.schema.json#/$defs/timestamp"
            },
        },
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "x-bytedesk-port-contract": (
            "bytedesk.port.control-plane-api-events."
            "append-capability-evidence.result/1"
        ),
    },
    "TargetEventResynchronization": {
        "type": "object",
        "required": ["targetState", "aggregateSequence", "resumeToken"],
        "properties": {
            "targetState": {
                "$ref": "../../schemas/v1/target-delivery-state.schema.json"
            },
            "aggregateSequence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 9007199254740991,
            },
            "resumeToken": {"type": "string", "minLength": 1, "maxLength": 256},
        },
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "x-bytedesk-port-contract": (
            "bytedesk.port.control-plane-api-events.resynchronize-events.result/1"
        ),
    },
}
OPENAPI_RESPONSE_COMPONENT_TOPOLOGY = {
    name: (
        "application/json",
        f"#/components/schemas/{name}",
        {"ETag": {"$ref": "#/components/headers/ETag"}},
    )
    for name in (
        "Action",
        "AgentSource",
        "Candidate",
        "CatalogIndex",
        "ConsumerDeployment",
        "DeploymentReceipt",
        "HarnessRender",
        "Installation",
        "Observation",
        "RendererRelease",
        "Rollout",
        "TargetDeliveryState",
        "VerificationResult",
    )
}
OPENAPI_RESPONSE_COMPONENT_TOPOLOGY.update(
    {
        "AcceptedAction": (
            "application/json",
            "#/components/schemas/Action",
            {
                "ETag": {"$ref": "#/components/headers/ETag"},
                "Location": {"$ref": "#/components/headers/Location"},
                "RateLimit-Limit": {"$ref": "#/components/headers/RateLimitLimit"},
                "RateLimit-Remaining": {
                    "$ref": "#/components/headers/RateLimitRemaining"
                },
                "RateLimit-Reset": {"$ref": "#/components/headers/RateLimitReset"},
            },
        ),
        "Problem": (
            "application/problem+json",
            "#/components/schemas/ProblemDetails",
            {},
        ),
        "CapabilityEvidenceReceipt": (
            "application/json",
            "#/components/schemas/CapabilityEvidenceReceipt",
            {"ETag": {"$ref": "#/components/headers/ETag"}},
        ),
        "TargetEventResynchronization": (
            "application/json",
            "#/components/schemas/TargetEventResynchronization",
            {"ETag": {"$ref": "#/components/headers/ETag"}},
        ),
    }
)
OPENAPI_SPECIAL_RESPONSE_COMPONENT_TOPOLOGY = {
    "TargetEventStream": {
        "content": {
            "text/event-stream": {
                "itemSchema": {"$ref": "#/components/schemas/AgentDeliveryCloudEvent"}
            }
        }
    }
}
OPENAPI_SECURITY_SCHEME_TOPOLOGY = {
    "consumerBearer": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "consumer-issued short-lived sender-bound token",
    },
    "targetReconcilerBearer": {"type": "mutualTLS"},
    "capabilityVerifierMtls": {"type": "mutualTLS"},
}
OPENAPI_SERVER_TOPOLOGY = [
    {
        "url": "https://{authority}",
        "variables": {"authority": {"default": "agent-delivery.invalid"}},
    }
]
ASYNCAPI_SERVER_TOPOLOGY = {
    "consumerFeed": {
        "host": "agent-delivery.invalid",
        "pathname": "/v1/events",
        "protocol": "https",
        "security": [{"$ref": "#/components/securitySchemes/consumerBearer"}],
    },
    "consumerWebhook": {
        "host": "consumer.invalid",
        "pathname": "/agent-delivery/events",
        "protocol": "https",
        "security": [{"$ref": "#/components/securitySchemes/mutualTLS"}],
    },
}
ASYNCAPI_SECURITY_SCHEME_TOPOLOGY = {
    "consumerBearer": {
        "type": "httpApiKey",
        "name": "Authorization",
        "in": "header",
    },
    "mutualTLS": {"type": "X509"},
}
ASYNCAPI_CHANNEL_TOPOLOGY = {
    "notifications": {
        "address": "/v1/events",
        "servers": [
            {"$ref": "#/servers/consumerFeed"},
            {"$ref": "#/servers/consumerWebhook"},
        ],
        "messages": {
            "agentDeliveryNotification": {
                "$ref": "#/components/messages/AgentDeliveryNotification"
            }
        },
    }
}
ASYNCAPI_OPERATION_TOPOLOGY = {
    "receiveNotifications": {
        "action": "receive",
        "channel": {"$ref": "#/channels/notifications"},
        "messages": [
            {"$ref": "#/channels/notifications/messages/agentDeliveryNotification"}
        ],
        "traits": [
            {
                "x-bytedesk-delivery": "at-least-once",
                "x-bytedesk-ordering": "per-aggregate-sequence",
                "x-bytedesk-authority": "notification-only",
                "x-bytedesk-gap-behavior": "stop-and-api-resynchronize",
                "x-bytedesk-deduplication-key": "CloudEvent.id",
            }
        ],
    }
}
ASYNCAPI_SCHEMA_COMPONENT_TOPOLOGY = {
    "EventDataEnvelope": (
        "../../schemas/v1/event-data-envelope.schema.json",
        EVENT_DATA_SCHEMA_ID,
        "sha256:b89b2091b29798a62b147da8132cde46bc42aae4beacf6709a03474bc6c90243",
    )
}
ASYNCAPI_EVENT_TYPE_ENUM = AGENT_DELIVERY_EVENT_TYPE_ENUM
ASYNCAPI_MESSAGE_COMPONENT_TOPOLOGY = {
    "AgentDeliveryNotification": {
        "name": "AgentDeliveryNotification",
        "contentType": "application/cloudevents+json",
        "correlationId": {"location": "$message.payload#/data/correlationId"},
        "x-bytedesk-cloudevents-version": "1.0.2",
        "x-bytedesk-data-schema-id": EVENT_DATA_SCHEMA_ID,
        "x-bytedesk-data-schema-digest": (
            "sha256:b89b2091b29798a62b147da8132cde46bc42aae4beacf6709a03474bc6c90243"
        ),
        "payload": {
            "type": "object",
            "required": [
                "specversion",
                "id",
                "source",
                "type",
                "subject",
                "time",
                "datacontenttype",
                "dataschema",
                "data",
            ],
            "properties": {
                "specversion": {"const": "1.0"},
                "id": {"type": "string", "minLength": 1, "maxLength": 256},
                "source": {
                    "type": "string",
                    "format": "uri-reference",
                    "maxLength": 2048,
                },
                "type": {"type": "string", "enum": ASYNCAPI_EVENT_TYPE_ENUM},
                "subject": {"type": "string", "minLength": 1, "maxLength": 256},
                "time": {"type": "string", "format": "date-time"},
                "datacontenttype": {"const": "application/json"},
                "dataschema": {"const": EVENT_DATA_SCHEMA_ID},
                "data": {"$ref": "#/components/schemas/EventDataEnvelope"},
            },
            "additionalProperties": False,
            "unevaluatedProperties": False,
        },
    }
}


def reject_projection_network_retrieval(uri: str) -> Resource[Any]:
    """Make an attempted non-vendored projection-schema lookup fail closed."""

    raise NoSuchResource(ref=uri)


def projection_schema_resources(
    schema: Any, specification: Specification[Any], description: str
) -> tuple[Registry[Any], int]:
    resources: list[tuple[str, Resource[Any]]] = []
    observed_ids: set[str] = set()
    stack = [schema]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            schema_id = current.get("$id")
            if isinstance(schema_id, str):
                if schema_id in observed_ids:
                    raise ContractToolError(
                        f"{description} official schema repeats embedded $id {schema_id}"
                    )
                observed_ids.add(schema_id)
                try:
                    resource = Resource.from_contents(
                        current, default_specification=specification
                    )
                except (TypeError, ValueError) as error:
                    raise ContractToolError(
                        f"{description} official schema has an invalid embedded resource"
                    ) from error
                resources.append((schema_id, resource))
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    if not resources:
        raise ContractToolError(f"{description} official schema has no identified resource")
    return (
        Registry(retrieve=reject_projection_network_retrieval).with_resources(resources),
        len(resources),
    )


SINGLE_SUBSCHEMA_KEYWORDS = {
    "additionalItems",
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
}
ARRAY_SUBSCHEMA_KEYWORDS = {"allOf", "anyOf", "oneOf", "prefixItems"}
MAP_SUBSCHEMA_KEYWORDS = {
    "$defs",
    "definitions",
    "dependentSchemas",
    "patternProperties",
    "properties",
}


def iter_schema_references(value: Any, base_uri: str) -> Iterable[tuple[str, str]]:
    """Walk only schema locations, excluding instance-valued examples/defaults."""

    if not isinstance(value, dict):
        return
    schema_id = value.get("$id")
    if isinstance(schema_id, str):
        base_uri = urljoin(base_uri, schema_id)
    for keyword in ("$ref", "$dynamicRef"):
        reference = value.get(keyword)
        if isinstance(reference, str):
            yield base_uri, reference
    for keyword in SINGLE_SUBSCHEMA_KEYWORDS:
        child = value.get(keyword)
        if isinstance(child, dict):
            yield from iter_schema_references(child, base_uri)
        elif keyword == "items" and isinstance(child, list):
            for item in child:
                yield from iter_schema_references(item, base_uri)
    for keyword in ARRAY_SUBSCHEMA_KEYWORDS:
        children = value.get(keyword)
        if isinstance(children, list):
            for child in children:
                yield from iter_schema_references(child, base_uri)
    for keyword in MAP_SUBSCHEMA_KEYWORDS:
        children = value.get(keyword)
        if isinstance(children, dict):
            for child in children.values():
                yield from iter_schema_references(child, base_uri)
    dependencies = value.get("dependencies")
    if isinstance(dependencies, dict):
        for child in dependencies.values():
            if isinstance(child, dict):
                yield from iter_schema_references(child, base_uri)


def require_offline_projection_references(
    schema: Any,
    registry: Registry[Any],
    schema_id: str,
    description: str,
) -> None:
    for base_uri, reference in iter_schema_references(schema, schema_id):
        try:
            registry.resolver(base_uri).lookup(reference)
        except (NoSuchResource, Unresolvable) as error:
            raise ContractToolError(
                f"{description} official schema requires forbidden network retrieval: {reference}"
            ) from error


def load_pinned_projection_schema(
    path: Path, expected_digest: str, expected_id: str, description: str
) -> dict[str, Any]:
    actual_digest = file_digest(path)
    if actual_digest != expected_digest:
        raise ContractToolError(
            f"{description} official schema digest mismatch: {actual_digest}"
        )
    schema = load_json(path)
    if not isinstance(schema, dict) or schema.get("$id") != expected_id:
        raise ContractToolError(f"{description} official schema identity mismatch")
    return schema


def check_pinned_vendor_files() -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for path, expected_digest in PINNED_VENDOR_FILES.items():
        actual_digest = file_digest(path)
        if actual_digest != expected_digest:
            raise ContractToolError(
                f"vendored projection dependency digest mismatch: {repository_path(path)}"
            )
        results.append({"path": repository_path(path), "digest": actual_digest})
    return results


def check_schema_component_topology(
    components: Any,
    expected: dict[str, tuple[str, str, str]],
    projection_name: str,
    additional_names: set[str] | None = None,
) -> None:
    schemas = components.get("schemas") if isinstance(components, dict) else None
    expected_names = set(expected) | (additional_names or set())
    if not isinstance(schemas, dict) or set(schemas) != expected_names:
        raise ContractToolError(f"{projection_name} schema component topology drift")
    for name, (reference, schema_id, schema_digest) in expected.items():
        if schemas[name] != {
            "$ref": reference,
            "x-bytedesk-schema-id": schema_id,
            "x-bytedesk-schema-digest": schema_digest,
        }:
            raise ContractToolError(
                f"{projection_name} schema component topology drift for {name}"
            )


def check_openapi_component_topology(components: Any) -> None:
    """Freeze authority-relevant component semantics while allowing prose edits."""

    if not isinstance(components, dict) or set(components) != {
        "securitySchemes",
        "parameters",
        "headers",
        "schemas",
        "responses",
    }:
        raise ContractToolError("OpenAPI component topology drift")
    check_schema_component_topology(
        components,
        OPENAPI_SCHEMA_COMPONENT_TOPOLOGY,
        "OpenAPI",
        set(OPENAPI_PROTOCOL_SCHEMA_COMPONENT_TOPOLOGY),
    )
    schemas = components["schemas"]
    for name, expected in OPENAPI_PROTOCOL_SCHEMA_COMPONENT_TOPOLOGY.items():
        schema = schemas[name]
        semantic_fields = (
            {key: value for key, value in schema.items() if key != "description"}
            if isinstance(schema, dict)
            else None
        )
        if semantic_fields != expected:
            raise ContractToolError(
                f"OpenAPI protocol schema component topology drift for {name}"
            )

    parameters = components.get("parameters")
    if not isinstance(parameters, dict) or set(parameters) != set(
        OPENAPI_PARAMETER_COMPONENT_TOPOLOGY
    ):
        raise ContractToolError("OpenAPI parameter component topology drift")
    for name, (parameter_name, location, required, schema) in (
        OPENAPI_PARAMETER_COMPONENT_TOPOLOGY.items()
    ):
        parameter = parameters[name]
        if not isinstance(parameter, dict):
            raise ContractToolError(
                f"OpenAPI parameter component topology drift for {name}"
            )
        semantic_fields = {
            key: value for key, value in parameter.items() if key != "description"
        }
        if semantic_fields != {
            "name": parameter_name,
            "in": location,
            "required": required,
            "schema": schema,
        }:
            raise ContractToolError(
                f"OpenAPI parameter component topology drift for {name}"
            )

    headers = components.get("headers")
    if not isinstance(headers, dict) or set(headers) != set(
        OPENAPI_HEADER_COMPONENT_TOPOLOGY
    ):
        raise ContractToolError("OpenAPI header component topology drift")
    for name, (required, schema) in OPENAPI_HEADER_COMPONENT_TOPOLOGY.items():
        header = headers[name]
        if not isinstance(header, dict):
            raise ContractToolError(f"OpenAPI header component topology drift for {name}")
        semantic_fields = {
            key: value for key, value in header.items() if key != "description"
        }
        if semantic_fields != {"required": required, "schema": schema}:
            raise ContractToolError(f"OpenAPI header component topology drift for {name}")

    responses = components.get("responses")
    expected_response_names = set(OPENAPI_RESPONSE_COMPONENT_TOPOLOGY) | set(
        OPENAPI_SPECIAL_RESPONSE_COMPONENT_TOPOLOGY
    )
    if not isinstance(responses, dict) or set(responses) != expected_response_names:
        raise ContractToolError("OpenAPI response component topology drift")
    for name, (media_type, schema_reference, response_headers) in (
        OPENAPI_RESPONSE_COMPONENT_TOPOLOGY.items()
    ):
        response = responses[name]
        if not isinstance(response, dict):
            raise ContractToolError(
                f"OpenAPI response component topology drift for {name}"
            )
        semantic_fields = {
            key: value for key, value in response.items() if key != "description"
        }
        expected_fields: dict[str, Any] = {
            "content": {
                media_type: {"schema": {"$ref": schema_reference}},
            }
        }
        if response_headers:
            expected_fields["headers"] = response_headers
        if semantic_fields != expected_fields:
            raise ContractToolError(
                f"OpenAPI response component topology drift for {name}"
            )
    for name, expected_fields in OPENAPI_SPECIAL_RESPONSE_COMPONENT_TOPOLOGY.items():
        response = responses[name]
        semantic_fields = (
            {key: value for key, value in response.items() if key != "description"}
            if isinstance(response, dict)
            else None
        )
        if semantic_fields != expected_fields:
            raise ContractToolError(
                f"OpenAPI response component topology drift for {name}"
            )


def check_asyncapi_component_topology(components: Any) -> None:
    """Freeze the event schema and CloudEvent envelope semantic bindings."""

    if not isinstance(components, dict) or set(components) != {
        "securitySchemes",
        "schemas",
        "messages",
    }:
        raise ContractToolError("AsyncAPI component topology drift")
    check_schema_component_topology(
        components, ASYNCAPI_SCHEMA_COMPONENT_TOPOLOGY, "AsyncAPI"
    )
    messages = components.get("messages")
    if not isinstance(messages, dict) or set(messages) != set(
        ASYNCAPI_MESSAGE_COMPONENT_TOPOLOGY
    ):
        raise ContractToolError("AsyncAPI message component topology drift")
    for name, expected in ASYNCAPI_MESSAGE_COMPONENT_TOPOLOGY.items():
        message = messages[name]
        if not isinstance(message, dict):
            raise ContractToolError(
                f"AsyncAPI message component topology drift for {name}"
            )
        semantic_fields = {
            key: value
            for key, value in message.items()
            if key not in {"title", "summary", "description"}
        }
        if semantic_fields != expected:
            raise ContractToolError(
                f"AsyncAPI message component topology drift for {name}"
            )


def check_openapi_topology(document: Any) -> None:
    """Freeze every accepted HTTP operation before per-operation lint runs."""

    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise ContractToolError("OpenAPI path/method topology drift: paths is absent")
    if "webhooks" in document:
        raise ContractToolError("OpenAPI webhook topology drift")
    servers = document.get("servers")
    if not isinstance(servers, list) or len(servers) != 1:
        raise ContractToolError("OpenAPI server topology drift")
    server = servers[0]
    if not isinstance(server, dict):
        raise ContractToolError("OpenAPI server topology drift")
    server_semantics = {
        key: value for key, value in server.items() if key != "description"
    }
    variables = server_semantics.get("variables")
    if isinstance(variables, dict):
        server_semantics["variables"] = {
            name: {
                key: value
                for key, value in variable.items()
                if key != "description"
            }
            if isinstance(variable, dict)
            else variable
            for name, variable in variables.items()
        }
    if [server_semantics] != OPENAPI_SERVER_TOPOLOGY:
        raise ContractToolError("OpenAPI server topology drift")
    paths = document["paths"]
    expected_paths = {path for path, _ in OPENAPI_OPERATION_TOPOLOGY}
    if set(paths) != expected_paths:
        raise ContractToolError(
            "OpenAPI path/method topology drift: "
            f"missing={sorted(expected_paths - set(paths))} "
            f"extra={sorted(set(paths) - expected_paths)}"
        )
    for path in sorted(expected_paths):
        path_item = paths[path]
        if not isinstance(path_item, dict):
            raise ContractToolError(f"OpenAPI path/method topology drift at {path}")
        expected_methods = {
            method for expected_path, method in OPENAPI_OPERATION_TOPOLOGY if expected_path == path
        }
        if set(path_item) != expected_methods:
            raise ContractToolError(f"OpenAPI path item topology drift at {path}")
        actual_methods = set(path_item).intersection(OPENAPI_HTTP_METHODS)
        if actual_methods != expected_methods:
            raise ContractToolError(
                f"OpenAPI path/method topology drift at {path}: "
                f"expected={sorted(expected_methods)} actual={sorted(actual_methods)}"
            )
        for method in sorted(expected_methods):
            operation = path_item.get(method)
            expected = OPENAPI_OPERATION_TOPOLOGY[(path, method)]
            if not isinstance(operation, dict):
                raise ContractToolError(
                    f"OpenAPI path/method topology drift at {method} {path}"
                )
            if operation.get("operationId") != expected["operationId"]:
                raise ContractToolError(
                    f"OpenAPI operation identity drift at {method} {path}"
                )
            allowed_operation_fields = {
                "operationId",
                "security",
                "parameters",
                "responses",
                "summary",
                "description",
                "tags",
            }
            if expected["operationId"] == "submitCommand":
                allowed_operation_fields.update(
                    {
                        "requestBody",
                        "x-bytedesk-command-authorization",
                        "x-bytedesk-conditional-request",
                    }
                )
            elif expected["operationId"] == "appendObservation":
                allowed_operation_fields.update(
                    {"requestBody", "x-bytedesk-conditional-request"}
                )
            elif expected["operationId"] == "appendCapabilityEvidence":
                allowed_operation_fields.update(
                    {
                        "requestBody",
                        "x-bytedesk-port-operation",
                        "x-bytedesk-authority",
                        "x-bytedesk-conditional-request",
                    }
                )
            elif expected["operationId"] == "watchTargetEvents":
                allowed_operation_fields.update(
                    {"x-bytedesk-port-operations", "x-bytedesk-sse"}
                )
            elif expected["operationId"] == "resynchronizeTargetEvents":
                allowed_operation_fields.update(
                    {
                        "x-bytedesk-port-operations",
                        "x-bytedesk-resynchronization",
                    }
                )
            if set(operation) - allowed_operation_fields:
                raise ContractToolError(
                    f"OpenAPI operation semantic topology drift for {expected['operationId']}"
                )
            if operation.get("security") != expected["security"]:
                raise ContractToolError(
                    f"OpenAPI operation security drift for {expected['operationId']}"
                )
            expected_input = OPENAPI_OPERATION_INPUT_TOPOLOGY[expected["operationId"]]
            expected_parameters = [
                {"$ref": reference} for reference in expected_input["parameters"]
            ]
            if operation.get("parameters") != expected_parameters:
                raise ContractToolError(
                    "OpenAPI operation parameter topology drift for "
                    f"{expected['operationId']}"
                )
            request_schema = expected_input["requestSchema"]
            if request_schema is None:
                if "requestBody" in operation:
                    raise ContractToolError(
                        "OpenAPI operation request body topology drift for "
                        f"{expected['operationId']}"
                    )
            elif operation.get("requestBody") != {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": request_schema},
                    }
                },
            }:
                raise ContractToolError(
                    "OpenAPI operation request body topology drift for "
                    f"{expected['operationId']}"
                )
            responses = operation.get("responses")
            if not isinstance(responses, dict) or set(responses) != expected["responses"]:
                raise ContractToolError(
                    f"OpenAPI operation response topology drift for {expected['operationId']}"
                )
            for status, reference in expected["responseRefs"].items():
                if responses.get(status) != {"$ref": reference}:
                    raise ContractToolError(
                        f"OpenAPI operation response topology drift for "
                        f"{expected['operationId']} status {status}"
                    )
            if "304" in expected["responses"]:
                not_modified = responses.get("304")
                if (
                    not isinstance(not_modified, dict)
                    or set(not_modified) != {"description"}
                    or not isinstance(not_modified["description"], str)
                    or not not_modified["description"]
                ):
                    raise ContractToolError(
                        f"OpenAPI operation response topology drift for "
                        f"{expected['operationId']} status 304"
                    )
            if expected["operationId"] == "watchTargetEvents":
                if operation.get("x-bytedesk-port-operations") != [
                    "bytedesk.port.desired-state-store/1#watch-target-state",
                    "bytedesk.port.control-plane-api-events/1#subscribe-events",
                ]:
                    raise ContractToolError(
                        "OpenAPI target event watch port binding drift"
                    )
                if operation.get("x-bytedesk-sse") != TARGET_EVENT_SSE_PROFILE:
                    raise ContractToolError("OpenAPI target event SSE profile drift")
            if expected["operationId"] == "resynchronizeTargetEvents":
                if operation.get("x-bytedesk-port-operations") != [
                    "bytedesk.port.desired-state-store/1#read-target-state",
                    "bytedesk.port.control-plane-api-events/1#resynchronize-events",
                ]:
                    raise ContractToolError(
                        "OpenAPI target event resynchronization port binding drift"
                    )
                if (
                    operation.get("x-bytedesk-resynchronization")
                    != TARGET_EVENT_RESYNCHRONIZATION_PROFILE
                ):
                    raise ContractToolError(
                        "OpenAPI target event resynchronization profile drift"
                    )
            if expected["operationId"] == "appendCapabilityEvidence":
                if operation.get("x-bytedesk-port-operation") != (
                    "bytedesk.port.control-plane-api-events/1#"
                    "append-capability-evidence"
                ):
                    raise ContractToolError(
                        "OpenAPI capability evidence port binding drift"
                    )
                if (
                    operation.get("x-bytedesk-authority")
                    != CAPABILITY_EVIDENCE_AUTHORITY_PROFILE
                ):
                    raise ContractToolError(
                        "OpenAPI capability evidence authority boundary drift"
                    )
                if (
                    operation.get("x-bytedesk-conditional-request")
                    != CAPABILITY_EVIDENCE_CONDITIONAL_REQUEST_PROFILE
                ):
                    raise ContractToolError(
                        "OpenAPI capability evidence conditional request drift"
                    )

    last_event_uses = [
        (path, method)
        for (path, method), expected in OPENAPI_OPERATION_TOPOLOGY.items()
        if {"$ref": "#/components/parameters/LastEventId"}
        in document["paths"][path][method].get("parameters", [])
    ]
    if last_event_uses != [("/v1/targets/{targetId}/events", "get")]:
        raise ContractToolError(
            "OpenAPI Last-Event-ID is not exclusive to the authenticated SSE watch"
        )
    capability_verifier_uses = [
        (path, method)
        for (path, method), expected in OPENAPI_OPERATION_TOPOLOGY.items()
        if {"capabilityVerifierMtls": []}
        in document["paths"][path][method].get("security", [])
    ]
    if capability_verifier_uses != [
        ("/v1/targets/{targetId}/capability-evidence", "post")
    ]:
        raise ContractToolError(
            "OpenAPI capability verifier mTLS identity is not intake-only"
        )

    components = document.get("components")
    check_openapi_component_topology(components)
    security_schemes = (
        components.get("securitySchemes") if isinstance(components, dict) else None
    )
    if (
        not isinstance(security_schemes, dict)
        or set(security_schemes) != set(OPENAPI_SECURITY_SCHEME_TOPOLOGY)
    ):
        raise ContractToolError("OpenAPI security scheme topology drift")
    for name, expected in OPENAPI_SECURITY_SCHEME_TOPOLOGY.items():
        scheme = security_schemes[name]
        semantic_fields = (
            {key: value for key, value in scheme.items() if key != "description"}
            if isinstance(scheme, dict)
            else None
        )
        if semantic_fields != expected:
            raise ContractToolError(f"OpenAPI security scheme topology drift for {name}")


def check_asyncapi_topology(document: Any) -> None:
    """Freeze event transports, channel binding, operation, and security."""

    if not isinstance(document, dict):
        raise ContractToolError("AsyncAPI server topology drift: root is not an object")
    servers = document.get("servers")
    if not isinstance(servers, dict) or set(servers) != set(ASYNCAPI_SERVER_TOPOLOGY):
        raise ContractToolError("AsyncAPI server topology drift")
    for name, expected in ASYNCAPI_SERVER_TOPOLOGY.items():
        server = servers[name]
        if not isinstance(server, dict):
            raise ContractToolError(f"AsyncAPI server topology drift for {name}")
        semantic_fields = {
            key: value for key, value in server.items() if key != "description"
        }
        if semantic_fields != expected:
            if server.get("security") != expected["security"]:
                raise ContractToolError(f"AsyncAPI server security drift for {name}")
            raise ContractToolError(f"AsyncAPI server topology drift for {name}")

    components = document.get("components")
    check_asyncapi_component_topology(components)
    security_schemes = (
        components.get("securitySchemes") if isinstance(components, dict) else None
    )
    if (
        not isinstance(security_schemes, dict)
        or set(security_schemes) != set(ASYNCAPI_SECURITY_SCHEME_TOPOLOGY)
    ):
        raise ContractToolError("AsyncAPI security scheme topology drift")
    for name, expected in ASYNCAPI_SECURITY_SCHEME_TOPOLOGY.items():
        scheme = security_schemes[name]
        semantic_fields = (
            {key: value for key, value in scheme.items() if key != "description"}
            if isinstance(scheme, dict)
            else None
        )
        if semantic_fields != expected:
            raise ContractToolError(f"AsyncAPI security scheme topology drift for {name}")

    channels = document.get("channels")
    if not isinstance(channels, dict) or set(channels) != set(ASYNCAPI_CHANNEL_TOPOLOGY):
        raise ContractToolError("AsyncAPI channel topology drift")
    for name, expected in ASYNCAPI_CHANNEL_TOPOLOGY.items():
        channel = channels[name]
        semantic_fields = (
            {key: value for key, value in channel.items() if key != "description"}
            if isinstance(channel, dict)
            else None
        )
        if semantic_fields != expected:
            raise ContractToolError(f"AsyncAPI channel topology drift for {name}")

    operations = document.get("operations")
    if not isinstance(operations, dict) or set(operations) != set(
        ASYNCAPI_OPERATION_TOPOLOGY
    ):
        raise ContractToolError("AsyncAPI operation topology drift")
    for name, expected in ASYNCAPI_OPERATION_TOPOLOGY.items():
        operation = operations[name]
        semantic_fields = (
            {
                key: value
                for key, value in operation.items()
                if key not in {"summary", "description"}
            }
            if isinstance(operation, dict)
            else None
        )
        if semantic_fields != expected:
            raise ContractToolError(f"AsyncAPI operation topology drift for {name}")


def validate_official_openapi(document: Any) -> dict[str, Any]:
    expected_digest = PINNED_VENDOR_FILES[OPENAPI_OFFICIAL_SCHEMA_PATH]
    schema = load_pinned_projection_schema(
        OPENAPI_OFFICIAL_SCHEMA_PATH,
        expected_digest,
        OPENAPI_OFFICIAL_SCHEMA_ID,
        "OpenAPI",
    )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise ContractToolError(f"invalid official OpenAPI schema: {error.message}") from error
    registry, resource_count = projection_schema_resources(
        schema, DRAFT202012, "OpenAPI"
    )
    require_offline_projection_references(
        schema, registry, OPENAPI_OFFICIAL_SCHEMA_ID, "OpenAPI"
    )
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(document),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"official OpenAPI schema rejected projection: {errors[0].message}")
    return {
        "path": repository_path(OPENAPI_OFFICIAL_SCHEMA_PATH),
        "id": OPENAPI_OFFICIAL_SCHEMA_ID,
        "digest": expected_digest,
        "dialect": "https://json-schema.org/draft/2020-12/schema",
        "resourceCount": resource_count,
    }


def validate_official_asyncapi(document: Any) -> dict[str, Any]:
    expected_digest = PINNED_VENDOR_FILES[ASYNCAPI_OFFICIAL_SCHEMA_PATH]
    schema = load_pinned_projection_schema(
        ASYNCAPI_OFFICIAL_SCHEMA_PATH,
        expected_digest,
        ASYNCAPI_OFFICIAL_SCHEMA_ID,
        "AsyncAPI",
    )
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as error:
        raise ContractToolError(f"invalid official AsyncAPI schema: {error.message}") from error
    registry, resource_count = projection_schema_resources(schema, DRAFT7, "AsyncAPI")
    require_offline_projection_references(
        schema, registry, ASYNCAPI_OFFICIAL_SCHEMA_ID, "AsyncAPI"
    )
    errors = sorted(
        Draft7Validator(
            schema,
            registry=registry,
            format_checker=Draft7Validator.FORMAT_CHECKER,
        ).iter_errors(document),
        key=validation_error_key,
    )
    if errors:
        raise ContractToolError(f"official AsyncAPI schema rejected projection: {errors[0].message}")
    return {
        "path": repository_path(ASYNCAPI_OFFICIAL_SCHEMA_PATH),
        "id": ASYNCAPI_OFFICIAL_SCHEMA_ID,
        "digest": expected_digest,
        "dialect": "http://json-schema.org/draft-07/schema",
        "resourceCount": resource_count,
    }


def walk(value: Any) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield (), value
    if isinstance(value, dict):
        for key, child in value.items():
            for suffix, nested in walk(child):
                yield (key, *suffix), nested
    elif isinstance(value, list):
        for index, child in enumerate(value):
            for suffix, nested in walk(child):
                yield (str(index), *suffix), nested


def json_pointer(document: Any, fragment: str, description: str) -> Any:
    if not fragment:
        return document
    if not fragment.startswith("/"):
        raise ContractToolError(f"unsupported non-pointer fragment in {description}")
    current = document
    for raw_token in fragment[1:].split("/"):
        token = unquote(raw_token).replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                current = current[int(token)]
            else:
                current = current[token]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ContractToolError(f"unresolved JSON Pointer in {description}") from error
    return current


def resolve_file_reference(document_path: Path, reference: str) -> tuple[Path, Any]:
    if reference.startswith(("http://", "https://")):
        raise ContractToolError(f"runtime network reference forbidden: {reference}")
    path_text, separator, fragment = reference.partition("#")
    target_path = (document_path.parent / path_text).resolve() if path_text else document_path.resolve()
    try:
        target_path.relative_to(CONTRACTS_ROOT.resolve())
    except ValueError as error:
        raise ContractToolError(f"projection reference escapes contracts/: {reference}") from error
    target = load_json(target_path)
    return target_path, json_pointer(target, fragment if separator else "", reference)


def resolve_projection_object(
    document_path: Path, value: Any, description: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractToolError(f"{description} is not an object")
    if isinstance(value.get("$ref"), str):
        _, value = resolve_file_reference(document_path, value["$ref"])
    if not isinstance(value, dict):
        raise ContractToolError(f"{description} does not resolve to an object")
    return value


def check_projection_root(
    document: Any,
    fixed_fields: set[str],
    identity_field: str,
    expected_document_uri: str,
    description: str,
) -> None:
    if not isinstance(document, dict):
        raise ContractToolError(f"{description} root is not an object")
    unknown_fixed = sorted(
        key
        for key in document
        if key not in fixed_fields and not EXTENSION_FIELD_PATTERN.fullmatch(key)
    )
    if unknown_fixed:
        raise ContractToolError(f"{description} root has unknown fixed fields: {unknown_fixed}")
    if document.get(identity_field) != expected_document_uri:
        raise ContractToolError(f"{description} has no exact stable document URI identity")


def check_header_object(path: Path, value: Any, description: str) -> None:
    if not isinstance(value, dict):
        raise ContractToolError(f"{description} is not an object")
    if "$ref" in value:
        if not isinstance(value["$ref"], str):
            raise ContractToolError(f"{description} reference is not a string")
        unknown_reference_fields = sorted(
            key
            for key in value
            if key not in REFERENCE_OBJECT_FIELDS and not EXTENSION_FIELD_PATTERN.fullmatch(key)
        )
        if unknown_reference_fields:
            raise ContractToolError(
                f"{description} reference has unknown fields: {unknown_reference_fields}"
            )
        for field in ("summary", "description"):
            if field in value and not isinstance(value[field], str):
                raise ContractToolError(
                    f"{description} reference {field} field is not a string"
                )
        resolved = resolve_projection_object(path, value, description)
        check_header_object(path, resolved, f"resolved {description}")
        return
    unknown_fields = sorted(
        key
        for key in value
        if key not in HEADER_OBJECT_FIELDS and not EXTENSION_FIELD_PATTERN.fullmatch(key)
    )
    if unknown_fields:
        raise ContractToolError(f"{description} has unknown Header Object fields: {unknown_fields}")
    if ("schema" in value) == ("content" in value):
        raise ContractToolError(f"{description} must use exactly one of schema or content")
    if "example" in value and "examples" in value:
        raise ContractToolError(f"{description} cannot use both example and examples")
    if "description" in value and not isinstance(value["description"], str):
        raise ContractToolError(f"{description} description field is not a string")
    for field in ("required", "deprecated", "explode"):
        if field in value and not isinstance(value[field], bool):
            raise ContractToolError(f"{description} {field} field is not boolean")
    if "examples" in value and not isinstance(value["examples"], dict):
        raise ContractToolError(f"{description} examples field is not an object")
    if value.get("style", "simple") != "simple":
        raise ContractToolError(f"{description} uses a non-header serialization style")
    if "content" in value and (
        not isinstance(value["content"], dict) or len(value["content"]) != 1
    ):
        raise ContractToolError(f"{description} content must contain exactly one media type")


def check_openapi_headers(path: Path, document: Any) -> int:
    count = 0
    components = document.get("components", {})
    component_headers = components.get("headers", {}) if isinstance(components, dict) else {}
    if not isinstance(component_headers, dict):
        raise ContractToolError("OpenAPI components.headers is not an object")
    for name, value in component_headers.items():
        check_header_object(path, value, f"component header {name}")
        count += 1
    for location, value in walk(document):
        if not isinstance(value, dict) or "headers" not in value or location == ("components",):
            continue
        # Schema properties named "headers" are JSON data models, not OAS
        # Header Object maps.
        if "schemas" in location:
            continue
        headers = value["headers"]
        if not isinstance(headers, dict):
            raise ContractToolError(f"OpenAPI headers map is invalid at {'/'.join(location)}")
        for name, header in headers.items():
            check_header_object(path, header, f"header {name} at {'/'.join(location)}")
            count += 1
    return count


def check_accepted_action_response(path: Path, response: Any, operation_id: str) -> None:
    response = resolve_projection_object(path, response, f"202 response for {operation_id}")
    headers = response.get("headers")
    if not isinstance(headers, dict) or set(headers) != ACCEPTED_ACTION_HEADERS:
        raise ContractToolError(
            f"202 response for {operation_id} must expose the exact accepted-action headers"
        )
    for header_name, header in headers.items():
        resolved_header = resolve_projection_object(
            path, header, f"{header_name} response header for {operation_id}"
        )
        if resolved_header.get("required") is not True:
            raise ContractToolError(
                f"202 response header {header_name} is not required for {operation_id}"
            )
    location = resolve_projection_object(
        path, headers["Location"], f"Location response header for {operation_id}"
    )
    if location.get("schema") != {
        "type": "string",
        "format": "uri-reference",
        "pattern": "^/v1/actions/[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        "maxLength": 256,
    }:
        raise ContractToolError(f"202 Location does not identify an exact action for {operation_id}")
    content = response.get("content")
    try:
        response_schema = content["application/json"]["schema"]
    except (KeyError, TypeError) as error:
        raise ContractToolError(f"202 response for {operation_id} has no JSON action body") from error
    if response_schema != {"$ref": "#/components/schemas/Action"}:
        raise ContractToolError(f"202 response for {operation_id} does not return an Action")


def check_references(document_path: Path, document: Any) -> list[str]:
    resolved: list[str] = []
    for location, value in walk(document):
        if not isinstance(value, dict) or "$ref" not in value:
            continue
        reference = value["$ref"]
        if not isinstance(reference, str):
            raise ContractToolError(f"non-string $ref at {'/'.join(location)}")
        target_path, _ = resolve_file_reference(document_path, reference)
        resolved.append(repository_path(target_path))
        if "schemas" in location and target_path.parent != SCHEMAS_ROOT.resolve():
            raise ContractToolError(
                f"schema projection must reference normative schemas/v1 source: {reference}"
            )
    return sorted(set(resolved))


def check_schema_projection_digests(
    document_path: Path,
    document: Any,
    expected_topology: dict[str, tuple[str, str, str]],
    additional_names: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    components = document.get("components", {})
    schemas = components.get("schemas", {})
    if not isinstance(schemas, dict) or not schemas:
        raise ContractToolError(f"{repository_path(document_path)} has no schema projections")
    expected_names = set(expected_topology) | (additional_names or set())
    if set(schemas) != expected_names:
        raise ContractToolError(
            f"{repository_path(document_path)} schema component topology drift"
        )
    evidence: dict[str, dict[str, str]] = {}
    for name, (expected_ref, expected_id, expected_digest) in expected_topology.items():
        projection = schemas[name]
        if not isinstance(projection, dict) or not isinstance(projection.get("$ref"), str):
            raise ContractToolError(f"component schema {name} is not a pure normative $ref projection")
        allowed = {"$ref", "x-bytedesk-schema-id", "x-bytedesk-schema-digest"}
        unexpected = sorted(set(projection) - allowed)
        if unexpected:
            raise ContractToolError(f"component schema {name} duplicates fields: {unexpected}")
        if projection.get("$ref") != expected_ref:
            raise ContractToolError(f"component schema {name} has wrong normative reference")
        if projection.get("x-bytedesk-schema-id") != expected_id:
            raise ContractToolError(f"component schema {name} has wrong schema ID binding")
        if projection.get("x-bytedesk-schema-digest") != expected_digest:
            raise ContractToolError(f"component schema {name} has wrong digest binding")
        target_path, target = resolve_file_reference(document_path, projection["$ref"])
        source_schema = load_json(target_path)
        if (
            target_path.parent != SCHEMAS_ROOT.resolve()
            or not isinstance(target, dict)
            or not isinstance(source_schema, dict)
        ):
            raise ContractToolError(f"component schema {name} does not reference a source schema")
        if projection.get("x-bytedesk-schema-id") != source_schema.get("$id"):
            raise ContractToolError(f"component schema {name} has stale schema ID")
        if projection.get("x-bytedesk-schema-digest") != canonical_digest(source_schema):
            raise ContractToolError(f"component schema {name} has stale canonical digest")
        evidence[name] = {
            "ref": expected_ref,
            "schemaId": expected_id,
            "schemaDigest": expected_digest,
        }
    return evidence


def check_openapi(path: Path) -> dict[str, Any]:
    document = load_json(path)
    official_schema = validate_official_openapi(document)
    check_projection_root(document, OPENAPI_ROOT_FIELDS, "$self", OPENAPI_DOCUMENT_URI, "OpenAPI")
    check_openapi_topology(document)
    if document.get("openapi") != "3.2.0":
        raise ContractToolError("OpenAPI projection must declare 3.2.0")
    if document.get("jsonSchemaDialect") != "https://json-schema.org/draft/2020-12/schema":
        raise ContractToolError("OpenAPI projection must declare Draft 2020-12")
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ContractToolError("OpenAPI projection has no paths")
    operation_ids: set[str] = set()
    mutation_count = 0
    accepted_action_count = 0
    authenticated_mutation_count = 0
    for resource_path, item in paths.items():
        if not resource_path.startswith("/v1/") or not isinstance(item, dict):
            raise ContractToolError(f"invalid v1 OpenAPI path: {resource_path}")
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete", "parameters"}:
                continue
            if method == "parameters":
                continue
            if not isinstance(operation, dict):
                raise ContractToolError(f"invalid operation {method} {resource_path}")
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or operation_id in operation_ids:
                raise ContractToolError(f"missing/duplicate operationId at {method} {resource_path}")
            operation_ids.add(operation_id)
            responses = operation.get("responses")
            if not isinstance(responses, dict) or "default" not in responses:
                raise ContractToolError(f"operation lacks default problem response: {operation_id}")
            if method in {"post", "put", "patch", "delete"}:
                mutation_count += 1
                security = operation.get("security")
                if not isinstance(security, list) or not security or {} in security:
                    raise ContractToolError(f"mutation {operation_id} permits an anonymous caller")
                authenticated_mutation_count += 1
                parameters = operation.get("parameters", [])
                header_parameters: dict[str, dict[str, Any]] = {}
                for parameter in parameters:
                    if not isinstance(parameter, dict):
                        continue
                    resolved_parameter = resolve_projection_object(
                        path, parameter, f"parameter for {operation_id}"
                    )
                    if (
                        resolved_parameter.get("in") == "header"
                        and isinstance(resolved_parameter.get("name"), str)
                    ):
                        header_name = resolved_parameter["name"]
                        if header_name in header_parameters:
                            raise ContractToolError(
                                f"mutation {operation_id} repeats header {header_name}"
                            )
                        header_parameters[header_name] = resolved_parameter
                required_headers = {"Idempotency-Key", "X-Canonical-Request-Digest"}
                if not required_headers.issubset(header_parameters):
                    raise ContractToolError(
                        f"mutation {operation_id} lacks idempotency/canonical-digest headers"
                    )
                if any(
                    header_parameters[name].get("required") is not True
                    for name in required_headers
                ):
                    raise ContractToolError(
                        f"mutation {operation_id} has an optional idempotency/digest header"
                    )
                precondition_headers = {"If-Match", "If-None-Match"}.intersection(
                    header_parameters
                )
                if not precondition_headers:
                    raise ContractToolError(f"mutation {operation_id} lacks an HTTP precondition")
                if len(precondition_headers) == 1 and any(
                    header_parameters[name].get("required") is not True
                    for name in precondition_headers
                ):
                    raise ContractToolError(
                        f"mutation {operation_id} has no required HTTP precondition"
                    )
                if len(precondition_headers) == 2 and operation_id != "submitCommand":
                    raise ContractToolError(
                        f"mutation {operation_id} has ambiguous conditional headers"
                    )
                if "202" in responses:
                    check_accepted_action_response(path, responses["202"], operation_id)
                    accepted_action_count += 1
            if operation_id == "submitCommand":
                if operation.get("security") != [{"consumerBearer": []}]:
                    raise ContractToolError("submitCommand must require consumerBearer authentication")
                if operation.get("x-bytedesk-command-authorization") != COMMAND_AUTHORIZATION_PROFILE:
                    raise ContractToolError("submitCommand authorization profile is not fail-closed")
                if (
                    operation.get("x-bytedesk-conditional-request")
                    != COMMAND_CONDITIONAL_REQUEST_PROFILE
                ):
                    raise ContractToolError("submitCommand conditional request profile has drifted")
                if set(responses) != {"202", "default"}:
                    raise ContractToolError("submitCommand must return only 202 or a problem response")
                if not {"If-Match", "If-None-Match"}.issubset(header_parameters):
                    raise ContractToolError("submitCommand does not project both conditional headers")
                if any(
                    header_parameters[name].get("required") is not False
                    for name in {"If-Match", "If-None-Match"}
                ):
                    raise ContractToolError(
                        "submitCommand conditional headers must be selected by the body precondition"
                    )
            if operation_id == "appendObservation":
                if operation.get("security") != [{"targetReconcilerBearer": []}]:
                    raise ContractToolError(
                        "appendObservation must require targetReconcilerBearer authentication"
                    )
                if (
                    operation.get("x-bytedesk-conditional-request")
                    != OBSERVATION_CONDITIONAL_REQUEST_PROFILE
                ):
                    raise ContractToolError(
                        "appendObservation conditional request profile has drifted"
                    )
                if set(header_parameters).intersection({"If-Match", "If-None-Match"}) != {
                    "If-Match"
                } or header_parameters["If-Match"].get("required") is not True:
                    raise ContractToolError(
                        "appendObservation must require only the exact If-Match condition"
                    )
            if operation_id == "appendCapabilityEvidence":
                if operation.get("security") != [{"capabilityVerifierMtls": []}]:
                    raise ContractToolError(
                        "appendCapabilityEvidence must require capabilityVerifierMtls"
                    )
                if set(header_parameters).intersection(
                    {"If-Match", "If-None-Match"}
                ) != {"If-None-Match"} or header_parameters[
                    "If-None-Match"
                ].get(
                    "schema"
                ) != {
                    "const": "*"
                }:
                    raise ContractToolError(
                        "appendCapabilityEvidence must require create-only If-None-Match star"
                    )
    referenced = check_references(path, document)
    header_object_count = check_openapi_headers(path, document)
    schema_components = check_schema_projection_digests(
        path,
        document,
        OPENAPI_SCHEMA_COMPONENT_TOPOLOGY,
        set(OPENAPI_PROTOCOL_SCHEMA_COMPONENT_TOPOLOGY),
    )
    return {
        "path": repository_path(path),
        "operationCount": len(operation_ids),
        "mutationCount": mutation_count,
        "authenticatedMutationCount": authenticated_mutation_count,
        "acceptedActionResponseCount": accepted_action_count,
        "headerObjectUseCount": header_object_count,
        "schemaProjectionCount": len(schema_components),
        "schemaComponents": schema_components,
        "officialSchema": official_schema,
        "resolvedFiles": referenced,
    }


def check_asyncapi(path: Path) -> dict[str, Any]:
    document = load_json(path)
    official_schema = validate_official_asyncapi(document)
    check_projection_root(
        document,
        ASYNCAPI_ROOT_FIELDS,
        "x-bytedesk-document-uri",
        ASYNCAPI_DOCUMENT_URI,
        "AsyncAPI",
    )
    check_asyncapi_topology(document)
    if document.get("asyncapi") != "3.1.0":
        raise ContractToolError("AsyncAPI projection must declare 3.1.0")
    if document.get("defaultContentType") != "application/cloudevents+json":
        raise ContractToolError("AsyncAPI must require structured JSON CloudEvents")
    channels = document.get("channels")
    operations = document.get("operations")
    if not isinstance(channels, dict) or not channels:
        raise ContractToolError("AsyncAPI projection has no channels")
    if not isinstance(operations, dict) or not operations:
        raise ContractToolError("AsyncAPI projection has no receive operations")
    event_types = validate_event_type_registry(load_json(EVENT_TYPES_PATH))
    try:
        projected_event_types = document["components"]["messages"][
            "AgentDeliveryNotification"
        ]["payload"]["properties"]["type"]["enum"]
    except (KeyError, TypeError) as error:
        raise ContractToolError("AsyncAPI message has no closed event-type enum") from error
    if projected_event_types != list(event_types):
        raise ContractToolError("AsyncAPI event-type enum differs from the closed registry")
    for name, operation in operations.items():
        if not isinstance(operation, dict) or operation.get("action") != "receive":
            raise ContractToolError(f"event operation {name} must describe consumer receive")
        traits = operation.get("traits", [])
        if not any(
            isinstance(trait, dict) and trait.get("x-bytedesk-delivery") == "at-least-once"
            for trait in traits
        ):
            raise ContractToolError(f"event operation {name} lacks at-least-once trait")
    referenced = check_references(path, document)
    schema_components = check_schema_projection_digests(
        path, document, ASYNCAPI_SCHEMA_COMPONENT_TOPOLOGY
    )
    return {
        "path": repository_path(path),
        "channelCount": len(channels),
        "operationCount": len(operations),
        "schemaProjectionCount": len(schema_components),
        "schemaComponents": schema_components,
        "officialSchema": official_schema,
        "resolvedFiles": referenced,
    }


def validate_event_type_registry(document: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict):
        raise ContractToolError("event type registry root is not an object")
    unexpected = sorted(set(document) - EVENT_TYPE_ROOT_FIELDS)
    if unexpected:
        raise ContractToolError(
            f"event type registry root has unknown fields: {unexpected}"
        )
    missing = sorted(EVENT_TYPE_ROOT_FIELDS - set(document))
    if missing:
        raise ContractToolError(f"event type registry root lacks fields: {missing}")
    event_type_entries = document["eventTypes"]
    if (
        document["$schema"]
        != "https://schemas.bytedesk.ai/agent-delivery/v1/event-types/1.0.0"
        or document["profile"] != "bytedesk.event-types/1"
        or document["cloudEventsVersion"] != "1.0.2"
        or document["delivery"] != "at-least-once"
        or document["ordering"] != "per-aggregate-sequence"
        or document["authority"] != "notification-only"
        or document["registryCompatibility"] != EVENT_REGISTRY_COMPATIBILITY
        or document["resynchronization"] != EVENT_REGISTRY_RESYNCHRONIZATION
        or not isinstance(event_type_entries, list)
        or not event_type_entries
    ):
        raise ContractToolError("event type registry has an invalid closed profile")
    event_types: dict[str, dict[str, Any]] = {}
    for entry in event_type_entries:
        if not isinstance(entry, dict):
            raise ContractToolError("event type registry entry is malformed")
        if set(entry) != EVENT_TYPE_ENTRY_FIELDS:
            raise ContractToolError(
                f"event type registry entry has unknown fields: {entry.get('type')}"
            )
        if not all(isinstance(entry[key], str) and entry[key] for key in EVENT_TYPE_ENTRY_FIELDS):
            raise ContractToolError("event type registry entry is malformed")
        if entry["redaction"] not in EVENT_REDACTION_CLASSES:
            raise ContractToolError(
                f"event type registry has unknown redaction class: {entry['type']}"
            )
        if entry["type"] in event_types:
            raise ContractToolError(f"duplicate event type: {entry['type']}")
        event_types[entry["type"]] = entry
    return event_types


def resource_uri_matches_template(template: str, uri: str) -> bool:
    if not template.startswith("/v1/") or not uri.startswith("/v1/"):
        return False
    template_segments = template.strip("/").split("/")
    resource_segments = uri.strip("/").split("/")
    if len(template_segments) != len(resource_segments):
        return False
    for template_segment, resource_segment in zip(
        template_segments, resource_segments, strict=True
    ):
        if template_segment.startswith("{") and template_segment.endswith("}"):
            parameter_name = template_segment[1:-1]
            if not parameter_name or not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9]*", parameter_name
            ):
                return False
            if not re.fullmatch(OPENAPI_IDENTIFIER_PATTERN, resource_segment):
                return False
        elif template_segment != resource_segment:
            return False
    return True


def openapi_json_response_schema_descriptor(
    document: dict[str, Any], operation: dict[str, Any], operation_id: str
) -> dict[str, str]:
    try:
        response_ref = operation["responses"]["200"]["$ref"]
        if not isinstance(response_ref, str) or not response_ref.startswith(
            "#/components/responses/"
        ):
            raise KeyError("response reference")
        response_name = response_ref.removeprefix("#/components/responses/")
        response = document["components"]["responses"][response_name]
        schema_ref = response["content"]["application/json"]["schema"]["$ref"]
        if not isinstance(schema_ref, str) or not schema_ref.startswith(
            "#/components/schemas/"
        ):
            raise KeyError("schema reference")
        schema_name = schema_ref.removeprefix("#/components/schemas/")
        projection = document["components"]["schemas"][schema_name]
        schema_id = projection["x-bytedesk-schema-id"]
        schema_digest = projection["x-bytedesk-schema-digest"]
    except (KeyError, TypeError) as error:
        raise ContractToolError(
            f"event resynchronization operation has no exact JSON schema: {operation_id}"
        ) from error
    if not isinstance(schema_id, str) or not isinstance(schema_digest, str):
        raise ContractToolError(
            f"event resynchronization operation has no exact JSON schema: {operation_id}"
        )
    return {"id": schema_id, "digest": schema_digest}


def check_event_registry_bindings(
    event_types_document: Any, openapi_document: Any
) -> dict[str, dict[str, Any]]:
    event_types = validate_event_type_registry(event_types_document)
    if not isinstance(openapi_document, dict) or not isinstance(
        openapi_document.get("paths"), dict
    ):
        raise ContractToolError("OpenAPI projection has no paths for event resynchronization")
    known_schema_digests: dict[str, str] = {}
    for schema_path in sorted(SCHEMAS_ROOT.glob("*.schema.json")):
        schema = load_json(schema_path)
        schema_id = schema.get("$id") if isinstance(schema, dict) else None
        if not isinstance(schema_id, str) or schema_id in known_schema_digests:
            raise ContractToolError(
                f"invalid or duplicate live schema identity: {repository_path(schema_path)}"
            )
        known_schema_digests[schema_id] = canonical_digest(schema)
    get_operations: dict[str, tuple[str, dict[str, Any]]] = {}
    for template, path_item in openapi_document["paths"].items():
        operation = path_item.get("get") if isinstance(path_item, dict) else None
        operation_id = operation.get("operationId") if isinstance(operation, dict) else None
        if isinstance(operation_id, str):
            if operation_id in get_operations:
                raise ContractToolError(
                    f"duplicate OpenAPI GET operationId: {operation_id}"
                )
            get_operations[operation_id] = (template, operation)
    for entry in event_types.values():
        schema_id = entry["resourceSchemaId"]
        expected_digest = known_schema_digests.get(schema_id)
        if expected_digest is None:
            raise ContractToolError(
                f"event type references unknown resource schema: {schema_id}"
            )
        if entry["resourceSchemaDigest"] != expected_digest:
            raise ContractToolError(
                f"event type resource schema digest drift: {entry['type']}"
            )
        operation_binding = get_operations.get(entry["resynchronizeOperationId"])
        if operation_binding is None:
            raise ContractToolError(
                f"event type references unknown resynchronization operation: {entry['type']}"
            )
        template, operation = operation_binding
        if template != entry["resourceUriTemplate"]:
            raise ContractToolError(
                f"event type resource URI template drift: {entry['type']}"
            )
        if not operation.get("security"):
            raise ContractToolError(
                f"event resynchronization operation is not authenticated: {entry['type']}"
            )
        descriptor = openapi_json_response_schema_descriptor(
            openapi_document, operation, entry["resynchronizeOperationId"]
        )
        if descriptor != {
            "id": entry["resourceSchemaId"],
            "digest": entry["resourceSchemaDigest"],
        }:
            raise ContractToolError(
                f"event resynchronization operation schema drift: {entry['type']}"
            )
    return event_types


def check_event_examples() -> dict[str, Any]:
    event_types_document = load_json(EVENT_TYPES_PATH)
    openapi_document = load_json(OPENAPI_PATH)
    event_types = check_event_registry_bindings(
        event_types_document, openapi_document
    )

    registry, schemas = build_registry()
    event_schema = schemas[EVENT_DATA_SCHEMA_ID][1]
    event_schema_digest = canonical_digest(event_schema)

    example_paths = sorted(EVENT_EXAMPLES_ROOT.glob("*.json"))
    if not example_paths:
        raise ContractToolError("event profile has no structured CloudEvent examples")
    required = {
        "specversion",
        "id",
        "source",
        "type",
        "subject",
        "time",
        "datacontenttype",
        "dataschema",
        "data",
    }
    results: list[dict[str, Any]] = []
    observed_event_types: set[str] = set()
    observed_event_ids: set[str] = set()
    for path in example_paths:
        event = load_json(path)
        if not isinstance(event, dict) or set(event) != required:
            raise ContractToolError(f"CloudEvent example has missing/unknown members: {path.name}")
        if event["specversion"] != "1.0" or event["datacontenttype"] != "application/json":
            raise ContractToolError(f"CloudEvent example is not structured JSON 1.0: {path.name}")
        if event["dataschema"] != EVENT_DATA_SCHEMA_ID:
            raise ContractToolError(f"CloudEvent example has wrong dataschema: {path.name}")
        event_type = event_types.get(event["type"])
        if event_type is None:
            raise ContractToolError(f"CloudEvent example uses unregistered type: {path.name}")
        if event["type"] in observed_event_types:
            raise ContractToolError(f"CloudEvent type has multiple examples: {event['type']}")
        if event["id"] in observed_event_ids:
            raise ContractToolError(f"CloudEvent example ID is duplicated: {event['id']}")
        observed_event_types.add(event["type"])
        observed_event_ids.add(event["id"])
        data = event["data"]
        errors = sorted(
            Draft202012Validator(
                event_schema,
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            ).iter_errors(data),
            key=validation_error_key,
        )
        if errors:
            raise ContractToolError(f"CloudEvent data rejected for {path.name}: {errors[0].message}")
        expected_descriptor = {"id": EVENT_DATA_SCHEMA_ID, "digest": event_schema_digest}
        if data["schema"] != expected_descriptor or data["dataSchema"] != expected_descriptor:
            raise ContractToolError(f"CloudEvent example has stale event schema descriptor: {path.name}")
        if data["eventType"] != event["type"]:
            raise ContractToolError(f"CloudEvent outer/data type mismatch: {path.name}")
        if data["aggregate"]["type"] != event_type["aggregateType"]:
            raise ContractToolError(f"CloudEvent aggregate type mismatch: {path.name}")
        if data["redaction"] != event_type["redaction"]:
            raise ContractToolError(
                f"CloudEvent redaction class differs from registry: {path.name}"
            )
        if data["resource"]["etag"] != data["aggregate"]["revisionDigest"]:
            raise ContractToolError(f"CloudEvent resource ETag/revision mismatch: {path.name}")
        projection = data["resource"]["projectionSchema"]
        if projection != {
            "id": event_type["resourceSchemaId"],
            "digest": event_type["resourceSchemaDigest"],
        }:
            raise ContractToolError(f"CloudEvent resource projection descriptor is stale: {path.name}")
        if not resource_uri_matches_template(
            event_type["resourceUriTemplate"], data["resource"]["uri"]
        ):
            raise ContractToolError(
                f"CloudEvent resource URI does not match registered template: {path.name}"
            )
        results.append(
            {
                "path": repository_path(path),
                "type": event["type"],
                "sequence": data["aggregate"]["sequence"],
                "resynchronizeOperationId": event_type["resynchronizeOperationId"],
                "redaction": event_type["redaction"],
            }
        )
    if observed_event_types != set(event_types):
        raise ContractToolError(
            "CloudEvent example coverage differs from registry "
            f"missing={sorted(set(event_types) - observed_event_types)} "
            f"extra={sorted(observed_event_types - set(event_types))}"
        )
    cases_document = load_json(EVENT_CASES_PATH)
    cases = cases_document.get("cases")
    if cases_document.get("profile") != "bytedesk.event-conformance-cases/1" or not isinstance(
        cases, list
    ):
        raise ContractToolError("event conformance cases have an invalid profile")
    expected_cases = {
        "next-sequence-applies-projection-only": (
            {"lastSequence": 7, "incomingSequence": 8, "eventIdSeen": False, "schemaKnown": True},
            "apply_projection",
        ),
        "duplicate-id-deduplicates": (
            {"lastSequence": 8, "incomingSequence": 8, "eventIdSeen": True, "schemaKnown": True},
            "deduplicate",
        ),
        "sequence-gap-resynchronizes": (
            {"lastSequence": 8, "incomingSequence": 10, "eventIdSeen": False, "schemaKnown": True},
            "stop_and_api_resynchronize",
        ),
        "reordered-event-does-not-move-backward": (
            {"lastSequence": 8, "incomingSequence": 7, "eventIdSeen": False, "schemaKnown": True},
            "retain_without_apply",
        ),
        "unknown-schema-resynchronizes": (
            {"lastSequence": 8, "incomingSequence": 9, "eventIdSeen": False, "schemaKnown": False},
            "stop_and_api_resynchronize",
        ),
        "sensitive-payload-is-rejected-and-redacted": (
            {
                "containsCredential": True,
                "containsRawPrivatePayload": False,
                "redactionClassification": "restricted",
            },
            "reject_and_record_redacted_diagnostic",
        ),
        "dead-letter-preserves-redacted-evidence": (
            {
                "deliveryAttemptsExhausted": True,
                "originalEnvelopePreserved": True,
                "diagnosticRedacted": True,
            },
            "dead_letter_preserve_evidence",
        ),
    }
    observed_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "input", "expected"}:
            raise ContractToolError("event conformance case is not closed")
        if not isinstance(case["id"], str) or case["id"] in observed_case_ids:
            raise ContractToolError("event conformance case has missing/duplicate ID")
        observed_case_ids.add(case["id"])
        event_input = case["input"]
        expected = case["expected"]
        expected_case = expected_cases.get(case["id"])
        if expected_case is None:
            raise ContractToolError(f"unknown event conformance case: {case['id']}")
        expected_input, expected_action = expected_case
        if event_input != expected_input:
            raise ContractToolError(f"event conformance input drifted: {case['id']}")
        if not isinstance(expected, dict) or set(expected) != {"action", "authoritativeWrite"}:
            raise ContractToolError(f"event conformance expectation is not closed: {case['id']}")
        if expected.get("action") != expected_action or expected["authoritativeWrite"] is not False:
            raise ContractToolError(f"event case has an invalid closed expectation: {case['id']}")
    if observed_case_ids != set(expected_cases):
        raise ContractToolError(
            f"event conformance coverage drift missing={sorted(set(expected_cases)-observed_case_ids)} "
            f"extra={sorted(observed_case_ids-set(expected_cases))}"
        )
    return {
        "registryPath": repository_path(EVENT_TYPES_PATH),
        "conformanceCasesPath": repository_path(EVENT_CASES_PATH),
        "eventTypeCount": len(event_types),
        "conformanceCaseCount": len(cases),
        "examples": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi", type=Path, default=OPENAPI_PATH)
    parser.add_argument("--asyncapi", type=Path, default=ASYNCAPI_PATH)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = {
        "profile": "bytedesk.projection-validation-evidence/1",
        "vendorDependencies": check_pinned_vendor_files(),
        "openapi": check_openapi(args.openapi),
        "asyncapi": check_asyncapi(args.asyncapi),
        "events": check_event_examples(),
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
        print(f"projection validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
