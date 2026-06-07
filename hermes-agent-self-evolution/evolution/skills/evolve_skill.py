"""DEPRECATED — Use `hermes-evolve run ...` instead.

This file is kept for backward compatibility.
Redirects to evolution.cli:cli.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "skills/evolve_skill.py is deprecated. Use `hermes-evolve run ...` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from evolution.cli import cli

if __name__ == "__main__":
    cli()
