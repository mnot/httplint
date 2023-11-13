from httplint.field import HttpField

from httplint.field import RFC2616


class mime_version(HttpField):
    canonical_name = "MIME-Version"
    description = """\
HTTP is not a MIME-compliant protocol. However, HTTP/1.1 messages can include a single MIME-Version
header to indicate what version of the MIME protocol was used to construct the message. Use
of the MIME-Version header indicates that the message is in full compliance with the MIME
protocol."""
    reference = f"{RFC2616}#section-19.4.1"
    list_header = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True
    no_coverage = True
