PROJECT = httplint
VERSIONING = calver

GITHUB_STEP_SUMMARY ?= throwaway

.PHONY: test
test: test_syntax test_fields test_notes test_messages test_smoke

.PHONY: test_syntax
test_syntax: venv
	PYTHONPATH=. $(VENV)/python test/test_syntax.py

.PHONY: test_fields
test_fields: test/http-fields.xml venv
	PYTHONPATH=. $(VENV)/python test/test_fields.py test/http-fields.xml

.PHONY: test_notes
test_notes: venv
	PYTHONPATH=. $(VENV)/python test/test_notes.py

.PHONY: test_messages
test_messages: venv
	$(VENV)/pytest --md $(GITHUB_STEP_SUMMARY) -k "not FieldTest" --config-file pyproject.toml
	rm -f throwaway

.PHONY: test_smoke
test_smoke: venv
	PYTHONPATH=. $(VENV)/python test/smoke.py

test/http-fields.xml:
	curl -o $@ https://www.iana.org/assignments/http-fields/http-fields.xml

.PHONY: clean
clean: clean_py

.PHONY: lint
lint: lint_py

.PHONY: typecheck
typecheck: typecheck_py

.PHONY: tidy
tidy: tidy_py

.PHONY: run
run: lint typecheck tidy


include Makefile.pyproject
