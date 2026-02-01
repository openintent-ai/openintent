# Contributing to OpenIntent SDK

Thank you for your interest in contributing to the OpenIntent Python SDK! This document provides guidelines for contributing.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/openintent-ai/openintent-sdk-python.git
   cd openintent-sdk-python
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Code Style

We use the following tools for code quality:

- **Black** for code formatting
- **Ruff** for linting
- **mypy** for type checking

Before submitting a PR, run:

```bash
black openintent/
ruff check openintent/ --fix
mypy openintent/
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=openintent --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

## Pull Request Process

1. **Fork the repository** and create your branch from `main`
2. **Add tests** for any new functionality
3. **Update documentation** if you're changing public APIs
4. **Run the full test suite** and ensure it passes
5. **Update CHANGELOG.md** with your changes
6. **Submit a pull request** with a clear description

## Commit Messages

Follow conventional commit format:

```
feat: add lease renewal support
fix: handle empty state updates
docs: update async usage examples
test: add validation tests
chore: update dependencies
```

## Adding New Features

When adding new features:

1. Check if the feature aligns with an OpenIntent RFC
2. Add type hints to all public functions
3. Add docstrings with examples
4. Add validation where appropriate
5. Add tests for both sync and async clients

## Reporting Issues

When reporting issues, please include:

- Python version
- SDK version
- Minimal code example to reproduce
- Expected vs actual behavior
- Full error traceback if applicable

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## Questions?

Open an issue or reach out at [contributors@openintent.ai](mailto:contributors@openintent.ai).
