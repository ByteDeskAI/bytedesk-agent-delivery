package planning

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

type plan struct {
	Schema                       string      `json:"schema"`
	ContractStatus               string      `json:"contractStatus"`
	Repository                   string      `json:"repository"`
	ProductionMutationAuthorized bool        `json:"productionMutationAuthorized"`
	Tracks                       []track     `json:"tracks"`
	Milestones                   []milestone `json:"milestones"`
	Tasks                        []task      `json:"tasks"`
}

type track struct {
	ID string `json:"id"`
}

type milestone struct {
	ID                  string   `json:"id"`
	Name                string   `json:"name"`
	Track               string   `json:"track"`
	DependsOnTasks      []string `json:"dependsOnTasks"`
	DependsOnMilestones []string `json:"dependsOnMilestones"`
}

type task struct {
	ID                  string   `json:"id"`
	Doc                 string   `json:"doc"`
	Track               string   `json:"track"`
	DependsOnTasks      []string `json:"dependsOnTasks"`
	DependsOnMilestones []string `json:"dependsOnMilestones"`
}

type repositoryFixtureIndex struct {
	Scope           string              `json:"scope"`
	Fixtures        []repositoryFixture `json:"fixtures"`
	BundleInclusion bool                `json:"bundleInclusion"`
}

type repositoryFixture struct {
	Path            string          `json:"path"`
	SchemaID        string          `json:"schemaId"`
	Valid           bool            `json:"valid"`
	Category        string          `json:"category"`
	ExpectedKeyword json.RawMessage `json:"expectedKeyword"`
}

func repoRoot(t *testing.T) string {
	t.Helper()
	root, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	return root
}

func TestRepositoryPlanProjectionAndDrift(t *testing.T) {
	root := repoRoot(t)
	planPath := filepath.Join(root, "docs", "planning", "development-plan.json")
	data, err := os.ReadFile(planPath)
	if err != nil {
		t.Fatal(err)
	}
	compiled := compilePlanSchema(t, root)
	planDocument, err := jsonschema.UnmarshalJSON(bytes.NewReader(data))
	if err != nil {
		t.Fatalf("parse repository development plan: %v", err)
	}
	if err := compiled.Validate(planDocument); err != nil {
		t.Fatalf("repository development plan violates its schema: %v", err)
	}
	var projection plan
	if err := json.Unmarshal(data, &projection); err != nil {
		t.Fatal(err)
	}
	if projection.Schema != "https://schemas.bytedesk.ai/agent-delivery/repository/development-plan/1" || projection.ContractStatus != "repository-internal" {
		t.Fatalf("development plan advertises a product contract: schema=%q status=%q", projection.Schema, projection.ContractStatus)
	}
	if projection.Repository != "ByteDeskAI/bytedesk-agent-delivery" || projection.ProductionMutationAuthorized {
		t.Fatal("development plan repository or production-mutation boundary changed")
	}
	if len(projection.Tracks) != 3 || len(projection.Tasks) != 18 || len(projection.Milestones) != 7 {
		t.Fatalf("expected 3 tracks, 18 tasks, and 7 milestones; got %d/%d/%d", len(projection.Tracks), len(projection.Tasks), len(projection.Milestones))
	}

	tracks := map[string]bool{}
	for _, item := range projection.Tracks {
		if item.ID == "" || tracks[item.ID] {
			t.Fatalf("invalid or duplicate track %q", item.ID)
		}
		tracks[item.ID] = true
	}
	tasks := map[string]task{}
	for _, item := range projection.Tasks {
		if _, duplicate := tasks[item.ID]; duplicate {
			t.Fatalf("duplicate task %q", item.ID)
		}
		if !tracks[item.Track] {
			t.Fatalf("task %s has unknown track %s", item.ID, item.Track)
		}
		tasks[item.ID] = item
		docPath := filepath.Join(root, "docs", "planning", filepath.FromSlash(item.Doc))
		doc, err := os.ReadFile(docPath)
		if err != nil {
			t.Fatalf("task %s: %v", item.ID, err)
		}
		expectedHeading := "# " + strings.ToUpper(item.ID[:2]) + item.ID[2:] + ":"
		if !strings.HasPrefix(string(doc), expectedHeading) {
			t.Fatalf("task %s document heading does not start with %q", item.ID, expectedHeading)
		}
	}
	milestones := map[string]milestone{}
	for _, item := range projection.Milestones {
		if _, duplicate := milestones[item.ID]; duplicate {
			t.Fatalf("duplicate milestone %q", item.ID)
		}
		if !tracks[item.Track] {
			t.Fatalf("milestone %s has unknown track %s", item.ID, item.Track)
		}
		milestones[item.ID] = item
	}

	edges := map[string][]string{}
	for _, item := range projection.Tasks {
		node := "task:" + item.ID
		for _, dependency := range item.DependsOnTasks {
			if _, ok := tasks[dependency]; !ok {
				t.Fatalf("task %s has unknown task dependency %s", item.ID, dependency)
			}
			edges[node] = append(edges[node], "task:"+dependency)
		}
		for _, dependency := range item.DependsOnMilestones {
			if _, ok := milestones[dependency]; !ok {
				t.Fatalf("task %s has unknown milestone dependency %s", item.ID, dependency)
			}
			edges[node] = append(edges[node], "milestone:"+dependency)
		}
	}
	for _, item := range projection.Milestones {
		node := "milestone:" + item.ID
		for _, dependency := range item.DependsOnTasks {
			if _, ok := tasks[dependency]; !ok {
				t.Fatalf("milestone %s has unknown task dependency %s", item.ID, dependency)
			}
			edges[node] = append(edges[node], "task:"+dependency)
		}
		for _, dependency := range item.DependsOnMilestones {
			if _, ok := milestones[dependency]; !ok {
				t.Fatalf("milestone %s has unknown milestone dependency %s", item.ID, dependency)
			}
			edges[node] = append(edges[node], "milestone:"+dependency)
		}
	}
	if err := assertAcyclic(edges); err != nil {
		t.Fatal(err)
	}

	breakdown, err := os.ReadFile(filepath.Join(root, "docs", "planning", "task-breakdown.md"))
	if err != nil {
		t.Fatal(err)
	}
	development, err := os.ReadFile(filepath.Join(root, "docs", "planning", "development-plan.md"))
	if err != nil {
		t.Fatal(err)
	}
	for _, item := range projection.Tasks {
		label := strings.ToUpper(item.ID[:2]) + item.ID[2:]
		if strings.Count(string(breakdown), "["+label+"](") != 1 {
			t.Fatalf("task breakdown does not contain exactly one linked %s row", label)
		}
	}
	for _, item := range projection.Milestones {
		if !strings.Contains(string(development), item.Name) {
			t.Fatalf("development plan Markdown omits milestone %q", item.Name)
		}
	}
}

func TestRepositoryOnlyFixtureIndexIsExecutedAndExcluded(t *testing.T) {
	root := repoRoot(t)
	indexPath := filepath.Join(root, "contracts", "fixtures", "schema", "repository-index.json")
	indexData, err := os.ReadFile(indexPath)
	if err != nil {
		t.Fatal(err)
	}
	decoder := json.NewDecoder(bytes.NewReader(indexData))
	decoder.DisallowUnknownFields()
	var index repositoryFixtureIndex
	if err := decoder.Decode(&index); err != nil {
		t.Fatalf("parse repository fixture index: %v", err)
	}
	if index.Scope != "repository-internal" || index.BundleInclusion || len(index.Fixtures) != 2 {
		t.Fatalf("unexpected repository fixture index boundary: %+v", index)
	}

	compiled := compilePlanSchema(t, root)
	currentPlan, err := os.ReadFile(filepath.Join(root, "docs", "planning", "development-plan.json"))
	if err != nil {
		t.Fatal(err)
	}
	seen := map[string]bool{}
	for _, fixture := range index.Fixtures {
		if seen[fixture.Path] {
			t.Fatalf("duplicate repository fixture %q", fixture.Path)
		}
		seen[fixture.Path] = true
		if fixture.SchemaID != "https://schemas.bytedesk.ai/agent-delivery/repository/development-plan/1" {
			t.Fatalf("repository fixture uses unexpected schema %q", fixture.SchemaID)
		}
		candidate := filepath.Join(root, filepath.FromSlash(fixture.Path))
		resolved, err := filepath.EvalSymlinks(candidate)
		if err != nil {
			t.Fatalf("resolve repository fixture %q: %v", fixture.Path, err)
		}
		allowedRoot := filepath.Join(root, "contracts", "fixtures", "schema")
		relative, err := filepath.Rel(allowedRoot, resolved)
		if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
			t.Fatalf("repository fixture escapes its root: %q", fixture.Path)
		}
		fixtureData, err := os.ReadFile(resolved)
		if err != nil {
			t.Fatal(err)
		}
		instance, err := jsonschema.UnmarshalJSON(bytes.NewReader(fixtureData))
		if err != nil {
			t.Fatalf("parse repository fixture %q: %v", fixture.Path, err)
		}
		validationErr := compiled.Validate(instance)
		if (validationErr == nil) != fixture.Valid {
			t.Fatalf("repository fixture %q valid=%v, err=%v", fixture.Path, fixture.Valid, validationErr)
		}
		if fixture.Valid && !bytes.Equal(fixtureData, currentPlan) {
			t.Fatalf("positive repository plan fixture drifted from docs/planning/development-plan.json")
		}
	}

	productIndex, err := os.ReadFile(filepath.Join(root, "contracts", "fixtures", "schema", "index.json"))
	if err != nil {
		t.Fatal(err)
	}
	for fixturePath := range seen {
		if bytes.Contains(productIndex, []byte(fixturePath)) {
			t.Fatalf("repository-only fixture leaked into product fixture index: %s", fixturePath)
		}
	}
}

func compilePlanSchema(t *testing.T, root string) *jsonschema.Schema {
	t.Helper()
	const planSchemaID = "https://schemas.bytedesk.ai/agent-delivery/repository/development-plan/1"
	schemaData, err := os.ReadFile(filepath.Join(root, "contracts", "schemas", "repository", "development-plan.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	schemaDocument, err := jsonschema.UnmarshalJSON(bytes.NewReader(schemaData))
	if err != nil {
		t.Fatalf("parse repository planning schema: %v", err)
	}
	compiler := jsonschema.NewCompiler()
	compiler.DefaultDraft(jsonschema.Draft2020)
	compiler.AssertFormat()
	if err := compiler.AddResource(planSchemaID, schemaDocument); err != nil {
		t.Fatalf("load repository planning schema: %v", err)
	}
	compiled, err := compiler.Compile(planSchemaID)
	if err != nil {
		t.Fatalf("compile repository planning schema: %v", err)
	}
	return compiled
}

func assertAcyclic(edges map[string][]string) error {
	state := map[string]int{}
	var visit func(string) error
	visit = func(node string) error {
		switch state[node] {
		case 1:
			return fmt.Errorf("planning graph cycle at %s", node)
		case 2:
			return nil
		}
		state[node] = 1
		for _, dependency := range edges[node] {
			if err := visit(dependency); err != nil {
				return err
			}
		}
		state[node] = 2
		return nil
	}
	for node := range edges {
		if err := visit(node); err != nil {
			return err
		}
	}
	return nil
}
