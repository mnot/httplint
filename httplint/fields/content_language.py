from . import HttpField
from ._test import FieldTest
from ..syntax import rfc7231


class content_language(HttpField):
    canonical_name = "Content-Language"
    description = """\
The `Content-Language` header describes the natural language(s) of the intended audience. Note that
this might not convey all of the languages used within the body."""
    reference = f"{rfc7231.SPEC_URL}#header.content_language"
    syntax = rfc7231.Content_Language
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True


class ContentLanguageTest(FieldTest):
    name = "Content-Language"
    inputs = [b"en-US"]
    expected_out = "en-US"
