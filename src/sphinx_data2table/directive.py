"""Sphinx directive for rendering TOML, YAML, and JSON data as docutils tables."""

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


class DataTableDirective(Directive):
    """A Sphinx directive that transforms structured data into HTML/LaTeX tables.

    Supports TOML, YAML, and JSON data provided either inline within the document
    or via an external data file path. Each table cell's text is parsed as Markdown/reST
    AST to preserve inline and block element formatting.
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
        """Orchestrates the table rendering pipeline and returns docutils AST nodes.

        Returns:
            A list containing either a constructed docutils.nodes.table instance or
            an error/warning message node if processing fails.
        """
        # 1. Load raw text content from external file or inline block
        raw_text, load_error = self._load_source_text()
        if load_error:
            return [load_error]

        # 2. Parse raw text into structured row dictionaries
        rows, parse_error = self._parse_to_row_dictionaries(raw_text)
        if parse_error:
            return [parse_error]

        # 3. Construct and return the docutils table AST node
        table_node, build_error = self._construct_table_node(rows)
        if build_error:
            return [build_error]

        return [table_node]

    # =========================================================================
    # Step 1: Source Text Loading
    # =========================================================================

    def _load_source_text(self) -> tuple[str, nodes.Node | None]:
        """Loads raw data text from the specified file option or inline content.

        Returns:
            A tuple containing:
                - The raw text content string.
                - An error node if neither content nor valid file path is provided,
                  otherwise None.
        """
        file_path = self.options.get("file")
        if file_path:
            return self._read_external_file(file_path)

        if self.content:
            inline_text = textwrap.dedent("\n".join(self.content)).strip()
            return inline_text, None

        error_node = self.state_machine.reporter.error(
            "data-table: Neither content nor ':file:' option provided.",
            line=self.lineno,
        )
        return "", error_node

    def _read_external_file(self, file_path: str) -> tuple[str, nodes.Node | None]:
        """Reads text from an external file path, tracking Sphinx dependency.

        Args:
            file_path: Relative or absolute path to the target data file.

        Returns:
            A tuple containing:
                - The file contents as a string.
                - An error node if the file cannot be read, otherwise None.
        """
        env = getattr(self.state.document.settings, "env", None)
        if env:
            rel_path, abs_path = env.relfn2path(file_path)
            env.note_dependency(rel_path)
        else:
            abs_path = os.path.abspath(file_path)

        try:
            with open(abs_path, encoding="utf-8") as f:
                return f.read(), None
        except OSError as err:
            error_node = self.state_machine.reporter.error(
                f"data-table: Could not read file '{file_path}': {err}",
                line=self.lineno,
            )
            return "", error_node

    # =========================================================================
    # Step 2: Data Parsing & Normalization
    # =========================================================================

    def _parse_to_row_dictionaries(
        self, raw_text: str
    ) -> tuple[list[dict[str, Any]], nodes.Node | None]:
        """Detects format, parses raw text, and normalizes into row dictionaries.

        Args:
            raw_text: Raw string content of TOML, YAML, or JSON data.

        Returns:
            A tuple containing:
                - A list of dictionary objects representing table rows.
                - An error or warning message node if parsing fails or data is empty,
                  otherwise None.
        """
        data_format = self._detect_data_format(raw_text)
        parsed_data, parse_err_msg = self._parse_by_format(raw_text, data_format)

        if parse_err_msg:
            error_node = self.state_machine.reporter.error(
                parse_err_msg, line=self.lineno
            )
            return [], error_node

        rows = self._normalize_parsed_data(parsed_data)
        if not rows:
            warning_node = self.state_machine.reporter.warning(
                "data-table: Data is empty or invalid format.",
                line=self.lineno,
            )
            return [], warning_node

        return rows, None

    def _detect_data_format(self, raw_text: str) -> str:
        """Detects data format using option, file extension, or content heuristic.

        Args:
            raw_text: The raw string content of the data.

        Returns:
            Format string ('json', 'toml', or 'yaml').
        """
        specified_format = self.options.get("format", "auto").lower()
        if specified_format != "auto":
            return specified_format

        file_path = self.options.get("file")
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".toml",):
                return "toml"
            if ext in (".yaml", ".yml"):
                return "yaml"
            if ext in (".json",):
                return "json"

        return self._heuristic_format_detection(raw_text)

    def _heuristic_format_detection(self, text: str) -> str:
        """Tries parsing as JSON, TOML, and YAML to infer data format.

        Args:
            text: Raw data text string.

        Returns:
            Format string ('json', 'toml', or 'yaml'). Defaults to 'yaml'.
        """
        with contextlib.suppress(Exception):
            if isinstance(json.loads(text), (list, dict)):
                return "json"

        with contextlib.suppress(Exception):
            if tomllib.loads(text):
                return "toml"

        with contextlib.suppress(Exception):
            if isinstance(yaml.safe_load(text), (list, dict)):
                return "yaml"

        return "yaml"

    def _parse_by_format(
        self, text: str, data_format: str
    ) -> tuple[Any, str | None]:
        """Parses raw text using target format parser (json, toml, yaml).

        Args:
            text: Raw data text string.
            data_format: Format identifier ('json', 'toml', or 'yaml').

        Returns:
            A tuple containing:
                - The parsed Python object (list or dict).
                - Error message string if parsing fails, otherwise None.
        """
        try:
            if data_format == "json":
                return json.loads(text), None
            if data_format == "toml":
                return tomllib.loads(text), None
            if data_format == "yaml":
                return yaml.safe_load(text), None
            return (
                None,
                f"Unsupported format '{data_format}'. Use 'json', 'yaml', or 'toml'.",
            )
        except Exception as err:
            return None, f"Failed to parse {data_format.upper()} data: {err}"

    def _normalize_parsed_data(self, data: Any) -> list[dict[str, Any]]:
        """Normalizes parsed object into a flat list of row dictionaries.

        Args:
            data: Parsed Python object resulting from JSON, TOML, or YAML parser.

        Returns:
            A list of dictionary objects representing table rows.
        """
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list) and all(isinstance(x, dict) for x in val):
                    return val
            return [data]

        return []

    # =========================================================================
    # Step 3: Table AST Node Construction
    # =========================================================================

    def _construct_table_node(
        self, rows: list[dict[str, Any]]
    ) -> tuple[nodes.table, nodes.Node | None]:
        """Constructs docutils table node including headers and row cells.

        Args:
            rows: List of row dictionary objects.

        Returns:
            A tuple containing:
                - Constructed docutils.nodes.table node.
                - An error node if column headers cannot be determined, otherwise None.
        """
        headers = self._resolve_column_headers(rows)
        if not headers:
            error_node = self.state_machine.reporter.error(
                "data-table: Could not determine headers from data.",
                line=self.lineno,
            )
            return nodes.table(), error_node

        table_node = nodes.table()
        table_node["classes"] += ["datatable"]

        tgroup = nodes.tgroup(cols=len(headers))
        table_node += tgroup

        for _ in headers:
            tgroup += nodes.colspec(colwidth=1)

        tgroup += self._build_header_row_node(headers)
        tgroup += self._build_body_row_nodes(headers, rows)

        return table_node, None

    def _resolve_column_headers(self, rows: list[dict[str, Any]]) -> list[str]:
        """Resolves column headers from explicit directive option or row dict keys.

        Args:
            rows: List of row dictionary objects.

        Returns:
            A list of column header strings.
        """
        headers_option = self.options.get("headers")
        if headers_option:
            return [h.strip() for h in headers_option.split(",") if h.strip()]

        headers: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in headers:
                    headers.append(key)
        return headers

    def _build_header_row_node(self, headers: list[str]) -> nodes.thead:
        """Builds docutils table header row node (thead).

        Args:
            headers: List of column header names.

        Returns:
            A docutils.nodes.thead element.
        """
        thead = nodes.thead()
        header_row = nodes.row()
        thead += header_row

        for header_name in headers:
            entry_node = nodes.entry()
            self._render_markdown_cell_content(str(header_name), entry_node)
            header_row += entry_node

        return thead

    def _build_body_row_nodes(
        self, headers: list[str], rows: list[dict[str, Any]]
    ) -> nodes.tbody:
        """Builds docutils table body rows node (tbody).

        Args:
            headers: List of column header names.
            rows: List of row dictionary objects.

        Returns:
            A docutils.nodes.tbody element.
        """
        tbody = nodes.tbody()

        for row_dict in rows:
            row_node = nodes.row()
            tbody += row_node
            for col_name in headers:
                entry_node = nodes.entry()
                cell_value = row_dict.get(col_name, "")
                if cell_value is None:
                    cell_value = ""
                self._render_markdown_cell_content(str(cell_value), entry_node)
                row_node += entry_node

        return tbody

    # =========================================================================
    # Step 4: Markdown Cell Rendering & Builder Line Break Handling
    # =========================================================================

    def _render_markdown_cell_content(
        self, cell_text: str, entry_node: nodes.entry
    ) -> None:
        """Parses Markdown cell text into AST nodes and appends to entry_node.

        Args:
            cell_text: Raw string content of a single table cell.
            entry_node: Target docutils.nodes.entry element to receive parsed nodes.
        """
        dedented_text = textwrap.dedent(cell_text).strip()
        if not dedented_text:
            return

        lines = dedented_text.splitlines()
        string_list = StringList(lines, source="datatable_cell")

        container = nodes.Element()
        self.state.nested_parse(string_list, 0, container)

        is_latex_builder = self._is_latex_builder_active()
        self._transform_line_breaks(container, is_latex=is_latex_builder)

        for child in container.children:
            entry_node += child

    def _is_latex_builder_active(self) -> bool:
        """Checks if current Sphinx build target is LaTeX.

        Returns:
            True if the current builder is 'latex', otherwise False.
        """
        env = getattr(self.state.document.settings, "env", None)
        if env and hasattr(env, "app") and hasattr(env.app, "builder"):
            return getattr(env.app.builder, "name", "") == "latex"
        return False

    def _transform_line_breaks(
        self, node: nodes.Node, is_latex: bool = False
    ) -> None:
        """Transforms in-cell line breaks for target builder (LaTeX vs HTML).

        Args:
            node: The docutils AST node to process recursively.
            is_latex: True if the current build target is LaTeX.
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
                if is_latex:
                    latex_break = nodes.raw("", r"\newline ", format="latex")
                    latex_break.parent = node
                    new_children.append(latex_break)
            elif isinstance(child, nodes.Text) and "\n" in child:
                modified = True
                parts = str(child).split("\n")
                for i, part in enumerate(parts):
                    clean_part = part.rstrip()
                    if clean_part:
                        text_node = nodes.Text(clean_part)
                        text_node.parent = node
                        new_children.append(text_node)
                    if i < len(parts) - 1:
                        if is_latex:
                            latex_break = nodes.raw("", r"\newline ", format="latex")
                            latex_break.parent = node
                            new_children.append(latex_break)
                        else:
                            html_break = nodes.raw("", "<br/>", format="html")
                            html_break.parent = node
                            new_children.append(html_break)
            else:
                self._transform_line_breaks(child, is_latex=is_latex)
                child.parent = node
                new_children.append(child)

        if modified:
            node.children = new_children
