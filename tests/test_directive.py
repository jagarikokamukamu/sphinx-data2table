"""Unit test suite for sphinx_data2table package and DataTableDirective."""

from __future__ import annotations

from unittest.mock import MagicMock

from docutils import nodes
from docutils.frontend import get_default_settings
from docutils.parsers.rst import Parser, directives
from docutils.utils import new_document

from sphinx_data2table import __version__, setup
from sphinx_data2table.directive import DataTableDirective


def parse_rst_with_datatable(rst_content: str) -> nodes.document:
    """Helper function to parse an RST string.

    Args:
        rst_content: RST string content.

    Returns:
        Docutils document AST.
    """
    directives.register_directive("data-table", DataTableDirective)
    directives.register_directive("datatable", DataTableDirective)
    parser = Parser()
    settings = get_default_settings(Parser)  # type: ignore[arg-type]
    doc = new_document("test.rst", settings)
    parser.parse(rst_content, doc)
    return doc


def test_sphinx_extension_setup():
    """Tests the Sphinx extension setup entry point function."""
    mock_app = MagicMock()
    metadata = setup(mock_app)

    assert metadata["version"] == __version__
    assert metadata["parallel_read_safe"] is True
    assert metadata["parallel_write_safe"] is True
    assert mock_app.add_directive.call_count == 2


def test_json_inline_datatable():
    """Tests parsing JSON inline content into a table."""
    rst = """
.. data-table::
   :format: json

   [
     {"name": "**JSON Alpha**", "desc": "First item with `code`"},
     {"name": "*JSON Beta*", "desc": "Second item"}
   ]
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1

    table = tables[0]
    thead = list(table.findall(nodes.thead))[0]
    headers = [node.astext() for node in thead.findall(nodes.entry)]
    assert headers == ["name", "desc"]

    tbody = list(table.findall(nodes.tbody))[0]
    rows = list(tbody.findall(nodes.row))
    assert len(rows) == 2


def test_yaml_inline_datatable():
    """Tests parsing YAML inline content into a table."""
    rst = """
.. datatable::
   :format: yaml

   - name: "**Alpha**"
     desc: "First item with `code`"
   - name: "*Beta*"
     desc: "Second item"
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1

    table = tables[0]
    thead = list(table.findall(nodes.thead))[0]
    headers = [node.astext() for node in thead.findall(nodes.entry)]
    assert headers == ["name", "desc"]

    tbody = list(table.findall(nodes.tbody))[0]
    rows = list(tbody.findall(nodes.row))
    assert len(rows) == 2


def test_toml_inline_datatable():
    """Tests parsing TOML inline content into a table."""
    rst = """
.. data-table::
   :format: toml

   [[items]]
   name = "TOML Item 1"
   val = "100"

   [[items]]
   name = "TOML Item 2"
   val = "200"
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1

    table = tables[0]
    tbody = list(table.findall(nodes.tbody))[0]
    rows = list(tbody.findall(nodes.row))
    assert len(rows) == 2


def test_format_auto_detection():
    """Tests format auto detection for JSON, TOML, and YAML."""
    rst_json = """
.. data-table::

   [{"col": "val"}]
"""
    doc = parse_rst_with_datatable(rst_json)
    assert len(list(doc.findall(nodes.table))) == 1

    rst_yaml = """
.. data-table::

   - col: val
"""
    doc_y = parse_rst_with_datatable(rst_yaml)
    assert len(list(doc_y.findall(nodes.table))) == 1


def test_custom_headers_option():
    """Tests custom :headers: option overriding dict keys."""
    rst = """
.. data-table::
   :format: yaml
   :headers: CustomA, CustomB

   - key1: "Val1"
     key2: "Val2"
"""
    doc = parse_rst_with_datatable(rst)
    table = list(doc.findall(nodes.table))[0]
    thead = list(table.findall(nodes.thead))[0]
    headers = [node.astext() for node in thead.findall(nodes.entry)]
    assert headers == ["CustomA", "CustomB"]


def test_external_file_option(tmp_path):
    """Tests reading data from external file via :file: option."""
    yaml_file = tmp_path / "data.yaml"
    yaml_file.write_text("- name: External\n  val: 42\n", encoding="utf-8")

    rst = f"""
.. data-table::
   :file: {yaml_file}
"""
    doc = parse_rst_with_datatable(rst)
    table = list(doc.findall(nodes.table))[0]
    assert len(list(table.findall(nodes.row))) == 2


def test_missing_file_error():
    """Tests error handling for non-existent file."""
    rst = """
.. data-table::
   :file: non_existent_file_path_xyz.yaml
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) > 0
    assert "Could not read file" in errors[0].astext()


def test_empty_content_and_file_error():
    """Tests error handling when neither content nor :file: is provided."""
    rst = """
.. data-table::
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) > 0
    assert "Neither content nor ':file:'" in errors[0].astext()


def test_invalid_syntax_error():
    """Tests error reporting when data contains invalid syntax."""
    rst = """
.. data-table::
   :format: json

   {invalid json content
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) > 0
    assert "Failed to parse JSON" in errors[0].astext()


def test_empty_data_warning():
    """Tests warning generation when data parses to empty or invalid list."""
    rst = """
.. data-table::
   :format: yaml

   "just a string"
"""
    doc = parse_rst_with_datatable(rst)
    warnings = list(doc.findall(nodes.system_message))
    assert len(warnings) > 0
    assert "Data is empty or invalid format" in warnings[0].astext()


def test_in_cell_newline_replacement():
    """Tests in-cell newline replacement logic for LaTeX and HTML builders."""
    mock_directive = object.__new__(DataTableDirective)

    # Test HTML builder path (br tag inserted, no \newline leak)
    container_html = nodes.Element()
    container_html += nodes.Text("Line 1\nLine 2")
    DataTableDirective._transform_line_breaks(
        mock_directive, container_html, is_latex=False
    )
    raw_html = list(container_html.findall(nodes.raw))
    assert len(raw_html) == 1
    assert raw_html[0].get("format") == "html"
    assert "<br/>" in raw_html[0].astext()
    assert not any(r.astext().strip() == r"\newline" for r in raw_html)

    # Test LaTeX builder path (\newline inserted)
    container_latex = nodes.Element()
    container_latex += nodes.Text("Line 1\nLine 2")
    DataTableDirective._transform_line_breaks(
        mock_directive, container_latex, is_latex=True
    )
    raw_latex = list(container_latex.findall(nodes.raw))
    assert len(raw_latex) == 1
    assert raw_latex[0].get("format") == "latex"
    assert r"\newline" in raw_latex[0].astext()
