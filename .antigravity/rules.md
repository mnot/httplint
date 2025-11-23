# Project Rules

You are writing a Python library for linting HTTP messages. Adherence to the relevant standard specifications is paramount; avoid relying on sources like MDN unless the standard is ambiguous or out of date. Always refer to the most current version of each standard.


## Code Style

- Target all currently supported versions of Python.
- PEP8 style Python.
- 100 characters on a line, max.
- all imports need to be at the top of each file.
- All code should have type declarations.


## Tests

- All code additions and changes should have tests, using existing infrastructure where possible.
- Tests should reside in the same file as the code unless it is used in multiple files, in which case it should be separate.
- New test files in `test/` should be added as a target in the Makefile and invoked by `make test`.

## Workflow

For each code change:

1. Typecheck by running `make typecheck`
2. Lint by running `make lint`
3. Test by running `make test`
4. Format by running `make tidy` (this can fix line length issues and trailing whitespace)

If you need to run a Python interpreter, use `.venv/bin/python`.

Note that `make` targets automatically use the virtual environment, so you don't need to activate it explicitly.

## Notes

- Common notes used by multiple fields should be in `httplint/field/notes.py`.
- Field-specific notes should be defined in the parser file for that field (e.g., `httplint/field/parsers/cache_control.py`).
- The _summary field of a Note is plain text and should be reasonably short.
- The _text field of a Note is markdown. That means it should NOT be indented.