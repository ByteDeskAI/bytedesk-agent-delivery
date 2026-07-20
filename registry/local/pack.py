"""Deterministic ORAS-compatible OCI artifact construction.

AD-07 required-work items 1 and 3: build source/render OCI artifacts from
canonical public inputs using ORAS-compatible JCS manifests, exact digest
references, and deterministic archives; annotations are descriptive only,
never trusted for identity.

# ponytail: this module builds one artifact shape - a single-layer source
# artifact wrapping a canonical JSON payload - proven end to end against a
# real local registry (see tests/test_local_registry.py). It does not yet
# implement the full AD-07 scope: public-render bundles with multiple
# layers/skills, referrers/subject graph construction, retention rules, or
# the publication-evidence/idempotency-key commit protocol. Build those as
# deliberate next slices, each proven against the same real registry.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from dataclasses import dataclass
from typing import Any

import rfc8785

OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
SOURCE_ARTIFACT_MEDIA_TYPE = "application/vnd.bytedesk.agent.source.v1+json"
SOURCE_LAYER_MEDIA_TYPE = "application/vnd.bytedesk.agent.source-layer.v1.tar+gzip"
EMPTY_CONFIG_MEDIA_TYPE = "application/vnd.oci.empty.v1+json"
EMPTY_CONFIG_BYTES = b"{}"


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def raw_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Descriptor:
    media_type: str
    digest: str
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {"mediaType": self.media_type, "digest": self.digest, "size": self.size}


@dataclass(frozen=True)
class OciArtifact:
    """A complete, deterministic ORAS artifact: manifest + config + one layer."""

    manifest_bytes: bytes
    manifest_digest: str
    config_bytes: bytes
    config_descriptor: Descriptor
    layer_bytes: bytes
    layer_descriptor: Descriptor


def _deterministic_layer_tar_gz(path: str, payload: bytes) -> bytes:
    """Single-entry deterministic USTAR+gzip layer: zeroed metadata, fixed mtime."""

    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        header = tarfile.TarInfo(path)
        header.size = len(payload)
        header.mode = 0o644
        header.mtime = 0
        header.uid = 0
        header.gid = 0
        header.uname = ""
        header.gname = ""
        tar.addfile(header, io.BytesIO(payload))
    return gzip.compress(archive.getvalue(), compresslevel=9, mtime=0)


def pack_source_artifact(source_document: dict[str, Any], *, layer_path: str = "agent-source.json") -> OciArtifact:
    """Build a deterministic single-layer ORAS artifact wrapping a canonical source.

    Reused convention: same deterministic-gzip-tar approach already
    established by generate_renderer_digest_fixtures.py:deterministic_oci_layer.
    """

    source_payload = rfc8785.dumps(source_document) + b"\n"
    layer_bytes = _deterministic_layer_tar_gz(layer_path, source_payload)
    layer_descriptor = Descriptor(SOURCE_LAYER_MEDIA_TYPE, raw_digest(layer_bytes), len(layer_bytes))

    config_descriptor = Descriptor(
        EMPTY_CONFIG_MEDIA_TYPE, raw_digest(EMPTY_CONFIG_BYTES), len(EMPTY_CONFIG_BYTES)
    )

    manifest = {
        "schemaVersion": 2,
        "mediaType": OCI_MANIFEST_MEDIA_TYPE,
        "artifactType": SOURCE_ARTIFACT_MEDIA_TYPE,
        "config": config_descriptor.as_dict(),
        "layers": [layer_descriptor.as_dict()],
        "annotations": {},
    }
    manifest_bytes = rfc8785.dumps(manifest)

    return OciArtifact(
        manifest_bytes=manifest_bytes,
        manifest_digest=raw_digest(manifest_bytes),
        config_bytes=EMPTY_CONFIG_BYTES,
        config_descriptor=config_descriptor,
        layer_bytes=layer_bytes,
        layer_descriptor=layer_descriptor,
    )


def extract_layer_payload(layer_bytes: bytes, expected_path: str) -> bytes:
    """Reverse of _deterministic_layer_tar_gz: extract and verify the one entry.

    Fails closed on anything but exactly one regular file at expected_path -
    AD-07 acceptance criteria: malformed/missing layers fail closed.
    """

    with tarfile.open(fileobj=io.BytesIO(layer_bytes)) as tar:
        members = tar.getmembers()
        if len(members) != 1:
            raise ValueError(f"expected exactly one layer entry, found {len(members)}")
        member = members[0]
        if member.name != expected_path:
            raise ValueError(f"unexpected layer entry path: {member.name!r}")
        if not member.isreg():
            raise ValueError(f"layer entry is not a regular file: {member.name!r}")
        extracted = tar.extractfile(member)
        if extracted is None:
            raise ValueError("layer entry could not be extracted")
        return extracted.read()
