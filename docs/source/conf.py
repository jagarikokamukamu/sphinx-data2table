# Configuration file for the Sphinx documentation builder.

import os
import sys
sys.path.insert(0, os.path.abspath('../../src'))

# -- Project information -----------------------------------------------------

project = 'sphinx-ext-dev'
copyright = '2026, Author'
author = 'Author'
release = '0.1.0'

# -- General configuration ---------------------------------------------------

extensions = [
    'myst_parser',
    'sphinx_data2table',
]

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

html_theme = 'alabaster'
html_static_path = ['_static']

# -- Options for LaTeX output ------------------------------------------------
latex_engine = 'lualatex'
latex_elements = {
    'fontpkg': r'\usepackage{luatexja-fontspec}',
}
