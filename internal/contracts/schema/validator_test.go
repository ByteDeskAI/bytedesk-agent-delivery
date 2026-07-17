package schema

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
	"github.com/santhosh-tekuri/jsonschema/v6/kind"
)

const testSchemaPrefix = "https://schemas.bytedesk.ai/agent-delivery/v1/"

func TestValidateRepositoryAcceptsClosedReferencesAndExpectedDenials(t *testing.T) {
	repository := testRepository(t)
	report, err := ValidateRepository(repository, filepath.Join(repository, "contracts/fixtures/schema/index.json"))
	if err != nil {
		t.Fatal(err)
	}
	if report.Validator != ValidatorID || report.SchemaCount != 2 || report.FixtureCount != 5 || report.Outcome != "pass" {
		t.Fatalf("unexpected report: %+v", report)
	}
	if report.ResourceBounds.Profile != "bytedesk.schema-resource-bounds/1" ||
		report.ResourceBounds.DirectArraySchemaCount != 0 ||
		report.ResourceBounds.DirectStringSchemaCount != 1 ||
		report.ResourceBounds.DirectIntegerSchemaCount != 0 ||
		report.ResourceBounds.DirectObjectSchemaCount != 1 ||
		report.ResourceBounds.Outcome != "pass" {
		t.Fatalf("unexpected resource-bound evidence: %+v", report.ResourceBounds)
	}
	if len(report.Schemas) != 2 || len(report.Fixtures) != 5 {
		t.Fatalf("incomplete evidence report: %+v", report)
	}
	if report.SchemaInventory.Profile != schemaInventoryProfile ||
		report.SchemaInventory.Path != schemaInventoryPath ||
		report.SchemaInventory.SchemaCount != 2 ||
		!exactSHA256(report.SchemaInventory.Digest) ||
		report.SchemaInventory.Outcome != "pass" {
		t.Fatalf("incomplete schema inventory evidence: %+v", report.SchemaInventory)
	}
	for _, item := range report.Schemas {
		if !strings.HasPrefix(item.Digest, "sha256:") || len(item.Digest) != 71 {
			t.Fatalf("schema digest is not exact: %+v", item)
		}
	}
	for _, item := range report.Fixtures {
		if item.ExpectedValid && item.ObservedKeywords == nil {
			t.Fatalf("positive fixture keywords must be an explicit empty array: %+v", item)
		}
	}
}

func TestValidateRepositoryFailsClosed(t *testing.T) {
	tests := []struct {
		name    string
		mutate  func(t *testing.T, repository string)
		wantErr string
	}{
		{
			name: "direct array lacks maxItems",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`value/1.0.0",
  "type":"array",
  "items":{"type":"string","maxLength":16}
}`)
			},
			wantErr: "array maxItems",
		},
		{
			name: "direct array exceeds parser node ceiling",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`value/1.0.0",
  "type":"array",
  "maxItems":100001,
  "items":{"type":"string","maxLength":16}
}`)
			},
			wantErr: "array maxItems",
		},
		{
			name: "direct string lacks maxLength",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"), ",\n  \"maxLength\":128", "")
			},
			wantErr: "string maxLength",
		},
		{
			name: "direct integer lacks maximum",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`value/1.0.0",
  "type":"integer",
  "minimum":0
}`)
			},
			wantErr: "integer minimum and maximum",
		},
		{
			name: "direct object is open and lacks maxProperties",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`value/1.0.0",
  "type":"object",
  "additionalProperties":{"type":"string","maxLength":16}
}`)
			},
			wantErr: "closed fixed property set or declare maxProperties",
		},
		{
			name: "schema lacks an indexed positive fixture",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `{
  "profile":"bytedesk.schema-fixtures/1",
  "fixtures":[
    {"path":"contracts/fixtures/schema/positive/valid.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":true,"category":"positive","expectedKeyword":[]},
    {"path":"contracts/fixtures/schema/negative/invalid.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":false,"category":"negative","expectedKeyword":"additionalProperties"}
  ]
}`)
			},
			wantErr: "schemas lack indexed valid positive fixtures",
		},
		{
			name: "schema lacks an indexed denial fixture",
			mutate: func(t *testing.T, repository string) {
				path := filepath.Join(repository, "contracts/fixtures/schema/index.json")
				payload, err := os.ReadFile(path)
				if err != nil {
					t.Fatal(err)
				}
				entry := `,
    {"path":"contracts/fixtures/schema/negative/value.json","schemaId":"` + testSchemaPrefix + `value/1.0.0","valid":false,"category":"negative","expectedKeyword":"minLength"}`
				updated := strings.Replace(string(payload), entry, "", 1)
				if updated == string(payload) {
					t.Fatal("value denial fixture entry was not found")
				}
				writeTestFile(t, path, updated)
			},
			wantErr: "schemas lack indexed denial fixtures",
		},
		{
			name: "fixture index root has unknown field",
			mutate: func(t *testing.T, repository string) {
				path := filepath.Join(repository, "contracts/fixtures/schema/index.json")
				writeTestFile(t, path, `{
  "profile":"bytedesk.schema-fixtures/1",
  "fixtures":[],
  "authority":"smuggled"
}`)
			},
			wantErr: "unknown fields",
		},
		{
			name: "fixture index entry has unknown field",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `{
  "profile":"bytedesk.schema-fixtures/1",
  "fixtures":[
    {"path":"contracts/fixtures/schema/positive/valid.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":true,"category":"positive","expectedKeyword":[],"force":true}
  ]
}`)
			},
			wantErr: "unknown fields",
		},
		{
			name: "fixture category is unknown",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"category":"positive"`, `"category":"advisory"`)
			},
			wantErr: "invalid category",
		},
		{
			name: "fixture category contradicts validity",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"valid":true,"category":"positive"`, `"valid":true,"category":"negative"`)
			},
			wantErr: "does not match valid",
		},
		{
			name: "fixture expected keyword is null",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":[]`, `"expectedKeyword":null`)
			},
			wantErr: "expectedKeyword",
		},
		{
			name: "fixture expected keyword array contains duplicate",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":"additionalProperties"`, `"expectedKeyword":["required","required"]`)
			},
			wantErr: "expectedKeyword",
		},
		{
			name: "fixture expected semantic error is unknown",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":"additionalProperties"`, `"expectedKeyword":[],"expectedSemanticError":"advisory"`)
			},
			wantErr: "expectedSemanticError",
		},
		{
			name: "valid fixture declares semantic error",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":[]`, `"expectedKeyword":[],"expectedSemanticError":"schema_id_mismatch"`)
			},
			wantErr: "valid fixture cannot declare expectedSemanticError",
		},
		{
			name: "denial fixture declares structural and semantic proofs",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":"additionalProperties"`, `"expectedKeyword":"additionalProperties","expectedSemanticError":"schema_id_mismatch"`)
			},
			wantErr: "exactly one of expectedKeyword or expectedSemanticError",
		},
		{
			name: "semantic denial misses intended descriptor error",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":"additionalProperties"`, `"expectedKeyword":[],"expectedSemanticError":"schema_id_mismatch"`)
			},
			wantErr: "schema descriptor semantic result mismatch",
		},
		{
			name: "denial fixture omits intended keyword",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":"additionalProperties"`, `"expectedKeyword":[]`)
			},
			wantErr: "denial fixture expectedKeyword must not be empty",
		},
		{
			name: "denial fixture misses intended keyword",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `"expectedKeyword":"additionalProperties"`, `"expectedKeyword":"pattern"`)
			},
			wantErr: "missed expected keywords",
		},
		{
			name: "unresolved reference",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/root.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`root/1.0.0",
  "$ref":"`+testSchemaPrefix+`missing/1.0.0"
}`)
			},
			wantErr: "unresolved offline reference",
		},
		{
			name: "fixture names unknown schema",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `{
  "profile":"bytedesk.schema-fixtures/1",
  "fixtures":[{"path":"contracts/fixtures/schema/positive/valid.json","schemaId":"`+testSchemaPrefix+`missing/1.0.0","valid":true,"category":"positive","expectedKeyword":[]}]
}`)
			},
			wantErr: "unknown schema",
		},
		{
			name: "fixture escapes contracts root",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "docs/outside.json"), `{"value":"ok"}`)
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `{
  "profile":"bytedesk.schema-fixtures/1",
  "fixtures":[{"path":"docs/outside.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":true,"category":"positive","expectedKeyword":[]}]
}`)
			},
			wantErr: "escapes contracts",
		},
		{
			name: "denial is accepted",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/negative/invalid.json"), `{"value":"still-valid"}`)
			},
			wantErr: "denial fixture unexpectedly accepted",
		},
		{
			name: "duplicate fixture member",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/positive/valid.json"), `{"value":"ok","value":"duplicate"}`)
			},
			wantErr: "duplicate",
		},
		{
			name: "unstable schema id",
			mutate: func(t *testing.T, repository string) {
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/root.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"https://example.invalid/root",
  "type":"object"
}`)
			},
			wantErr: "stable $id",
		},
		{
			name: "schema inventory root has unknown field",
			mutate: func(t *testing.T, repository string) {
				mutateTestSchemaInventoryRoot(t, repository, func(root map[string]any) {
					root["authority"] = "smuggled"
				})
			},
			wantErr: "schema inventory root has unknown fields",
		},
		{
			name: "schema inventory entry has unknown field",
			mutate: func(t *testing.T, repository string) {
				mutateTestSchemaInventoryRoot(t, repository, func(root map[string]any) {
					root["schemas"].([]any)[0].(map[string]any)["force"] = true
				})
			},
			wantErr: "schema inventory entry 0 has unknown fields",
		},
		{
			name: "schema removed from the closed inventory",
			mutate: func(t *testing.T, repository string) {
				mutateTestSchemaInventory(t, repository, func(entries []any) []any {
					return entries[1:]
				})
			},
			wantErr: "schema inventory mismatch",
		},
		{
			name: "schema path renamed outside the closed inventory",
			mutate: func(t *testing.T, repository string) {
				if err := os.Rename(
					filepath.Join(repository, "contracts/schemas/v1/value.schema.json"),
					filepath.Join(repository, "contracts/schemas/v1/renamed.schema.json"),
				); err != nil {
					t.Fatal(err)
				}
			},
			wantErr: "schema inventory mismatch",
		},
		{
			name: "schema id substituted outside the closed inventory",
			mutate: func(t *testing.T, repository string) {
				for _, path := range []string{
					"contracts/schemas/v1/value.schema.json",
					"contracts/schemas/v1/root.schema.json",
					"contracts/fixtures/schema/index.json",
				} {
					replaceInTestFile(t, filepath.Join(repository, path), testSchemaPrefix+"value/1.0.0", testSchemaPrefix+"substituted/1.0.0")
				}
			},
			wantErr: "schema inventory mismatch",
		},
		{
			name: "schema digest is stale in the closed inventory",
			mutate: func(t *testing.T, repository string) {
				replaceInTestFile(
					t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"),
					`"maxLength":128`, `"maxLength":129`,
				)
			},
			wantErr: "schema inventory mismatch",
		},
		{
			name: "schema added outside the closed inventory",
			mutate: func(t *testing.T, repository string) {
				const extraID = testSchemaPrefix + "extra/1.0.0"
				writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/extra.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+extraID+`",
  "type":"string",
  "minLength":1,
  "maxLength":128
}`)
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/positive/extra.json"), `"ok"`)
				writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/negative/extra.json"), `""`)
				mutateTestFixtureIndex(t, repository, func(entries []any) []any {
					return append(entries,
						map[string]any{"path": "contracts/fixtures/schema/positive/extra.json", "schemaId": extraID, "valid": true, "category": "positive", "expectedKeyword": []any{}},
						map[string]any{"path": "contracts/fixtures/schema/negative/extra.json", "schemaId": extraID, "valid": false, "category": "negative", "expectedKeyword": "minLength"},
					)
				})
			},
			wantErr: "schema inventory mismatch",
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			repository := testRepository(t)
			test.mutate(t, repository)
			_, err := ValidateRepository(repository, filepath.Join(repository, "contracts/fixtures/schema/index.json"))
			if err == nil || !strings.Contains(err.Error(), test.wantErr) {
				t.Fatalf("error=%v, want substring %q", err, test.wantErr)
			}
		})
	}
}

func TestValidationKeywordsNormalizesEngineSpecificKinds(t *testing.T) {
	err := &jsonschema.ValidationError{
		SchemaURL: "https://schemas.example/root#/$defs/value/unevaluatedProperties",
		ErrorKind: &kind.FalseSchema{},
		Causes: []*jsonschema.ValidationError{
			{SchemaURL: "https://schemas.example/root#/$defs/value/allOf/0", ErrorKind: &kind.Not{}},
		},
	}
	want := []string{"not", "unevaluatedProperties"}
	if got := validationKeywords(err); !reflect.DeepEqual(got, want) {
		t.Fatalf("validationKeywords()=%v, want %v", got, want)
	}
}

func TestFixtureSchemaDescriptorErrorBindsSelectedSchema(t *testing.T) {
	const (
		schemaID     = testSchemaPrefix + "root/1.0.0"
		schemaDigest = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
	)
	tests := []struct {
		name     string
		instance any
		want     string
	}{
		{
			name: "absent descriptor is outside this cross-field rule",
			instance: map[string]any{
				"value": "ok",
			},
		},
		{
			name: "exact descriptor",
			instance: map[string]any{
				"schema": map[string]any{"id": schemaID, "digest": schemaDigest},
			},
		},
		{
			name: "wrong schema id",
			instance: map[string]any{
				"schema": map[string]any{"id": testSchemaPrefix + "other/1.0.0", "digest": schemaDigest},
			},
			want: "schema_id_mismatch",
		},
		{
			name: "wrong schema digest",
			instance: map[string]any{
				"schema": map[string]any{
					"id":     schemaID,
					"digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
				},
			},
			want: "schema_digest_mismatch",
		},
		{
			name: "malformed descriptor fails at id comparison",
			instance: map[string]any{
				"schema": "not-an-object",
			},
			want: "schema_id_mismatch",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := fixtureSchemaDescriptorError(test.instance, schemaID, schemaDigest); got != test.want {
				t.Fatalf("fixtureSchemaDescriptorError()=%q, want %q", got, test.want)
			}
		})
	}
}

func TestCommonDefinitionsLibraryIsTheOnlyNarrowDenialCoverageExemption(t *testing.T) {
	schemas := map[string]*loadedSchema{
		commonSchemaID: {
			document: map[string]any{
				"$schema": draft2020Schema,
				"$id":     commonSchemaID,
				"title":   "definitions",
				"$defs":   map[string]any{"value": map[string]any{"type": "string"}},
			},
		},
	}
	exemptions, err := denialCoverageExemptions(schemas)
	if err != nil {
		t.Fatal(err)
	}
	want := []SchemaCoverageExemption{{
		ID: commonSchemaID, Reason: "definitions-library-no-instance-contract",
	}}
	if !reflect.DeepEqual(exemptions, want) {
		t.Fatalf("exemptions=%v, want %v", exemptions, want)
	}
	schemas[commonSchemaID].document.(map[string]any)["type"] = "object"
	if _, err := denialCoverageExemptions(schemas); err == nil || !strings.Contains(err.Error(), "gained instance-contract fields") {
		t.Fatalf("mutated common exemption error=%v", err)
	}
}

func testRepository(t *testing.T) string {
	t.Helper()
	repository := t.TempDir()
	writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/value.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`value/1.0.0",
  "type":"string",
  "minLength":1,
  "maxLength":128
}`)
	writeTestFile(t, filepath.Join(repository, "contracts/schemas/v1/root.schema.json"), `{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"`+testSchemaPrefix+`root/1.0.0",
  "type":"object",
  "properties":{"value":{"$ref":"`+testSchemaPrefix+`value/1.0.0"}},
  "required":["value"],
  "additionalProperties":false
}`)
	writeTestSchemaInventory(t, repository)
	writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/positive/valid.json"), `{"value":"ok"}`)
	writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/positive/value.json"), `"ok"`)
	writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/negative/invalid.json"), `{"value":"ok","authority":"smuggled"}`)
	writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/negative/value.json"), `""`)
	writeTestFile(t, filepath.Join(repository, "contracts/compatibility/current.json"), `{"value":"authoritative-profile"}`)
	writeTestFile(t, filepath.Join(repository, "contracts/fixtures/schema/index.json"), `{
  "profile":"bytedesk.schema-fixtures/1",
  "fixtures":[
    {"path":"contracts/fixtures/schema/positive/valid.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":true,"category":"positive","expectedKeyword":[]},
    {"path":"contracts/fixtures/schema/positive/value.json","schemaId":"`+testSchemaPrefix+`value/1.0.0","valid":true,"category":"positive","expectedKeyword":[]},
    {"path":"contracts/fixtures/schema/negative/invalid.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":false,"category":"negative","expectedKeyword":"additionalProperties"},
    {"path":"contracts/compatibility/current.json","schemaId":"`+testSchemaPrefix+`root/1.0.0","valid":true,"category":"positive","expectedKeyword":[]},
    {"path":"contracts/fixtures/schema/negative/value.json","schemaId":"`+testSchemaPrefix+`value/1.0.0","valid":false,"category":"negative","expectedKeyword":"minLength"}
  ]
}`)
	return repository
}

func writeTestSchemaInventory(t *testing.T, repository string) {
	t.Helper()
	paths, err := filepath.Glob(filepath.Join(repository, "contracts/schemas/v1/*.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	entries := make([]any, 0, len(paths))
	for _, path := range paths {
		document, digest, err := loadStrictJSON(path)
		if err != nil {
			t.Fatal(err)
		}
		root := document.(map[string]any)
		entries = append(entries, map[string]any{
			"id": root["$id"], "path": repositoryPath(repository, path), "digest": digest,
		})
	}
	sortSchemaInventoryEntries(entries)
	writeTestJSON(t, filepath.Join(repository, "contracts/bundle/v1/schema-inventory.json"), map[string]any{
		"profile": "bytedesk.contract-schema-inventory/1",
		"schemas": entries,
	})
}

func mutateTestSchemaInventory(t *testing.T, repository string, mutate func([]any) []any) {
	t.Helper()
	mutateTestSchemaInventoryRoot(t, repository, func(root map[string]any) {
		root["schemas"] = mutate(root["schemas"].([]any))
	})
}

func mutateTestSchemaInventoryRoot(t *testing.T, repository string, mutate func(map[string]any)) {
	t.Helper()
	path := filepath.Join(repository, "contracts/bundle/v1/schema-inventory.json")
	document, _, err := loadStrictJSON(path)
	if err != nil {
		t.Fatal(err)
	}
	root := document.(map[string]any)
	mutate(root)
	writeTestJSON(t, path, root)
}

func mutateTestFixtureIndex(t *testing.T, repository string, mutate func([]any) []any) {
	t.Helper()
	path := filepath.Join(repository, "contracts/fixtures/schema/index.json")
	document, _, err := loadStrictJSON(path)
	if err != nil {
		t.Fatal(err)
	}
	root := document.(map[string]any)
	root["fixtures"] = mutate(root["fixtures"].([]any))
	writeTestJSON(t, path, root)
}

func sortSchemaInventoryEntries(entries []any) {
	for first := 0; first < len(entries); first++ {
		for second := first + 1; second < len(entries); second++ {
			left := entries[first].(map[string]any)["id"].(string)
			right := entries[second].(map[string]any)["id"].(string)
			if right < left {
				entries[first], entries[second] = entries[second], entries[first]
			}
		}
	}
}

func writeTestJSON(t *testing.T, path string, value any) {
	t.Helper()
	payload, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	writeTestFile(t, path, string(payload))
}

func replaceInTestFile(t *testing.T, path, old, replacement string) {
	t.Helper()
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	updated := strings.Replace(string(payload), old, replacement, 1)
	if updated == string(payload) {
		t.Fatalf("test mutation did not find %q", old)
	}
	if err := os.WriteFile(path, []byte(updated), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeTestFile(t *testing.T, path, contents string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(contents), 0o644); err != nil {
		t.Fatal(err)
	}
}
