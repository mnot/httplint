from typing import Tuple

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7231
from httplint.types import AddNoteMethodType, ParamDictType
from httplint.field.utils import parse_params
from httplint.field.notes import SINGLE_HEADER_REPEAT, PARAM_STAR_QUOTED


class content_disposition(HttpField):
    canonical_name = "Content-Disposition"
    description = """\
The `Content-Disposition` header suggests a name to use when saving the file.

When the disposition (the first value) is set to `attachment`, it also prompts browsers to download
the file, rather than display it."""
    reference = "https://tools.ietf.org/html/rfc6266"
    syntax = rf"(?:{rfc7231.token}(?:\s*;\s*{rfc7231.parameter})*)"
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, ParamDictType]:
        try:
            disposition, param_str = field_value.split(";", 1)
        except ValueError:
            disposition, param_str = field_value, ""
        disposition = disposition.lower()
        param_dict = parse_params(param_str, add_note)
        if disposition not in ["inline", "attachment"]:
            add_note(DISPOSITION_UNKNOWN, disposition=disposition)
        if disposition == "attachment" and "filename" not in param_dict:
            add_note(DISPOSITION_OMITS_FILENAME)
        filename = param_dict.get("filename", None)
        filename_star = param_dict.get("filename*", None)
        if filename and "%" in filename:
            add_note(DISPOSITION_FILENAME_PERCENT)
        if (filename and "/" in filename) or (filename_star and r"\\" in filename_star):
            add_note(DISPOSITION_FILENAME_PATH_CHAR)
        return disposition, param_dict


class DISPOSITION_UNKNOWN(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(disposition)s' Content-Disposition isn't known."
    _text = """\
The `Content-Disposition` header has two widely-known values; `inline` and `attachment`.
`%(disposition)s` isn't recognised, and most implementations will default to handling it like
`attachment`."""


class DISPOSITION_OMITS_FILENAME(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The Content-Disposition header doesn't have a 'filename' parameter."
    _text = """\
The `Content-Disposition` header with a disposition of `attachment` suggests a filename for clients
to use when saving the file locally.

It should always contain a `filename` parameter, even when the `filename*` parameter is used to
carry an internationalised filename, so that browsers can fall back to an ASCII-only filename."""


class DISPOSITION_FILENAME_PERCENT(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = (
        "The 'filename' parameter on the Content-Disposition header"
        "contains a '%%' character."
    )
    _text = """\
The `Content-Disposition` header suggests a filename for clients to use when saving the file
locally, using the `filename` parameter.

[RFC6266](http://tools.ietf.org/html/rfc6266) specifies how to carry non-ASCII characters in this
parameter. However, historically some (but not all) browsers have also decoded %%-encoded
characters in the `filename` parameter, which means that they'll be treated differently depending
on the browser you're using.

As a result, it's not interoperable to use percent characters in the `filename` parameter. Use the
correct encoding in the `filename*` parameter instead."""


class DISPOSITION_FILENAME_PATH_CHAR(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = (
        "The filename in the Content-Disposition header contains a path character."
    )
    _text = """\
The `Content-Disposition` header suggests a filename for clients to use when saving the file
locally, using the `filename` and `filename*` parameters.

One of these parameters contains a path character ("\" or "/"), used to navigate between
directories on common operating systems.

Because this can be used to attach the browser's host operating system (e.g., by saving a file to a
system directory), browsers will usually ignore these parameters, or remove path information.

You should remove these characters."""


class QuotedCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b'attachment; filename="foo.txt"']
    expected_out = ("attachment", {"filename": "foo.txt"})


class TokenCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b"attachment; filename=foo.txt"]
    expected_out = ("attachment", {"filename": "foo.txt"})


class InlineCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b"inline; filename=foo.txt"]
    expected_out = ("inline", {"filename": "foo.txt"})


class RepeatCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b"attachment; filename=foo.txt", b"inline; filename=bar.txt"]
    expected_out = ("inline", {"filename": "bar.txt"})
    expected_notes = [SINGLE_HEADER_REPEAT]


class FilenameStarCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b"attachment; filename=foo.txt; filename*=UTF-8''a%cc%88.txt"]
    expected_out = ("attachment", {"filename": "foo.txt", "filename*": "a\u0308.txt"})


class FilenameStarQuotedCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b"attachment; filename=foo.txt; filename*=\"UTF-8''a%cc%88.txt\""]
    expected_out = ("attachment", {"filename": "foo.txt", "filename*": "a\u0308.txt"})
    expected_notes = [PARAM_STAR_QUOTED]


class FilenamePercentCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b"attachment; filename=fo%22o.txt"]
    expected_out = ("attachment", {"filename": "fo%22o.txt"})
    expected_notes = [DISPOSITION_FILENAME_PERCENT]


class FilenamePathCharCDTest(FieldTest):
    name = "Content-Disposition"
    inputs = [b'attachment; filename="/foo.txt"']
    expected_out = ("attachment", {"filename": "/foo.txt"})
    expected_notes = [DISPOSITION_FILENAME_PATH_CHAR]
