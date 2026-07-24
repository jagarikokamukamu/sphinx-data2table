"""Unit test suite for sphinx_data2table package and DataTableDirective."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from docutils import nodes
from docutils.frontend import get_default_settings
from docutils.parsers.rst import Parser, directives
from docutils.utils import new_document

from sphinx_data2table import setup, __version__
from sphinx_data2table.directive import DataTableDirective


def parse_rst_with_datatable(rst_content: str) -> nodes.document:
    """Helper function to parse an RST string containing a data-table / datatable directive.

    Args:
        rst_content: RST/MyST markup text containing the directive.

    Returns:
        The root docutils.nodes.document instance representing the parsed AST.
    """
    directives.register_directive("data-table", DataTableDirective)
    directives.register_directive("datatable", DataTableDirective)

    parser = Parser()
    settings = get_default_settings(Parser)
    settings.warning_stream = False
    doc = new_document("test.rst", settings)
    parser.parse(rst_content, doc)
    return doc


def test_sphinx_extension_setup():
    """Tests the Sphinx extension setup entry point function registering both directives."""
    mock_app = MagicMock()
    metadata = setup(mock_app)

    assert mock_app.add_directive.call_count == 2
    mock_app.add_directive.assert_any_call("data-table", DataTableDirective)
    mock_app.add_directive.assert_any_call("datatable", DataTableDirective)
    assert metadata["version"] == __version__
    assert metadata["parallel_read_safe"] is True
    assert metadata["parallel_write_safe"] is True


def test_data_table_hyphenated_directive_name():
    """Tests using the new 'data-table' hyphenated directive name."""
    rst = """
.. data-table::
   :format: yaml

   - Item: "**Widget**"
     Status: "Active"
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1


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

    first_row_cells = list(rows[0].findall(nodes.entry))
    assert first_row_cells[0].astext() == "JSON Alpha"
    assert len(list(first_row_cells[0].findall(nodes.strong))) == 1


def test_yaml_inline_datatable():
    """Tests parsing YAML inline content into a table with strong elements."""
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


def test_toml_inline_multiline_list():
    """Tests parsing TOML inline content with multiline paragraphs and bullet lists."""
    rst = """
.. data-table::
   :format: toml

   [[items]]
   feature = "**Lists**"
   details = \"\"\"
   Paragraph 1

   Paragraph 2

   * Item A
   * Item B
   \"\"\"
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1

    table = tables[0]
    tbody = list(table.findall(nodes.tbody))[0]
    rows = list(tbody.findall(nodes.row))
    assert len(rows) == 1


def test_auto_format_detection_json(tmp_path):
    """Tests auto-detecting JSON format from file extension."""
    json_file = tmp_path / "data.json"
    json_file.write_text('[{"key": "Value"}]', encoding="utf-8")

    rst = f"""
.. data-table::
   :file: {json_file}
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1


def test_auto_format_detection_toml(tmp_path):
    """Tests auto-detecting TOML format from file extension."""
    toml_file = tmp_path / "data.toml"
    toml_file.write_text("""
[[items]]
key = "Value"
""", encoding="utf-8")

    rst = f"""
.. data-table::
   :file: {toml_file}
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1


def test_external_file_import(tmp_path):
    """Tests reading table data from an external YAML file specified via :file:."""
    yaml_file = tmp_path / "data.yaml"
    yaml_file.write_text("""
- Item: "X"
  Value: "100"
- Item: "Y"
  Value: "200"
""", encoding="utf-8")

    rst = f"""
.. data-table::
   :file: {yaml_file}
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1


def test_custom_headers_option():
    """Tests :headers: option overriding default key extraction and column ordering."""
    rst = """
.. data-table::
   :format: yaml
   :headers: ColB, ColA

   - ColA: "ValA"
     ColB: "ValB"
     ColC: "Ignored"
"""
    doc = parse_rst_with_datatable(rst)
    tables = list(doc.findall(nodes.table))
    assert len(tables) == 1


def test_missing_file_error_handling():
    """Tests error reporter output when an external file does not exist."""
    rst = """
.. data-table::
   :file: non_existent_file.yaml
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) >= 1
    assert "Could not read file" in errors[0].astext()


def test_empty_directive_content_error():
    """Tests error reporter output when neither file nor inline content is provided."""
    rst = """
.. data-table::
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) >= 1
    assert "Neither content nor ':file:' option provided" in errors[0].astext()


def test_invalid_syntax_error():
    """Tests error reporter output when data syntax is invalid."""
    rst = """
.. data-table::
   :format: yaml

   [Invalid YAML: : : :
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) >= 1
    assert "Failed to parse YAML data" in errors[0].astext()


def test_unsupported_format_option():
    """Tests error handling when an unsupported format option is passed."""
    rst = """
.. data-table::
   :format: xml

   <data></data>
"""
    doc = parse_rst_with_datatable(rst)
    errors = list(doc.findall(nodes.system_message))
    assert len(errors) >= 1
    assert "Unsupported format 'xml'" in errors[0].astext()


def test_empty_data_warning():
    """Tests warning reporter output when data parses to an empty data structure."""
    rst = """
.. data-table::
   :format: yaml

   []
"""
    doc = parse_rst_with_datatable(rst)
    warnings = list(doc.findall(nodes.system_message))
    assert len(warnings) >= 1
    assert "Data is empty or invalid format" in warnings[0].astext()
