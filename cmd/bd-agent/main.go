// Command bd-agent is the AD-15 marketplace and deployment CLI. This build
// implements the "contract digest" command as the first real command on
// the stable exit-code and canonical-JSON-output foundation
// (internal/clioutput) every future command shares. The full command tree
// (catalog, package, render, artifact, install, binding, update,
// deployment, receipt) needs a wired control-plane API client, OCI
// registry client, and consumer authentication profile this environment
// does not have.
package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/clioutput"
	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

func main() {
	os.Exit(int(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr)))
}

type digestResult struct {
	Profile string `json:"profile"`
	Digest  string `json:"digest"`
}

func run(arguments []string, stdin io.Reader, stdout, stderr io.Writer) clioutput.ExitCode {
	if len(arguments) < 2 || arguments[0] != "contract" || arguments[1] != "digest" {
		writeUsage(stderr)
		return clioutput.ExitUsageError
	}

	flags := flag.NewFlagSet("contract digest", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	formatName := flags.String("format", "", "required input format: json or yaml")
	jsonOutput := flags.Bool("json", false, "emit canonical JSON result instead of a bare digest")
	if err := flags.Parse(arguments[2:]); err != nil {
		fmt.Fprintln(stderr, "invalid_arguments")
		return clioutput.ExitUsageError
	}
	if *formatName == "" {
		fmt.Fprintln(stderr, "--format is required (json or yaml)")
		return clioutput.ExitUsageError
	}
	format, ok := parseFormat(*formatName)
	if !ok {
		fmt.Fprintln(stderr, "unsupported_format")
		return clioutput.ExitUsageError
	}
	if flags.NArg() != 1 {
		fmt.Fprintln(stderr, "exactly one input path or - is required")
		return clioutput.ExitUsageError
	}

	reader := stdin
	var file *os.File
	if path := flags.Arg(0); path != "-" {
		var err error
		file, err = os.Open(path)
		if err != nil {
			fmt.Fprintln(stderr, "input_open_failed")
			return clioutput.ExitDependencyUnavailable
		}
		defer file.Close()
		reader = file
	}

	result, err := canonical.Canonicalize(reader, format, canonical.DefaultLimits())
	if err != nil {
		code := canonical.CodeOf(err)
		if code == "" {
			code = "canonicalization_failed"
		}
		fmt.Fprintln(stderr, code)
		return clioutput.ExitValidationFailure
	}

	if !*jsonOutput {
		fmt.Fprintln(stdout, result.Digest)
		return clioutput.ExitSuccess
	}

	if err := clioutput.WriteCanonicalJSON(stdout, digestResult{
		Profile: "bd-agent.contract-digest-result/1",
		Digest:  result.Digest,
	}); err != nil {
		fmt.Fprintln(stderr, "output_write_failed")
		return clioutput.ExitDependencyUnavailable
	}
	return clioutput.ExitSuccess
}

func parseFormat(name string) (canonical.Format, bool) {
	switch name {
	case "json":
		return canonical.FormatJSON, true
	case "yaml":
		return canonical.FormatYAML, true
	default:
		return "", false
	}
}

func writeUsage(output io.Writer) {
	fmt.Fprintln(output, "usage: bd-agent contract digest --format <json|yaml> [--json] <path|->")
}
