PROJECT = httplint


.PHONY: test
test: test/http-fields.xml
	PYTHONPATH=. $(VENV)/python test/test_syntax.py
	PYTHONPATH=. $(VENV)/python test/test_fields.py test/http-fields.xml

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



include Makefile.pyproject
