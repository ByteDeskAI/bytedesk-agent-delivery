package operations

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

type sourceResolutionFixtures struct {
	Profile string                        `json:"profile"`
	Cases   []sourceResolutionFixtureCase `json:"cases"`
}

type sourceResolutionFixtureCase struct {
	Name                 string              `json:"name"`
	DeclaredKind         AgentSpecSourceKind `json:"declaredKind"`
	Document             any                 `json:"document"`
	OfficialValid        bool                `json:"officialValid"`
	OfficialWarningCount int                 `json:"officialWarningCount,omitempty"`
	Valid                bool                `json:"valid"`
	ExpectedBaseID       string              `json:"expectedBaseId,omitempty"`
}

type rebaseFixtures struct {
	Profile string              `json:"profile"`
	Cases   []rebaseFixtureCase `json:"cases"`
}

type rebaseFixtureCase struct {
	Name     string           `json:"name"`
	Target   FunctionalTarget `json:"target"`
	Previous any              `json:"previous"`
	Proposed any              `json:"proposed"`
	Patch    JSONPatch        `json:"patch"`
	Valid    bool             `json:"valid"`
	Expected any              `json:"expected,omitempty"`
}

type recordingAgentSpecValidator struct {
	calls int
}

func (v *recordingAgentSpecValidator) ValidateAgentSpec(
	_ context.Context,
	version string,
	canonicalDocument []byte,
) (AgentSpecSourceKind, error) {
	v.calls++
	if version != PinnedAgentSpecVersion {
		return "", errTestOfficialValidation
	}
	var document map[string]any
	if err := json.Unmarshal(canonicalDocument, &document); err != nil {
		return "", err
	}
	switch document["component_type"] {
	case "Agent":
		return AgentSpecSourceAgent, nil
	case "SpecializedAgent":
		return AgentSpecSourceSpecializedAgent, nil
	default:
		return "", errTestOfficialValidation
	}
}

var errTestOfficialValidation = &testValidationError{}

type testValidationError struct{}

func (*testValidationError) Error() string { return "official validation denied" }

func TestAgentSpecSourceResolutionFixtures(t *testing.T) {
	var fixtures sourceResolutionFixtures
	decodeFixture(t, "source-resolution.cases.json", &fixtures)
	if fixtures.Profile != "bytedesk.agent-spec-source-resolution-fixtures/1" {
		t.Fatalf("unexpected profile %q", fixtures.Profile)
	}
	for _, fixture := range fixtures.Cases {
		fixture := fixture
		t.Run(fixture.Name, func(t *testing.T) {
			payload := canonicalPayload(t, fixture.Document)
			validator := &recordingAgentSpecValidator{}
			resolved, err := ResolveAgentSpecSource(
				context.Background(), fixture.DeclaredKind, digestBytes(payload), payload, validator,
			)
			if (err == nil) != fixture.Valid {
				t.Fatalf("valid=%v, err=%v", fixture.Valid, err)
			}
			expectedCalls := 1
			if validator.calls != expectedCalls {
				t.Fatalf("official validator calls=%d, expected %d", validator.calls, expectedCalls)
			}
			if !fixture.Valid {
				return
			}
			if resolved.Kind != fixture.DeclaredKind || resolved.Digest != digestBytes(payload) ||
				!bytes.Equal(resolved.CanonicalDocument, payload) {
				t.Fatalf("resolved identity drift: %+v", resolved)
			}
			if resolved.BaseAgent["id"] != fixture.ExpectedBaseID {
				t.Fatalf("base agent id=%v, expected %q", resolved.BaseAgent["id"], fixture.ExpectedBaseID)
			}
		})
	}
}

type fixedAgentSpecValidator struct {
	kind  AgentSpecSourceKind
	err   error
	calls int
}

func (v *fixedAgentSpecValidator) ValidateAgentSpec(
	_ context.Context, _ string, _ []byte,
) (AgentSpecSourceKind, error) {
	v.calls++
	return v.kind, v.err
}

func TestAgentSpecSourceRequiresOneAgreeingOfficialValidation(t *testing.T) {
	document := map[string]any{"agentspec_version": PinnedAgentSpecVersion, "component_type": "Agent", "id": "agent"}
	payload := canonicalPayload(t, document)

	denied := &fixedAgentSpecValidator{err: errTestOfficialValidation}
	if _, err := ResolveAgentSpecSource(
		context.Background(), AgentSpecSourceAgent, digestBytes(payload), payload, denied,
	); err == nil || denied.calls != 1 {
		t.Fatalf("official validation denial did not fail closed exactly once: err=%v calls=%d", err, denied.calls)
	}

	substituted := &fixedAgentSpecValidator{kind: AgentSpecSourceSpecializedAgent}
	if _, err := ResolveAgentSpecSource(
		context.Background(), AgentSpecSourceAgent, digestBytes(payload), payload, substituted,
	); err == nil || substituted.calls != 1 {
		t.Fatalf("official kind substitution did not fail closed exactly once: err=%v calls=%d", err, substituted.calls)
	}
}

func TestAgentSpecSourceRejectsDigestAndCanonicalSubstitutionBeforeOfficialValidation(t *testing.T) {
	document := map[string]any{"agentspec_version": PinnedAgentSpecVersion, "component_type": "Agent", "id": "agent"}
	canonicalDocument := canonicalPayload(t, document)

	validator := &recordingAgentSpecValidator{}
	if _, err := ResolveAgentSpecSource(
		context.Background(), AgentSpecSourceAgent, "sha256:"+strings.Repeat("0", 64), canonicalDocument, validator,
	); err == nil {
		t.Fatal("wrong exact source digest was accepted")
	}
	if validator.calls != 0 {
		t.Fatal("untrusted digest substitution reached the official validator")
	}

	validator = &recordingAgentSpecValidator{}
	noncanonical := []byte("{\n  \"id\": \"agent\",\n  \"component_type\": \"Agent\"\n}\n")
	if _, err := ResolveAgentSpecSource(
		context.Background(), AgentSpecSourceAgent, digestBytes(noncanonical), noncanonical, validator,
	); err == nil {
		t.Fatal("noncanonical source bytes were accepted as semantic source authority")
	}
	if validator.calls != 0 {
		t.Fatal("noncanonical source reached the official validator")
	}
}

func TestResolvedSourceViewsCannotMutateEachOtherOrCanonicalAuthority(t *testing.T) {
	document := map[string]any{"agentspec_version": PinnedAgentSpecVersion, "component_type": "Agent", "id": "agent"}
	payload := canonicalPayload(t, document)
	resolved, err := ResolveAgentSpecSource(
		context.Background(), AgentSpecSourceAgent, digestBytes(payload), payload, &recordingAgentSpecValidator{},
	)
	if err != nil {
		t.Fatal(err)
	}
	resolved.BaseAgent["id"] = "mutated"
	if resolved.Document["id"] != "agent" || !bytes.Equal(resolved.CanonicalDocument, payload) {
		t.Fatal("mutable convenience view changed another view or canonical source authority")
	}
}

func TestThreeWayRebaseFixtures(t *testing.T) {
	var fixtures rebaseFixtures
	decodeFixture(t, "three-way-rebase.cases.json", &fixtures)
	if fixtures.Profile != "bytedesk.json-patch-three-way-rebase-fixtures/1" {
		t.Fatalf("unexpected profile %q", fixtures.Profile)
	}
	for _, fixture := range fixtures.Cases {
		fixture := fixture
		t.Run(fixture.Name, func(t *testing.T) {
			previousBefore := cloneForTest(t, fixture.Previous)
			proposedBefore := cloneForTest(t, fixture.Proposed)
			result, err := RebaseJSONPatch(fixture.Previous, fixture.Proposed, fixture.Patch, fixture.Target)
			if (err == nil) != fixture.Valid {
				t.Fatalf("valid=%v, err=%v", fixture.Valid, err)
			}
			if !reflect.DeepEqual(fixture.Previous, previousBefore) || !reflect.DeepEqual(fixture.Proposed, proposedBefore) {
				t.Fatal("three-way rebase mutated an input document")
			}
			if fixture.Valid && !reflect.DeepEqual(result, fixture.Expected) {
				t.Fatalf("result=%#v, expected=%#v", result, fixture.Expected)
			}
		})
	}
}

func TestJSONPatchRequiresDashForArrayAppend(t *testing.T) {
	document := map[string]any{"items": []any{"first"}}
	patch := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{{
		Op: "add", Path: "/items/1", Value: json.RawMessage(`"second"`),
	}}}
	if _, err := ApplyJSONPatch(document, patch, TargetAgentSpec); err == nil {
		t.Fatal("numeric end index appended to an array; v1 requires final '-'")
	}
}

func TestJSONPatchRechecksAggregateCanonicalResourceLimits(t *testing.T) {
	document := map[string]any{}
	large := bytes.Repeat([]byte("x"), 2*1024*1024+128)
	value, err := json.Marshal(string(large))
	if err != nil {
		t.Fatal(err)
	}
	patch := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{
		{Op: "add", Path: "/first", Value: value},
		{Op: "add", Path: "/second", Value: value},
	}}
	if _, err := ApplyJSONPatch(document, patch, TargetAgentSpec); err == nil {
		t.Fatal("patch aggregate exceeding canonical resource limits was accepted")
	}
	if len(document) != 0 {
		t.Fatal("failed over-limit patch mutated its input")
	}
}

func TestJSONPointerEnforcesSemanticUTF8ByteLimit(t *testing.T) {
	withinLimitKey := strings.Repeat("é", 2047)
	withinLimit := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{{
		Op: "replace", Path: "/" + withinLimitKey, Value: json.RawMessage(`true`),
	}}}
	if _, err := ApplyJSONPatch(map[string]any{withinLimitKey: false}, withinLimit, TargetAgentSpec); err != nil {
		t.Fatalf("pointer within the 4096-byte semantic limit was denied: %v", err)
	}

	overLimitKey := strings.Repeat("é", 2048)
	overLimitPath := "/" + overLimitKey
	if len([]rune(overLimitPath)) > 4096 || len([]byte(overLimitPath)) <= 4096 {
		t.Fatal("test pointer does not isolate JSON Schema characters from semantic UTF-8 bytes")
	}
	overLimit := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{{
		Op: "replace", Path: overLimitPath, Value: json.RawMessage(`true`),
	}}}
	if _, err := ApplyJSONPatch(map[string]any{overLimitKey: false}, overLimit, TargetAgentSpec); err == nil {
		t.Fatal("schema-character-valid pointer exceeding 4096 UTF-8 bytes was accepted")
	}
}

func canonicalPayload(t *testing.T, value any) []byte {
	t.Helper()
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	result, err := canonical.CanonicalizeBytes(encoded, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		t.Fatal(err)
	}
	return result.Bytes
}

func digestBytes(payload []byte) string {
	sum := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(sum[:])
}
