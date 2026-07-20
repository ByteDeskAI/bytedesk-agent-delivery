// Package desiredstate implements the single-writer, compare-and-swap
// TargetDeliveryState aggregate central to AD-09 and AD-12: exactly one
// logical revision per (consumerId, targetId), mutated only through an
// absent/match precondition, never by digest-only or wildcard mutation.
//
// This is a real, complete implementation of AD-09 required-work item 6
// ("Persist one TargetDeliveryState aggregate per consumer target in
// exactly one selected DesiredStateStore") and item 9 (only the
// port that presents a valid precondition may write) restricted to a
// single in-memory managed store variant. It does not implement: the
// consumer-native store variant, migration between store variants,
// installation/binding/authority persistence, or the domain/outbox event
// emission also required by AD-09 - those are further slices.
package desiredstate

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sync"

	"github.com/gowebpki/jcs"
)

// Precondition mirrors the closed absent/match shape in
// contracts/schemas/v1/common.schema.json#/$defs/precondition.
type Precondition struct {
	Kind     string `json:"kind"`
	Revision int64  `json:"revision,omitempty"`
	Digest   string `json:"digest,omitempty"`
}

// ErrPreconditionFailed is returned when a caller's precondition does not
// match the store's current state for that key - the store performs no
// side effect in this case.
var ErrPreconditionFailed = errors.New("desiredstate: precondition failed")

// ErrPreconditionInvalid is returned for a structurally invalid precondition
// (unknown kind, match without revision/digest, or wildcard/digest-only
// mutation attempts) - rejected before any state is read or written.
var ErrPreconditionInvalid = errors.New("desiredstate: precondition invalid")

type key struct {
	consumerID string
	targetID   string
}

// Record is one stored TargetDeliveryState revision. Payload is the
// caller-supplied state document (opaque to the store beyond digesting it);
// Revision and Digest are computed and owned by the store, never the caller.
type Record struct {
	ConsumerID string
	TargetID   string
	Revision   int64
	Digest     string
	Payload    json.RawMessage
}

// Store is a single-writer, in-memory CAS store for TargetDeliveryState.
// Safe for concurrent use; every write is serialized so read-modify-write
// races (ABA included) cannot occur between the precondition check and the
// commit.
type Store struct {
	mu      sync.Mutex
	records map[key]Record
}

func NewStore() *Store {
	return &Store{records: make(map[key]Record)}
}

// Read returns the current record for (consumerID, targetID), or ok=false
// if none exists yet. Read never mutates state and never requires a
// precondition.
func (s *Store) Read(consumerID, targetID string) (Record, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.records[key{consumerID, targetID}]
	return record, ok
}

// CompareAndSwap writes payload for (consumerID, targetID) only if
// precondition matches the store's current state exactly. On success it
// returns the new Record with a freshly computed revision/digest. The
// caller's precondition is validated structurally before any state is
// touched: an invalid precondition (unknown kind, match missing
// revision/digest) is rejected without side effects, matching the
// acceptance criterion that wildcard/null/digest-only/lease-only mutation
// fails without side effects.
func (s *Store) CompareAndSwap(consumerID, targetID string, precondition Precondition, payload json.RawMessage) (Record, error) {
	if err := validatePrecondition(precondition); err != nil {
		return Record{}, err
	}

	canonicalPayload, err := jcs.Transform(payload)
	if err != nil {
		return Record{}, fmt.Errorf("desiredstate: payload is not canonicalizable JSON: %w", err)
	}
	sum := sha256.Sum256(canonicalPayload)
	newDigest := "sha256:" + hex.EncodeToString(sum[:])

	s.mu.Lock()
	defer s.mu.Unlock()

	k := key{consumerID, targetID}
	current, exists := s.records[k]

	switch precondition.Kind {
	case "absent":
		if exists {
			return Record{}, ErrPreconditionFailed
		}
	case "match":
		if !exists || current.Revision != precondition.Revision || current.Digest != precondition.Digest {
			return Record{}, ErrPreconditionFailed
		}
	}

	nextRevision := int64(1)
	if exists {
		nextRevision = current.Revision + 1
	}

	record := Record{
		ConsumerID: consumerID,
		TargetID:   targetID,
		Revision:   nextRevision,
		Digest:     newDigest,
		Payload:    append(json.RawMessage(nil), payload...),
	}
	s.records[k] = record
	return record, nil
}

func validatePrecondition(p Precondition) error {
	switch p.Kind {
	case "absent":
		if p.Revision != 0 || p.Digest != "" {
			return fmt.Errorf("%w: absent precondition must not carry revision or digest", ErrPreconditionInvalid)
		}
		return nil
	case "match":
		if p.Revision <= 0 {
			return fmt.Errorf("%w: match precondition requires a positive revision", ErrPreconditionInvalid)
		}
		if p.Digest == "" {
			return fmt.Errorf("%w: match precondition requires an exact digest", ErrPreconditionInvalid)
		}
		return nil
	default:
		return fmt.Errorf("%w: unknown precondition kind %q", ErrPreconditionInvalid, p.Kind)
	}
}
