package privatecompile

import (
	"errors"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/operations"
)

func TestApplyCustomizationAppliesFunctionalPatch(t *testing.T) {
	req := CustomizationRequest{
		BaseAgentSpec: map[string]any{
			"component_type": "Agent",
			"name":           "assistant",
		},
		Patch: operations.JSONPatch{
			Profile: "bytedesk.json-patch/1",
			Operations: []operations.PatchOperation{
				{Op: "replace", Path: "/name", Value: []byte(`"customized-assistant"`)},
			},
		},
		InitialFiles:  map[string]operations.FileRecord{},
		FileOps:       operations.FileOperationSet{Contract: "bytedesk.file-operations/1"},
		InitialSkills: map[string]operations.SkillRecord{},
		SkillOps:      operations.SkillOperationSet{Contract: "bytedesk.skill-operations/1"},
	}

	result, err := ApplyCustomization(req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	spec, ok := result.EffectiveAgentSpec.(map[string]any)
	if !ok {
		t.Fatalf("expected a map result, got %T", result.EffectiveAgentSpec)
	}
	if spec["name"] != "customized-assistant" {
		t.Fatalf("expected patched name, got %v", spec["name"])
	}
}

func TestApplyCustomizationRejectsRawSecretBeforeApplying(t *testing.T) {
	req := CustomizationRequest{
		BaseAgentSpec: map[string]any{
			"component_type": "Agent",
			"name":           "assistant",
		},
		Patch: operations.JSONPatch{
			Profile: "bytedesk.json-patch/1",
			Operations: []operations.PatchOperation{
				{Op: "replace", Path: "/name", Value: []byte(`"AKIAABCDEFGHIJKLMNOP"`)},
			},
		},
		InitialFiles:  map[string]operations.FileRecord{},
		FileOps:       operations.FileOperationSet{Contract: "bytedesk.file-operations/1"},
		InitialSkills: map[string]operations.SkillRecord{},
		SkillOps:      operations.SkillOperationSet{Contract: "bytedesk.skill-operations/1"},
	}

	_, err := ApplyCustomization(req)
	if !errors.Is(err, ErrRawSecretDetected) {
		t.Fatalf("expected ErrRawSecretDetected, got %v", err)
	}
}

func TestApplyCustomizationRejectsInvalidPatchWithoutPartialApply(t *testing.T) {
	req := CustomizationRequest{
		BaseAgentSpec: map[string]any{
			"component_type": "Agent",
			"name":           "assistant",
		},
		Patch: operations.JSONPatch{
			Profile: "bytedesk.json-patch/1",
			Operations: []operations.PatchOperation{
				{Op: "replace", Path: "/missing/nested", Value: []byte(`"value"`)},
			},
		},
		InitialFiles:  map[string]operations.FileRecord{},
		FileOps:       operations.FileOperationSet{Contract: "bytedesk.file-operations/1"},
		InitialSkills: map[string]operations.SkillRecord{},
		SkillOps:      operations.SkillOperationSet{Contract: "bytedesk.skill-operations/1"},
	}

	result, err := ApplyCustomization(req)
	if err == nil {
		t.Fatal("expected an error for a patch targeting a missing parent")
	}
	if result.EffectiveAgentSpec != nil || result.Files != nil || result.Skills != nil {
		t.Fatalf("expected a zero-value result on failure, got %+v", result)
	}
}
