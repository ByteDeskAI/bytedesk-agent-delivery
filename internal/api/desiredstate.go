// Package api implements a real, tractable slice of AD-10: the
// TargetDeliveryState read/CAS HTTP surface over internal/desiredstate,
// using strong ETags and absent/match conditional-request semantics
// (required-work item 9, item 11) and RFC 9457 problem responses on
// conflict (required-work item 5, using the exact field names in
// contracts/schemas/v1/problem-details.schema.json).
//
// # ponytail
//
// This is one resource family (desired-state read/CAS) of AD-10's full
// scope, not the whole task. Not built here: catalog/inspect/render
// endpoints, installation preview/commit flows, OpenAPI/AsyncAPI document
// generation, generated Go/Python/TypeScript clients, CloudEvents outbox,
// authentication/authorization-decision enforcement, and pagination. Each
// is a further slice; see docs/planning/tasks/AD-10-control-plane-api.md
// for the complete required-work list.
package api

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/desiredstate"
)

const (
	portID          = "bytedesk.port.desired-state-store/1"
	problemDocsBase = "https://docs.bytedesk.ai/agent-delivery/problems/"
)

// resolveCorrelationID returns the caller-supplied correlation ID if present,
// otherwise generates one. contracts/schemas/v1/problem-details.schema.json
// requires a non-empty identifier - an absent X-Correlation-Id header must
// never become an empty string in the response.
func resolveCorrelationID(supplied string) string {
	if supplied != "" {
		return supplied
	}
	var raw [16]byte
	_, _ = rand.Read(raw[:])
	return "cid-" + hex.EncodeToString(raw[:])
}

// catalogEntry mirrors the fixed type/status/retryable triple every code
// carries in contracts/ports/v1/problem-catalog.json. type/status/retryable
// are properties of the code alone, not caller-chosen per response - a
// caller only selects which registered code applies and, where the
// registered operation's error list permits more than one, which
// sideEffectState.
var problemCatalog = map[string]struct {
	problemType string
	status      int
	retryable   bool
}{
	"invalid_request":              {"https://problems.bytedesk.ai/agent-delivery/invalid-request", http.StatusBadRequest, false},
	"resource_not_found":           {"https://problems.bytedesk.ai/agent-delivery/resource-not-found", http.StatusNotFound, false},
	"dependency_unavailable":       {"https://problems.bytedesk.ai/agent-delivery/dependency-unavailable", http.StatusServiceUnavailable, true},
	"desired_state_cas_mismatch":   {"https://problems.bytedesk.ai/agent-delivery/desired-state-cas-mismatch", http.StatusPreconditionFailed, false},
	"desired_state_wrong_writer":   {"https://problems.bytedesk.ai/agent-delivery/desired-state-wrong-writer", http.StatusForbidden, false},
	"idempotency_collision":        {"https://problems.bytedesk.ai/agent-delivery/idempotency-collision", http.StatusConflict, false},
	"desired_state_commit_unknown": {"https://problems.bytedesk.ai/agent-delivery/desired-state-commit-unknown", http.StatusServiceUnavailable, true},
	"region_epoch_stale":           {"https://problems.bytedesk.ai/agent-delivery/region-epoch-stale", http.StatusConflict, false},
}

type problemDetails struct {
	Type             string `json:"type"`
	Title            string `json:"title"`
	Status           int    `json:"status"`
	Code             string `json:"code"`
	PortID           string `json:"portId"`
	OperationID      string `json:"operationId"`
	CorrelationID    string `json:"correlationId"`
	Retryable        bool   `json:"retryable"`
	SideEffectState  string `json:"sideEffectState"`
	Violations       []any  `json:"violations"`
	Documentation    string `json:"documentation"`
	ExpectedRevision int64  `json:"expectedRevision,omitempty"`
	CurrentRevision  int64  `json:"currentRevision,omitempty"`
	ExpectedDigest   string `json:"expectedDigest,omitempty"`
	CurrentDigest    string `json:"currentDigest,omitempty"`
}

// writeProblem writes a bytedesk.problem-details/1 response. status,
// type, and retryable are looked up from problemCatalog by code - never
// chosen ad hoc by the caller - so every response is a member of the
// schema's closed set by construction.
func writeProblem(w http.ResponseWriter, code, sideEffectState, title, operationID, correlationID string, mutate func(*problemDetails)) {
	entry, known := problemCatalog[code]
	if !known {
		panic("api: unregistered problem code: " + code)
	}
	problem := problemDetails{
		Type:            entry.problemType,
		Title:           title,
		Status:          entry.status,
		Code:            code,
		PortID:          portID,
		OperationID:     operationID,
		CorrelationID:   resolveCorrelationID(correlationID),
		Retryable:       entry.retryable,
		SideEffectState: sideEffectState,
		Violations:      []any{},
		Documentation:   problemDocsBase + strings.ReplaceAll(code, "_", "-"),
	}
	if mutate != nil {
		mutate(&problem)
	}
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(entry.status)
	_ = json.NewEncoder(w).Encode(problem)
}

// DesiredStateHandler exposes read-target-state and compare-and-swap-target-state
// (bytedesk.port.desired-state-store/1) over HTTP for one target-delivery-state
// resource, addressed as /consumers/{consumerId}/targets/{targetId}/desired-state.
type DesiredStateHandler struct {
	Store *desiredstate.Store
}

// routingProblem reports a request that never reaches a real port operation
// (unknown path, unsupported method). It reuses read-target-state's
// registered resource_not_found/none combination - the one closed code
// every path through this handler can validly report before an operation
// is even identified. The catalog fixes its HTTP status to 404 regardless
// of the routing reason (e.g. an unsupported method on a matched path is
// also reported as 404, not 405, to stay inside the closed contract).
func routingProblem(w http.ResponseWriter, title, correlationID string) {
	writeProblem(w, "resource_not_found", "none", title, "read-target-state", correlationID, nil)
}

func (h *DesiredStateHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	consumerID, targetID, ok := parseTargetPath(r.URL.Path)
	if !ok {
		routingProblem(w, "unknown desired-state resource path", r.Header.Get("X-Correlation-Id"))
		return
	}

	switch r.Method {
	case http.MethodGet:
		h.get(w, r, consumerID, targetID)
	case http.MethodPut:
		h.put(w, r, consumerID, targetID)
	default:
		routingProblem(w, "method not allowed", r.Header.Get("X-Correlation-Id"))
	}
}

func parseTargetPath(path string) (consumerID, targetID string, ok bool) {
	const prefix = "/consumers/"
	const suffix = "/desired-state"
	if !strings.HasPrefix(path, prefix) || !strings.HasSuffix(path, suffix) {
		return "", "", false
	}
	middle := strings.TrimSuffix(strings.TrimPrefix(path, prefix), suffix)
	parts := strings.SplitN(middle, "/targets/", 2)
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", "", false
	}
	return parts[0], parts[1], true
}

func (h *DesiredStateHandler) get(w http.ResponseWriter, r *http.Request, consumerID, targetID string) {
	record, exists := h.Store.Read(consumerID, targetID)
	if !exists {
		writeProblem(w, "resource_not_found", "none", "no desired state for this target", "read-target-state", r.Header.Get("X-Correlation-Id"), nil)
		return
	}
	w.Header().Set("ETag", strongETag(record.Revision, record.Digest))
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(record.Payload)
}

// put implements compare-and-swap-target-state. The precondition is derived
// entirely from standard HTTP conditional-request headers, never a body
// field a caller could spoof independently of the transport-level check:
//   - If-None-Match: * -> absent (initial creation only)
//   - If-Match: "<revision>-<digest>" -> match(revision, digest)
//
// Any other combination (missing header, wildcard If-Match, malformed ETag)
// is rejected before the store is touched - "wildcard/null/digest-only/
// lease-only mutation... fail without side effects."
func (h *DesiredStateHandler) put(w http.ResponseWriter, r *http.Request, consumerID, targetID string) {
	correlationID := r.Header.Get("X-Correlation-Id")

	var payload json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeCASProblem(w, "invalid_request", "request body is not valid JSON", correlationID, nil)
		return
	}

	precondition, ok := parsePrecondition(r.Header.Get("If-None-Match"), r.Header.Get("If-Match"))
	if !ok {
		writeCASProblem(w, "invalid_request", "a strong If-None-Match: * or If-Match precondition is required", correlationID, nil)
		return
	}

	record, err := h.Store.CompareAndSwap(consumerID, targetID, precondition, payload)
	switch {
	case err == nil:
		w.Header().Set("ETag", strongETag(record.Revision, record.Digest))
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(record.Payload)
	case isPreconditionFailed(err):
		current, exists := h.Store.Read(consumerID, targetID)
		writeCASProblem(w, "desired_state_cas_mismatch", "desired-state precondition did not match current state", correlationID, func(p *problemDetails) {
			p.ExpectedRevision = precondition.Revision
			p.ExpectedDigest = precondition.Digest
			if exists {
				p.CurrentRevision = current.Revision
				p.CurrentDigest = current.Digest
			}
		})
	case isPreconditionInvalid(err):
		writeCASProblem(w, "invalid_request", err.Error(), correlationID, nil)
	default:
		writeCASProblem(w, "dependency_unavailable", "desired-state store is unavailable", correlationID, nil)
	}
}

// writeCASProblem writes a problem response for compare-and-swap-target-state,
// whose registered error catalog (contracts/ports/v1/port-registry.json) fixes
// sideEffectState to "not-committed" for every code but
// desired_state_commit_unknown - this handler never returns that code since
// it has no remote-commit uncertainty window.
func writeCASProblem(w http.ResponseWriter, code, title, correlationID string, mutate func(*problemDetails)) {
	writeProblem(w, code, "not-committed", title, "compare-and-swap-target-state", correlationID, func(p *problemDetails) {
		if mutate != nil {
			mutate(p)
		}
	})
}

func isPreconditionFailed(err error) bool {
	return errors.Is(err, desiredstate.ErrPreconditionFailed)
}

func isPreconditionInvalid(err error) bool {
	return errors.Is(err, desiredstate.ErrPreconditionInvalid)
}

func parsePrecondition(ifNoneMatch, ifMatch string) (desiredstate.Precondition, bool) {
	if ifNoneMatch != "" {
		if ifNoneMatch != "*" || ifMatch != "" {
			return desiredstate.Precondition{}, false
		}
		return desiredstate.Precondition{Kind: "absent"}, true
	}
	if ifMatch == "" || ifMatch == "*" {
		return desiredstate.Precondition{}, false
	}
	revision, digest, ok := parseStrongETag(ifMatch)
	if !ok {
		return desiredstate.Precondition{}, false
	}
	return desiredstate.Precondition{Kind: "match", Revision: revision, Digest: digest}, true
}
