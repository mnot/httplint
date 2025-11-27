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

## Translation
.PHONY: extract_messages
extract_messages: venv
	PYTHONPATH=. $(VENV)/pybabel extract -F tools/i18n/babel.cfg -o tools/i18n/data/messages.pot .

.PHONY: update_po
update_po: extract_messages
	$(VENV)/pybabel update -i tools/i18n/data/messages.pot -d httplint/translations

.PHONY: apply_memory
apply_memory: venv
	$(VENV)/python -m tools.i18n.apply --locale_dir httplint/translations

.PHONY: save_memory
save_memory: venv
	$(VENV)/python -m tools.i18n.extract --locale_dir httplint/translations

.PHONY: autotranslate
autotranslate: venv
	$(VENV)/python -m tools.i18n.autotranslate --locale_dir httplint/translations --model $(or $(MODEL),gemini-2.5-flash-lite) --rpm $(or $(RPM),15)

.PHONY: compile_translations
compile_translations: venv
	$(VENV)/pybabel compile -d httplint/translations

.PHONY: translations
translations: update_po apply_memory compile_translations

.PHONY: init_locale
init_locale: venv
	@if [ -z "$(LOCALE)" ]; then echo "Usage: make init_locale LOCALE=xx"; exit 1; fi
	$(VENV)/pybabel init -i tools/i18n/data/messages.pot -d httplint/translations -l $(LOCALE)



include Makefile.pyproject
