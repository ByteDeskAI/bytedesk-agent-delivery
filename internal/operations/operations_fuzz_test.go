package operations

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
	"unicode/utf8"

	"golang.org/x/text/unicode/norm"
)

func FuzzJSONPatchAtomicityAndUnicode(f *testing.F) {
	for _, seed := range []string{"name", "café", "a/b", "tilde~key", "東京"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, key string) {
		if key == "" || len([]byte(key)) > 128 || strings.ContainsRune(key, 0) ||
			!utf8.ValidString(key) || !norm.NFC.IsNormalString(key) {
			t.Skip()
		}
		document := map[string]any{"stable": "value", key: "original"}
		before := cloneForTest(t, document)
		if !reflect.DeepEqual(document, before) {
			t.Fatal("fuzz snapshot changed the input before the operation")
		}
		pointerToken := strings.ReplaceAll(strings.ReplaceAll(key, "~", "~0"), "/", "~1")
		patch := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{
			{Op: "replace", Path: "/" + pointerToken, Value: json.RawMessage(`"changed"`)},
			{Op: "remove", Path: ""},
		}}
		if _, err := ApplyJSONPatch(document, patch, TargetAgentSpec); err == nil {
			t.Fatal("seeded atomic-failure patch unexpectedly passed")
		}
		if !reflect.DeepEqual(document, before) {
			t.Fatal("failed seeded patch mutated input")
		}
	})
}

func FuzzJSONPointerUnicodeAndEscapes(f *testing.F) {
	for _, seed := range []string{"café", "cafe\u0301", "a/b", "tilde~key", "東京"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, key string) {
		if key == "" || len([]byte(key)) > 128 || strings.ContainsRune(key, 0) || !utf8.ValidString(key) {
			t.Skip()
		}
		document := map[string]any{key: "original"}
		before := cloneForTest(t, document)
		pointerToken := strings.ReplaceAll(strings.ReplaceAll(key, "~", "~0"), "/", "~1")
		patch := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{{
			Op: "replace", Path: "/" + pointerToken, Value: json.RawMessage(`"changed"`),
		}}}
		result, err := ApplyJSONPatch(document, patch, TargetAgentSpec)
		if !norm.NFC.IsNormalString(key) {
			if err == nil {
				t.Fatal("non-NFC pointer token was accepted")
			}
			if !reflect.DeepEqual(document, before) {
				t.Fatal("denied non-NFC pointer mutated input")
			}
			return
		}
		if err != nil {
			t.Fatalf("valid escaped NFC pointer was denied: %v", err)
		}
		object, ok := result.(map[string]any)
		if !ok || object[key] != "changed" {
			t.Fatalf("valid escaped NFC pointer produced %#v", result)
		}
		if !reflect.DeepEqual(document, before) {
			t.Fatal("successful patch mutated input instead of its clone")
		}
	})
}

func FuzzJSONPatchOperationOrder(f *testing.F) {
	for _, seed := range []string{"value", "café", "東京", "slash/value"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, value string) {
		if len([]byte(value)) > 256 || !utf8.ValidString(value) {
			t.Skip()
		}
		encoded, err := json.Marshal(value)
		if err != nil {
			t.Fatal(err)
		}
		document := map[string]any{}
		ordered := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{
			{Op: "add", Path: "/parent", Value: json.RawMessage(`{}`)},
			{Op: "add", Path: "/parent/value", Value: encoded},
		}}
		result, err := ApplyJSONPatch(document, ordered, TargetAgentSpec)
		if err != nil {
			t.Fatalf("ordered dependent operations were denied: %v", err)
		}
		parent := result.(map[string]any)["parent"].(map[string]any)
		if parent["value"] != value {
			t.Fatalf("ordered dependent operations produced %#v", result)
		}

		reversed := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{
			{Op: "add", Path: "/parent/value", Value: encoded},
			{Op: "add", Path: "/parent", Value: json.RawMessage(`{}`)},
		}}
		if _, err := ApplyJSONPatch(document, reversed, TargetAgentSpec); err == nil {
			t.Fatal("reversed dependent operations were accepted")
		}
		if len(document) != 0 {
			t.Fatal("denied reversed operation order mutated input")
		}
	})
}

func FuzzJSONArrayOperations(f *testing.F) {
	for _, seed := range []struct {
		op    string
		token string
	}{
		{"add", "-"},
		{"add", "2"},
		{"add", "02"},
		{"replace", "0"},
		{"replace", "1"},
		{"replace", "00"},
		{"remove", "0"},
		{"remove", "-"},
	} {
		f.Add(seed.op, seed.token)
	}
	f.Fuzz(func(t *testing.T, operation, token string) {
		if len(token) > 32 || strings.ContainsAny(token, "/~") {
			t.Skip()
		}
		document := map[string]any{"items": []any{"first", "second"}}
		before := cloneForTest(t, document)
		patchOperation := PatchOperation{Op: operation, Path: "/items/" + token}
		if operation == "add" || operation == "replace" {
			patchOperation.Value = json.RawMessage(`"changed"`)
		}
		result, err := ApplyJSONPatch(document, JSONPatch{
			Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{patchOperation},
		}, TargetAgentSpec)
		expectSuccess := (operation == "add" && token == "-") ||
			((operation == "replace" || operation == "remove") && (token == "0" || token == "1"))
		if (err == nil) != expectSuccess {
			t.Fatalf("operation=%q token=%q success=%v err=%v", operation, token, expectSuccess, err)
		}
		if !reflect.DeepEqual(document, before) {
			t.Fatal("array operation mutated input")
		}
		if expectSuccess {
			items := result.(map[string]any)["items"].([]any)
			if operation == "add" && (len(items) != 3 || items[2] != "changed") {
				t.Fatalf("append result=%#v", items)
			}
			if operation == "replace" && items[0] != "changed" && items[1] != "changed" {
				t.Fatalf("replace result=%#v", items)
			}
			if operation == "remove" && len(items) != 1 {
				t.Fatalf("remove result=%#v", items)
			}
		}
	})
}

func FuzzThreeWayRebaseChangedTargetDenial(f *testing.F) {
	for _, seed := range []string{"old", "Ω", "array-sensitive", "private"} {
		f.Add(seed, seed+"-upstream")
	}
	f.Add(string([]byte{0x8b}), string([]byte{0x88}))
	f.Fuzz(func(t *testing.T, previousValue, proposedValue string) {
		if previousValue == proposedValue || len(previousValue) > 256 || len(proposedValue) > 256 {
			t.Skip()
		}
		previous := map[string]any{"target": previousValue}
		proposed := map[string]any{"target": proposedValue}
		patch := JSONPatch{Profile: "bytedesk.json-patch/1", Operations: []PatchOperation{{
			Op: "replace", Path: "/target", Value: json.RawMessage(`"private"`),
		}}}
		if _, err := RebaseJSONPatch(previous, proposed, patch, TargetAgentSpec); err == nil {
			t.Fatal("changed target was rebased")
		}
	})
}

func FuzzFileOperationCollisionIsAtomic(f *testing.F) {
	for _, seed := range []string{"case-fold", "normalization", "tree", "東京"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, seed string) {
		digest := sha256.Sum256([]byte(seed))
		token := fmt.Sprintf("%x", digest[:8])
		var first, second string
		switch len(seed) % 3 {
		case 0:
			first, second = "files/"+token+".txt", "FILES/"+token+".TXT"
		case 1:
			first, second = "café-"+token+".txt", "cafe\u0301-"+token+".txt"
		default:
			first, second = "tree-"+token, "tree-"+token+"/child.txt"
		}
		initial := map[string]FileRecord{}
		before := cloneFileState(initial)
		set := FileOperationSet{Contract: "bytedesk.file-operations/1", Operations: []FileOperation{
			{Op: "add", Path: first, Precondition: Precondition{Kind: "absent"}, Content: fuzzDescriptor("a"), Mode: "0644"},
			{Op: "add", Path: second, Precondition: Precondition{Kind: "absent"}, Content: fuzzDescriptor("b"), Mode: "0644"},
		}}
		if _, err := ApplyFileOperations(initial, set); err == nil {
			t.Fatalf("distinct colliding paths %q and %q unexpectedly passed", first, second)
		}
		if !reflect.DeepEqual(initial, before) {
			t.Fatal("failed file operation set mutated input")
		}
	})
}

func FuzzSkillOperationConflictIsAtomic(f *testing.F) {
	for _, seed := range []string{"skill", "skill.v1", "Skill-01"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, packageID string) {
		if packageID == "" || len(packageID) > 64 {
			t.Skip()
		}
		initial := map[string]SkillRecord{}
		before := cloneSkillState(initial)
		set := SkillOperationSet{Contract: "bytedesk.skill-operations/1", Operations: []SkillOperation{
			{Op: "add", PackageID: packageID, Precondition: Precondition{Kind: "absent"}, Descriptor: fuzzDescriptor("c")},
			{Op: "add", PackageID: packageID, Precondition: Precondition{Kind: "absent"}, Descriptor: fuzzDescriptor("d")},
		}}
		if _, err := ApplySkillOperations(initial, set); err == nil {
			t.Fatal("duplicate or invalid skill operation seed unexpectedly passed")
		}
		if !reflect.DeepEqual(initial, before) {
			t.Fatal("failed skill operation set mutated input")
		}
	})
}

func fuzzDescriptor(nibble string) *ArtifactDescriptor {
	return &ArtifactDescriptor{
		Repository: "registry.example/fixtures",
		Digest:     "sha256:" + strings.Repeat(nibble, 64),
		MediaType:  "application/octet-stream",
		Size:       1,
		TrustPolicy: TrustPolicyRef{
			ID:     "fixture-policy",
			Digest: "sha256:" + strings.Repeat("e", 64),
		},
	}
}
