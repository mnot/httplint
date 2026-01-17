from typing import TYPE_CHECKING, Tuple, Dict


from httplint.field.list_field import HttpListField
from httplint.field import FIELD_DEPRECATED
from httplint.note import categories
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


# pylint: disable=line-too-long
DEPRECATED_FIELDS: Dict[str, Tuple[categories, str]] = {
    "Accept-CH-Lifetime": (
        categories.CONNEG,
        "https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-client-hints-08#appendix-B.8",
    ),
    "Accept-Charset": (
        categories.CONNEG,
        "https://www.rfc-editor.org/rfc/rfc9110.html#name-accept-charset",
    ),
    "C-PEP-Info": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "Pragma": (categories.CACHING, "https://www.rfc-editor.org/rfc/rfc9111.html#name-pragma"),
    "Protocol-Info": (categories.GENERAL, "https://www.w3.org/TR/NOTE-jepi"),
    "Protocol-Query": (categories.GENERAL, "https://www.w3.org/TR/NOTE-jepi"),
}

OBSOLETED_FIELDS: Dict[str, Tuple[categories, str]] = {
    "Access-Control": (
        categories.SECURITY,
        "https://www.w3.org/TR/2007/WD-access-control-20071126/#access-control0",
    ),
    "C-Ext": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "C-Man": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "C-Opt": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "C-PEP": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "Content-Base": (
        categories.GENERAL,
        "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    ),
    "Content-ID": (categories.GENERAL, "https://www.w3.org/TR/NOTE-drp"),
    "Content-MD5": (categories.GENERAL, "https://www.rfc-editor.org/rfc/rfc7231.html#appendix-B"),
    "Content-Script-Type": (
        categories.GENERAL,
        "https://www.w3.org/TR/html4/interact/scripts.html#h-18.2.2.1",
    ),
    "Content-Style-Type": (
        categories.GENERAL,
        "https://www.w3.org/TR/html401/present/styles.html#h-14.2.1",
    ),
    "Content-Version": (
        categories.GENERAL,
        "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    ),
    "Cookie2": (categories.COOKIES, "https://www.rfc-editor.org/rfc/rfc6265.html#section-1"),
    "Default-Style": (
        categories.GENERAL,
        "https://www.w3.org/TR/2010/WD-html-markup-20100624/meta.http-equiv.default-style.html",
    ),
    "Derived-From": (
        categories.GENERAL,
        "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    ),
    "Differential-ID": (categories.GENERAL, "https://www.w3.org/TR/NOTE-drp"),
    "Digest": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/draft-ietf-httpbis-digest-headers/",
    ),
    "Expect-CT": (
        categories.SECURITY,
        "https://mailarchive.ietf.org/arch/msg/httpbisa/XpAWZsIre5WAte3lXGTh6A77sok/",
    ),
    "Ext": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "Feature-Policy": (categories.SECURITY, "https://www.w3.org/TR/feature-policy/"),
    "GetProfile": (categories.GENERAL, "https://www.w3.org/TR/NOTE-OPS-OverHTTP"),
    "HTTP2-Settings": (
        categories.GENERAL,
        "https://www.rfc-editor.org/rfc/rfc9113.html#name-http2-settings-header-field",
    ),
    "Man": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "Method-Check": (
        categories.SECURITY,
        "https://www.w3.org/TR/2007/WD-access-control-20071126/#method-check",
    ),
    "Method-Check-Expires": (
        categories.SECURITY,
        "https://www.w3.org/TR/2007/WD-access-control-20071126/#method-check-expires",
    ),
    "Opt": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "P3P": (categories.GENERAL, "https://www.w3.org/TR/P3P"),
    "PEP": (categories.GENERAL, "http://www.w3.org/TR/WD-http-pep"),
    "Pep-Info": (categories.GENERAL, "http://www.w3.org/TR/WD-http-pep"),
    "PICS-Label": (categories.GENERAL, "https://www.w3.org/TR/REC-PICS-labels-961031"),
    "ProfileObject": (categories.GENERAL, "https://www.w3.org/TR/NOTE-OPS-OverHTTP"),
    "Protocol": (categories.GENERAL, "https://www.w3.org/TR/REC-PICS-labels-961031"),
    "Protocol-Request": (categories.GENERAL, "https://www.w3.org/TR/REC-PICS-labels-961031"),
    "Proxy-Features": (categories.GENERAL, "https://www.w3.org/TR/WD-proxy.html"),
    "Proxy-Instruction": (categories.GENERAL, "https://www.w3.org/TR/WD-proxy.html"),
    "Public": (categories.GENERAL, "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3"),
    "Public-Key-Pins": (categories.SECURITY, "https://www.rfc-editor.org/rfc/rfc7469.html"),
    "Public-Key-Pins-Report-Only": (
        categories.SECURITY,
        "https://www.rfc-editor.org/rfc/rfc7469.html",
    ),
    "Referer-Root": (
        categories.SECURITY,
        "https://www.w3.org/TR/2007/WD-access-control-20071126/#referer-root",
    ),
    "Safe": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "Security-Scheme": (
        categories.SECURITY,
        "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    ),
    "Set-Cookie2": (categories.COOKIES, "https://www.rfc-editor.org/rfc/rfc6265.html#section-1"),
    "SetProfile": (categories.GENERAL, "https://www.w3.org/TR/NOTE-OPS-OverHTTP"),
    "URI": (categories.GENERAL, "https://www.rfc-editor.org/rfc/rfc2068.html#section-19.6.2.5"),
    "Want-Digest": (
        categories.GENERAL,
        "https://datatracker.ietf.org/doc/draft-ietf-httpbis-digest-headers/",
    ),
    "Warning": (categories.CACHING, "https://www.rfc-editor.org/rfc/rfc9111.html#name-warning"),
}

UNREGISGTERED_DEPRECATED_FIELDS: Dict[str, Tuple[categories, str]] = {
    "X-UA-Compatible": (
        categories.GENERAL,
        "https://learn.microsoft.com/en-us/openspecs/ie_standards/ms-iedoco/380e2488-f5eb-4457-a07a-0cb1b6e4b4b5",
    ),
    "X-Meta-MSSmartTagsPreventParsing": (
        categories.SECURITY,
        "https://web.archive.org/web/20120211140254/http://blogs.msdn.com/b/ieinternals/archive/2009/06/30/internet-explorer-custom-http-headers.aspx",
    ),
    "X-Download-Options": (
        categories.SECURITY,
        "https://web.archive.org/web/20120211140254/http://blogs.msdn.com/b/ieinternals/archive/2009/06/30/internet-explorer-custom-http-headers.aspx",
    ),
    "X-XSS-Protection": (
        categories.SECURITY,
        "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-XSS-Protection",
    ),
}

fields = {}
fields.update(UNREGISGTERED_DEPRECATED_FIELDS)
fields.update(DEPRECATED_FIELDS)
fields.update(OBSOLETED_FIELDS)
field_lookup = {k.lower(): k for k in fields}


class DeprecatedField(HttpListField):
    syntax = False
    list_header = False
    deprecated = True
    no_coverage = True
    valid_in_requests = True
    valid_in_responses = True  # dont' want to complain about these

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        HttpListField.__init__(self, wire_name, message)
        assert self.norm_name in field_lookup
        self.canonical_name = field_lookup[self.norm_name]
        self.category, self.reference = fields[field_lookup[self.norm_name]]
        self.description = f"""\
The {self.canonical_name} field is deprecated; it is not actively used by HTTP software.
It is safe to remove it from this message. For more information, see [here]({self.reference})."""

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> None:
        return

    def pre_check(self, message: "HttpMessageLinter", add_note: AddNoteMethodType) -> bool:
        # Override pre_check to use the specific note category
        # First, standard checks (copied from HttpField.pre_check, excluding deprecated check)

        # check whether we're in the right message type
        # We can't call super().pre_check() because it would emit the generic FIELD_DEPRECATED note

        if self.message.message_type == "request":
            if not self.valid_in_requests:
                # We can import these from the base class module or assume availability?
                # They are imported in __init__.py but not exposed directly.
                # We need to import them here or change imports.
                pass  # Relying on HttpField logic for this part is tricky if we want to avoid double notes.
        else:
            if not self.valid_in_responses:
                pass

        # Let's see... HttpField.pre_check does request/response check, then syntax check, then deprecated check.
        # If we want to replace ONLY the deprecated check, we would ideally just set deprecated=False on self
        # but semantically we want it True.

        # Actually... if we set self.deprecated = False just before calling super().pre_check(),
        # then set it back?

        self.deprecated = False
        result = super().pre_check(message, add_note)
        self.deprecated = True

        if not result:
            return False

        # Now emit our custom note
        deprecation_ref = getattr(self, "deprecation_ref", self.reference)
        note = add_note(FIELD_DEPRECATED, deprecation_ref=deprecation_ref)
        note.category = self.category

        return True
