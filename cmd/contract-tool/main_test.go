package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestRunCanonicalize(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"canonicalize", "--format", "json", "-"}, strings.NewReader(`{"b":2,"a":1}`), &stdout, &stderr)
	if exit != 0 {
		t.Fatalf("exit=%d stderr=%q", exit, stderr.String())
	}
	if got, want := stdout.String(), "{\"a\":1,\"b\":2}"; got != want {
		t.Fatalf("stdout=%q want=%q", got, want)
	}
	if stderr.Len() != 0 {
		t.Fatalf("unexpected stderr: %q", stderr.String())
	}
}

func TestRunDigest(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"digest", "--format=yaml", "-"}, strings.NewReader("b: 2\na: 1\n"), &stdout, &stderr)
	if exit != 0 {
		t.Fatalf("exit=%d stderr=%q", exit, stderr.String())
	}
	if got, want := stdout.String(), "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777\n"; got != want {
		t.Fatalf("stdout=%q want=%q", got, want)
	}
}

func TestRunRequiresExplicitFormat(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"canonicalize", "-"}, strings.NewReader(`{}`), &stdout, &stderr)
	if exit != 2 {
		t.Fatalf("exit=%d want=2", exit)
	}
	if !strings.Contains(stderr.String(), "--format") {
		t.Fatalf("stderr does not explain required format: %q", stderr.String())
	}
}

func TestRunReturnsStableValidationCodeWithoutInput(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	secretLikeKey := "never-echo-this-key"
	input := `{"` + secretLikeKey + `":1,"` + secretLikeKey + `":2}`
	exit := run([]string{"canonicalize", "--format=json", "-"}, strings.NewReader(input), &stdout, &stderr)
	if exit != 1 {
		t.Fatalf("exit=%d want=1", exit)
	}
	if got := strings.TrimSpace(stderr.String()); got != "duplicate_key" {
		t.Fatalf("stderr=%q want stable code", got)
	}
	if strings.Contains(stderr.String(), secretLikeKey) {
		t.Fatalf("stderr echoed input: %q", stderr.String())
	}
}

func TestRunDoesNotExposeRaisableContractLimits(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"canonicalize", "--format=json", "--max-depth=65", "-"}, strings.NewReader(`{}`), &stdout, &stderr)
	if exit != 2 {
		t.Fatalf("exit=%d want=2", exit)
	}
	if got := strings.TrimSpace(stderr.String()); got != "invalid_arguments" {
		t.Fatalf("stderr=%q want invalid_arguments", got)
	}
}
