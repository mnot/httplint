# Contributing to httplint

Contributions - in the form of code, bugs, or ideas - are very welcome!

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Setting up a Development Environment](#setting-up-a-development-environment)
- [Coding Conventions](#coding-conventions)
- [Before you Submit](#before-you-submit)
- [Common Tasks](#common-tasks)
  - [Adding a New Field Handler](#adding-a-new-field-handler)
    - [The _HttpField_ Class](#the-_httpfield_-class)
    - [The _parse_ method](#the-_parse_-method)
    - [The _evaluate_ method](#the-_evaluate_-method)
    - [The _message_ instance variable](#the-_message_-instance-variable)
    - [Creating Notes](#creating-notes)
    - [Writing Tests](#writing-tests)
- [Intellectual Property](#intellectual-property)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->


## Setting up a Development Environment

It should be possible to use modern Unix-like environment, provided that a recent release of Python is installed.

Thanks to [Makefile.venv](https://github.com/sio/Makefile.venv), a Python virtual environment is set up and run each time you use `make`. As long as you use `make`, Python dependencies will be installed automatically.

Helpful make targets include:

* `make shell` - start a shell in the Python virtual environment
* `make python` - start an interactive Python interpreter in the virtual environment
* `make lint` - run pylint with httplint-specific configuration
* `make typecheck` - run mypy to check Python types
* `make tidy` - format Python source
* `make test` - run the tests

You can run the tests in an individual `field/parsers/foo_bar.py` file by running `make test_field_foo_bar`.


## Coding Conventions

* All user-visible strings need to be internationalised; see `TRANSLATION.md`.
* Every new field and every new `Note` should have a test covering it.
* All Python functions and methods need to have type annotations. See `pyproject.toml` for specific pylint and mypy settings.


## Before you Submit

The best way to submit a change is through a pull request. A few things to keep in mind when you're doing so:

* Run `make tidy`.
* Check your code with `make lint` and address any issues found.
* Check your code with `make typecheck` and address any issues found.

If you're not sure how to dig in, feel free to ask for help, or sketch out an idea in an issue first.


## Common Tasks


### Adding a New Field Handler

The `httplint/field/parser` directory contains field handlers for httplint. They parse and check field values, set any field-specific notes that are appropriate, and join the values together in a data structure that represents the field.

Note that not all checks are in these files; ones that require coordination between several fields' values, for example, belong in a separate type of check (as cache testing is done, in _cache.py_). This is because fields can come in any order, so you can't be sure that another field's value will be available when your parser runs.

It's pretty easy to add support for new fields. To start, fork the source and add a new file into
the `parsers` directory, whose name corresponds to the field's name, but in all lowercase, and
with special characters (most commonly, _-_) transposed to an underscore.

For example, if your field's name is `Foo-Example`, the appropriate filename is `foo_example.py`.

If your field name doesn't work with this convention, please raise an issue.

The easiest way to get started is to copy `httplint/field/parsers/field.tpl` to your new file.

class vary(HttpField):
    canonical_name = "Vary"
    description = """..."""
    reference = f"{rfc9110.SPEC_URL}#field.vary"
    syntax = rfc9110.Vary
    valid_in_requests = False
    valid_in_responses = True
~~~

When using `HttpField`:
- `parse` is called for each individual value in the list (separated by commas).
- `value` (the property accessed in `evaluate`) is a list of the results of calling `parse`.
- `syntax` (if provided) is checked against each individual value in the list.

#### The _SingletonField_ Class

If the header you are adding strictly allows only one value (e.g., `Age`, `Date`), it should inherit from `httplint.field.singleton_field.SingletonField` (which itself inherits from `HttpField`).

`SingletonField` has no additional instance variables, but it alters how `parse` and `evaluate` work.

When using `SingletonField`:
- `parse` is called once for the entire field value.
- `value` (the property accessed in `evaluate`) is a single value, representing the first call to `parse`.
- `syntax` (if provided) is checked against the entire value.
- If the field is repeated in a message, it will be flagged with a `SINGLE_HEADER_REPEAT` note and only the first value will be used.

For example, a `SingletonField` like `Age` starts with:

~~~ python
class age(SingletonField):
    canonical_name = "Age"
    description = """\
The `Age` response header conveys the sender's estimate of the amount of time since the response
(or its validation) was generated at the origin server."""
    reference = f"{rfc9111.SPEC_URL}#field.age"
    syntax = False  # rfc9111.Age
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
~~~

#### The _StructuredField_ Class

If the header you are adding is a [Structured Field](https://www.rfc-editor.org/rfc/rfc8941.html), it should inherit from `httplint.field.structured_field.StructuredField` (which itself inherits from `HttpField`).

`StructuredField` has one additional instance variable:

* `sf_type` - string, the type of Structured Field (`item`, `list`, or `dictionary`). _required_

When using `StructuredField`, you do not need to provide a `syntax` regex or implement a `parse` method; the base class handles parsing using the `http_sf` library.

For example, a `StructuredField` like `Cache-Status` starts with:

~~~ python
class cache_status(StructuredField):
    canonical_name = "Cache-Status"
    reference = "https://www.rfc-editor.org/rfc/rfc9211.html"
    description = """..."""
    valid_in_requests = False
    valid_in_responses = True
    sf_type = "list"
~~~


#### The _parse_ method

The _parse_ method is called with two arguments, `field_value` and `add_note`, for each field line
in the message. In other words, in this message:

~~~
Foo: a
Foo: b
Bar: 1, 2, 3
Baz: "def, ghi"
~~~

_parse_ will be called twice for `Foo` (once with the `field_value` _a_ and once with _b_) and once
for `Bar` and once for `Baz` (with the `field_value`s _1, 2, 3_ and _"def, ghi"_ respectively).

_parse_ should return the parsed value corresponding to the `field_value`. If there is an error and
the value shouldn't be remembered, raise `ValueError`.

When using `HttpField`, _parse_ will be called for each _item_ in the list, after separating on commas (excepting those inside quoted strings). In the example above, if `Bar` were a `HttpField`, _parse_ would be called three times for `Bar` (with the `field_value`s _1_, _2_, and _3_), but still only once for `Baz`.

Note that `syntax` is checked against each item before _parse_ is called in a `HttpField`.

communicate something about the field_value. It returns the created _Note_ instance.

_parse_ should return the parsed value corresponding to the `field_value`. If there is an error and
the value shouldn't be remembered, raise `ValueError`.


#### The _evaluate_ method

_evaluate_ is called with one argument, `add_note`. As above, it allows setting _Note_s about the
complete field.

_evaluate_ is called once all of the field lines are processed, to enable the entire set of the
field's values to be considered. To access the parsed value(s), use the _value_ instance
variable.

_evaluate_ is called once all of the field lines are processed, to enable the entire set of the
field's values to be considered. To access the parsed value(s), use the _value_ instance
variable.

When using `HttpField`, _value_ is a list of the results of calling _parse_. When using `SingletonField`, it is a single value, representing the first call to _parse_.


#### The _post_check_ method

_post_check_ is called with two arguments, `message` (the message linter instance) and `add_note`.

It is called after the entire message has been processed, including the body and other post-parsing steps (like checking for cacheability). This is the appropriate place for checks that rely on the state of the message derived from other fields or the body.

Note that if `message.no_content` is set, the body will not be processed, so checks relying on it should be skipped.


#### The _message_ instance variable

Some checks may need to access other parts of the message; for example, the HTTP status code. You
can access the `httplint.message` instance that the field is part of using the _message_ instance
variable.


#### Creating Notes

Field checkers report their results using _Note_s.

The `_summary` field of a Note is plain text and should be reasonably short (e.g., about one line of text). In REDbot, it's what's displayed in the "Notes" section of the results.

The `_text` field of a Note is markdown. That means it should NOT be indented. In REDbot, it's what's displayed when you hover over the summary.

Common notes used by multiple fields should be in `httplint/field/notes.py`. When possible, bias towards emitting a single note for a condition with details in `_text`, rather than creating multiple notes.

When reporting a syntax error, prefer `BAD_SYNTAX_DETAILED` over `BAD_SYNTAX` if you can provide the specific value that failed and the reason why. `BAD_SYNTAX_DETAILED` takes `value` and `problem` arguments to populate the note details.

Notes can also have child notes (sub-notes) attached to them. To do so, call `add_child` on the
parent note instance (returned by `add_note`). `add_child` takes the Note class and any variables
as arguments; the subject and other variables are inherited from the parent note.

~~~ python
parent_note = add_note(MY_NOTE)
parent_note.add_child(MY_SUB_NOTE)
~~~


#### Writing Tests

Each field definition should also include tests, as subclasses of
`httplint.field.tests.FieldTest`. It expects the following class properties:

* `name` - the field field-name
* `inputs` - a list of field field-values, one item per line.
    E.g., `[b"foo", b"foo, bar"]`
* `expected_out` - the data structure that _parse_ should return, given
    the inputs
* `expected_notes` - a list of `httplint.note.Note` classes that are expected
    to be set with `add_note` when parsing the inputs

You can create any number of tests this way; they will be run automatically when
_tests/test\_fields.py_ is run.


## Intellectual Property

By contributing code, bugs or enhancements to this project (whether that be through pull requests, the issues list, e-mail or other means), you are licensing your contribution under the [project's terms](LICENSE.md).

