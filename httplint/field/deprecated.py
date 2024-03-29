from typing import TYPE_CHECKING

from httplint.field import HttpField
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


# pylint: disable=line-too-long
DEPRECATED_FIELDS = {
    "Accept-Charset": "https://www.rfc-editor.org/rfc/rfc9110.html#name-accept-charset",
    "C-PEP-Info": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "Pragma": "https://www.rfc-editor.org/rfc/rfc9111.html#name-pragma",
    "Protocol-Info": "https://www.w3.org/TR/NOTE-jepi",
    "Protocol-Query": "https://www.w3.org/TR/NOTE-jepi",
}

OBSOLETED_FIELDS = {
    "Access-Control": "https://www.w3.org/TR/2007/WD-access-control-20071126/#access-control0",
    "C-Ext": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "C-Man": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "C-Opt": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "C-PEP": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "Content-Base": "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    "Content-ID": "https://www.w3.org/TR/NOTE-drp",
    "Content-MD5": "https://www.rfc-editor.org/rfc/rfc7231.html#appendix-B",
    "Content-Script-Type": "https://www.w3.org/TR/html4/interact/scripts.html#h-18.2.2.1",
    "Content-Style-Type": "https://www.w3.org/TR/html401/present/styles.html#h-14.2.1",
    "Content-Version": "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    "Cookie2": "https://www.rfc-editor.org/rfc/rfc6265.html#section-1",
    "Default-Style": "https://www.w3.org/TR/2010/WD-html-markup-20100624/meta.http-equiv.default-style.html",
    "Derived-From": "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    "Differential-ID": "https://www.w3.org/TR/NOTE-drp",
    "Digest": "https://datatracker.ietf.org/doc/draft-ietf-httpbis-digest-headers/",
    "Expect-CT": "https://mailarchive.ietf.org/arch/msg/httpbisa/XpAWZsIre5WAte3lXGTh6A77sok/",
    "Ext": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "GetProfile": "https://www.w3.org/TR/NOTE-OPS-OverHTTP",
    "HTTP2-Settings": "https://www.rfc-editor.org/rfc/rfc9113.html#name-http2-settings-header-field",
    "Man": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "Method-Check": "https://www.w3.org/TR/2007/WD-access-control-20071126/#method-check",
    "Method-Check-Expires": "https://www.w3.org/TR/2007/WD-access-control-20071126/#method-check-expires",
    "Opt": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "P3P": "https://www.w3.org/TR/P3P",
    "PEP": "http://www.w3.org/TR/WD-http-pep",
    "Pep-Info": "http://www.w3.org/TR/WD-http-pep",
    "PICS-Label": "https://www.w3.org/TR/REC-PICS-labels-961031",
    "ProfileObject": "https://www.w3.org/TR/NOTE-OPS-OverHTTP",
    "Protocol": "https://www.w3.org/TR/REC-PICS-labels-961031",
    "Protocol-Request": "https://www.w3.org/TR/REC-PICS-labels-961031",
    "Proxy-Features": "https://www.w3.org/TR/WD-proxy.html",
    "Proxy-Instruction": "https://www.w3.org/TR/WD-proxy.html",
    "Public": "https://www.rfc-editor.org/rfc/rfc2616.html#section-19.6.3",
    "Referer-Root": "https://www.w3.org/TR/2007/WD-access-control-20071126/#referer-root",
    "Safe": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "Security-Scheme": "https://datatracker.ietf.org/doc/status-change-http-experiments-to-historic/",
    "Set-Cookie2": "https://www.rfc-editor.org/rfc/rfc6265.html#section-1",
    "SetProfile": "https://www.w3.org/TR/NOTE-OPS-OverHTTP",
    "URI": "https://www.rfc-editor.org/rfc/rfc2068.html#section-19.6.2.5",
    "Want-Digest": "https://datatracker.ietf.org/doc/draft-ietf-httpbis-digest-headers/",
    "Warning": "https://www.rfc-editor.org/rfc/rfc9111.html#name-warning",
}

UNREGISGTERED_DEPRECATED_FIELDS = {
    "X-UA-Compatible": "https://learn.microsoft.com/en-us/openspecs/ie_standards/ms-iedoco/380e2488-f5eb-4457-a07a-0cb1b6e4b4b5",
    "X-Meta-MSSmartTagsPreventParsing": "https://web.archive.org/web/20120211140254/http://blogs.msdn.com/b/ieinternals/archive/2009/06/30/internet-explorer-custom-http-headers.aspx",
    "X-Download-Options": "https://web.archive.org/web/20120211140254/http://blogs.msdn.com/b/ieinternals/archive/2009/06/30/internet-explorer-custom-http-headers.aspx",
}

fields = {}
fields.update(UNREGISGTERED_DEPRECATED_FIELDS)
fields.update(DEPRECATED_FIELDS)
fields.update(OBSOLETED_FIELDS)
field_lookup = {k.lower(): k for k in fields}


class DeprecatedField(HttpField):
    syntax = False
    list_header = False
    deprecated = True
    no_coverage = True
    valid_in_requests = True
    valid_in_responses = True  # dont' want to complain about these

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        HttpField.__init__(self, wire_name, message)
        assert self.norm_name in field_lookup
        self.canonical_name = field_lookup[self.norm_name]
        self.reference = fields[field_lookup[self.norm_name]]
        self.description = f"""\
The {self.canonical_name} field is deprecated; it is not actively used by HTTP software.
It is safe to remove it from this message. For more information, see [here]({self.reference})."""

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> None:
        return
