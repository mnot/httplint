from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.syntax import rfc7231
from httplint.types import AddNoteMethodType
from httplint.util import f_num


class vary(HttpField):
    canonical_name = "Vary"
    description = """\
The `Vary` response header indicates the set of request headers that determines whether a cache is
permitted to use the response to reply to a subsequent request without validation.

In uncacheable or stale responses, the Vary field value advises the user agent about the criteria
that were used to select the representation."""
    reference = f"{rfc7231.SPEC_URL}#header.vary"
    syntax = rfc7231.Vary
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> str:
        return field_value.lower()

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if "*" in self.value:
            add_note(VARY_ASTERISK)
        if len(self.value) > 3:
            add_note(VARY_COMPLEX, vary_count=f_num(len(self.value)))
        if "user-agent" in self.value:
            add_note(VARY_USER_AGENT)
        if "host" in self.value:
            add_note(VARY_HOST)


class VARY_ASTERISK(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Vary: * effectively makes this response uncacheable."
    _text = """\
`Vary *` indicates that responses for this resource vary by some aspect that can't (or won't) be
described by the server. This makes this response effectively uncacheable."""


class VARY_USER_AGENT(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Vary: User-Agent can cause cache inefficiency."
    _text = """\
Sending `Vary: User-Agent` requires caches to store a separate copy of the response for every
`User-Agent` request header they see.

Since there are so many different `User-Agent`s, this can "bloat" caches with many copies of the
same thing, or cause them to give up on storing these responses at all.

Consider having different URIs for the various versions of your content instead; this will give
finer control over caching without sacrificing efficiency."""


class VARY_HOST(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "Vary: Host is not necessary."
    _text = """\
Some servers (e.g., [Apache](http://httpd.apache.org/) with
[mod_rewrite](http://httpd.apache.org/docs/2.4/mod/mod_rewrite.html)) will send `Host` in the
`Vary` header, in the belief that since it affects how the server selects what to send back, this
is necessary.

This is not the case; HTTP specifies that the URI is the basis of the cache key, and the URI
incorporates the `Host` header.

The presence of `Vary: Host` may make some caches not store an otherwise cacheable response (since
some cache implementations will not store anything that has a `Vary` header)."""


class VARY_COMPLEX(Note):
    category = categories.CACHING
    level = levels.WARN
    _summary = "This resource varies in %(vary_count)s ways."
    _text = """\
The `Vary` mechanism allows a resource to describe the dimensions that its responses vary, or
change, over; each listed header is another dimension.

Varying by too many dimensions makes using this information impractical."""
