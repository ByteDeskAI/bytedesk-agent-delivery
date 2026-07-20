"""Native Agent Spec renderer: the deterministic, lossless reference transform.

AD-04 required-work item 3: "Implement native Agent Spec rendering as the
reference implementation with no semantic drift." Native output is the
validated source's own RFC 8785 canonical JSON, so it is exactly and
verifiably lossless by construction - not a lossy reinterpretation.

# ponytail: this module implements only the pure transform (source ->
# output tree -> archive/tree digests), reusing the exact deterministic-tar
# convention already established in
# scripts/contracts/generate_renderer_digest_fixtures.py:deterministic_render_archive.
# It does NOT yet assemble a full bytedesk.render-manifest/1 instance: that
# schema (and renderer-compatibility-result nested inside it) has ~20
# required fields each, several referencing further nested artifact
# descriptors (productRelease, rendererRelease, executedDistribution,
# compiledAllowlistDigest) that depend on a renderer registry/compile step
# this pass doesn't build yet. Assemble the full manifest as a deliberate
# next step, validated against the real schema, not hand-authored blind.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
from dataclasses import dataclass
from typing import Any

import rfc8785

OUTPUT_TREE_PROFILE = "bytedesk.renderer-output-tree/1"
NATIVE_OUTPUT_PATH = "agent.json"
NATIVE_OUTPUT_MODE = "0644"


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def raw_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class OutputFile:
    path: str
    digest: str
    size: int
    mode: str
    origin: str
    ownership_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "digest": self.digest,
            "size": self.size,
            "mode": self.mode,
            "origin": self.origin,
            "ownershipClass": self.ownership_class,
        }


@dataclass(frozen=True)
class NativeRenderResult:
    files: tuple[OutputFile, ...]
    archive_bytes: bytes
    tree_digest: str
    archive_digest: str
    expanded_size: int

    @property
    def file_count(self) -> int:
        return len(self.files)


def render_native(agent_spec_document: dict[str, Any]) -> NativeRenderResult:
    """Render the validated Agent Spec JSON model to native output.

    The single output file is the RFC 8785 canonical bytes of the source
    document itself: native output is defined as the lossless reference
    representation, so this is a faithful (not approximated) transform.
    """

    payload = rfc8785.dumps(agent_spec_document) + b"\n"
    output_file = OutputFile(
        path=NATIVE_OUTPUT_PATH,
        digest=raw_digest(payload),
        size=len(payload),
        mode=NATIVE_OUTPUT_MODE,
        origin="source_payload",
        ownership_class="runtime_read_only",
    )
    files = (output_file,)

    tree_digest = canonical_digest(
        {"profile": OUTPUT_TREE_PROFILE, "files": [f.as_dict() for f in files]}
    )
    archive_bytes = _deterministic_archive(files, {NATIVE_OUTPUT_PATH: payload})

    return NativeRenderResult(
        files=files,
        archive_bytes=archive_bytes,
        tree_digest=tree_digest,
        archive_digest=raw_digest(archive_bytes),
        expanded_size=sum(f.size for f in files),
    )


def _deterministic_archive(files: tuple[OutputFile, ...], payloads: dict[str, bytes]) -> bytes:
    """Deterministic USTAR archive: fixed mtime/uid/gid, NFC-path order.

    Same normalization convention as generate_renderer_digest_fixtures.py's
    deterministic_render_archive - reused for consistency, not reinvented.
    """

    ordered = sorted(files, key=lambda f: f.path.encode("utf-8"))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for file in ordered:
            payload = payloads[file.path]
            header = tarfile.TarInfo(file.path)
            header.size = len(payload)
            header.mode = int(file.mode, 8)
            header.mtime = 0
            header.uid = 0
            header.gid = 0
            header.uname = ""
            header.gname = ""
            archive.addfile(header, io.BytesIO(payload))
    return buffer.getvalue()
