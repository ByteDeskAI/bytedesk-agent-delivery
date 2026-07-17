// Package schema provides the independent Go/Draft 2020-12 contract validator.
// It deliberately shares only source schemas and fixture expectations with the
// Python validator; validation behavior comes from a separate implementation.
package schema

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
	"github.com/santhosh-tekuri/jsonschema/v6/kind"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

const (
	ValidatorID             = "go-jsonschema-v6-draft-2020-12"
	schemaIDPrefix          = "https://schemas.bytedesk.ai/agent-delivery/v1/"
	schemaInventoryProfile  = "bytedesk.contract-schema-inventory/1"
	schemaInventoryPath     = "contracts/bundle/v1/schema-inventory.json"
	commonSchemaID          = schemaIDPrefix + "common/1.0.0"
	draft2020Schema         = "https://json-schema.org/draft/2020-12/schema"
	maxContractArrayItems   = int64(100_000)
	maxContractStringLength = int64(4 << 20)
	maxContractProperties   = int64(100_000)
	minSafeInteger          = int64(-9_007_199_254_740_991)
	maxSafeInteger          = int64(9_007_199_254_740_991)
)

// Report is stable machine-readable evidence for one complete validation run.
type Report struct {
	Profile                  string                    `json:"profile"`
	Validator                string                    `json:"validator"`
	SchemaCount              int                       `json:"schemaCount"`
	FixtureCount             int                       `json:"fixtureCount"`
	Schemas                  []SchemaEvidence          `json:"schemas"`
	Fixtures                 []FixtureEvidence         `json:"fixtures"`
	SchemaInventory          SchemaInventoryEvidence   `json:"schemaInventory"`
	ResourceBounds           ResourceBoundsEvidence    `json:"resourceBounds"`
	DenialCoverageExemptions []SchemaCoverageExemption `json:"denialCoverageExemptions"`
	Outcome                  string                    `json:"outcome"`
}

// SchemaInventoryEvidence binds this validation run to the one reviewed,
// source-controlled inventory of product schemas.
type SchemaInventoryEvidence struct {
	Profile     string `json:"profile"`
	Path        string `json:"path"`
	Digest      string `json:"digest"`
	SchemaCount int    `json:"schemaCount"`
	Outcome     string `json:"outcome"`
}

// ResourceBoundsEvidence proves that every directly typed collection and
// scalar in the normative schemas has a portable, machine-enforced ceiling.
// Closed fixed-shape objects and const/enum strings are inherently bounded.
type ResourceBoundsEvidence struct {
	Profile                  string `json:"profile"`
	DirectArraySchemaCount   int    `json:"directArraySchemaCount"`
	DirectStringSchemaCount  int    `json:"directStringSchemaCount"`
	DirectIntegerSchemaCount int    `json:"directIntegerSchemaCount"`
	DirectObjectSchemaCount  int    `json:"directObjectSchemaCount"`
	MaximumArrayItems        int64  `json:"maximumArrayItems"`
	MaximumStringLength      int64  `json:"maximumStringLength"`
	MaximumObjectProperties  int64  `json:"maximumObjectProperties"`
	Outcome                  string `json:"outcome"`
}

// SchemaCoverageExemption records the single non-instance schema that cannot
// have a denial fixture because it intentionally contains definitions only.
type SchemaCoverageExemption struct {
	ID     string `json:"id"`
	Reason string `json:"reason"`
}

type SchemaEvidence struct {
	ID     string `json:"id"`
	Path   string `json:"path"`
	Digest string `json:"digest"`
}

type FixtureEvidence struct {
	Path                  string   `json:"path"`
	SchemaID              string   `json:"schemaId"`
	ExpectedValid         bool     `json:"expectedValid"`
	ObservedKeywords      []string `json:"observedKeywords"`
	ObservedSemanticError *string  `json:"observedSemanticError"`
	Outcome               string   `json:"outcome"`
}

type loadedSchema struct {
	path      string
	document  any
	digest    string
	validator *jsonschema.Schema
}

// ValidateRepository compiles every product schema without network access and
// proves every indexed positive and denial fixture against its exact schema.
func ValidateRepository(repositoryRoot, indexPath string) (Report, error) {
	repositoryRoot, err := filepath.Abs(repositoryRoot)
	if err != nil {
		return Report{}, fmt.Errorf("resolve repository root: %w", err)
	}
	schemaRoot := filepath.Join(repositoryRoot, "contracts", "schemas", "v1")
	paths, err := filepath.Glob(filepath.Join(schemaRoot, "*.schema.json"))
	if err != nil {
		return Report{}, fmt.Errorf("enumerate schemas: %w", err)
	}
	sort.Strings(paths)
	if len(paths) == 0 {
		return Report{}, errors.New("no source schemas found")
	}

	compiler := jsonschema.NewCompiler()
	compiler.DefaultDraft(jsonschema.Draft2020)
	compiler.AssertFormat()
	compiler.AssertVocabs()
	compiler.UseLoader(offlineLoader{})

	schemas := make(map[string]*loadedSchema, len(paths))
	for _, path := range paths {
		document, digest, err := loadStrictJSON(path)
		if err != nil {
			return Report{}, fmt.Errorf("read schema %s: %w", repositoryPath(repositoryRoot, path), err)
		}
		object, ok := document.(map[string]any)
		if !ok {
			return Report{}, fmt.Errorf("schema root is not an object: %s", repositoryPath(repositoryRoot, path))
		}
		if object["$schema"] != draft2020Schema {
			return Report{}, fmt.Errorf("schema does not declare Draft 2020-12: %s", repositoryPath(repositoryRoot, path))
		}
		id, ok := object["$id"].(string)
		if !ok || !stableSchemaID(id) {
			return Report{}, fmt.Errorf("missing or invalid stable $id: %s", repositoryPath(repositoryRoot, path))
		}
		if _, duplicate := schemas[id]; duplicate {
			return Report{}, fmt.Errorf("duplicate schema $id: %s", id)
		}
		if err := compiler.AddResource(id, document); err != nil {
			return Report{}, fmt.Errorf("register schema %s: %w", id, err)
		}
		schemas[id] = &loadedSchema{path: path, document: document, digest: digest}
	}
	for id, item := range schemas {
		if err := validateReferenceClosure(id, item.document, schemas); err != nil {
			return Report{}, err
		}
		compiled, err := compiler.Compile(id)
		if err != nil {
			return Report{}, fmt.Errorf("compile schema %s: %w", id, err)
		}
		item.validator = compiled
	}
	resourceBounds, err := validateResourceBounds(schemas)
	if err != nil {
		return Report{}, err
	}
	exemptions, err := denialCoverageExemptions(schemas)
	if err != nil {
		return Report{}, err
	}
	schemaInventory, err := validateSchemaInventory(
		repositoryRoot,
		filepath.Join(repositoryRoot, filepath.FromSlash(schemaInventoryPath)),
		schemas,
	)
	if err != nil {
		return Report{}, err
	}

	fixtures, err := loadFixtureIndex(repositoryRoot, indexPath, schemas)
	if err != nil {
		return Report{}, err
	}
	report := Report{
		Profile:                  "bytedesk.contract-validation-evidence/1",
		Validator:                ValidatorID,
		SchemaCount:              len(schemas),
		FixtureCount:             len(fixtures),
		SchemaInventory:          schemaInventory,
		ResourceBounds:           resourceBounds,
		DenialCoverageExemptions: exemptions,
		Outcome:                  "pass",
	}
	ids := make([]string, 0, len(schemas))
	for id := range schemas {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		item := schemas[id]
		report.Schemas = append(report.Schemas, SchemaEvidence{
			ID: id, Path: repositoryPath(repositoryRoot, item.path), Digest: item.digest,
		})
	}

	for _, fixture := range fixtures {
		instance, _, err := loadStrictJSON(fixture.absolutePath)
		if err != nil {
			return Report{}, fmt.Errorf("read fixture %s: %w", fixture.path, err)
		}
		selectedSchema := schemas[fixture.schemaID]
		semanticError := fixtureSchemaDescriptorError(
			instance, fixture.schemaID, selectedSchema.digest,
		)
		if semanticError != fixture.expectedSemanticError {
			return Report{}, fmt.Errorf(
				"fixture %s schema descriptor semantic result mismatch: expected %q, observed %q",
				fixture.path, fixture.expectedSemanticError, semanticError,
			)
		}
		validationErr := selectedSchema.validator.Validate(instance)
		if fixture.expectedSemanticError != "" && validationErr != nil {
			return Report{}, fmt.Errorf(
				"semantic denial fixture also failed structural validation: %s: %w",
				fixture.path, validationErr,
			)
		}
		accepted := validationErr == nil
		if fixture.valid && !accepted {
			return Report{}, fmt.Errorf("valid fixture rejected: %s: %w", fixture.path, validationErr)
		}
		if !fixture.valid && fixture.expectedSemanticError == "" && accepted {
			return Report{}, fmt.Errorf("denial fixture unexpectedly accepted: %s", fixture.path)
		}
		keywords := validationKeywords(validationErr)
		missingExpected := missingKeywords(fixture.expectedKeywords, keywords)
		if len(missingExpected) > 0 {
			return Report{}, fmt.Errorf(
				"denial fixture %s missed expected keywords %v; observed %v",
				fixture.path, missingExpected, keywords,
			)
		}
		var observedSemanticError *string
		if semanticError != "" {
			observedSemanticError = &semanticError
		}
		report.Fixtures = append(report.Fixtures, FixtureEvidence{
			Path: fixture.path, SchemaID: fixture.schemaID, ExpectedValid: fixture.valid,
			ObservedKeywords: keywords, ObservedSemanticError: observedSemanticError, Outcome: "pass",
		})
	}
	return report, nil
}

type schemaInventoryEntry struct {
	id     string
	path   string
	digest string
}

func validateSchemaInventory(
	repositoryRoot, inventoryPath string,
	schemas map[string]*loadedSchema,
) (SchemaInventoryEvidence, error) {
	document, inventoryDigest, err := loadStrictJSON(inventoryPath)
	if err != nil {
		return SchemaInventoryEvidence{}, fmt.Errorf("read schema inventory: %w", err)
	}
	root, ok := document.(map[string]any)
	if !ok {
		return SchemaInventoryEvidence{}, errors.New("schema inventory root must be an object")
	}
	if unexpected := unknownObjectFields(root, "profile", "schemas"); len(unexpected) > 0 {
		return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory root has unknown fields: %v", unexpected)
	}
	if len(root) != 2 {
		return SchemaInventoryEvidence{}, errors.New("schema inventory root lacks profile or schemas")
	}
	if root["profile"] != schemaInventoryProfile {
		return SchemaInventoryEvidence{}, errors.New("schema inventory has an unknown profile")
	}
	rawEntries, ok := root["schemas"].([]any)
	if !ok || len(rawEntries) == 0 {
		return SchemaInventoryEvidence{}, errors.New("schema inventory schemas must be a non-empty array")
	}

	expected := make(map[string]schemaInventoryEntry, len(rawEntries))
	paths := make(map[string]struct{}, len(rawEntries))
	previousID := ""
	for index, raw := range rawEntries {
		item, ok := raw.(map[string]any)
		if !ok {
			return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory entry %d must be an object", index)
		}
		if unexpected := unknownObjectFields(item, "id", "path", "digest"); len(unexpected) > 0 {
			return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory entry %d has unknown fields: %v", index, unexpected)
		}
		if len(item) != 3 {
			return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory entry %d lacks id, path, or digest", index)
		}
		id, idOK := item["id"].(string)
		path, pathOK := item["path"].(string)
		digest, digestOK := item["digest"].(string)
		if !idOK || !stableSchemaID(id) || !pathOK || !validInventorySchemaPath(path) || !digestOK || !exactSHA256(digest) {
			return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory entry %d has an invalid id, path, or digest", index)
		}
		if previousID != "" && id <= previousID {
			return SchemaInventoryEvidence{}, errors.New("schema inventory entries must have unique IDs in ascending order")
		}
		previousID = id
		if _, duplicate := expected[id]; duplicate {
			return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory contains duplicate ID: %s", id)
		}
		if _, duplicate := paths[path]; duplicate {
			return SchemaInventoryEvidence{}, fmt.Errorf("schema inventory contains duplicate path: %s", path)
		}
		paths[path] = struct{}{}
		expected[id] = schemaInventoryEntry{id: id, path: path, digest: digest}
	}

	actual := make(map[string]schemaInventoryEntry, len(schemas))
	for id, item := range schemas {
		actual[id] = schemaInventoryEntry{
			id: id, path: repositoryPath(repositoryRoot, item.path), digest: item.digest,
		}
	}
	missing := make([]string, 0)
	added := make([]string, 0)
	changed := make([]string, 0)
	for id, expectedEntry := range expected {
		actualEntry, exists := actual[id]
		if !exists {
			missing = append(missing, id)
			continue
		}
		if actualEntry.path != expectedEntry.path || actualEntry.digest != expectedEntry.digest {
			changed = append(changed, id)
		}
	}
	for id := range actual {
		if _, exists := expected[id]; !exists {
			added = append(added, id)
		}
	}
	if len(missing) > 0 || len(added) > 0 || len(changed) > 0 {
		sort.Strings(missing)
		sort.Strings(added)
		sort.Strings(changed)
		return SchemaInventoryEvidence{}, fmt.Errorf(
			"schema inventory mismatch missing=%v added=%v changed=%v", missing, added, changed,
		)
	}
	return SchemaInventoryEvidence{
		Profile:     schemaInventoryProfile,
		Path:        repositoryPath(repositoryRoot, inventoryPath),
		Digest:      inventoryDigest,
		SchemaCount: len(expected),
		Outcome:     "pass",
	}, nil
}

func validInventorySchemaPath(value string) bool {
	if !strings.HasPrefix(value, "contracts/schemas/v1/") ||
		!strings.HasSuffix(value, ".schema.json") ||
		strings.Contains(value, "\\") || filepath.IsAbs(value) {
		return false
	}
	return filepath.ToSlash(filepath.Clean(filepath.FromSlash(value))) == value
}

func exactSHA256(value string) bool {
	if len(value) != 71 || !strings.HasPrefix(value, "sha256:") {
		return false
	}
	for _, character := range value[len("sha256:"):] {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') {
			return false
		}
	}
	return true
}

type fixture struct {
	path                  string
	absolutePath          string
	schemaID              string
	valid                 bool
	category              string
	expectedKeywords      []string
	expectedSemanticError string
}

func loadFixtureIndex(repositoryRoot, indexPath string, schemas map[string]*loadedSchema) ([]fixture, error) {
	document, _, err := loadStrictJSON(indexPath)
	if err != nil {
		return nil, fmt.Errorf("read fixture index: %w", err)
	}
	root, ok := document.(map[string]any)
	if !ok {
		return nil, errors.New("fixture index must be an object")
	}
	if unexpected := unknownObjectFields(root, "profile", "fixtures"); len(unexpected) > 0 {
		return nil, fmt.Errorf("fixture index root has unknown fields: %v", unexpected)
	}
	if root["profile"] != "bytedesk.schema-fixtures/1" {
		return nil, errors.New("fixture index has an unknown profile")
	}
	rawFixtures, ok := root["fixtures"].([]any)
	if !ok || len(rawFixtures) == 0 {
		return nil, errors.New("fixture index must contain a non-empty fixtures array")
	}
	contractsRoot := filepath.Join(repositoryRoot, "contracts")
	resolvedRoot, err := filepath.EvalSymlinks(contractsRoot)
	if err != nil {
		return nil, fmt.Errorf("resolve contracts root: %w", err)
	}
	seen := make(map[string]struct{}, len(rawFixtures))
	positiveSchemas := make(map[string]struct{}, len(schemas))
	denialSchemas := make(map[string]struct{}, len(schemas))
	result := make([]fixture, 0, len(rawFixtures))
	for index, raw := range rawFixtures {
		item, ok := raw.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("fixture index entry %d is not an object", index)
		}
		if unexpected := unknownObjectFields(
			item, "path", "schemaId", "valid", "category", "expectedKeyword", "expectedSemanticError",
		); len(unexpected) > 0 {
			return nil, fmt.Errorf("fixture index entry %d has unknown fields: %v", index, unexpected)
		}
		path, pathOK := item["path"].(string)
		schemaID, schemaOK := item["schemaId"].(string)
		valid, validOK := item["valid"].(bool)
		category, categoryOK := item["category"].(string)
		if !pathOK || path == "" || !schemaOK || schemaID == "" || !validOK || !categoryOK {
			return nil, fmt.Errorf("fixture index entry %d lacks path/schemaId/valid", index)
		}
		if !validFixtureCategory(category) {
			return nil, fmt.Errorf("fixture index entry %d has invalid category %q", index, category)
		}
		if valid != (category == "positive" || category == "boundary") {
			return nil, fmt.Errorf("fixture index entry %d category %q does not match valid=%t", index, category, valid)
		}
		if _, duplicate := seen[path]; duplicate {
			return nil, fmt.Errorf("duplicate fixture path in index: %s", path)
		}
		seen[path] = struct{}{}
		if _, exists := schemas[schemaID]; !exists {
			return nil, fmt.Errorf("fixture references unknown schema: %s", schemaID)
		}
		absolutePath := filepath.Join(repositoryRoot, filepath.FromSlash(path))
		resolvedPath, err := filepath.EvalSymlinks(absolutePath)
		if err != nil {
			return nil, fmt.Errorf("resolve fixture %s: %w", path, err)
		}
		if !pathWithin(resolvedRoot, resolvedPath) {
			return nil, fmt.Errorf("fixture path escapes contracts root: %s", path)
		}
		expectedRaw, expectedPresent := item["expectedKeyword"]
		if !expectedPresent {
			return nil, fmt.Errorf("fixture %s: expectedKeyword is required", path)
		}
		expected, err := expectedKeywords(expectedRaw)
		if err != nil {
			return nil, fmt.Errorf("fixture %s: %w", path, err)
		}
		expectedSemanticError := ""
		if rawSemanticError, present := item["expectedSemanticError"]; present {
			value, ok := rawSemanticError.(string)
			if !ok || !validFixtureSemanticError(value) {
				return nil, fmt.Errorf(
					"fixture %s: expectedSemanticError must be schema_id_mismatch or schema_digest_mismatch",
					path,
				)
			}
			expectedSemanticError = value
		}
		if valid && len(expected) != 0 {
			return nil, fmt.Errorf("fixture %s: valid fixture expectedKeyword must be an empty array", path)
		}
		if valid && expectedSemanticError != "" {
			return nil, fmt.Errorf("fixture %s: valid fixture cannot declare expectedSemanticError", path)
		}
		if !valid && len(expected) == 0 && expectedSemanticError == "" {
			return nil, fmt.Errorf(
				"fixture %s: denial fixture expectedKeyword must not be empty unless expectedSemanticError is present",
				path,
			)
		}
		if !valid && len(expected) != 0 && expectedSemanticError != "" {
			return nil, fmt.Errorf(
				"fixture %s: denial fixture must declare exactly one of expectedKeyword or expectedSemanticError",
				path,
			)
		}
		if valid && category == "positive" {
			positiveSchemas[schemaID] = struct{}{}
		}
		if !valid {
			denialSchemas[schemaID] = struct{}{}
		}
		result = append(result, fixture{
			path: path, absolutePath: resolvedPath, schemaID: schemaID,
			valid: valid, category: category, expectedKeywords: expected,
			expectedSemanticError: expectedSemanticError,
		})
	}
	missingPositive := make([]string, 0)
	for schemaID := range schemas {
		if _, covered := positiveSchemas[schemaID]; !covered {
			missingPositive = append(missingPositive, schemaID)
		}
	}
	if len(missingPositive) > 0 {
		sort.Strings(missingPositive)
		return nil, fmt.Errorf("schemas lack indexed valid positive fixtures: %v", missingPositive)
	}
	missingDenial := make([]string, 0)
	for schemaID := range schemas {
		if schemaID == commonSchemaID {
			continue
		}
		if _, covered := denialSchemas[schemaID]; !covered {
			missingDenial = append(missingDenial, schemaID)
		}
	}
	if len(missingDenial) > 0 {
		sort.Strings(missingDenial)
		return nil, fmt.Errorf("schemas lack indexed denial fixtures: %v", missingDenial)
	}
	return result, nil
}

func validateResourceBounds(schemas map[string]*loadedSchema) (ResourceBoundsEvidence, error) {
	evidence := ResourceBoundsEvidence{
		Profile:                 "bytedesk.schema-resource-bounds/1",
		MaximumArrayItems:       maxContractArrayItems,
		MaximumStringLength:     maxContractStringLength,
		MaximumObjectProperties: maxContractProperties,
		Outcome:                 "pass",
	}
	ids := make([]string, 0, len(schemas))
	for id := range schemas {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		if err := walkResourceBounds(id, schemas[id].document, "", &evidence); err != nil {
			return ResourceBoundsEvidence{}, err
		}
	}
	return evidence, nil
}

func walkResourceBounds(schemaID string, value any, pointer string, evidence *ResourceBoundsEvidence) error {
	switch typed := value.(type) {
	case map[string]any:
		if directType, ok := typed["type"].(string); ok {
			switch directType {
			case "array":
				evidence.DirectArraySchemaCount++
				maximum, ok := schemaInteger(typed["maxItems"])
				if !ok || maximum < 0 || maximum > maxContractArrayItems {
					return resourceBoundError(schemaID, pointer, "array maxItems must be an integer in 0..100000")
				}
			case "string":
				evidence.DirectStringSchemaCount++
				if _, hasConst := typed["const"]; hasConst {
					break
				}
				if enum, ok := typed["enum"].([]any); ok && len(enum) > 0 {
					break
				}
				maximum, ok := schemaInteger(typed["maxLength"])
				if !ok || maximum < 0 || maximum > maxContractStringLength {
					return resourceBoundError(schemaID, pointer, "string maxLength must be an integer in 0..4194304 unless const or enum bounds the value")
				}
			case "integer":
				evidence.DirectIntegerSchemaCount++
				if _, hasConst := typed["const"]; hasConst {
					break
				}
				if enum, ok := typed["enum"].([]any); ok && len(enum) > 0 {
					break
				}
				minimum, minOK := schemaInteger(typed["minimum"])
				maximum, maxOK := schemaInteger(typed["maximum"])
				if !minOK || !maxOK || minimum < minSafeInteger || maximum > maxSafeInteger || minimum > maximum {
					return resourceBoundError(schemaID, pointer, "integer minimum and maximum must be exact safe integers in interoperable order")
				}
			case "object":
				evidence.DirectObjectSchemaCount++
				if maximum, ok := schemaInteger(typed["maxProperties"]); ok {
					if maximum < 0 || maximum > maxContractProperties {
						return resourceBoundError(schemaID, pointer, "object maxProperties must be an integer in 0..100000")
					}
					break
				}
				_, fixedProperties := typed["properties"].(map[string]any)
				closed := typed["additionalProperties"] == false || typed["unevaluatedProperties"] == false
				_, patternMap := typed["patternProperties"].(map[string]any)
				additionalMap := schemaValuedKeyword(typed["additionalProperties"])
				unevaluatedMap := schemaValuedKeyword(typed["unevaluatedProperties"])
				if !fixedProperties || !closed || patternMap || additionalMap || unevaluatedMap {
					return resourceBoundError(schemaID, pointer, "object must be a closed fixed property set or declare maxProperties")
				}
			}
		}
		keys := make([]string, 0, len(typed))
		for key := range typed {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			if err := walkResourceBounds(schemaID, typed[key], pointer+"/"+escapeJSONPointerToken(key), evidence); err != nil {
				return err
			}
		}
	case []any:
		for index, child := range typed {
			if err := walkResourceBounds(schemaID, child, fmt.Sprintf("%s/%d", pointer, index), evidence); err != nil {
				return err
			}
		}
	}
	return nil
}

func schemaInteger(value any) (int64, bool) {
	number, ok := value.(json.Number)
	if !ok {
		return 0, false
	}
	parsed, err := number.Int64()
	return parsed, err == nil
}

func schemaValuedKeyword(value any) bool {
	_, object := value.(map[string]any)
	_, boolean := value.(bool)
	return object || (value != nil && !boolean)
}

func escapeJSONPointerToken(value string) string {
	return strings.ReplaceAll(strings.ReplaceAll(value, "~", "~0"), "/", "~1")
}

func resourceBoundError(schemaID, pointer, detail string) error {
	if pointer == "" {
		pointer = "/"
	}
	return fmt.Errorf("schema resource bound violation: %s#%s: %s", schemaID, pointer, detail)
}

func denialCoverageExemptions(schemas map[string]*loadedSchema) ([]SchemaCoverageExemption, error) {
	common, exists := schemas[commonSchemaID]
	if !exists {
		return []SchemaCoverageExemption{}, nil
	}
	root, ok := common.document.(map[string]any)
	if !ok {
		return nil, errors.New("common denial-coverage exemption is not an object")
	}
	allowed := map[string]struct{}{"$schema": {}, "$id": {}, "title": {}, "$defs": {}}
	if unexpected := unknownObjectFields(root, "$schema", "$id", "title", "$defs"); len(unexpected) > 0 {
		return nil, fmt.Errorf(
			"common denial-coverage exemption gained instance-contract fields: %v", unexpected,
		)
	}
	definitions, ok := root["$defs"].(map[string]any)
	if !ok || len(definitions) == 0 || len(root) != len(allowed) {
		return nil, errors.New("common denial-coverage exemption must remain a definitions-library root")
	}
	return []SchemaCoverageExemption{{
		ID: commonSchemaID, Reason: "definitions-library-no-instance-contract",
	}}, nil
}

func expectedKeywords(raw any) ([]string, error) {
	switch typed := raw.(type) {
	case string:
		if typed == "" {
			return nil, errors.New("expectedKeyword cannot be empty")
		}
		return []string{typed}, nil
	case []any:
		result := make([]string, 0, len(typed))
		seen := make(map[string]struct{}, len(typed))
		for _, item := range typed {
			keyword, ok := item.(string)
			if !ok || keyword == "" {
				return nil, errors.New("expectedKeyword array must contain non-empty strings")
			}
			if _, duplicate := seen[keyword]; duplicate {
				return nil, errors.New("expectedKeyword array must contain unique strings")
			}
			seen[keyword] = struct{}{}
			result = append(result, keyword)
		}
		return result, nil
	default:
		return nil, errors.New("expectedKeyword must be a non-empty string or a unique string array")
	}
}

func validFixtureCategory(value string) bool {
	switch value {
	case "positive", "boundary", "negative", "malicious":
		return true
	default:
		return false
	}
}

func validFixtureSemanticError(value string) bool {
	switch value {
	case "schema_id_mismatch", "schema_digest_mismatch":
		return true
	default:
		return false
	}
}

// fixtureSchemaDescriptorError independently binds an instance's optional
// root schema descriptor to the exact schema selected by the fixture index.
// Descriptor shape remains the selected JSON Schema's responsibility; this
// cross-field rule prevents a well-formed descriptor from naming different
// schema authority.
func fixtureSchemaDescriptorError(instance any, expectedID, expectedDigest string) string {
	root, ok := instance.(map[string]any)
	if !ok {
		return ""
	}
	rawDescriptor, present := root["schema"]
	if !present {
		return ""
	}
	descriptor, ok := rawDescriptor.(map[string]any)
	if !ok {
		return "schema_id_mismatch"
	}
	id, ok := descriptor["id"].(string)
	if !ok || id != expectedID {
		return "schema_id_mismatch"
	}
	digest, ok := descriptor["digest"].(string)
	if !ok || digest != expectedDigest {
		return "schema_digest_mismatch"
	}
	return ""
}

func unknownObjectFields(object map[string]any, allowed ...string) []string {
	accepted := make(map[string]struct{}, len(allowed))
	for _, field := range allowed {
		accepted[field] = struct{}{}
	}
	unexpected := make([]string, 0)
	for field := range object {
		if _, ok := accepted[field]; !ok {
			unexpected = append(unexpected, field)
		}
	}
	sort.Strings(unexpected)
	return unexpected
}

func validateReferenceClosure(schemaID string, document any, schemas map[string]*loadedSchema) error {
	var walk func(any) error
	walk = func(value any) error {
		switch typed := value.(type) {
		case map[string]any:
			for key, child := range typed {
				if (key == "$ref" || key == "$dynamicRef") && child != nil {
					reference, ok := child.(string)
					if !ok {
						return fmt.Errorf("schema %s has non-string %s", schemaID, key)
					}
					if strings.HasPrefix(reference, "#") {
						continue
					}
					parsed, err := url.Parse(reference)
					if err != nil || !parsed.IsAbs() {
						return fmt.Errorf("schema %s has relative or invalid reference %q", schemaID, reference)
					}
					parsed.Fragment = ""
					if _, exists := schemas[parsed.String()]; !exists {
						return fmt.Errorf("schema %s has unresolved offline reference %q", schemaID, reference)
					}
					continue
				}
				if err := walk(child); err != nil {
					return err
				}
			}
		case []any:
			for _, child := range typed {
				if err := walk(child); err != nil {
					return err
				}
			}
		}
		return nil
	}
	return walk(document)
}

func loadStrictJSON(path string) (any, string, error) {
	payload, err := os.ReadFile(path)
	if err != nil {
		return nil, "", err
	}
	result, err := canonical.CanonicalizeBytes(payload, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		return nil, "", err
	}
	decoder := json.NewDecoder(bytes.NewReader(result.Bytes))
	decoder.UseNumber()
	var document any
	if err := decoder.Decode(&document); err != nil {
		return nil, "", err
	}
	return document, result.Digest, nil
}

func stableSchemaID(value string) bool {
	parsed, err := url.Parse(value)
	return err == nil && strings.HasPrefix(value, schemaIDPrefix) && parsed.IsAbs() && parsed.RawQuery == "" && parsed.Fragment == ""
}

type offlineLoader struct{}

func (offlineLoader) Load(value string) (any, error) {
	return nil, fmt.Errorf("offline resource unavailable: %s", value)
}

func validationKeywords(err error) []string {
	var root *jsonschema.ValidationError
	if !errors.As(err, &root) {
		return []string{}
	}
	set := map[string]struct{}{}
	var walk func(*jsonschema.ValidationError)
	walk = func(item *jsonschema.ValidationError) {
		if item.ErrorKind != nil {
			path := item.ErrorKind.KeywordPath()
			if len(path) > 0 {
				set[path[len(path)-1]] = struct{}{}
			}
			switch item.ErrorKind.(type) {
			case *kind.Not:
				// santhosh-tekuri deliberately gives `not` an empty
				// KeywordPath, so normalize the typed error explicitly.
				set["not"] = struct{}{}
			case *kind.FalseSchema:
				// A false unevaluatedProperties/unevaluatedItems schema is
				// reported only as FalseSchema. Its absolute schema location
				// carries the engine-independent keyword.
				if keyword := falseSchemaKeyword(item.SchemaURL); keyword != "" {
					set[keyword] = struct{}{}
				}
			}
		}
		for _, cause := range item.Causes {
			walk(cause)
		}
	}
	walk(root)
	if _, additional := set["additionalProperties"]; additional {
		// santhosh-tekuri collapses schemas that declare both closure
		// keywords to additionalProperties. Expose the shared, intentional
		// unknown-field denial keyword used by cross-engine fixtures too.
		set["unevaluatedProperties"] = struct{}{}
	}
	result := make([]string, 0, len(set))
	for keyword := range set {
		result = append(result, keyword)
	}
	sort.Strings(result)
	return result
}

func falseSchemaKeyword(schemaURL string) string {
	parsed, err := url.Parse(schemaURL)
	if err != nil || parsed.Fragment == "" {
		return ""
	}
	parts := strings.Split(parsed.Fragment, "/")
	token := parts[len(parts)-1]
	token = strings.ReplaceAll(strings.ReplaceAll(token, "~1", "/"), "~0", "~")
	switch token {
	case "additionalProperties", "additionalItems", "unevaluatedProperties", "unevaluatedItems":
		return token
	default:
		return ""
	}
}

func missingKeywords(required, observed []string) []string {
	available := make(map[string]struct{}, len(observed))
	for _, keyword := range observed {
		available[keyword] = struct{}{}
	}
	missing := make([]string, 0)
	for _, keyword := range required {
		if _, ok := available[keyword]; !ok {
			missing = append(missing, keyword)
		}
	}
	sort.Strings(missing)
	return missing
}

func repositoryPath(root, path string) string {
	relative, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(relative)
}

func pathWithin(root, candidate string) bool {
	relative, err := filepath.Rel(root, candidate)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator)) && !filepath.IsAbs(relative)
}
