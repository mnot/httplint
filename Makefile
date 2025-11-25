PROJECT = httplint
VERSIONING = calver

GITHUB_STEP_SUMMARY ?= throwaway

TEST_SCRIPTS = $(wildcard test/test_*.py)
TEST_TARGETS = $(patsubst test/%.py,%,$(TEST_SCRIPTS))

.PHONY: test
test: $(TEST_TARGETS) test_smoke

.PHONY: test_fields
test_fields: test/http-fields.xml venv
	PYTHONPATH=. $(VENV)/python test/test_fields.py test/http-fields.xml
	PYTHONPATH=. $(VENV)/pytest --md $(GITHUB_STEP_SUMMARY) -k "not FieldTest" --config-file pyproject.toml
	rm -f throwaway

test_field_%: venv
	PYTHONPATH=. $(VENV)/pytest -k "not FieldTest" httplint/field/parsers/$*.py

test_%: venv
	PYTHONPATH=. $(VENV)/python test/$@.py

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
	curl -si $(URL_ARGS) | $(VENV)/httplint --now

include Makefile.pyproject
