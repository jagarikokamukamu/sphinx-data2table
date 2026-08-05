# sphinx-data2table

Sphinx extension to render TOML, YAML, or JSON data as HTML/LaTeX tables with Markdown cell parsing.

## Installation & Setup

```bash
uv add sphinx-data2table  # or pip install sphinx-data2table
```

`conf.py`:
```python
extensions = ["sphinx_data2table"]
```

## Usage

Use the `data-table` directive (alias `datatable` is also supported).

### Inline Data Example

```rst
.. data-table::
   :format: yaml

   - Feature: "**Markdown Support**"
     Details: "Supports **bold**, [links](https://example.com), and more inside cells."

   - Feature: "List Support"
     Details: |
       - Item A
       - Item B
```

### Loading External File

```rst
.. data-table::
   :file: path/to/data.yaml
```

## Options

- `:file:` Path to the external data file
- `:format:` Data format specifier (`yaml`, `toml`, `json`, `auto`)
- `:headers:` Comma-separated column headers to display
