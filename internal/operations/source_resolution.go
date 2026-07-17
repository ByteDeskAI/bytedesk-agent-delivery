package operations

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

// PinnedAgentSpecVersion is the only Agent Spec language version accepted by
// the v1 source contract. A version change is an intentional compatibility
// decision, never a floating dependency update.
const PinnedAgentSpecVersion = "26.1.2"

// AgentSpecSourceKind is the delivery-level discriminator recorded beside an
// exact public source. Agent Spec remains authoritative for document semantics.
type AgentSpecSourceKind string

const (
	AgentSpecSourceAgent            AgentSpecSourceKind = "agent"
	AgentSpecSourceSpecializedAgent AgentSpecSourceKind = "specialized-agent"
)

// AgentSpecValidator is the trusted Adapter to the official pinned Agent Spec
// validator. The core passes exact canonical bytes once and requires the
// Adapter's observed top-level kind to agree with the delivery manifest.
type AgentSpecValidator interface {
	ValidateAgentSpec(context.Context, string, []byte) (AgentSpecSourceKind, error)
}

// ResolvedAgentSpecSource preserves the complete official document while
// exposing the one embedded base Agent uniformly to downstream renderers. It
// deliberately does not flatten or reinterpret official specialization
// semantics.
type ResolvedAgentSpecSource struct {
	Kind              AgentSpecSourceKind
	Digest            string
	CanonicalDocument []byte
	Document          map[string]any
	BaseAgent         map[string]any
	Specialization    map[string]any
}

// ResolveAgentSpecSource enforces ByteDesk's exact-byte, kind, and one-time
// resolution boundary around a document accepted by the official SDK. Agent
// Spec 26.1.2 SpecializedAgent embeds one complete Agent and one complete
// AgentSpecializationParameters object; remote, package-relative, or nested
// specialization references are not a second delivery inheritance system.
func ResolveAgentSpecSource(
	ctx context.Context,
	declaredKind AgentSpecSourceKind,
	expectedDigest string,
	payload []byte,
	validator AgentSpecValidator,
) (ResolvedAgentSpecSource, error) {
	if ctx == nil {
		return ResolvedAgentSpecSource{}, errors.New("Agent Spec source resolution requires context")
	}
	if declaredKind != AgentSpecSourceAgent && declaredKind != AgentSpecSourceSpecializedAgent {
		return ResolvedAgentSpecSource{}, errors.New("unknown Agent Spec source kind")
	}
	if !digestPattern.MatchString(expectedDigest) {
		return ResolvedAgentSpecSource{}, errors.New("invalid exact Agent Spec source digest")
	}
	sum := sha256.Sum256(payload)
	observedDigest := "sha256:" + hex.EncodeToString(sum[:])
	if observedDigest != expectedDigest {
		return ResolvedAgentSpecSource{}, errors.New("Agent Spec source digest mismatch")
	}
	canonicalResult, err := canonical.CanonicalizeBytes(
		payload, canonical.FormatJSON, canonical.DefaultLimits(),
	)
	if err != nil {
		return ResolvedAgentSpecSource{}, fmt.Errorf("parse exact Agent Spec source: %w", err)
	}
	if !bytes.Equal(payload, canonicalResult.Bytes) {
		return ResolvedAgentSpecSource{}, errors.New("Agent Spec semantic source is not exact RFC 8785 bytes")
	}
	if validator == nil {
		return ResolvedAgentSpecSource{}, errors.New("official Agent Spec validator Adapter is absent")
	}
	officialKind, err := validator.ValidateAgentSpec(
		ctx,
		PinnedAgentSpecVersion,
		append([]byte(nil), canonicalResult.Bytes...),
	)
	if err != nil {
		return ResolvedAgentSpecSource{}, errors.New("official Agent Spec validation denied the source")
	}

	var document map[string]any
	decoder := json.NewDecoder(bytes.NewReader(canonicalResult.Bytes))
	decoder.UseNumber()
	if err := decoder.Decode(&document); err != nil || document == nil {
		return ResolvedAgentSpecSource{}, errors.New("Agent Spec source root is not an object")
	}
	if document["agentspec_version"] != PinnedAgentSpecVersion {
		return ResolvedAgentSpecSource{}, errors.New("Agent Spec document version is not the exact pinned delivery version")
	}
	if _, legacyVersion := document["air_version"]; legacyVersion {
		return ResolvedAgentSpecSource{}, errors.New("legacy air_version cannot substitute for agentspec_version")
	}
	observedKind, err := sourceKindFromComponentType(document["component_type"])
	if err != nil || observedKind != declaredKind {
		return ResolvedAgentSpecSource{}, errors.New("source component_type differs from its declared kind")
	}
	if officialKind != declaredKind {
		return ResolvedAgentSpecSource{}, errors.New("declared source kind differs from official Agent Spec kind")
	}

	base := document
	var specialization map[string]any
	if declaredKind == AgentSpecSourceSpecializedAgent {
		var ok bool
		base, ok = document["agent"].(map[string]any)
		if !ok || base == nil {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent must embed one complete Agent")
		}
		if _, officialReference := base["$component_ref"]; officialReference {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent base component reference is forbidden")
		}
		if _, genericReference := base["$ref"]; genericReference {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent base reference escape is forbidden")
		}
		baseKind, kindErr := sourceKindFromComponentType(base["component_type"])
		if kindErr != nil {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent embedded base has no official Agent kind")
		}
		if baseKind == AgentSpecSourceSpecializedAgent {
			return ResolvedAgentSpecSource{}, errors.New("nested SpecializedAgent resolution cycle is forbidden")
		}
		if baseKind != AgentSpecSourceAgent {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent base is not an Agent")
		}

		specialization, ok = document["agent_specialization_parameters"].(map[string]any)
		if !ok || specialization == nil {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent must embed specialization parameters")
		}
		if _, officialReference := specialization["$component_ref"]; officialReference {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent parameter component reference is forbidden")
		}
		if _, genericReference := specialization["$ref"]; genericReference {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent parameter reference escape is forbidden")
		}
		if specialization["component_type"] != "AgentSpecializationParameters" {
			return ResolvedAgentSpecSource{}, errors.New("SpecializedAgent parameters have the wrong component type")
		}
	}

	documentView, err := cloneJSONObject(document)
	if err != nil {
		return ResolvedAgentSpecSource{}, fmt.Errorf("clone resolved Agent Spec document: %w", err)
	}
	resolved := ResolvedAgentSpecSource{
		Kind:              declaredKind,
		Digest:            observedDigest,
		CanonicalDocument: append([]byte(nil), canonicalResult.Bytes...),
		Document:          documentView,
	}
	resolved.BaseAgent, err = cloneJSONObject(base)
	if err != nil {
		return ResolvedAgentSpecSource{}, fmt.Errorf("clone resolved base Agent: %w", err)
	}
	if specialization != nil {
		resolved.Specialization, err = cloneJSONObject(specialization)
		if err != nil {
			return ResolvedAgentSpecSource{}, fmt.Errorf("clone specialization parameters: %w", err)
		}
	}
	return resolved, nil
}

func cloneJSONObject(document map[string]any) (map[string]any, error) {
	clone, err := cloneJSON(document)
	if err != nil {
		return nil, err
	}
	object, ok := clone.(map[string]any)
	if !ok {
		return nil, errors.New("cloned JSON document is not an object")
	}
	return object, nil
}

func sourceKindFromComponentType(value any) (AgentSpecSourceKind, error) {
	switch value {
	case "Agent":
		return AgentSpecSourceAgent, nil
	case "SpecializedAgent":
		return AgentSpecSourceSpecializedAgent, nil
	default:
		return "", errors.New("unknown Agent Spec component_type")
	}
}

// RebaseJSONPatch applies an accepted functional delta to a proposed exact
// source only when the path context used by every ordered operation is stable
// between the previous and proposed sources. The document root is excluded
// from ancestor comparison so unrelated top-level changes may advance; a
// changed target, containing top-level subtree, parent, or array conflicts.
func RebaseJSONPatch(
	previous any,
	proposed any,
	patch JSONPatch,
	target FunctionalTarget,
) (any, error) {
	if patch.Profile != "bytedesk.json-patch/1" {
		return nil, fmt.Errorf("unsupported patch profile %q", patch.Profile)
	}
	if target != TargetAgentSpec && target != TargetRendererFunctionalConfig {
		return nil, fmt.Errorf("unsupported functional patch target %q", target)
	}
	if len(patch.Operations) > 10_000 {
		return nil, errors.New("patch exceeds 10000 operations")
	}
	previousWorking, err := cloneJSON(previous)
	if err != nil {
		return nil, fmt.Errorf("clone previous source: %w", err)
	}
	proposedWorking, err := cloneJSON(proposed)
	if err != nil {
		return nil, fmt.Errorf("clone proposed source: %w", err)
	}
	if _, ok := previousWorking.(map[string]any); !ok {
		return nil, errors.New("previous functional source must be a complete object")
	}
	if _, ok := proposedWorking.(map[string]any); !ok {
		return nil, errors.New("proposed functional source must be a complete object")
	}

	for index, operation := range patch.Operations {
		tokens, err := parsePointer(operation.Path)
		if err != nil {
			return nil, fmt.Errorf("operation %d: %w", index, err)
		}
		if err := stableRebasePath(previousWorking, proposedWorking, tokens); err != nil {
			return nil, fmt.Errorf("operation %d: three-way rebase conflict: %w", index, err)
		}
		value, err := patchOperationValue(operation, index)
		if err != nil {
			return nil, err
		}
		previousValue, err := cloneJSON(value)
		if err != nil {
			return nil, fmt.Errorf("operation %d value cannot be cloned: %w", index, err)
		}
		proposedValue, err := cloneJSON(value)
		if err != nil {
			return nil, fmt.Errorf("operation %d value cannot be cloned: %w", index, err)
		}
		previousWorking, err = applyJSONOperation(previousWorking, tokens, operation.Op, previousValue)
		if err != nil {
			return nil, fmt.Errorf("operation %d does not apply to previous source: %w", index, err)
		}
		previousWorking, err = cloneJSON(previousWorking)
		if err != nil {
			return nil, fmt.Errorf("operation %d previous result exceeds canonical resource limits: %w", index, err)
		}
		proposedWorking, err = applyJSONOperation(proposedWorking, tokens, operation.Op, proposedValue)
		if err != nil {
			return nil, fmt.Errorf("operation %d does not apply to proposed source: %w", index, err)
		}
		proposedWorking, err = cloneJSON(proposedWorking)
		if err != nil {
			return nil, fmt.Errorf("operation %d proposed result exceeds canonical resource limits: %w", index, err)
		}
	}
	return proposedWorking, nil
}

func stableRebasePath(previous, proposed any, tokens []string) error {
	if len(tokens) == 0 {
		return errors.New("empty root pointer is forbidden")
	}
	previousRoot, previousObject := previous.(map[string]any)
	proposedRoot, proposedObject := proposed.(map[string]any)
	if !previousObject || !proposedObject {
		return errors.New("functional source root changed type")
	}
	previousValue, previousExists := previousRoot[tokens[0]]
	proposedValue, proposedExists := proposedRoot[tokens[0]]
	if previousExists != proposedExists || (previousExists && !reflect.DeepEqual(previousValue, proposedValue)) {
		return errors.New("target or containing top-level ancestor changed")
	}
	return nil
}

func patchOperationValue(operation PatchOperation, index int) (any, error) {
	var value any
	switch operation.Op {
	case "add", "replace":
		if len(operation.Value) == 0 {
			return nil, fmt.Errorf("operation %d: %s requires value", index, operation.Op)
		}
		decoded, err := decodeJSON(operation.Value)
		if err != nil {
			return nil, fmt.Errorf("operation %d value: %w", index, err)
		}
		value = decoded
	case "remove":
		if len(operation.Value) != 0 {
			return nil, fmt.Errorf("operation %d: remove forbids value", index)
		}
	default:
		return nil, fmt.Errorf("operation %d: unsupported operation %q", index, operation.Op)
	}
	return value, nil
}
