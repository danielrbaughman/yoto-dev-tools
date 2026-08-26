"""Shared CLI parameter definitions and the verbose flag convention."""

from typing import Annotated

import typer
from typer_verbose import Verbose

# `@verbose()` under `@app.command()` adds --verbose/-v and flips the "yoto"
# loggers to DEBUG (handler installed in app.py's root callback).
verbose = Verbose("yoto")

JsonOpt = Annotated[
    bool, typer.Option("--json", help="Emit machine-readable JSON on stdout.")
]
YesOpt = Annotated[
    bool, typer.Option("--yes", "-y", help="Do not ask for confirmation.")
]
