package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/clioutput"
)

func TestRunContractDigestBareOutput(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"contract", "digest", "--format=yaml", "-"}, strings.NewReader("b: 2\na: 1\n"), &stdout, &stderr)
	if exit != clioutput.ExitSuccess {
		t.Fatalf("exit=%d stderr=%q", exit, stderr.String())
	}
	if got, want := stdout.String(), "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777\n"; got != want {
		t.Fatalf("stdout=%q want=%q", got, want)
	}
}

func TestRunContractDigestJSONOutputIsCanonical(t *testing.T) {
	t.Parallel()

	var bareStdout, jsonStdout, stderr bytes.Buffer
	if exit := run([]string{"contract", "digest", "--format=json", "-"}, strings.NewReader(`{"a":1}`), &bareStdout, &stderr); exit != clioutput.ExitSuccess {
		t.Fatalf("bare exit=%d stderr=%q", exit, stderr.String())
	}
	digest := strings.TrimSuffix(bareStdout.String(), "\n")

	exit := run([]string{"contract", "digest", "--format=json", "--json", "-"}, strings.NewReader(`{"a":1}`), &jsonStdout, &stderr)
	if exit != clioutput.ExitSuccess {
		t.Fatalf("json exit=%d stderr=%q", exit, stderr.String())
	}
	// RFC 8785 JCS orders object keys lexicographically: "digest" before "profile".
	want := `{"digest":"` + digest + `","profile":"bd-agent.contract-digest-result/1"}` + "\n"
	if jsonStdout.String() != want {
		t.Fatalf("stdout=%q want=%q", jsonStdout.String(), want)
	}
}

func TestRunUnknownCommandIsUsageError(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"deploy", "now"}, strings.NewReader(""), &stdout, &stderr)
	if exit != clioutput.ExitUsageError {
		t.Fatalf("exit=%d want=%d", exit, clioutput.ExitUsageError)
	}
	if !strings.Contains(stderr.String(), "usage:") {
		t.Fatalf("expected a usage message, got %q", stderr.String())
	}
}

func TestRunMissingFormatIsUsageError(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exit := run([]string{"contract", "digest", "-"}, strings.NewReader(`{}`), &stdout, &stderr)
	if exit != clioutput.ExitUsageError {
		t.Fatalf("exit=%d want=%d", exit, clioutput.ExitUsageError)
	}
}

func TestRunInvalidInputIsValidationFailure(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	input := `{"dup":1,"dup":2}`
	exit := run([]string{"contract", "digest", "--format=json", "-"}, strings.NewReader(input), &stdout, &stderr)
	if exit != clioutput.ExitValidationFailure {
		t.Fatalf("exit=%d want=%d stderr=%q", exit, clioutput.ExitValidationFailure, stderr.String())
	}
}
