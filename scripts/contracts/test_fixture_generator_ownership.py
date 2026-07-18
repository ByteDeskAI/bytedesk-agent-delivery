#!/usr/bin/env python3
"""Prove deterministic fixture generators have disjoint output ownership."""

from __future__ import annotations

import sys

import generate_private_compilation_graph_fixtures as private_generator
import generate_renderer_digest_fixtures as renderer_generator
from fixture_ownership import (
    PRIVATE_COMPILATION_STATIC_OUTPUT_RELATIVE_PATHS,
    RENDERER_PRIVATE_AUXILIARY_RELATIVE_PATHS,
    FixtureOwnershipError,
    assert_generator_outputs_disjoint,
    assert_private_generator_owns_declared_outputs,
    assert_renderer_excludes_private_outputs,
    renderer_private_auxiliary_paths,
)


def run_validation() -> dict[str, int | str]:
    repository_root = renderer_generator.REPOSITORY_ROOT
    renderer_outputs = renderer_generator.expected_documents()
    private_outputs, _ = private_generator.build_graph()
    if len(PRIVATE_COMPILATION_STATIC_OUTPUT_RELATIVE_PATHS) != 17:
        raise FixtureOwnershipError("private static output ownership count drift")
    if len(RENDERER_PRIVATE_AUXILIARY_RELATIVE_PATHS) != 2:
        raise FixtureOwnershipError("renderer auxiliary input count drift")
    assert_renderer_excludes_private_outputs(
        renderer_outputs.keys(), repository_root
    )
    assert_private_generator_owns_declared_outputs(
        private_outputs.keys(), repository_root
    )
    assert_generator_outputs_disjoint(
        renderer_outputs.keys(), private_outputs.keys(), repository_root
    )
    auxiliary_leaks = renderer_private_auxiliary_paths(repository_root) & set(
        renderer_outputs
    )
    if auxiliary_leaks:
        raise FixtureOwnershipError(
            "renderer returned private auxiliary inputs"
        )
    return {
        "profile": "bytedesk.fixture-generator-output-ownership/1",
        "rendererOutputs": len(renderer_outputs),
        "privateOutputs": len(private_outputs),
        "overlap": 0,
        "privateStaticOutputs": 17,
        "rendererPrivateAuxiliaryInputs": 2,
    }


def main() -> int:
    try:
        result = run_validation()
    except (KeyError, TypeError, FixtureOwnershipError) as error:
        print(f"fixture generator ownership validation failed: {error}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
