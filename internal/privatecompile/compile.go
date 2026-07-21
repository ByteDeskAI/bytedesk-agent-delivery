package privatecompile

import (
	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/operations"
)

// CustomizationRequest is the exact private customization input AD-13
// required-work item 4 applies atomically: the functional JSON Patch over
// the effective Agent Spec, plus the declared file and skill operations.
// The functional target is always operations.TargetAgentSpec here - the
// renderer-functional-config document follows the identical profile but is
// a distinct compile-time input this slice does not wire up.
type CustomizationRequest struct {
	BaseAgentSpec map[string]any
	Patch         operations.JSONPatch
	InitialFiles  map[string]operations.FileRecord
	FileOps       operations.FileOperationSet
	InitialSkills map[string]operations.SkillRecord
	SkillOps      operations.SkillOperationSet
}

// CustomizationResult is the effective Agent Spec, file set, and skill set
// produced by an accepted CustomizationRequest.
type CustomizationResult struct {
	EffectiveAgentSpec any
	Files              map[string]operations.FileRecord
	Skills             map[string]operations.SkillRecord
}

// ApplyCustomization implements AD-13 required-work items 3 (partial) and 4:
// it first rejects any functional patch operation carrying a raw-secret-
// shaped value, then atomically applies the functional patch, file
// operations, and skill operations - reusing operations.ApplyJSONPatch,
// operations.ApplyFileOperations, and operations.ApplySkillOperations
// exactly as AD-04 already built and proved them. Nothing is applied
// partially: the first failing step returns an error and CustomizationResult
// is the zero value.
//
// This does not implement the full required-work item 3 boundary (identity/
// grant/credential/trust-root/mandatory-sandbox-weakening rejection beyond
// raw secret values) because agent-spec and renderer-functional-config
// documents structurally never carry an authority plane
// (functional-customization-profile.schema.json's authorityPlanePresent:
// false already guarantees this at the schema level), and no
// mandatory-sandbox-control schema exists yet in this repository to check
// weakening against - that needs AD-14's runtime/harness contracts.
func ApplyCustomization(req CustomizationRequest) (CustomizationResult, error) {
	if err := ScanPatchForRawSecrets(req.Patch); err != nil {
		return CustomizationResult{}, err
	}

	effective, err := operations.ApplyJSONPatch(req.BaseAgentSpec, req.Patch, operations.TargetAgentSpec)
	if err != nil {
		return CustomizationResult{}, err
	}

	files, err := operations.ApplyFileOperations(req.InitialFiles, req.FileOps)
	if err != nil {
		return CustomizationResult{}, err
	}

	skills, err := operations.ApplySkillOperations(req.InitialSkills, req.SkillOps)
	if err != nil {
		return CustomizationResult{}, err
	}

	return CustomizationResult{EffectiveAgentSpec: effective, Files: files, Skills: skills}, nil
}
