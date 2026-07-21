// Package clioutput implements the real, testable core of AD-15 available
// without a wired control-plane API or OCI registry client: the stable
// bd-agent CLI exit-code specification (required-work item 6) and the RFC
// 8785 JCS canonical JSON output rule for authoritative/digest-bearing
// results (required-work item 2).
//
// This is a slice of AD-15, not the full task. It does not implement any
// of the command tree's real subcommands wired to AD-10's control-plane
// API, AD-13's private compiler, or AD-14's host reconciler, consumer
// authentication profiles, or shell completion - those need a running
// Agent Delivery service and a real consumer adapter this environment does
// not have, per docs/planning/infra-defaults.md. What is real here is the
// foundation every future command must share: one CLI process, its
// arguments, its exit code, and its canonical JSON output are governed by
// this package, not reinvented per command.
package clioutput

// ExitCode is the closed, stable set of bd-agent process exit codes.
// Required-work item 6: "Return stable exit codes for validation,
// compatibility, trust, authorization decision, conflict, unavailable
// dependency, and rollout failure." These values are part of the CLI's
// public contract - never renumber an existing code, only add new ones.
type ExitCode int

const (
	ExitSuccess               ExitCode = 0
	ExitUsageError            ExitCode = 2
	ExitValidationFailure     ExitCode = 3
	ExitCompatibilityFailure  ExitCode = 4
	ExitTrustFailure          ExitCode = 5
	ExitAuthorizationDenied   ExitCode = 6
	ExitConflict              ExitCode = 7
	ExitDependencyUnavailable ExitCode = 8
	ExitRolloutFailure        ExitCode = 9
)
