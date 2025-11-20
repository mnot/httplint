from httplint.field import HttpField
from httplint.field.tests import FieldTest
from httplint.syntax import rfc9110



class content_language(HttpField):
    canonical_name = "Content-Language"
    description = """\
The `Content-Language` header describes the natural language(s) of the intended audience for the
messsage. Note that this might not convey all of the languages used."""
    reference = f"{rfc9110.SPEC_URL}#field.content-language"
    syntax = rfc9110.Content_Language
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = True


class ContentLanguageTest(FieldTest):
    name = "Content-Language"
    inputs = [b"en-US"]
    expected_out = "en-US"
