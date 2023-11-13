# Contributing to httplint

Contributions - in the form of code, bugs, or ideas - are very welcome!

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Intellectual Property](#intellectual-property)
- [Coding Conventions](#coding-conventions)
- [Setting up a Development Environment](#setting-up-a-development-environment)
- [Before you Submit](#before-you-submit)
- [Common Tasks](#common-tasks)
  - [Adding a New Field Handler](#adding-a-new-field-handler)
    - [The _HttpField_ Class](#the-_httpfield_-class)
    - [The _parse_ method](#the-_parse_-method)
    - [The _evaluate_ method](#the-_evaluate_-method)
    - [The _message_ instance variable](#the-_message_-instance-variable)
    - [Creating Notes](#creating-notes)
    - [Writing Tests](#writing-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Intellectual Property

By contributing code, bugs or enhancements to this project (whether that be through pull requests, the issues list, e-mail or other means), you are licensing your contribution under the [project's terms](LICENSE.md).


## Coding Conventions

We use [black](https://pypi.org/project/black/) for Python formatting, which can be run with `make tidy`.

All Python functions and methods need to have type annotations. See `pyproject.toml` for specific pylint and mypy settings.


## Setting up a Development Environment

It should be possible to use modern Unix-like environment, provided that a recent release of Python is installed.

Thanks to [Makefile.venv](https://github.com/sio/Makefile.venv), a Python virtual environment is set up and run each time you use `make`. As long as you use `make`, Python dependencies will be installed automatically.

Helpful make targets include:

* `make shell` - start a shell in the Python virtual environment
* `make python` - start an interactive Python interpreter in the virtual environment
* `make lint` - run pylint with REDbot-specific configuration
* `make typecheck` - run mypy to check Python types
* `make tidy` - format Python source
* `make test` - run the tests


## Before you Submit

The best way to submit a change is through a pull request. A few things to keep in mind when you're doing so:

* Run `make tidy`.
* Check your code with `make lint` and address any issues found.
* Check your code with `make typecheck` and address any issues found.
* Every new field and every new `Note` should have a test covering it.

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

The easiest way to get started is to run (from redbot's root):

> make httplint/field/parsers/my_field_name.py

That will give you a skeleton to start working with.


#### The _HttpField_ Class

Each file should define exactly one `fields.HttpField` class, whose name is the same as the filename (e.g., `foo_example`, as per above).

`HttpField` has a number of instance variables (which are often set as class variables):

* `canonical_name` - unicode string, the "normal" capitalisation of the field name. _required_
* `description` - unicode string, general description of the field. Markdown formatting. _required_
* `reference` - unicode string, URL to the most recent definition of the field.
* `syntax` - string, regular expression for the field's syntax (evaluated with `re.VERBOSE` and `re.IGNORECASE`). _required_
* `list_field` - boolean, indicates whether the field supports list syntax (see `parse`). _required_
* `deprecated` - boolean, indicates whether the field has been deprecated.
* `valid_in_requests` - boolean, indicates whether the field is valid in HTTP requests. _required_
* `valid_in_responses` - boolean, indicates whether the field is valid in HTTP responses. _required_
* `no_coverage` - boolean, turns off coverage checks for trivial fields.

For example, `Age` starts with:

~~~ python
class age(HttpField):
    canonical_name = "Age"
    description = """\
The `Age` response header conveys the sender's estimate of the amount of time since the response
(or its validation) was generated at the origin server."""
    reference = f"{rfc9111.SPEC_URL}#field.age"
    syntax = False  # rfc9111.Age
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
~~~~

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

However, if the `list_field` class variable is `True`, this is altered; _parse_ will be called for
each _value_, after separating on commas (excepting those inside quoted strings). In the example
above, _parse_ would be called three times for `Bar` (with the `field_value`s _1_, _2_, and _3_),
but still only once for `Baz`.

Note that `syntax` is checked against the `field_value` before _parse_ is called, subject to
`list_field` processing.

`add_note` is a function that can be called with the appropriate _Note_, when it's necessary to
communicate something about the field_value.

_parse_ should return the parsed value corresponding to the `field_value`. If there is an error and
the value shouldn't be remembered, raise `ValueError`.


#### The _evaluate_ method

_evaluate_ is called with one argument, `add_note`. As above, it allows setting _Note_s about the
field field.

_evaluate_ is called once all of the field fields are processed, to enable the entire set of the
field field's values to be considered. To access the parsed value(s), use the _value_ instance
variable.

When _list_field_ is `True`, _value_ is a list of the results of calling _parse_. When it is
`False`, it is a single value, representing the most recent call to _parse_.


#### The _message_ instance variable

Some checks may need to access other parts of the message; for example, the HTTP status code. You
can access the `redbot.message` instance that the field is part of using the _message_ instance
variable.


#### Creating Notes

Field definitions should also include field specific _Note_ classes.

When writing new notes, it's important to keep in mind that the `text` field is expected to contain
valid HTML; any variables you pass to it will be escaped for you before rendering.


#### Writing Tests

Each field definition should also include tests, as subclasses of
`httplint.field.tests.FieldTest`. It expects the following class properties:

* `name` - the field field-name
* `inputs` - a list of field field-values, one item per line.
    E.g., `["foo", "foo, bar"]`
* `expected_out` - the data structure that _parse_ should return, given
    the inputs
* `expected_notes` - a list of `redbot.speak.Note` classes that are expected
    to be set with `add_note` when parsing the inputs

You can create any number of tests this way; they will be run automatically when
_tests/test\_fields.py_ is run.
