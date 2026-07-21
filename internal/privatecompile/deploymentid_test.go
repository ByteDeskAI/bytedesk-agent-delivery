package privatecompile

import "testing"

func sampleInputs() DeploymentIDInputs {
	return DeploymentIDInputs{
		ConsumerID:             "consumer-1",
		SubjectID:              "subject-1",
		TargetID:               "target-1",
		CandidateDigest:        "sha256:" + repeatHex('a'),
		DesiredRevisionDigest:  "sha256:" + repeatHex('b'),
		CompilationInputDigest: "sha256:" + repeatHex('c'),
	}
}

func repeatHex(c byte) string {
	b := make([]byte, 64)
	for i := range b {
		b[i] = c
	}
	return string(b)
}

func TestComputeDeploymentIDIsDeterministic(t *testing.T) {
	first, err := ComputeDeploymentID(sampleInputs())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	second, err := ComputeDeploymentID(sampleInputs())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if first != second {
		t.Fatalf("expected identical inputs to produce identical ids, got %q vs %q", first, second)
	}
	if len(first) != len("deployment-")+64 {
		t.Fatalf("expected deployment- prefix plus 64 hex chars, got %q", first)
	}
}

func TestComputeDeploymentIDChangesWithAnyField(t *testing.T) {
	base, err := ComputeDeploymentID(sampleInputs())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	mutators := []func(*DeploymentIDInputs){
		func(in *DeploymentIDInputs) { in.ConsumerID = "consumer-2" },
		func(in *DeploymentIDInputs) { in.SubjectID = "subject-2" },
		func(in *DeploymentIDInputs) { in.TargetID = "target-2" },
		func(in *DeploymentIDInputs) { in.CandidateDigest = "sha256:" + repeatHex('d') },
		func(in *DeploymentIDInputs) { in.DesiredRevisionDigest = "sha256:" + repeatHex('e') },
		func(in *DeploymentIDInputs) { in.CompilationInputDigest = "sha256:" + repeatHex('f') },
	}
	for i, mutate := range mutators {
		in := sampleInputs()
		mutate(&in)
		id, err := ComputeDeploymentID(in)
		if err != nil {
			t.Fatalf("mutator %d: unexpected error: %v", i, err)
		}
		if id == base {
			t.Fatalf("mutator %d: expected a changed field to change the deployment id", i)
		}
	}
}
