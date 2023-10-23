"""
Common header-related Notes.
"""

from httplint.note import Note, categories, levels


class SINGLE_HEADER_REPEAT(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "Only one %(field_name)s field is allowed in a response's headers."
    _text = """\
This field is designed to only occur once in a message. When it occurs more than once, a receiver
needs to choose the one to use, which can lead to interoperability problems, since different
implementations may make different choices."""


class FIELD_NAME_BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" is not a valid field name.'
    _text = """\
Field names are limited to the `token` production in HTTP; i.e., they can't contain parenthesis,
angle brackes (<>), ampersands (@), commas, semicolons, colons, backslashes (\\), forward
slashes (/), quotes, square brackets ([]), question marks, equals signs (=), curly brackets ({})
spaces or tabs."""


class BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s field value isn't valid."
    _text = """\
The value for this field doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information."""


class PARAM_STAR_QUOTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The '%(param)s' parameter's value cannot be quoted."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` field has double-quotes around it, which is not
valid."""


class PARAM_STAR_ERROR(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(param)s parameter's value is invalid."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` field is not valid; it needs to have three
parts, separated by single quotes (')."""


class PARAM_STAR_BAD(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(param)s* parameter isn't allowed on the %(field_name)s field."
    _text = """\
Parameter values that end in '*' are reserved for non-ascii text, as explained in
[RFC5987](http://tools.ietf.org/html/rfc5987).

The `%(param)s` parameter on the `%(field_name)s` field does not allow this; you should use
%(param)s without the "*" on the end (and without the associated encoding)."""


class PARAM_STAR_NOCHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(param)s parameter's value doesn't define an encoding."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header doesn't declare its character encoding,
which means that recipients can't understand it. It should be `UTF-8`."""


class PARAM_STAR_CHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(param)s parameter's value uses an encoding other than UTF-8."
    _text = """\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header uses the `'%(enc)s` encoding, which has
interoperability issues with some browsers. It should be `UTF-8`."""


class PARAM_REPEATS(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The '%(param)s' parameter repeats in the %(field_name)s header."
    _text = """\
Parameters on the %(field_name)s field should not repeat; implementations may handle them
differently."""


class PARAM_SINGLE_QUOTED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = (
        "The '%(param)s' parameter on the %(field_name)s header is single-quoted."
    )
    _text = """\
The `%(param)s`'s value on the %(field_name)s field starts and ends with a single quote (').
However, single quotes don't mean anything there.

This means that the value will be interpreted as `%(param_val)s`, **not**
`%(param_val_unquoted)s`. If you intend the latter, remove the single quotes."""


class BAD_DATE_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = "The %(field_name)s header's value isn't a valid date."
    _text = """\
HTTP dates have specific syntax, and sending an invalid date can cause a number of problems,
especially with caching. Common problems include sending "1 May" instead of "01 May" (the month
is a fixed-width field), and sending a date in a timezone other than GMT.

See [the HTTP specification](http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.3) for more
information."""


class DATE_OBSOLETE(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header's value uses an obsolete format."
    _text = """\
HTTP has a number of defined date formats for historical reasons. This header is using an old
format that are now obsolete. See [the
specification](http://httpwg.org/specs/rfc7231.html#http.date) for more information.
"""


class REQUEST_HDR_IN_RESPONSE(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" is a request header.'
    _text = """\
The %(field_name)s field isn't defined to have any meaning in responses."""


class RESPONSE_HDR_IN_REQUEST(Note):
    category = categories.GENERAL
    level = levels.BAD
    _summary = '"%(field_name)s" is a request header.'
    _text = """\
The %(field_name)s field isn't defined to have any meaning in requests."""


class FIELD_DEPRECATED(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header is deprecated."
    _text = """\
This field is no longer recommended for use, because of interoperability problems and/or
lack of use.

See [the deprecation notice](%(deprecation_ref)s) for more information."""
