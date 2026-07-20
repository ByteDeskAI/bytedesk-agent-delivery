"""Minimal OCI Distribution API v2 client: enough to push/pull/verify one artifact.

# ponytail: implements only PUT/GET blob and PUT/GET/HEAD manifest against a
# plain HTTP (or HTTPS) OCI Distribution API v2 registry (e.g. the reference
# `registry:2` image) - no auth, no chunked upload, no cross-repo mount.
# Sufficient to prove real push/pull/tamper/tag-retargeting behavior; extend
# for a real production registry (auth, chunked/resumable upload) later.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class RegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Registry:
    base_url: str  # e.g. "http://localhost:5000"
    repository: str  # e.g. "bytedesk/agent-source"

    def _url(self, path: str) -> str:
        return f"{self.base_url}/v2/{self.repository}/{path}"

    def push_blob(self, digest: str, payload: bytes) -> None:
        upload_url = self._url("blobs/uploads/")
        request = urllib.request.Request(upload_url, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            location = response.headers.get("Location")
        if not location:
            raise RegistryError("registry did not return an upload location")
        if location.startswith("/"):
            location = self.base_url + location
        separator = "&" if "?" in location else "?"
        put_url = f"{location}{separator}digest={digest}"
        request = urllib.request.Request(put_url, data=payload, method="PUT")
        request.add_header("Content-Type", "application/octet-stream")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status not in (201, 202):
                    raise RegistryError(f"blob push rejected: HTTP {response.status}")
        except urllib.error.HTTPError as error:
            raise RegistryError(f"blob push failed: HTTP {error.code} {error.read()!r}") from error

    def blob_exists(self, digest: str) -> bool:
        request = urllib.request.Request(self._url(f"blobs/{digest}"), method="HEAD")
        try:
            urllib.request.urlopen(request, timeout=30)
            return True
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return False
            raise RegistryError(f"blob HEAD failed: HTTP {error.code}") from error

    def pull_blob(self, digest: str) -> bytes:
        request = urllib.request.Request(self._url(f"blobs/{digest}"), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            raise RegistryError(f"blob pull failed: HTTP {error.code}") from error
        observed_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if observed_digest != digest:
            raise RegistryError(
                f"pulled blob digest mismatch: expected {digest}, observed {observed_digest}"
            )
        return payload

    def push_manifest(self, reference: str, manifest_bytes: bytes, media_type: str) -> None:
        request = urllib.request.Request(
            self._url(f"manifests/{reference}"), data=manifest_bytes, method="PUT"
        )
        request.add_header("Content-Type", media_type)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status not in (200, 201):
                    raise RegistryError(f"manifest push rejected: HTTP {response.status}")
        except urllib.error.HTTPError as error:
            raise RegistryError(f"manifest push failed: HTTP {error.code} {error.read()!r}") from error

    def pull_manifest(self, reference: str) -> bytes:
        request = urllib.request.Request(self._url(f"manifests/{reference}"), method="GET")
        request.add_header("Accept", "application/vnd.oci.image.manifest.v1+json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raise RegistryError(f"manifest pull failed: HTTP {error.code}") from error

    def manifest_digest_by_tag(self, reference: str) -> str:
        request = urllib.request.Request(self._url(f"manifests/{reference}"), method="HEAD")
        request.add_header("Accept", "application/vnd.oci.image.manifest.v1+json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                digest = response.headers.get("Docker-Content-Digest")
        except urllib.error.HTTPError as error:
            raise RegistryError(f"manifest HEAD failed: HTTP {error.code}") from error
        if not digest:
            raise RegistryError("registry did not return Docker-Content-Digest")
        return digest


def push_artifact(registry: Registry, reference: str, artifact) -> None:
    """Push config, layer, and manifest for a pack.OciArtifact."""

    registry.push_blob(artifact.config_descriptor.digest, artifact.config_bytes)
    registry.push_blob(artifact.layer_descriptor.digest, artifact.layer_bytes)
    registry.push_manifest(reference, artifact.manifest_bytes, "application/vnd.oci.image.manifest.v1+json")


def pull_and_verify_artifact(registry: Registry, reference: str) -> dict:
    """Pull a manifest by reference and independently re-hash every referenced blob.

    Fails closed (raises RegistryError) on any digest mismatch - AD-07
    acceptance criteria: verify exact digest before extraction, never trust
    tags or annotations for identity.
    """

    manifest_bytes = registry.pull_manifest(reference)
    observed_manifest_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)

    config = manifest["config"]
    config_bytes = registry.pull_blob(config["digest"])
    if len(config_bytes) != config["size"]:
        raise RegistryError("config size mismatch")

    layers = []
    for layer in manifest["layers"]:
        layer_bytes = registry.pull_blob(layer["digest"])
        if len(layer_bytes) != layer["size"]:
            raise RegistryError(f"layer size mismatch: {layer['digest']}")
        layers.append(layer_bytes)

    return {
        "manifestDigest": observed_manifest_digest,
        "manifest": manifest,
        "configBytes": config_bytes,
        "layerBytes": layers,
    }
