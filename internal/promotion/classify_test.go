package promotion

import (
	"encoding/json"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/operations"
)

func baseProposal() UpdateProposal {
	return UpdateProposal{
		Previous: map[string]any{
			"component_type": "Agent",
			"name":           "assistant",
			"other":          "unchanged",
		},
		Proposed: map[string]any{
			"component_type": "Agent",
			"name":           "assistant",
			"other":          "unchanged",
		},
		Patch: operations.JSONPatch{
			Profile: "bytedesk.json-patch/1",
			Operations: []operations.PatchOperation{
				{Op: "replace", Path: "/name", Value: json.RawMessage(`"customized-assistant"`)},
			},
		},
		Target:                  operations.TargetAgentSpec,
		SkillDigestsUnchanged:   true,
		TrustPolicyUnchanged:    true,
		ConsumerPolicyVerdictOK: true,
	}
}

func TestCleanStableSuccessorAutoProgresses(t *testing.T) {
	result := ClassifyUpdate(baseProposal())
	if result.Disposition != DispositionAutoProgress {
		t.Fatalf("expected auto-progress, got %s: %s", result.Disposition, result.Reason)
	}
	if result.RebasedProposed == nil {
		t.Fatal("expected a rebased source on auto-progress")
	}
}

func TestChangedSkillDigestsForcesApproval(t *testing.T) {
	proposal := baseProposal()
	proposal.SkillDigestsUnchanged = false
	result := ClassifyUpdate(proposal)
	if result.Disposition != DispositionApprovalRequired {
		t.Fatalf("expected approval-required, got %s", result.Disposition)
	}
}

func TestChangedTrustPolicyForcesApproval(t *testing.T) {
	proposal := baseProposal()
	proposal.TrustPolicyUnchanged = false
	result := ClassifyUpdate(proposal)
	if result.Disposition != DispositionApprovalRequired {
		t.Fatalf("expected approval-required, got %s", result.Disposition)
	}
}

func TestInvalidConsumerPolicyVerdictForcesApproval(t *testing.T) {
	proposal := baseProposal()
	proposal.ConsumerPolicyVerdictOK = false
	result := ClassifyUpdate(proposal)
	if result.Disposition != DispositionApprovalRequired {
		t.Fatalf("expected approval-required, got %s", result.Disposition)
	}
}

func TestSecurityAuthorityMutationForcesApproval(t *testing.T) {
	proposal := baseProposal()
	proposal.SecurityAuthorityChanged = true
	result := ClassifyUpdate(proposal)
	if result.Disposition != DispositionApprovalRequired {
		t.Fatalf("expected approval-required, got %s", result.Disposition)
	}
	if result.RebasedProposed != nil {
		t.Fatal("approval-required must not carry a rebased source")
	}
}

func TestRawSecretForcesApproval(t *testing.T) {
	proposal := baseProposal()
	proposal.RawSecretPresent = true
	result := ClassifyUpdate(proposal)
	if result.Disposition != DispositionApprovalRequired {
		t.Fatalf("expected approval-required, got %s", result.Disposition)
	}
}

func TestConflictingRebaseForcesApproval(t *testing.T) {
	proposal := baseProposal()
	// Proposed diverges the exact subtree the accepted patch targets, so the
	// three-way rebase must conflict.
	proposal.Proposed = map[string]any{
		"component_type": "Agent",
		"name":           map[string]any{"unexpectedly": "restructured"},
		"other":          "unchanged",
	}
	result := ClassifyUpdate(proposal)
	if result.Disposition != DispositionApprovalRequired {
		t.Fatalf("expected approval-required on rebase conflict, got %s: %s", result.Disposition, result.Reason)
	}
}
