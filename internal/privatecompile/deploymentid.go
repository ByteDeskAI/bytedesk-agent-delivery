// Package privatecompile implements the real, testable core of AD-13
// available without a running KMS, private OCI registry, or consumer-
// authority verifier: the deterministic consumer-deployment identity digest,
// a raw-secret guard over private customization patches, and the atomic
// customization apply that reuses AD-04's internal/operations package.
//
// This is a slice of AD-13, not the full task. It does not implement the
// private-compilation-input lock, consumer-authority-snapshot verification,
// skill-approval freshness, consumer-isolated KMS signing, private registry
// publication, or the private-compilation-evidence/runtime-release graph -
// those need a real running consumer-authority verifier, per-consumer KMS
// keys, and a private OCI registry this environment does not have, per
// docs/planning/infra-defaults.md.
package privatecompile

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"

	"github.com/gowebpki/jcs"
)

// DeploymentIDInputs are the exact fields AD-13's normative
// bytedesk.consumer-deployment-id/1 preimage binds.
type DeploymentIDInputs struct {
	ConsumerID             string `json:"consumerId"`
	SubjectID              string `json:"subjectId"`
	TargetID               string `json:"targetId"`
	CandidateDigest        string `json:"candidateDigest"`
	DesiredRevisionDigest  string `json:"desiredRevisionDigest"`
	CompilationInputDigest string `json:"compilationInputDigest"`
}

// ComputeDeploymentID implements the exact deterministic
// D.deploymentId rule from AD-13's task doc: "deployment-" plus the
// lowercase hexadecimal SHA-256 of the RFC 8785 JCS bytes of
// {"profile":"bytedesk.consumer-deployment-id/1","consumerId":...,
// "subjectId":...,"targetId":...,"candidateDigest":...,
// "desiredRevisionDigest":...,"compilationInputDigest":...}.
// It is a pure function of its inputs, never a wall-clock or random value,
// so an idempotent replay of the same lock always yields the same
// deploymentId.
func ComputeDeploymentID(in DeploymentIDInputs) (string, error) {
	preimage := struct {
		Profile                string `json:"profile"`
		ConsumerID             string `json:"consumerId"`
		SubjectID              string `json:"subjectId"`
		TargetID               string `json:"targetId"`
		CandidateDigest        string `json:"candidateDigest"`
		DesiredRevisionDigest  string `json:"desiredRevisionDigest"`
		CompilationInputDigest string `json:"compilationInputDigest"`
	}{
		Profile:                "bytedesk.consumer-deployment-id/1",
		ConsumerID:             in.ConsumerID,
		SubjectID:              in.SubjectID,
		TargetID:               in.TargetID,
		CandidateDigest:        in.CandidateDigest,
		DesiredRevisionDigest:  in.DesiredRevisionDigest,
		CompilationInputDigest: in.CompilationInputDigest,
	}
	raw, err := json.Marshal(preimage)
	if err != nil {
		return "", fmt.Errorf("privatecompile: marshal deployment id preimage: %w", err)
	}
	canonical, err := jcs.Transform(raw)
	if err != nil {
		return "", fmt.Errorf("privatecompile: canonicalize deployment id preimage: %w", err)
	}
	sum := sha256.Sum256(canonical)
	return "deployment-" + hex.EncodeToString(sum[:]), nil
}
