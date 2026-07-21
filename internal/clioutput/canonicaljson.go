package clioutput

import (
	"encoding/json"
	"fmt"
	"io"

	"github.com/gowebpki/jcs"
)

// WriteCanonicalJSON implements required-work item 2's machine-JSON rule for
// authoritative/digest-bearing objects: "Machine JSON for authoritative/
// digest-bearing objects emits RFC 8785 JCS bytes; human presentation
// formatting is never used for digest or signature verification." It
// marshals value with the standard library, then canonicalizes those bytes
// with the same RFC 8785 JCS transform every digest in this repository is
// computed over (github.com/gowebpki/jcs, already used by
// internal/desiredstate and internal/privatecompile), and writes exactly
// those canonical bytes followed by a single newline - never a
// human-readable indented re-serialization.
func WriteCanonicalJSON(w io.Writer, value any) error {
	raw, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("clioutput: marshal value: %w", err)
	}
	canonical, err := jcs.Transform(raw)
	if err != nil {
		return fmt.Errorf("clioutput: canonicalize value: %w", err)
	}
	if _, err := w.Write(canonical); err != nil {
		return err
	}
	_, err = w.Write([]byte("\n"))
	return err
}
