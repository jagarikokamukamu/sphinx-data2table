"""Directive implementation for rendering TOML, YAML, and JSON tables."""

from __future__ import annotations

import contextlib
import json
import os
import textwrap
import tomllib
from typing import Any, TypeGuard

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


class TableAstBuilder:
    """Handles docutils table AST node construction and Markdown cell rendering."""

    def __init__(self, directive: Directive) -> None:
        self.directive = directive

    def build(
        self, rows: list[dict[str, Any]]
    ) -> tuple[nodes.table, nodes.Node | None]:
        """Constructs docutils table node containing column headers and row cells.

        Returns:
            A tuple containing constructed table node and an optional error node.
        """
        headers = self._resolve_headers(rows)
        if not headers:
            error_node = self.directive.state_machine.reporter.error(
                "data-table: Could not determine headers from data.",
                line=self.directive.lineno,
            )
            return nodes.table(), error_node

        table_node = nodes.table()
        table_node["classes"] += ["datatable"]

        tgroup = nodes.tgroup(cols=len(headers))
        table_node += tgroup

        for _ in headers:
            tgroup += nodes.colspec(colwidth=1)

        tgroup += self._build_thead(headers)
        tgroup += self._build_tbody(headers, rows)

        return table_node, None

    def _resolve_headers(self, rows: list[dict[str, Any]]) -> list[str]:
        """Resolves headers from explicit option or row dictionary keys."""
        headers_option = self.directive.options.get("headers")
        if headers_option:
            return [h.strip() for h in headers_option.split(",") if h.strip()]

        headers: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in headers:
                    headers.append(key)
        return headers

    def _build_thead(self, headers: list[str]) -> nodes.thead:
        """Constructs docutils table header row (thead)."""
        thead = nodes.thead()
        header_row = nodes.row()
        thead += header_row

        for header_name in headers:
            entry_node = nodes.entry()
            self._render_cell_markdown(str(header_name), entry_node)
            header_row += entry_node

        return thead

    def _build_tbody(
        self, headers: list[str], rows: list[dict[str, Any]]
    ) -> nodes.tbody:
        """Constructs docutils table body rows (tbody)."""
        tbody = nodes.tbody()

        for row_dict in rows:
            row_node = nodes.row()
            tbody += row_node
            for col_name in headers:
                entry_node = nodes.entry()
                cell_value = row_dict.get(col_name, "")
                if cell_value is None:
                    cell_value = ""
                self._render_cell_markdown(str(cell_value), entry_node)
                row_node += entry_node

        return tbody

    def _render_cell_markdown(self, cell_text: str, entry_node: nodes.entry) -> None:
        """Parses cell Markdown text into AST nodes and attaches to entry_node."""
        dedented_text = textwrap.dedent(cell_text).strip()
        if not dedented_text:
            return

        lines = dedented_text.splitlines()
        string_list = StringList(lines, source="datatable_cell")

        container = nodes.Element()
        self.directive.state.nested_parse(string_list, 0, container)

        is_latex = self._is_latex_builder()
        self._transform_line_breaks(container, is_latex=is_latex)

        for child in container.children:
            entry_node += child

    @property
    def _builder_name(self) -> str:
        """Safely extracts Sphinx builder name."""
        with contextlib.suppress(AttributeError):
            return self.directive.state.document.settings.env.app.builder.name
        return ""

    def _is_latex_builder(self) -> bool:
        """Checks if current Sphinx builder is LaTeX."""
        return self._builder_name == "latex"

    def _create_break_node(self, is_latex: bool) -> nodes.raw:
        """Creates target builder raw line break node."""
        if is_latex:
            return nodes.raw("", r"\newline ", format="latex")
        return nodes.raw("", "<br/>", format="html")

    def _is_latex_line_break_raw_node(self, node: nodes.Node) -> bool:
        """Checks if node is a raw LaTeX line break node."""
        return (
            isinstance(node, nodes.raw)
            and node.get("format") == "latex"
            and node.astext().strip() in ("\\\\", r"\\")
        )

    def _is_multiline_text_node(self, node: nodes.Node) -> TypeGuard[nodes.Text]:
        """TypeGuard checking if node is a Text node containing newlines."""
        return isinstance(node, nodes.Text) and "\n" in str(node)

    def _split_text_with_line_breaks(
        self, text_node: nodes.Text, is_latex: bool
    ) -> list[nodes.Node]:
        """Splits multiline text node into text fragments and break nodes."""
        parts = str(text_node).split("\n")
        new_nodes: list[nodes.Node] = []

        for i, part in enumerate(parts):
            clean_part = part.rstrip()
            if clean_part:
                new_nodes.append(nodes.Text(clean_part))
            if i < len(parts) - 1:
                new_nodes.append(self._create_break_node(is_latex))

        return new_nodes

    def _transform_line_breaks(self, node: nodes.Node, is_latex: bool = False) -> None:
        """Transforms in-cell line breaks recursively."""
        transformed_children: list[nodes.Node] = []

        for child in list(node.children):
            if self._is_latex_line_break_raw_node(child):
                break_node = self._create_break_node(is_latex=True)
                break_node.parent = node
                transformed_children.append(break_node)
            elif self._is_multiline_text_node(child):
                split_nodes = self._split_text_with_line_breaks(child, is_latex)
                for sub_node in split_nodes:
                    sub_node.parent = node
                    transformed_children.append(sub_node)
            else:
                self._transform_line_breaks(child, is_latex=is_latex)
                child.parent = node
                transformed_children.append(child)

        if node.children != transformed_children:
            node.children = transformed_children


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
        data_text, load_error = DataLoader(self).load()
        if load_error:
            return [load_error]

        rows, parse_error = DataParser(self).parse(data_text)
        if parse_error:
            return [parse_error]

        table_node, build_error = TableAstBuilder(self).build(rows)
        if build_error:
            return [build_error]

        return [table_node]
