"""Sphinx Data2Table Extension.

Renders TOML, YAML, or JSON data as HTML/LaTeX tables with Markdown cell parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sphinx_data2table.directive import DataTableDirective

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__version__ = "0.1.2"


def setup(app: Sphinx) -> dict[str, Any]:
    """Registers the data-table and datatable directives with the Sphinx application.

    Args:
        app: The active Sphinx application instance.

    Returns:
        A dictionary containing metadata about the extension, including
        version and parallel read/write safety flags.
    """
    app.add_directive("data-table", DataTableDirective)
    app.add_directive("datatable", DataTableDirective)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
