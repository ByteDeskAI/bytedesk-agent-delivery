package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(arguments []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(arguments) == 0 {
		writeUsage(stderr)
		return 2
	}
	command := arguments[0]
	if command != "canonicalize" && command != "digest" {
		writeUsage(stderr)
		return 2
	}

	limits := canonical.DefaultLimits()
	flags := flag.NewFlagSet(command, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	formatName := flags.String("format", "", "required input format: json or yaml")
	if err := flags.Parse(arguments[1:]); err != nil {
		fmt.Fprintln(stderr, "invalid_arguments")
		return 2
	}
	if *formatName == "" {
		fmt.Fprintln(stderr, "--format is required (json or yaml)")
		return 2
	}
	format, ok := parseFormat(*formatName)
	if !ok {
		fmt.Fprintln(stderr, "unsupported_format")
		return 2
	}
	if flags.NArg() != 1 {
		fmt.Fprintln(stderr, "exactly one input path or - is required")
		return 2
	}

	reader := stdin
	var file *os.File
	if path := flags.Arg(0); path != "-" {
		var err error
		file, err = os.Open(path)
		if err != nil {
			fmt.Fprintln(stderr, "input_open_failed")
			return 1
		}
		defer file.Close()
		reader = file
	}

	result, err := canonical.Canonicalize(reader, format, limits)
	if err != nil {
		code := canonical.CodeOf(err)
		if code == "" {
			code = "canonicalization_failed"
		}
		fmt.Fprintln(stderr, code)
		return 1
	}

	if command == "canonicalize" {
		if err := writeAll(stdout, result.Bytes); err != nil {
			return 1
		}
	} else {
		if err := writeAll(stdout, []byte(result.Digest+"\n")); err != nil {
			return 1
		}
	}
	return 0
}

func writeAll(output io.Writer, value []byte) error {
	for len(value) > 0 {
		written, err := output.Write(value)
		if err != nil {
			return err
		}
		if written <= 0 || written > len(value) {
			return io.ErrShortWrite
		}
		value = value[written:]
	}
	return nil
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
	fmt.Fprintln(output, "usage: contract-tool <canonicalize|digest> --format <json|yaml> <path|->")
}
