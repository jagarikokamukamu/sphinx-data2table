# Contributing to sphinx-data2table

Thank you for your interest in contributing to `sphinx-data2table`!

## Architecture & Code Design Guidelines

When implementing features or refactoring components in this codebase, please refer to and follow these standard reference guides:

- **Refactoring Catalog**: [Refactoring.Guru Catalog](https://refactoring.guru/ja/refactoring/catalog)
- **Python Style Guide**: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

### Key Development Principles
- **Self-Documenting Code**: Favor clear naming, clear function signatures, and decoupled class structures over redundant comments.
- **Single Responsibility (SRP)**: Keep classes and functions focused on a single responsibility.
- **Immutability & Early Returns**: Avoid mutable control flags (`modified = True`) and handle errors immediately with guard clauses.
- **Google Style Docstrings**: Write clear Google Style Python Docstrings (`Args:`, `Returns:`) for major classes and functions.
