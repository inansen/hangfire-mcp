# Contributing to Hangfire MCP

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/inansen/hangfire-mcp.git
cd hangfire-mcp
python setup.py
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -v
```

## Code Style

- Follow PEP 8
- Use type hints for function signatures
- Keep functions focused and small

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit with a clear message: `git commit -am "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Include Python version and OS
- Include relevant error messages

## Adding New MCP Tools

1. Add the database query in `src/hangfire_mcp/database.py`
2. Add the tool definition and handler in `src/hangfire_mcp/server.py`
3. Add a dashboard view in `src/hangfire_mcp/dashboard.py` (if applicable)
4. Update `README.md` with the new tool

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
