#!/usr/bin/env python3
"""Central output ownership for deterministic contract fixture generators.

Nested schema references are dependencies, not output ownership.  These exact
paths and subtrees belong to the private-compilation generator; the renderer
generator may read only the declared auxiliary inputs and must never return
them from ``expected_documents()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Collection


PRIVATE_COMPILATION_STATIC_OUTPUT_RELATIVE_PATHS = frozenset(
    {
        "contracts/fixtures/operations/private-compilation-graph.cases.json",
        "contracts/fixtures/schema/negative/activation-authorization__unknown-authority-field.json",
        "contracts/fixtures/schema/negative/consumer-deployment__compilation-evidence-backlink.json",
        "contracts/fixtures/schema/negative/consumer-deployment__runtime-release-backlink.json",
        "contracts/fixtures/schema/negative/consumer-deployment__unknown-authority-field.json",
        "contracts/fixtures/schema/negative/private-compilation-evidence__deployment-backlink.json",
        "contracts/fixtures/schema/negative/private-input-authentication-bundle__unknown-root-field.json",
        "contracts/fixtures/schema/negative/runtime-release__unknown-authority-field.json",
        "contracts/fixtures/schema/positive/activation-authorization__complete.json",
        "contracts/fixtures/schema/positive/consumer-authority__compile.json",
        "contracts/fixtures/schema/positive/consumer-deployment__effective-render.json",
        "contracts/fixtures/schema/positive/private-compilation-evidence__committed.json",
        "contracts/fixtures/schema/positive/private-compilation-input__complete-lock.json",
        "contracts/fixtures/schema/positive/private-input-authentication-bundle__complete.json",
        "contracts/fixtures/schema/positive/render-manifest__hermes-private.json",
        "contracts/fixtures/schema/positive/renderer-compatibility-result__hermes-lossy.json",
        "contracts/fixtures/schema/positive/runtime-release__prepared.json",
    }
)
PRIVATE_COMPILATION_CAS_RELATIVE_ROOT = (
    "contracts/fixtures/operations/private-compilation-cas"
)
RENDERER_PRIVATE_AUXILIARY_RELATIVE_PATHS = frozenset(
    {
        "contracts/fixtures/schema/positive/consumer-authority__compile.json",
        "contracts/fixtures/schema/positive/private-compilation-input__complete-lock.json",
    }
)


class FixtureOwnershipError(RuntimeError):
    """Deterministic generators claim the same path or violate ownership."""


def _absolute_paths(
    repository_root: Path, relative_paths: Collection[str]
) -> frozenset[Path]:
    return frozenset(repository_root / path for path in relative_paths)


def private_compilation_static_output_paths(
    repository_root: Path,
) -> frozenset[Path]:
    return _absolute_paths(
        repository_root, PRIVATE_COMPILATION_STATIC_OUTPUT_RELATIVE_PATHS
    )


def renderer_private_auxiliary_paths(
    repository_root: Path,
) -> frozenset[Path]:
    return _absolute_paths(
        repository_root, RENDERER_PRIVATE_AUXILIARY_RELATIVE_PATHS
    )


def private_compilation_cas_root(repository_root: Path) -> Path:
    return repository_root / PRIVATE_COMPILATION_CAS_RELATIVE_ROOT


def is_private_compilation_owned_output(
    path: Path, repository_root: Path
) -> bool:
    return path in private_compilation_static_output_paths(
        repository_root
    ) or path.is_relative_to(private_compilation_cas_root(repository_root))


def assert_renderer_excludes_private_outputs(
    renderer_outputs: Collection[Path], repository_root: Path
) -> None:
    violations = sorted(
        (
            path
            for path in renderer_outputs
            if is_private_compilation_owned_output(path, repository_root)
        ),
        key=lambda path: path.as_posix(),
    )
    if violations:
        rendered = ", ".join(
            path.relative_to(repository_root).as_posix() for path in violations
        )
        raise FixtureOwnershipError(
            f"renderer returned private-owned outputs: {rendered}"
        )


def assert_private_generator_owns_declared_outputs(
    private_outputs: Collection[Path], repository_root: Path
) -> None:
    output_set = set(private_outputs)
    missing = sorted(
        private_compilation_static_output_paths(repository_root) - output_set,
        key=lambda path: path.as_posix(),
    )
    cas_root = private_compilation_cas_root(repository_root)
    has_cas_output = any(path.is_relative_to(cas_root) for path in output_set)
    if missing or not has_cas_output:
        details = [
            path.relative_to(repository_root).as_posix() for path in missing
        ]
        if not has_cas_output:
            details.append(f"{PRIVATE_COMPILATION_CAS_RELATIVE_ROOT}/**")
        raise FixtureOwnershipError(
            "private generator omitted declared outputs: " + ", ".join(details)
        )


def assert_generator_outputs_disjoint(
    renderer_outputs: Collection[Path],
    private_outputs: Collection[Path],
    repository_root: Path,
) -> None:
    overlap = sorted(
        set(renderer_outputs) & set(private_outputs),
        key=lambda path: path.as_posix(),
    )
    if overlap:
        rendered = ", ".join(
            path.relative_to(repository_root).as_posix() for path in overlap
        )
        raise FixtureOwnershipError(f"generator output overlap: {rendered}")
