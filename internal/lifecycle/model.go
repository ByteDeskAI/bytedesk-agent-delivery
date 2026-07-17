package lifecycle

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"unicode/utf8"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/contracts/canonical"
)

const transitionSchemaID = "https://schemas.bytedesk.ai/agent-delivery/v1/transition-model/1.0.0"

var (
	contractNamePattern = regexp.MustCompile(`^bytedesk\.[a-z0-9.-]+/[1-9][0-9]*$`)
	identifierPattern   = regexp.MustCompile(`^[A-Za-z0-9](?:[A-Za-z0-9._:-]{0,255})$`)
)

// Model is the executable representation of one versioned lifecycle contract.
// Guards and effects are stable identifiers evaluated by the owning domain;
// this package closes the legal actor/state/transition graph.
type Model struct {
	Schema        string       `json:"$schema"`
	Profile       string       `json:"profile"`
	Version       int          `json:"version"`
	InitialStates []string     `json:"initialStates"`
	States        []State      `json:"states"`
	Transitions   []Transition `json:"transitions"`
}

type State struct {
	Name            string `json:"name"`
	Terminal        bool   `json:"terminal"`
	terminalPresent bool
}

type Transition struct {
	Name             string   `json:"name"`
	From             []string `json:"from"`
	To               string   `json:"to"`
	Actor            string   `json:"actor"`
	Guard            string   `json:"guard"`
	CAS              string   `json:"cas"`
	Effects          []string `json:"effects"`
	Event            string   `json:"event"`
	Retryable        bool     `json:"retryable"`
	retryablePresent bool
}

// UnmarshalJSON preserves presence for required booleans. A plain bool cannot
// distinguish an omitted member from an explicit false, while the authoritative
// schema requires terminal on every state and retryable on every transition.
func (s *State) UnmarshalJSON(data []byte) error {
	var wire struct {
		Name     string `json:"name"`
		Terminal *bool  `json:"terminal"`
	}
	if err := decodeClosedObject(data, &wire); err != nil {
		return err
	}
	s.Name = wire.Name
	if wire.Terminal != nil {
		s.Terminal = *wire.Terminal
		s.terminalPresent = true
	}
	return nil
}

func (t *Transition) UnmarshalJSON(data []byte) error {
	var wire struct {
		Name      string   `json:"name"`
		From      []string `json:"from"`
		To        string   `json:"to"`
		Actor     string   `json:"actor"`
		Guard     string   `json:"guard"`
		CAS       string   `json:"cas"`
		Effects   []string `json:"effects"`
		Event     string   `json:"event"`
		Retryable *bool    `json:"retryable"`
	}
	if err := decodeClosedObject(data, &wire); err != nil {
		return err
	}
	t.Name = wire.Name
	t.From = wire.From
	t.To = wire.To
	t.Actor = wire.Actor
	t.Guard = wire.Guard
	t.CAS = wire.CAS
	t.Effects = wire.Effects
	t.Event = wire.Event
	if wire.Retryable != nil {
		t.Retryable = *wire.Retryable
		t.retryablePresent = true
	}
	return nil
}

func decodeClosedObject(data []byte, target any) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	return requireEOF(decoder)
}

func LoadFile(path string) (*Model, error) {
	input, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer input.Close()
	result, err := canonical.Canonicalize(input, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		return nil, fmt.Errorf("canonicalize lifecycle model: %w", err)
	}
	return parseCanonical(result.Bytes)
}

func Parse(data []byte) (*Model, error) {
	result, err := canonical.CanonicalizeBytes(data, canonical.FormatJSON, canonical.DefaultLimits())
	if err != nil {
		return nil, fmt.Errorf("canonicalize lifecycle model: %w", err)
	}
	return parseCanonical(result.Bytes)
}

func parseCanonical(data []byte) (*Model, error) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var model Model
	if err := decoder.Decode(&model); err != nil {
		return nil, fmt.Errorf("decode lifecycle model: %w", err)
	}
	if err := requireEOF(decoder); err != nil {
		return nil, err
	}
	if err := model.Validate(); err != nil {
		return nil, fmt.Errorf("validate lifecycle model: %w", err)
	}
	return &model, nil
}

func requireEOF(decoder *json.Decoder) error {
	var extra any
	err := decoder.Decode(&extra)
	if errors.Is(err, io.EOF) {
		return nil
	}
	if err == nil {
		return errors.New("decode lifecycle model: trailing JSON value")
	}
	return fmt.Errorf("decode lifecycle model trailer: %w", err)
}

func (m *Model) Validate() error {
	if m == nil {
		return errors.New("nil lifecycle model")
	}
	if m.Schema != transitionSchemaID {
		return fmt.Errorf("unexpected transition schema %q", m.Schema)
	}
	if utf8.RuneCountInString(m.Profile) > 128 || !contractNamePattern.MatchString(m.Profile) {
		return fmt.Errorf("invalid lifecycle profile %q", m.Profile)
	}
	if m.Version != 1 {
		return fmt.Errorf("unsupported lifecycle model version %d", m.Version)
	}
	if len(m.InitialStates) == 0 || len(m.States) == 0 || len(m.Transitions) == 0 {
		return errors.New("lifecycle model requires initial states, states, and transitions")
	}

	states := make(map[string]State, len(m.States))
	for _, state := range m.States {
		if !state.terminalPresent {
			return fmt.Errorf("lifecycle state %q omits required terminal", state.Name)
		}
		if !identifierPattern.MatchString(state.Name) {
			return errors.New("lifecycle state name is invalid")
		}
		if _, exists := states[state.Name]; exists {
			return fmt.Errorf("duplicate lifecycle state %q", state.Name)
		}
		states[state.Name] = state
	}

	initial := map[string]struct{}{}
	for _, name := range m.InitialStates {
		if _, ok := states[name]; !ok {
			return fmt.Errorf("unknown initial state %q", name)
		}
		if _, duplicate := initial[name]; duplicate {
			return fmt.Errorf("duplicate initial state %q", name)
		}
		initial[name] = struct{}{}
	}

	transitionNames := map[string]struct{}{}
	outgoing := map[string]int{}
	adjacency := map[string][]string{}
	for _, transition := range m.Transitions {
		if !transition.retryablePresent {
			return fmt.Errorf("transition %q omits required retryable", transition.Name)
		}
		if !identifierPattern.MatchString(transition.Name) ||
			!identifierPattern.MatchString(transition.To) ||
			!identifierPattern.MatchString(transition.Actor) ||
			!identifierPattern.MatchString(transition.CAS) ||
			transition.Guard == "" || utf8.RuneCountInString(transition.Guard) > 1024 ||
			transition.Event == "" || utf8.RuneCountInString(transition.Event) > 256 {
			return fmt.Errorf("transition has an invalid required field: %+v", transition)
		}
		if _, duplicate := transitionNames[transition.Name]; duplicate {
			return fmt.Errorf("duplicate transition name %q", transition.Name)
		}
		transitionNames[transition.Name] = struct{}{}
		if _, ok := states[transition.To]; !ok {
			return fmt.Errorf("transition %q has unknown target %q", transition.Name, transition.To)
		}
		if len(transition.From) == 0 || len(transition.Effects) == 0 {
			return fmt.Errorf("transition %q requires sources and effects", transition.Name)
		}
		seenFrom := map[string]struct{}{}
		for _, from := range transition.From {
			if !identifierPattern.MatchString(from) {
				return fmt.Errorf("transition %q has invalid source identifier", transition.Name)
			}
			state, ok := states[from]
			if !ok {
				return fmt.Errorf("transition %q has unknown source %q", transition.Name, from)
			}
			if state.Terminal {
				return fmt.Errorf("terminal state %q has outgoing transition %q", from, transition.Name)
			}
			if _, duplicate := seenFrom[from]; duplicate {
				return fmt.Errorf("transition %q repeats source %q", transition.Name, from)
			}
			seenFrom[from] = struct{}{}
			outgoing[from]++
			adjacency[from] = append(adjacency[from], transition.To)
		}
		seenEffects := map[string]struct{}{}
		for _, effect := range transition.Effects {
			if effect == "" || utf8.RuneCountInString(effect) > 512 {
				return fmt.Errorf("transition %q has invalid effect", transition.Name)
			}
			if _, duplicate := seenEffects[effect]; duplicate {
				return fmt.Errorf("transition %q repeats effect", transition.Name)
			}
			seenEffects[effect] = struct{}{}
		}
	}

	for _, state := range m.States {
		if !state.Terminal && outgoing[state.Name] == 0 {
			return fmt.Errorf("nonterminal state %q has no outgoing transition", state.Name)
		}
	}

	reachable := map[string]bool{}
	queue := append([]string(nil), m.InitialStates...)
	for len(queue) > 0 {
		state := queue[0]
		queue = queue[1:]
		if reachable[state] {
			continue
		}
		reachable[state] = true
		queue = append(queue, adjacency[state]...)
	}
	for _, state := range m.States {
		if !reachable[state.Name] {
			return fmt.Errorf("unreachable lifecycle state %q", state.Name)
		}
	}
	return nil
}

// Resolve returns the one declared transition matching the complete tuple.
// The caller must additionally evaluate the returned stable Guard identifier.
func (m *Model) Resolve(from, to, actor, name string) (Transition, bool) {
	if m == nil || m.Validate() != nil {
		return Transition{}, false
	}
	for _, transition := range m.Transitions {
		if transition.Name != name || transition.To != to || transition.Actor != actor {
			continue
		}
		for _, source := range transition.From {
			if source == from {
				return transition, true
			}
		}
	}
	return Transition{}, false
}

func (m *Model) hasDeclaredPair(from, to string) bool {
	for _, transition := range m.Transitions {
		if transition.To != to {
			continue
		}
		for _, source := range transition.From {
			if source == from {
				return true
			}
		}
	}
	return false
}
