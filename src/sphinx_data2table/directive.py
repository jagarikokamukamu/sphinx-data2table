"""Directive implementation for rendering TOML, YAML, and JSON tables."""

from __future__ import annotations

import contextlib
import json
import os
import textwrap
import tomllib
from typing import Any

import yaml
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import StringList


class DataLoader:
    """Handles raw data text loading from external file or inline directive content."""

    def __init__(self, directive: Directive) -> None:
        self.directive = directive

    def load(self) -> tuple[str, nodes.Node | None]:
        """Loads data text prioritizing external file path option over inline content.

        Returns:
            A tuple containing raw data text and an optional error reporter node.
        """
        file_path = self.directive.options.get("file")
        if file_path:
            return self._load_from_file(file_path)

        if self.directive.content:
            return self._load_from_inline(), None

        error_node = self.directive.state_machine.reporter.error(
            "data-table: Neither content nor ':file:' option provided.",
            line=self.directive.lineno,
        )
        return "", error_node

    def _load_from_file(self, file_path: str) -> tuple[str, nodes.Node | None]:
        """Reads raw text from external file path and registers Sphinx dependency."""
        env = getattr(self.directive.state.document.settings, "env", None)
        if env:
            rel_path, abs_path = env.relfn2path(file_path)
            env.note_dependency(rel_path)
        else:
            abs_path = os.path.abspath(file_path)

        try:
            with open(abs_path, encoding="utf-8") as f:
                return f.read(), None
        except OSError as err:
            error_node = self.directive.state_machine.reporter.error(
                f"data-table: Could not read file '{file_path}': {err}",
                line=self.directive.lineno,
            )
            return "", error_node

    def _load_from_inline(self) -> str:
        """Extracts and dedents raw data text from inline directive block."""
        return textwrap.dedent("\n".join(self.directive.content)).strip()


class DataParser:
    """Handles format detection, parsing, and data normalization into row dicts."""

    def __init__(self, directive: Directive) -> None:
        self.directive = directive

    def parse(self, data_text: str) -> tuple[list[dict[str, Any]], nodes.Node | None]:
        """Detects data format, parses text, and normalizes into row dictionaries.

        Returns:
            A tuple containing a list of row dicts and an optional error/warning node.
        """
        data_format = self._detect_format(data_text)
        parsed_data, parse_err_msg = self._parse_by_format(data_text, data_format)

        if parse_err_msg:
            error_node = self.directive.state_machine.reporter.error(
                parse_err_msg, line=self.directive.lineno
            )
            return [], error_node

        rows = self._normalize_to_rows(parsed_data)
        if not rows:
            warning_node = self.directive.state_machine.reporter.warning(
                "data-table: Data is empty or invalid format.",
                line=self.directive.lineno,
            )
            return [], warning_node

        return rows, None

    def _detect_format(self, data_text: str) -> str:
        """Determines format via option specifier, file extension, or heuristic."""
        specified_format = self.directive.options.get("format", "auto").lower()
        if specified_format != "auto":
            return specified_format

        file_path = self.directive.options.get("file")
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".toml",):
                return "toml"
            if ext in (".yaml", ".yml"):
                return "yaml"
            if ext in (".json",):
                return "json"

        return self._detect_format_from_content(data_text)

    def _detect_format_from_content(self, data_text: str) -> str:
        """Heuristically checks if text is valid JSON, TOML, or YAML."""
        if self._is_valid_json(data_text):
            return "json"
        if self._is_valid_toml(data_text):
            return "toml"
        if self._is_valid_yaml(data_text):
            return "yaml"
        return "yaml"

    def _is_valid_json(self, text: str) -> bool:
        with contextlib.suppress(Exception):
            return isinstance(json.loads(text), (list, dict))
        return False

    def _is_valid_toml(self, text: str) -> bool:
        with contextlib.suppress(Exception):
            return bool(tomllib.loads(text))
        return False

    def _is_valid_yaml(self, text: str) -> bool:
        with contextlib.suppress(Exception):
            return isinstance(yaml.safe_load(text), (list, dict))
        return False

    def _parse_by_format(
        self, data_text: str, data_format: str
    ) -> tuple[Any, str | None]:
        try:
            if data_format == "json":
                return json.loads(data_text), None
            if data_format == "toml":
                return tomllib.loads(data_text), None
            if data_format == "yaml":
                return yaml.safe_load(data_text), None
            return (
                None,
                f"Unsupported format '{data_format}'. Use 'json', 'yaml', or 'toml'.",
            )
        except Exception as err:
            return None, f"Failed to parse {data_format.upper()} data: {err}"

    def _normalize_to_rows(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list) and all(isinstance(x, dict) for x in val):
                    return val
            return [data]

        return []


class DataTableDirective(Directive):
    """Sphinx/Docutils directive to render TOML, YAML, or JSON data as tables.

    This directive parses data text (inline or external) into structured row
    dictionaries and constructs docutils table nodes. Each cell's text is parsed
    via nested_parse to support Markdown inline and block elements.
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
        """Main execution method invoked by docutils when parsing directive.

        Returns:
            A list containing constructed docutils table node or error nodes.
        """
        # 1. Obtain raw data content
        data_text, load_error = DataLoader(self).load()
        if load_error:
            return [load_error]

        # 2. Parse data into row dictionaries
        rows, parse_error = DataParser(self).parse(data_text)
        if parse_error:
            return [parse_error]

        # 3. Determine Headers
        headers_opt = self.options.get("headers")
        if headers_opt:
            headers = [h.strip() for h in headers_opt.split(",") if h.strip()]
        else:
            # Collect all unique keys across rows while preserving order
            headers = []
            for row in rows:
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

        # 4. Build Docutils Table Node
        table_node = self._build_table_node(headers, rows)
        return [table_node]

    # =========================================================================
    # Table AST Construction
    # =========================================================================

    def _build_table_node(
        self, headers: list[str], rows_data: list[dict[str, Any]]
    ) -> nodes.table:
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
        """Parses cell string as Markdown/reST AST into docutils nodes in entry_node.

        Args:
            content_str: The raw text content of the table cell.
            entry_node: Target docutils.nodes.entry node to append child nodes into.
        """
        dedented_str = textwrap.dedent(content_str).strip()
        if not dedented_str:
            return

        lines = dedented_str.splitlines()
        string_list = StringList(lines, source="datatable_cell")

        # Create temporary container node to hold nested parsed nodes
        container = nodes.Element()
        self.state.nested_parse(string_list, 0, container)

        # Post-process container nodes to replace in-cell newlines with latex-safe
        self._replace_cell_newlines(container)

        # Transfer children from container to entry_node
        for child in container.children:
            entry_node += child

    def _replace_cell_newlines(self, node: nodes.Node) -> None:
        """Recursively replaces in-cell line breaks with raw break nodes.

        WORKAROUND:
            Sphinx's default LaTeXTranslator turns in-cell line break nodes into
            '\\\\', which LaTeX interprets as a table row separator.

        Args:
            node: The docutils AST node to process recursively.
        """
        new_children: list[nodes.Node] = []
        modified = False

        for child in list(node.children):
            if (
                isinstance(child, nodes.raw)
                and child.get("format") == "latex"
                and child.astext().strip() in ("\\\\", r"\\")
            ):
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
