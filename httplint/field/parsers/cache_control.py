from typing import Tuple, Union, Dict, List, Callable

from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7234
from httplint.types import AddNoteMethodType
from httplint.util import prose_list
from httplint.field.utils import unquote_string


# known cache directives; assumed to not allow duplicates
# values are (valid_in_requests, valid_in_responses, value_type)
KNOWN_CC: Dict[str, Tuple[bool, bool, Union[None, Callable]]] = {
    "immutable": (False, True, None),
    "max-age": (True, True, int),
    "max-stale": (True, False, int),
    "min-fresh": (True, False, int),
    "must-revalidate": (False, True, None),
    "must-understand": (False, True, None),
    "no-cache": (True, True, unquote_string),
    "no-store": (True, True, None),
    "no-transform": (True, True, None),
    "only-if-cached": (True, False, None),
    "private": (False, True, unquote_string),
    "proxy-revalidate": (False, True, None),
    "public": (False, True, None),
    "s-maxage": (False, True, int),
    "stale-if-error": (False, True, int),
    "stale-while-revalidate": (False, True, int),
    "pre-check": (False, True, int),
    "post-check": (False, True, int),
}

# cache directives and those they override. Listed in order of
# significance; only the first match will be shown.
CONFLICTING_CC: List[Tuple[str, List[str]]] = [
    (
        "no-store",
        [
            "immutable",
            "max-age",
            "must-revalidate",
            "no-cache",
            "private",
            "proxy-revalidate",
            "public",
            "s-maxage",
            "stale-if-error",
            "stale-while-revalidate",
            "pre-check",
            "post-check",
        ],
    ),
    (
        "no-cache",
        [
            "immutable",
            "max-age",
            "must-revalidate",
            "proxy-revalidate",
            "s-maxage",
            "stale-if-error",
            "stale-while-revalidate",
            "pre-check",
            "post-check",
        ],
    ),
    (
        "must-revalidate",
        [
            "immutable",
            "stale-if-error",
            "stale-while-revalidate",
            "pre-check",
            "post-check",
        ],
    ),
]


class cache_control(HttpField):
    canonical_name = "Cache-Control"
    description = """\
The `Cache-Control` header is used to specify required directives to all caches that
handle the response. It can also occur in requests, but caches have the option of
ignoring it there."""
    reference = f"{rfc7234.SPEC_URL}#header.cache-control"
    syntax = rfc7234.Cache_Control
    list_header = True
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True

    def parse(
        self, field_value: str, add_note: AddNoteMethodType
    ) -> Tuple[str, Union[int, str, None]]:
        try:
            directive_name, directive_val = field_value.split("=", 1)
        except ValueError:
            directive_name = field_value
            directive_val = None
        if directive_name != directive_name.lower():
            add_note(
                CC_MISCAP,
                directive_lower=directive_name.lower(),
                directive=directive_name,
            )
        directive_name = directive_name.lower()

        if directive_name in KNOWN_CC:
            value_func = KNOWN_CC[directive_name][2]
            if value_func is None:
                if directive_val is not None:
                    add_note(BAD_CC_SYNTAX, bad_directive=directive_name)
            else:
                try:
                    return (directive_name, value_func(directive_val))
                except (ValueError, TypeError):
                    add_note(BAD_CC_SYNTAX, bad_directive=directive_name)
                    raise ValueError  # pylint: disable=raise-missing-from
        return (directive_name, directive_val)

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        cc_list = [d for (d, v) in self.value]
        cc_dict = dict(self.value)

        # conflicting directives; all in responses
        if self.message.message_type == "response":
            for directive, potential_conflicts in CONFLICTING_CC:
                if directive in cc_list:
                    conflicts = list(
                        set(cc_list).intersection(set(potential_conflicts))
                    )
                    if len(conflicts) > 0:
                        add_note(
                            CC_CONFLICTING,
                            directive=directive,
                            conflicts=prose_list(conflicts, markup="`"),
                        )
                        break  # only show the first conflict

        for directive in set(cc_list):
            # wrong message type
            if (
                self.message.message_type == "request"
                and KNOWN_CC.get(directive, (True, True))[0] is False
            ):
                add_note(
                    CC_WRONG_MESSAGE,
                    directive=directive,
                    message="request",
                    other_message="response",
                )
                continue  # don't run other checks
            if (
                self.message.message_type == "response"
                and KNOWN_CC.get(directive, (True, True))[1] is False
            ):
                add_note(
                    CC_WRONG_MESSAGE,
                    directive=directive,
                    message="response",
                    other_message="request",
                )
                continue  # don't run other checks

            # duplicate directives
            if directive in KNOWN_CC and cc_list.count(directive) > 1:
                add_note(CC_DUP, directive=directive)

        # pre-check / post-check
        if "pre-check" in cc_list or "post-check" in cc_list:
            if "pre-check" not in cc_list or "post-check" not in cc_list:
                add_note(CHECK_SINGLE)
            else:
                pre_check = cc_dict["pre-check"]
                post_check = cc_dict["post-check"]
                if pre_check is not None and post_check is not None:
                    if pre_check == 0 and post_check == 0:
                        add_note(CHECK_ALL_ZERO)
                    elif post_check > pre_check:
                        add_note(CHECK_POST_BIGGER)
                        post_check = pre_check
                    elif post_check == 0:
                        add_note(CHECK_POST_ZERO)
                    else:
                        add_note(
                            CHECK_POST_PRE,
                            pre_check=pre_check,
                            post_check=post_check,
                        )


class BAD_CC_SYNTAX(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The %(bad_directive)s cache directive's syntax is incorrect."
    _text = "This value must be an integer."


class CC_MISCAP(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The %(directive)s cache directive has non-lowercase characters."
    _text = """\
cache directive names are case-insensitive, but some implementations don't
recognize directives that aren't all-lowercase.

Therefore, it's safest to use `%(directive_lower)s` instead of `%(directive)s`."""


class CC_DUP(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The %(directive)s cache directive appears more than once."
    _text = """\
The `%(directive)s` cache directive is only defined to appear once; it is used more than
once here, so implementations may use different instances (e.g., the first, or the last),
making their behaviour unpredictable."""


class CC_CONFLICTING(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The %(directive)s cache directive overrides other directives."
    _text = """\
The `%(directive)s` cache directive overrides or conflicts with %(conflicts)s.

The conflicting directives will be ignored by caches, and can be safely omitted.
    """


class CC_WRONG_MESSAGE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The %(directive)s cache directive has no meaning in a %(message)s."
    _text = """\
The `%(directive)s` cache directive is only defined to appear in %(other_message)s
messages; is has no defined meaning in a %(message)s."""


class CHECK_SINGLE(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Only one of the pre-check and post-check cache directives is present."
    _text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(message)s uses only one of these directives; as a result, Internet Explorer will ignore the
directive, since it requires both to be present.

See [this blog entry](http://bit.ly/rzT0um) for more information.
"""


class CHECK_ALL_ZERO(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The pre-check and post-check cache directives are both '0'."
    _text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(message)s gives a value of "0" for both; as a result, Internet Explorer will ignore the
directive, since it requires both to be present.

In other words, setting these to zero has **no effect** (besides wasting bandwidth),
and may trigger bugs in some beta versions of IE.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_POST_BIGGER(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "The post-check cache directive's value is larger than pre-check's."
    _text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(message)s assigns a higher value to `post-check` than to `pre-check`; this means that Internet
Explorer will treat `post-check` as if its value is the same as `pre-check`'s.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_POST_ZERO(Note):
    category = categories.CACHING
    level = levels.BAD
    _summary = "The post-check cache directive's value is '0'."
    _text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(message)s assigns a value of "0" to `post-check`, which means that Internet Explorer will reload
the content as soon as it enters the browser cache, effectively **doubling the load on the server**.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_POST_PRE(Note):
    category = categories.CACHING
    level = levels.INFO
    _summary = "%(message)s may be refreshed in the background by Internet Explorer."
    _text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

Once it has been cached for more than %(post_check)s seconds, a new request will result in the
cached response being served while it is refreshed in the background. However, if it has been
cached for more than %(pre_check)s seconds, the browser will download a fresh response before
showing it to the user.

Note that these directives do not have any effect on other clients or caches.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CacheControlTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"a=b, c=d", b"e=f", b"g"]
    expected_out = [("a", "b"), ("c", "d"), ("e", "f"), ("g", None)]


class CacheControlCaseTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"A=b, c=D"]
    expected_out = [("a", "b"), ("c", "D")]
    expected_notes = [CC_MISCAP]


class CacheControlQuotedTest(FieldTest):
    name = "Cache-Control"
    inputs = [b'private="b,c", c=d']
    expected_out = [("private", "b,c"), ("c", "d")]


class CacheControlMaxAgeTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"max-age=5"]
    expected_out = [("max-age", 5)]


class CacheControlBadMaxAgeTest(FieldTest):
    name = "Cache-Control"
    inputs = [b"max-age=foo"]
    expected_notes = [BAD_CC_SYNTAX]
