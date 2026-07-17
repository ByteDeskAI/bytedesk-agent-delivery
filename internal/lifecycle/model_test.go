package lifecycle

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
)

type fixtureSet struct {
	Profile string        `json:"profile"`
	Cases   []fixtureCase `json:"cases"`
}

type fixtureCase struct {
	Name       string `json:"name"`
	Model      string `json:"model"`
	From       string `json:"from"`
	To         string `json:"to"`
	Actor      string `json:"actor"`
	Transition string `json:"transition"`
	Valid      bool   `json:"valid"`
}

func contractRoot(t *testing.T) string {
	t.Helper()
	root, err := filepath.Abs(filepath.Join("..", "..", "contracts"))
	if err != nil {
		t.Fatal(err)
	}
	return root
}

func TestModelsAreClosedReachableAndExhaustive(t *testing.T) {
	paths, err := filepath.Glob(filepath.Join(contractRoot(t), "lifecycle", "*.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(paths) != 7 {
		t.Fatalf("expected 7 lifecycle models, got %d", len(paths))
	}

	for _, path := range paths {
		path := path
		t.Run(filepath.Base(path), func(t *testing.T) {
			model, err := LoadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			if err := model.Validate(); err != nil {
				t.Fatal(err)
			}

			for _, transition := range model.Transitions {
				declaredSources := map[string]bool{}
				for _, from := range transition.From {
					declaredSources[from] = true
					if _, ok := model.Resolve(from, transition.To, transition.Actor, transition.Name); !ok {
						t.Fatalf("declared transition did not resolve: %s %s -> %s", transition.Name, from, transition.To)
					}
					if _, ok := model.Resolve(from, transition.To, "wrong-actor", transition.Name); ok {
						t.Fatalf("transition accepted wrong actor: %s", transition.Name)
					}
					if _, ok := model.Resolve(from, transition.To, transition.Actor, "unknown-transition"); ok {
						t.Fatalf("transition accepted unknown name from %s to %s", from, transition.To)
					}
					for _, wrongDestination := range model.States {
						if wrongDestination.Name == transition.To {
							continue
						}
						if _, ok := model.Resolve(from, wrongDestination.Name, transition.Actor, transition.Name); ok {
							t.Fatalf("transition %s accepted wrong destination %s", transition.Name, wrongDestination.Name)
						}
					}
				}
				for _, wrongSource := range model.States {
					if declaredSources[wrongSource.Name] {
						continue
					}
					if _, ok := model.Resolve(wrongSource.Name, transition.To, transition.Actor, transition.Name); ok {
						t.Fatalf("transition %s accepted wrong source %s", transition.Name, wrongSource.Name)
					}
				}
			}

			for _, from := range model.States {
				for _, to := range model.States {
					if model.hasDeclaredPair(from.Name, to.Name) {
						continue
					}
					for _, transition := range model.Transitions {
						if _, ok := model.Resolve(from.Name, to.Name, transition.Actor, transition.Name); ok {
							t.Fatalf("illegal state pair accepted by %s: %s -> %s", transition.Name, from.Name, to.Name)
						}
					}
				}
			}
		})
	}
}

func TestLifecycleFixtures(t *testing.T) {
	bytes, err := os.ReadFile(filepath.Join(contractRoot(t), "fixtures", "lifecycle", "cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var fixtures fixtureSet
	if err := json.Unmarshal(bytes, &fixtures); err != nil {
		t.Fatal(err)
	}
	if fixtures.Profile != "bytedesk.lifecycle-fixtures/1" {
		t.Fatalf("unexpected fixture profile %q", fixtures.Profile)
	}
	if len(fixtures.Cases) < 16 {
		t.Fatalf("expected at least 16 lifecycle fixtures, got %d", len(fixtures.Cases))
	}

	models := map[string]*Model{}
	for _, fixture := range fixtures.Cases {
		model := models[fixture.Model]
		if model == nil {
			model, err = LoadFile(filepath.Join(contractRoot(t), "lifecycle", fixture.Model))
			if err != nil {
				t.Fatalf("%s: %v", fixture.Name, err)
			}
			models[fixture.Model] = model
		}
		_, accepted := model.Resolve(fixture.From, fixture.To, fixture.Actor, fixture.Transition)
		if accepted != fixture.Valid {
			t.Fatalf("fixture %s: accepted=%v, want %v", fixture.Name, accepted, fixture.Valid)
		}
	}
}

func TestLifecycleStatesMatchAuthoritySchemas(t *testing.T) {
	mappings := []struct {
		model    string
		schema   string
		property string
	}{
		{model: "installation.v1.json", schema: "installation.schema.json", property: "state"},
		{model: "candidate.v1.json", schema: "candidate.schema.json", property: "state"},
		{model: "rollout.v1.json", schema: "rollout.schema.json", property: "state"},
		{model: "host-reconciliation-attempt.v1.json", schema: "host-reconciliation-attempt.schema.json", property: "state"},
		{model: "runtime-slot.v1.json", schema: "runtime-slot.schema.json", property: "state"},
		{model: "durable-action.v1.json", schema: "action.schema.json", property: "state"},
		{model: "target-condition.v1.json", schema: "target-delivery-state.schema.json", property: "condition"},
	}
	for _, mapping := range mappings {
		mapping := mapping
		t.Run(mapping.model, func(t *testing.T) {
			model, err := LoadFile(filepath.Join(contractRoot(t), "lifecycle", mapping.model))
			if err != nil {
				t.Fatal(err)
			}
			modelStates := make([]string, 0, len(model.States))
			for _, state := range model.States {
				modelStates = append(modelStates, state.Name)
			}
			sort.Strings(modelStates)

			payload, err := os.ReadFile(filepath.Join(contractRoot(t), "schemas", "v1", mapping.schema))
			if err != nil {
				t.Fatal(err)
			}
			var schema struct {
				Properties map[string]struct {
					Enum []string `json:"enum"`
				} `json:"properties"`
			}
			if err := json.Unmarshal(payload, &schema); err != nil {
				t.Fatal(err)
			}
			schemaStates := append([]string(nil), schema.Properties[mapping.property].Enum...)
			sort.Strings(schemaStates)
			if !reflect.DeepEqual(schemaStates, modelStates) {
				t.Fatalf("state drift: schema=%v model=%v", schemaStates, modelStates)
			}
		})
	}
}

func TestParseRejectsUntrustedOrUnvalidatedModels(t *testing.T) {
	tests := []struct {
		name  string
		input string
	}{
		{
			name:  "duplicate member",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","profile":"bytedesk.other-lifecycle/1","version":1,"initialStates":[],"states":[],"transitions":[]}`,
		},
		{
			name:  "unknown member",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":[],"states":[],"transitions":[],"authority":"smuggled"}`,
		},
		{
			name:  "semantic invalidity",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":[],"states":[],"transitions":[]}`,
		},
		{
			name:  "schema-invalid actor with otherwise valid graph",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":["start"],"states":[{"name":"start","terminal":false},{"name":"done","terminal":true}],"transitions":[{"name":"complete","from":["start"],"to":"done","actor":"bad actor","guard":"ready","cas":"match","effects":["append"],"event":"done.v1","retryable":false}]}`,
		},
		{
			name:  "schema-invalid duplicate effects with otherwise valid graph",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":["start"],"states":[{"name":"start","terminal":false},{"name":"done","terminal":true}],"transitions":[{"name":"complete","from":["start"],"to":"done","actor":"worker","guard":"ready","cas":"match","effects":["append","append"],"event":"done.v1","retryable":false}]}`,
		},
		{
			name:  "required state terminal omitted",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":["start"],"states":[{"name":"start"},{"name":"done","terminal":true}],"transitions":[{"name":"complete","from":["start"],"to":"done","actor":"worker","guard":"ready","cas":"match","effects":["append"],"event":"done.v1","retryable":false}]}`,
		},
		{
			name:  "required transition retryable omitted",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":["start"],"states":[{"name":"start","terminal":false},{"name":"done","terminal":true}],"transitions":[{"name":"complete","from":["start"],"to":"done","actor":"worker","guard":"ready","cas":"match","effects":["append"],"event":"done.v1"}]}`,
		},
		{
			name:  "required booleans cannot be null",
			input: `{"$schema":"https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0","profile":"bytedesk.fake-lifecycle/1","version":1,"initialStates":["start"],"states":[{"name":"start","terminal":null},{"name":"done","terminal":true}],"transitions":[{"name":"complete","from":["start"],"to":"done","actor":"worker","guard":"ready","cas":"match","effects":["append"],"event":"done.v1","retryable":false}]}`,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if _, err := Parse([]byte(test.input)); err == nil {
				t.Fatal("untrusted lifecycle model was accepted")
			}
		})
	}
}

func TestResolveRefusesDirectlyConstructedInvalidModel(t *testing.T) {
	model := &Model{
		Schema:        "https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0",
		Profile:       "not-a-contract",
		Version:       1,
		InitialStates: []string{"start"},
		States:        []State{{Name: "start"}, {Name: "done", Terminal: true}},
		Transitions: []Transition{{
			Name: "complete", From: []string{"start"}, To: "done", Actor: "worker",
			Guard: "ready", CAS: "match", Effects: []string{"append"}, Event: "done.v1",
		}},
	}
	if _, ok := model.Resolve("start", "done", "worker", "complete"); ok {
		t.Fatal("Resolve accepted a model that did not pass validation")
	}
	if err := model.Validate(); err == nil || !strings.Contains(err.Error(), "profile") {
		t.Fatalf("unexpected validation error: %v", err)
	}
}
