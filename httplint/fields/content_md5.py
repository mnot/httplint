from httplint.fields import HttpField
from httplint.fields._test import FieldTest
from httplint.fields._notes import FIELD_DEPRECATED


class content_md5(HttpField):
    canonical_name = "Content-MD5"
    description = """\
The `Content-MD5` header is an MD5 digest of the content, and provides an end-to-end message
integrity check (MIC).

Note that while a MIC is good for detecting accidental modification of content in transit, it is
not proof against malicious attacks."""
    reference = "https://tools.ietf.org/html/rfc1864"
    syntax = r"(?: [A-Za-z0-9+/]{22} ={2} )"
    list_header = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True


class ContentMD5Test(FieldTest):
    name = "Content-MD5"
    inputs = [b"Q2hlY2sgSW50ZWdyaXR5IQ=="]
    expected_out = "Q2hlY2sgSW50ZWdyaXR5IQ=="
    expected_notes = [FIELD_DEPRECATED]
