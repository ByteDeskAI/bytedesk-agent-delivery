package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/ByteDeskAI/bytedesk-agent-delivery/internal/desiredstate"
)

func newTestServer() *httptest.Server {
	handler := &DesiredStateHandler{Store: desiredstate.NewStore()}
	return httptest.NewServer(handler)
}

func doRequest(t *testing.T, server *httptest.Server, method, path string, headers map[string]string, body []byte) *http.Response {
	t.Helper()
	req, err := http.NewRequest(method, server.URL+path, bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	for key, value := range headers {
		req.Header.Set(key, value)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	return resp
}

func decodeProblem(t *testing.T, resp *http.Response) problemDetails {
	t.Helper()
	defer resp.Body.Close()
	var problem problemDetails
	if err := json.NewDecoder(resp.Body).Decode(&problem); err != nil {
		t.Fatal(err)
	}
	return problem
}

func TestGetOnMissingTargetReturns404Problem(t *testing.T) {
	server := newTestServer()
	defer server.Close()

	resp := doRequest(t, server, http.MethodGet, "/consumers/c1/targets/t1/desired-state", nil, nil)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}
	problem := decodeProblem(t, resp)
	if problem.Code != "resource_not_found" {
		t.Fatalf("expected resource_not_found, got %q", problem.Code)
	}
}

func TestCreateRequiresIfNoneMatchStar(t *testing.T) {
	server := newTestServer()
	defer server.Close()

	// Missing precondition entirely: invalid_request is fixed to HTTP 400
	// in the registered problem catalog.
	resp := doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", nil, []byte(`{"v":1}`))
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", resp.StatusCode)
	}

	// Correct absent precondition succeeds.
	resp = doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":1}`))
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}
	etag := resp.Header.Get("ETag")
	if etag == "" {
		t.Fatal("expected an ETag header")
	}

	// Repeating creation fails: resource already exists.
	resp = doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":2}`))
	if resp.StatusCode != http.StatusPreconditionFailed {
		t.Fatalf("expected 412 on duplicate creation, got %d", resp.StatusCode)
	}
	problem := decodeProblem(t, resp)
	if problem.Code != "desired_state_cas_mismatch" {
		t.Fatalf("expected desired_state_cas_mismatch, got %q", problem.Code)
	}
}

func TestUpdateRequiresExactIfMatchETag(t *testing.T) {
	server := newTestServer()
	defer server.Close()

	resp := doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":1}`))
	etag := resp.Header.Get("ETag")

	// Wildcard If-Match is rejected (not a strong exact precondition).
	resp = doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-Match": "*"}, []byte(`{"v":2}`))
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 for wildcard If-Match, got %d", resp.StatusCode)
	}

	// Stale ETag is rejected with current state surfaced in the problem.
	staleETag := `"999-sha256:` + strings.Repeat("0", 64) + `"`
	resp = doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-Match": staleETag}, []byte(`{"v":2}`))
	if resp.StatusCode != http.StatusPreconditionFailed {
		t.Fatalf("expected 412 for stale ETag, got %d", resp.StatusCode)
	}
	problem := decodeProblem(t, resp)
	if problem.CurrentRevision != 1 {
		t.Fatalf("expected problem to surface current revision 1, got %d", problem.CurrentRevision)
	}

	// Exact current ETag succeeds.
	resp = doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-Match": etag}, []byte(`{"v":2}`))
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 for exact If-Match, got %d", resp.StatusCode)
	}
}

func TestGetReturnsAStrongETagThatRoundTripsAsIfMatch(t *testing.T) {
	server := newTestServer()
	defer server.Close()

	doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":1}`))

	getResp := doRequest(t, server, http.MethodGet, "/consumers/c1/targets/t1/desired-state", nil, nil)
	etag := getResp.Header.Get("ETag")

	putResp := doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-Match": etag}, []byte(`{"v":2}`))
	if putResp.StatusCode != http.StatusOK {
		t.Fatalf("expected GET's ETag to be usable as If-Match, got %d", putResp.StatusCode)
	}
}

func TestUnknownPathReturns404(t *testing.T) {
	server := newTestServer()
	defer server.Close()
	resp := doRequest(t, server, http.MethodGet, "/not-a-real-path", nil, nil)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown path, got %d", resp.StatusCode)
	}
}

func TestCrossTargetIsolation(t *testing.T) {
	server := newTestServer()
	defer server.Close()

	doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":1}`))

	resp := doRequest(t, server, http.MethodGet, "/consumers/c1/targets/t2/desired-state", nil, nil)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected an unrelated target to be untouched, got %d", resp.StatusCode)
	}
}

func TestConcurrentUpdatesOnlyOneSucceeds(t *testing.T) {
	server := newTestServer()
	defer server.Close()

	resp := doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-None-Match": "*"}, []byte(`{"v":0}`))
	etag := resp.Header.Get("ETag")

	const writers = 16
	var wg sync.WaitGroup
	var successCount int64
	for i := 0; i < writers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			resp := doRequest(t, server, http.MethodPut, "/consumers/c1/targets/t1/desired-state", map[string]string{"If-Match": etag}, []byte(`{"v":1}`))
			if resp.StatusCode == http.StatusOK {
				atomic.AddInt64(&successCount, 1)
			}
		}()
	}
	wg.Wait()

	if successCount != 1 {
		t.Fatalf("expected exactly one concurrent update to succeed, got %d", successCount)
	}
}
