package clioutput

import (
	"bytes"
	"testing"
)

func TestWriteCanonicalJSONProducesJCSOrderedBytes(t *testing.T) {
	value := map[string]any{"b": 1, "a": 2}
	var buf bytes.Buffer
	if err := WriteCanonicalJSON(&buf, value); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// RFC 8785 JCS sorts object keys lexicographically, regardless of Go map
	// iteration order or struct field order.
	if got, want := buf.String(), `{"a":2,"b":1}`+"\n"; got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}

func TestWriteCanonicalJSONIsDeterministicAcrossCalls(t *testing.T) {
	value := struct {
		Z string `json:"z"`
		A string `json:"a"`
	}{Z: "last", A: "first"}

	var first, second bytes.Buffer
	if err := WriteCanonicalJSON(&first, value); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if err := WriteCanonicalJSON(&second, value); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if first.String() != second.String() {
		t.Fatalf("expected identical output across calls, got %q vs %q", first.String(), second.String())
	}
}
