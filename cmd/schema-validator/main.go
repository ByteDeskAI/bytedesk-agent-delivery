package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	contractschema "github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/schema"
)

func main() {
	repository := flag.String("repository", ".", "repository root")
	index := flag.String("index", "contracts/fixtures/schema/index.json", "schema fixture index")
	evidence := flag.String("evidence", "", "optional evidence JSON output")
	flag.Parse()

	indexPath := *index
	if !filepath.IsAbs(indexPath) {
		indexPath = filepath.Join(*repository, indexPath)
	}
	report, err := contractschema.ValidateRepository(*repository, indexPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "contract validation failed: %v\n", err)
		os.Exit(1)
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "encode validation evidence: %v\n", err)
		os.Exit(1)
	}
	payload = append(payload, '\n')
	if *evidence != "" {
		if err := writeAtomic(*evidence, payload); err != nil {
			fmt.Fprintf(os.Stderr, "write validation evidence: %v\n", err)
			os.Exit(1)
		}
	}
	if _, err := os.Stdout.Write(payload); err != nil {
		fmt.Fprintf(os.Stderr, "write validation evidence: %v\n", err)
		os.Exit(1)
	}
}

func writeAtomic(path string, payload []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".schema-evidence-*.tmp")
	if err != nil {
		return err
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)
	if err := temporary.Chmod(0o644); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.Write(payload); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(temporaryPath, path)
}
