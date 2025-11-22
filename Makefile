PROJECT = httplint
VERSIONING = calver

GITHUB_STEP_SUMMARY ?= throwaway

.PHONY: test
test: test_syntax test_fields test_notes test_messages test_status test_cache test_smoke

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

.PHONY: test_status
test_status: venv
	PYTHONPATH=. $(VENV)/python test/test_status.py

.PHONY: test_cache
test_cache: venv
	PYTHONPATH=. $(VENV)/python test/test_cache.py

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

# Pass arguments to the url target
ifeq (url,$(firstword $(MAKECMDGOALS)))
  URL_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  .DEFAULT: ; @:
endif

.PHONY: url
url: venv
	curl -si $(URL_ARGS) | $(VENV)/httplint

include Makefile.pyproject
