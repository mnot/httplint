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

.PHONY: update_readme
update_readme: venv
	PYTHONPATH=. $(VENV)/python test/update_readme.py

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

###############################################################################
## i18n

.PHONY: i18n-extract
i18n-extract: venv
	PYTHONPATH=. $(VENV)/pybabel extract -F tools/i18n/babel.cfg -o httplint/translations/messages.pot .

.PHONY: i18n-update
i18n-update: i18n-extract
	$(VENV)/pybabel update -i httplint/translations/messages.pot -d httplint/translations

.PHONY: i18n-autotranslate
i18n-autotranslate: venv
	$(VENV)/python -m tools.i18n.autotranslate --locale_dir httplint/translations --model $(or $(MODEL),gemini-2.5-flash-lite) --rpm $(or $(RPM),15)

.PHONY: i18n-compile
i18n-compile: venv
	$(VENV)/pybabel compile -d httplint/translations

.PHONY: translations
translations: i18n-update i18n-compile

.PHONY: i18n-init
i18n-init: venv
	@if [ -z "$(LOCALE)" ]; then echo "Usage: make init_locale LOCALE=xx"; exit 1; fi
	$(VENV)/pybabel init -i httplint/translations/messages.pot -d httplint/translations -l $(LOCALE)

###############################################################################


include Makefile.pyproject
