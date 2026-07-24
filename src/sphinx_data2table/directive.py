"""Directive implementation for rendering TOML, YAML, and JSON tables."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import StringList
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]


class DataTableDirective(Directive):
    """Sphinx/Docutils directive to render TOML, YAML, or JSON data as tables.

    This directive parses raw inline TOML/YAML/JSON text or external data files into
    structured data and constructs docutils table nodes. Each cell's text is
    parsed via nested_parse to support Markdown inline and block elements.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        "file": directives.path,
        "format": directives.unchanged,
        "headers": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        """Main execution method invoked by docutils when parsing the directive.

        Returns:
            A list containing either a constructed docutils table node or error/warning nodes.
        """
        env = self.state.document.settings.env if hasattr(self.state.document.settings, "env") else None

        # 1. Obtain raw data content
        file_path = self.options.get("file")
        raw_text = ""

        if file_path:
            if env:
                # Resolve relative path to sphinx doc source directory
                rel_path, abs_path = env.relfn2path(file_path)
                env.note_dependency(rel_path)
            else:
                abs_path = os.path.abspath(file_path)

            try:
                with open(abs_path, encoding="utf-8") as f:
                    raw_text = f.read()
            except OSError as err:
                return [
                    self.state_machine.reporter.error(
                        f"data-table: Could not read file '{file_path}': {err}",
                        line=self.lineno,
                    )
                ]
        elif self.content:
            raw_text = textwrap.dedent("\n".join(self.content)).strip()
        else:
            return [
                self.state_machine.reporter.error(
                    "data-table: Neither content nor ':file:' option provided.",
                    line=self.lineno,
                )
            ]

        # 2. Determine format (yaml / toml / json)
        fmt = self.options.get("format", "auto").lower()

        if fmt == "auto":
            if file_path:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in (".toml",):
                    fmt = "toml"
                elif ext in (".yaml", ".yml"):
                    fmt = "yaml"
                elif ext in (".json",):
                    fmt = "json"
            if fmt == "auto":
                fmt = self._guess_format(raw_text)

        # 3. Parse data
        data, parse_err = self._parse_data(raw_text, fmt)
        if parse_err:
            return [
                self.state_machine.reporter.error(
                    f"data-table: Failed to parse {fmt.upper()} data: {parse_err}",
                    line=self.lineno,
                )
            ]

        rows_data = self._normalize_rows(data)
        if not rows_data:
            return [
                self.state_machine.reporter.warning(
                    "data-table: Data is empty or invalid format.",
                    line=self.lineno,
                )
            ]

        # 4. Determine Headers
        headers_opt = self.options.get("headers")
        if headers_opt:
            headers = [h.strip() for h in headers_opt.split(",") if h.strip()]
        else:
            # Collect all unique keys across rows while preserving order
            headers = []
            for row in rows_data:
                if isinstance(row, dict):
                    for k in row.keys():
                        if k not in headers:
                            headers.append(k)

        if not headers:
            return [
                self.state_machine.reporter.error(
                    "data-table: Could not determine headers from data.",
                    line=self.lineno,
                )
            ]

        # 5. Build Docutils Table Node
        table_node = self._build_table_node(headers, rows_data)
        return [table_node]

    def _guess_format(self, text: str) -> str:
        """Guesses whether raw text content is JSON, TOML, or YAML.

        Args:
            text: The raw string content of the data.

        Returns:
            The string 'json', 'toml', or 'yaml'. Defaults to 'yaml' if ambiguous.
        """
        # Try JSON first
        try:
            parsed_json = json.loads(text)
            if isinstance(parsed_json, (list, dict)):
                return "json"
        except Exception:
            pass

        # Try TOML
        if tomllib:
            try:
                parsed_toml = tomllib.loads(text)
                if isinstance(parsed_toml, dict) and parsed_toml:
                    return "toml"
            except Exception:
                pass

        # Try YAML
        try:
            parsed_yaml = yaml.safe_load(text)
            if isinstance(parsed_yaml, (list, dict)):
                return "yaml"
        except Exception:
            pass

        return "yaml"

    def _parse_data(self, text: str, fmt: str) -> tuple[Any, str | None]:
        """Parses raw text data using the specified format parser.

        Args:
            text: Raw data text string.
            fmt: Format string ('json', 'toml', or 'yaml').

        Returns:
            A tuple containing (parsed_object, error_message_or_None).
        """
        if fmt == "json":
            try:
                return json.loads(text), None
            except Exception as e:
                return None, str(e)
        elif fmt == "toml":
            if not tomllib:
                return None, "tomllib module not available in this Python environment."
            try:
                return tomllib.loads(text), None
            except Exception as e:
                return None, str(e)
        elif fmt == "yaml":
            try:
                return yaml.safe_load(text), None
            except Exception as e:
                return None, str(e)
        else:
            return None, f"Unsupported format '{fmt}'. Use 'json', 'yaml', or 'toml'."

    def _normalize_rows(self, data: Any) -> list[dict[str, Any]]:
        """Normalizes parsed data into a list of row dictionaries.

        Args:
            data: Parsed data resulting from JSON, TOML, or YAML parser.

        Returns:
            A list of dictionary objects representing table rows.
        """
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            # If root is a dict containing a list of dicts (e.g. {"items": [...]})
            for val in data.values():
                if isinstance(val, list) and all(isinstance(x, dict) for x in val):
                    return val
            # Or a single row dict
            return [data]
        return []

    def _build_table_node(self, headers: list[str], rows_data: list[dict[str, Any]]) -> nodes.table:
        """Constructs docutils table nodes and parses Markdown for each cell.

        Args:
            headers: A list of column header names.
            rows_data: A list of row dictionary objects containing cell contents.

        Returns:
            A docutils.nodes.table instance containing header and body rows.
        """
        table = nodes.table()
        table["classes"] += ["datatable"]
        tgroup = nodes.tgroup(cols=len(headers))
        table += tgroup

        for _ in headers:
            tgroup += nodes.colspec(colwidth=1)

        # Header Row
        thead = nodes.thead()
        tgroup += thead
        header_row = nodes.row()
        thead += header_row

        for header_text in headers:
            entry = nodes.entry()
            self._parse_cell_markdown(str(header_text), entry)
            header_row += entry

        # Body Rows
        tbody = nodes.tbody()
        tgroup += tbody

        for row_dict in rows_data:
            row_node = nodes.row()
            tbody += row_node
            for h in headers:
                entry = nodes.entry()
                cell_value = row_dict.get(h, "")
                if cell_value is None:
                    cell_value = ""
                self._parse_cell_markdown(str(cell_value), entry)
                row_node += entry

        return table

    def _parse_cell_markdown(self, content_str: str, entry_node: nodes.entry) -> None:
        """Parses a cell string as Markdown/reST AST into docutils nodes inside entry_node.

        Args:
            content_str: The raw text content of the table cell.
            entry_node: Target docutils.nodes.entry node to append parsed child nodes into.
        """
        dedented_str = textwrap.dedent(content_str).strip()
        if not dedented_str:
            return

        lines = dedented_str.splitlines()
        string_list = StringList(lines, source="datatable_cell")

        # Create temporary container node to hold nested parsed nodes
        container = nodes.Element()
        self.state.nested_parse(string_list, 0, container)

        # Post-process container nodes to replace in-cell newlines with latex-safe \newline
        self._replace_cell_newlines(container)

        # Transfer children from container to entry_node
        for child in container.children:
            entry_node += child

    def _replace_cell_newlines(self, node: nodes.Node) -> None:
        """Recursively replaces text node newlines with format-safe break nodes.

        Args:
            node: The docutils node to process recursively.
        """
        new_children: list[nodes.Node] = []
        modified = False

        for child in list(node.children):
            if isinstance(child, nodes.raw) and child.get("format") == "latex" and child.astext().strip() in ("\\\\", r"\\"):
                modified = True
                latex_break = nodes.raw("", r"\newline ", format="latex")
                latex_break.parent = node
                new_children.append(latex_break)
            elif isinstance(child, nodes.Text) and "\n" in child:
                modified = True
                parts = str(child).split("\n")
                for i, part in enumerate(parts):
                    clean_part = part.rstrip()
                    if clean_part:
                        t = nodes.Text(clean_part)
                        t.parent = node
                        new_children.append(t)
                    if i < len(parts) - 1:
                        latex_break = nodes.raw("", r"\newline ", format="latex")
                        html_break = nodes.raw("", "<br/>", format="html")
                        latex_break.parent = node
                        html_break.parent = node
                        new_children.extend([latex_break, html_break])
            else:
                self._replace_cell_newlines(child)
                child.parent = node
                new_children.append(child)

        if modified:
            node.children = new_children
