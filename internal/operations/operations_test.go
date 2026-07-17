package operations

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"
)

var customMarshalerInvoked atomic.Bool

type customJSONMarshalerString string

func (value customJSONMarshalerString) MarshalJSON() ([]byte, error) {
	customMarshalerInvoked.Store(true)
	return []byte(`"coerced"`), nil
}

type customPointerTextMarshalerString string

func (value *customPointerTextMarshalerString) MarshalText() ([]byte, error) {
	customMarshalerInvoked.Store(true)
	return []byte("coerced"), nil
}

type patchFixtures struct {
	Profile string             `json:"profile"`
	Cases   []patchFixtureCase `json:"cases"`
}

type patchFixtureCase struct {
	Name     string           `json:"name"`
	Target   FunctionalTarget `json:"target"`
	Document any              `json:"document"`
	Patch    JSONPatch        `json:"patch"`
	Valid    bool             `json:"valid"`
	Expected any              `json:"expected"`
}

type fileFixtures struct {
	Profile string            `json:"profile"`
	Cases   []fileFixtureCase `json:"cases"`
}

type fileFixtureCase struct {
	Name       string                `json:"name"`
	Initial    map[string]FileRecord `json:"initial"`
	Operations FileOperationSet      `json:"operations"`
	Valid      bool                  `json:"valid"`
	Expected   map[string]FileRecord `json:"expected"`
}

type skillFixtures struct {
	Profile string             `json:"profile"`
	Cases   []skillFixtureCase `json:"cases"`
}

type skillFixtureCase struct {
	Name       string                 `json:"name"`
	Initial    map[string]SkillRecord `json:"initial"`
	Operations SkillOperationSet      `json:"operations"`
	Valid      bool                   `json:"valid"`
	Expected   map[string]SkillRecord `json:"expected"`
}

func fixturePath(t *testing.T, name string) string {
	t.Helper()
	path, err := filepath.Abs(filepath.Join("..", "..", "contracts", "fixtures", "operations", name))
	if err != nil {
		t.Fatal(err)
	}
	return path
}

func decodeFixture(t *testing.T, name string, target any) {
	t.Helper()
	data, err := os.ReadFile(fixturePath(t, name))
	if err != nil {
		t.Fatal(err)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		t.Fatal(err)
	}
}

func TestJSONPatchFixtures(t *testing.T) {
	var fixtures patchFixtures
	decodeFixture(t, "json-patch.cases.json", &fixtures)
	if fixtures.Profile != "bytedesk.json-patch-fixtures/1" {
		t.Fatalf("unexpected profile %q", fixtures.Profile)
	}
	for _, fixture := range fixtures.Cases {
		fixture := fixture
		t.Run(fixture.Name, func(t *testing.T) {
			before := cloneForTest(t, fixture.Document)
			result, err := ApplyJSONPatch(fixture.Document, fixture.Patch, fixture.Target)
			if (err == nil) != fixture.Valid {
				t.Fatalf("valid=%v, err=%v", fixture.Valid, err)
			}
			if !fixture.Valid {
				if !reflect.DeepEqual(fixture.Document, before) {
					t.Fatal("failed patch mutated the input document")
				}
				return
			}
			if !reflect.DeepEqual(result, fixture.Expected) {
				t.Fatalf("result=%#v, expected=%#v", result, fixture.Expected)
			}
		})
	}
}

func TestJSONPatchRejectsNonCanonicalUntrustedValues(t *testing.T) {
	tests := []struct {
		name  string
		value json.RawMessage
	}{
		{name: "duplicate nested member", value: json.RawMessage(`{"role":"reader","role":"admin"}`)},
		{name: "lone surrogate", value: json.RawMessage(`{"text":"\ud800"}`)},
		{name: "value exceeds canonical input limit", value: json.RawMessage(`"` + strings.Repeat("x", 4*1024*1024) + `"`)},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			document := map[string]any{"name": "agent"}
			patch := JSONPatch{
				Profile: "bytedesk.json-patch/1",
				Operations: []PatchOperation{{
					Op: "add", Path: "/custom", Value: test.value,
				}},
			}
			if _, err := ApplyJSONPatch(document, patch, TargetAgentSpec); err == nil {
				t.Fatal("non-canonical untrusted patch value was accepted")
			}
			if !reflect.DeepEqual(document, map[string]any{"name": "agent"}) {
				t.Fatal("failed patch mutated the input document")
			}
		})
	}
}

func TestJSONPatchRejectsCustomSerializationWithoutExecution(t *testing.T) {
	tests := []struct {
		name     string
		document map[string]any
	}{
		{
			name: "value JSON marshaler",
			document: map[string]any{
				"target": customJSONMarshalerString("original"),
			},
		},
		{
			name: "pointer text marshaler on addressable slice element",
			document: map[string]any{
				"target": []customPointerTextMarshalerString{"original"},
			},
		},
	}

	patch := JSONPatch{
		Profile: "bytedesk.json-patch/1",
		Operations: []PatchOperation{{
			Op: "add", Path: "/new", Value: json.RawMessage(`true`),
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			customMarshalerInvoked.Store(false)
			if _, err := ApplyJSONPatch(test.document, patch, TargetAgentSpec); err == nil {
				t.Fatal("custom serializer input was accepted")
			}
			if customMarshalerInvoked.Load() {
				t.Fatal("custom serializer executed before the input was rejected")
			}
			if _, exists := test.document["new"]; exists {
				t.Fatal("rejected patch mutated the input document")
			}
		})
	}
}

func TestFileOperationFixtures(t *testing.T) {
	var fixtures fileFixtures
	decodeFixture(t, "file-operations.cases.json", &fixtures)
	if fixtures.Profile != "bytedesk.file-operation-fixtures/1" {
		t.Fatalf("unexpected profile %q", fixtures.Profile)
	}
	for _, fixture := range fixtures.Cases {
		fixture := fixture
		t.Run(fixture.Name, func(t *testing.T) {
			before := cloneFileState(fixture.Initial)
			result, err := ApplyFileOperations(fixture.Initial, fixture.Operations)
			if (err == nil) != fixture.Valid {
				t.Fatalf("valid=%v, err=%v", fixture.Valid, err)
			}
			if !reflect.DeepEqual(fixture.Initial, before) {
				t.Fatal("file operation mutated its input state")
			}
			if fixture.Valid && !reflect.DeepEqual(result, fixture.Expected) {
				t.Fatalf("result=%#v, expected=%#v", result, fixture.Expected)
			}
		})
	}
}

func TestSkillOperationFixtures(t *testing.T) {
	var fixtures skillFixtures
	decodeFixture(t, "skill-operations.cases.json", &fixtures)
	if fixtures.Profile != "bytedesk.skill-operation-fixtures/1" {
		t.Fatalf("unexpected profile %q", fixtures.Profile)
	}
	for _, fixture := range fixtures.Cases {
		fixture := fixture
		t.Run(fixture.Name, func(t *testing.T) {
			before := cloneSkillState(fixture.Initial)
			result, err := ApplySkillOperations(fixture.Initial, fixture.Operations)
			if (err == nil) != fixture.Valid {
				t.Fatalf("valid=%v, err=%v", fixture.Valid, err)
			}
			if !reflect.DeepEqual(fixture.Initial, before) {
				t.Fatal("skill operation mutated its input state")
			}
			if fixture.Valid && !reflect.DeepEqual(result, fixture.Expected) {
				t.Fatalf("result=%#v, expected=%#v", result, fixture.Expected)
			}
		})
	}
}

func TestDescriptorRepositoryGrammarMatchesTheClosedContract(t *testing.T) {
	valid := []string{
		"registry.example/agents/release",
		"registry.example:5000/agents/release",
		"[2001:db8::1]:5000/agents/release",
	}
	for _, repository := range valid {
		if !validOCIRepository(repository) {
			t.Fatalf("valid OCI repository rejected: %s", repository)
		}
	}
	invalid := []string{
		"https://registry.example/agents/release",
		"registry.example/agents/release:latest",
		"registry.example/agents/release@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		"Registry.example/agents/release",
		"[2001:DB8::1]/agents/release",
		"[127.0.0.1]/agents/release",
		"[::ffff:192.0.2.1]/agents/release",
		strings.Repeat("a", 64) + ".example/agents/release",
		"registry.example:0001/agents/release",
	}
	for _, repository := range invalid {
		if validOCIRepository(repository) {
			t.Fatalf("invalid OCI repository accepted: %s", repository)
		}
	}
}

func TestPortablePathsRejectCrossPlatformFilenameHazards(t *testing.T) {
	tests := []string{
		`files/a<b.txt`,
		`files/a>b.txt`,
		`files/a"b.txt`,
		`files/a|b.txt`,
		`files/a?b.txt`,
		`files/a*b.txt`,
		`files/CONIN$`,
		`files/conout$.log`,
		`files/COM¹.txt`,
		`files/lpt³`,
		"files/" + strings.Repeat("é", 128),
	}
	for _, path := range tests {
		if _, err := validatePortablePath(path); err == nil {
			t.Fatalf("cross-platform hazardous path accepted: %q", path)
		}
	}
	if _, err := validatePortablePath("files/" + strings.Repeat("a", 255)); err != nil {
		t.Fatalf("exact 255-byte portable segment rejected: %v", err)
	}
}

func TestPortablePathEnforcesSemanticUTF8ByteLimits(t *testing.T) {
	exact := strings.Join([]string{
		strings.Repeat("a", 204),
		strings.Repeat("b", 204),
		strings.Repeat("c", 204),
		strings.Repeat("d", 204),
		strings.Repeat("e", 204),
	}, "/")
	if len([]byte(exact)) != 1024 {
		t.Fatalf("test path is %d bytes, expected 1024", len([]byte(exact)))
	}
	if _, err := validatePortablePath(exact); err != nil {
		t.Fatalf("exact 1024-byte portable path rejected: %v", err)
	}

	schemaCharacterValidButByteOversized := strings.Join([]string{
		strings.Repeat("é", 120),
		strings.Repeat("è", 120),
		strings.Repeat("ê", 120),
		strings.Repeat("ë", 120),
		strings.Repeat("á", 120),
	}, "/")
	if len([]rune(schemaCharacterValidButByteOversized)) > 1024 ||
		len([]byte(schemaCharacterValidButByteOversized)) <= 1024 {
		t.Fatal("test path does not isolate JSON Schema characters from semantic UTF-8 bytes")
	}
	if _, err := validatePortablePath(schemaCharacterValidButByteOversized); err == nil {
		t.Fatal("schema-character-valid path exceeding 1024 UTF-8 bytes was accepted")
	}
}

func cloneForTest(t *testing.T, value any) any {
	t.Helper()
	data, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var clone any
	if err := decoder.Decode(&clone); err != nil {
		t.Fatal(err)
	}
	return clone
}
