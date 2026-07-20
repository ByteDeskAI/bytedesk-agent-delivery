package api

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

func repositoryRoot(t *testing.T) string {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("could not determine caller")
	}
	return filepath.Join(filepath.Dir(thisFile), "..", "..")
}

// TestPreconditionFailedProblemValidatesAgainstTheRealSchema proves the
// 412 problem response is a real, schema-valid bytedesk.problem-details/1
// instance, not just a hand-shaped struct that happens to compile. Compiles
// every checked-in schema offline (problem-details references common.schema.json).
func TestPreconditionFailedProblemValidatesAgainstTheRealSchema(t *testing.T) {
	root := repositoryRoot(t)
	schemaDir := filepath.Join(root, "contracts", "schemas", "v1")

	compiler := jsonschema.NewCompiler()
	compiler.DefaultDraft(jsonschema.Draft2020)
	compiler.AssertFormat()

	entries, err := os.ReadDir(schemaDir)
	if err != nil {
		t.Fatal(err)
	}
	var problemSchemaID string
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}
		path := filepath.Join(schemaDir, entry.Name())
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		var document map[string]any
		if err := json.Unmarshal(raw, &document); err != nil {
			t.Fatalf("%s: %v", path, err)
		}
		id, _ := document["$id"].(string)
		if id == "" {
			continue
		}
		if entry.Name() == "problem-details.schema.json" {
			problemSchemaID = id
		}
		if err := compiler.AddResource(id, document); err != nil {
			t.Fatalf("add resource %s: %v", id, err)
		}
	}
	if problemSchemaID == "" {
		t.Fatal("could not locate problem-details schema $id")
	}

	schema, err := compiler.Compile(problemSchemaID)
	if err != nil {
		t.Fatalf("compile problem-details schema: %v", err)
	}

	server := newTestServer()
	defer server.Close()
	doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":1}`))

	staleETag := `"999-sha256:0000000000000000000000000000000000000000000000000000000000000000"`
	resp := doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-Match": staleETag}, []byte(`{"v":2}`))
	if resp.StatusCode != http.StatusPreconditionFailed {
		t.Fatalf("expected 412, got %d", resp.StatusCode)
	}
	defer resp.Body.Close()

	var instance any
	if err := json.NewDecoder(resp.Body).Decode(&instance); err != nil {
		t.Fatal(err)
	}
	if err := schema.Validate(instance); err != nil {
		t.Fatalf("problem response is not schema-valid: %v", err)
	}
}
