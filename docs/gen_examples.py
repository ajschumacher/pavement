#!/usr/bin/env python3
"""Regenerate the live example outputs embedded on the Examples page.

Runs the relevant scripts from ``examples/`` and drops their HTML into
``docs/examples/assets/`` so MkDocs can embed them in ``<iframe>``s. The
interactive demo already pulls Plotly and Bokeh from their CDNs; any other
plotly ``write_html`` output is pointed at the CDN too (instead of inlining
~4.5 MB of plotly.js) to keep the site light.

Usage (from the repo root, with the backends installed)::

    pip install -e '.[all,pandas,polars]'
    python docs/gen_examples.py
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"
ASSETS = REPO / "docs" / "examples" / "assets"

# Demos that emit a standalone HTML page we embed on the Examples page.
DEMOS = [
    "svg_demo",
    "summary_demo",
    "value_format_demo",
    "box_edges_demo",
    "interactive_demo",
    "pandas_polars_demo",
]


def _patch_plotly_to_cdn() -> None:
    """Make plotly's write_html reference the CDN rather than inline the lib."""
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        return
    original = go.Figure.write_html

    def write_html(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("include_plotlyjs", "cdn")
        return original(self, *args, **kwargs)

    go.Figure.write_html = write_html  # type: ignore[method-assign]


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    _patch_plotly_to_cdn()
    cwd = os.getcwd()
    os.chdir(ASSETS)
    try:
        for demo in DEMOS:
            print(f"generating {demo} ...")
            runpy.run_path(str(EXAMPLES / f"{demo}.py"), run_name="__main__")
    finally:
        os.chdir(cwd)
    print(f"\nwrote {len(list(ASSETS.glob('*.html')))} HTML files to {ASSETS}")


if __name__ == "__main__":
    main()
