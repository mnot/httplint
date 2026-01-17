from typing import TYPE_CHECKING

from httplint.field.list_field import HttpListField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


UNNECESSARY_FIELDS = {
    "x-aspnet-version": "x-aspnet-version reveals the ASP.NET version.",
    "x-aspnetmvc-version": "x-aspnetmvc-version reveals the ASP.NET MVC version.",
    "x-powered-by": "x-powered-by reveals the technology used to generate the response.",
    "x-generator": "x-generator reveals the software used to generate the response.",
    "x-drupal-cache": "x-drupal-cache reveals Drupal caching information.",
    "x-varnish": "x-varnish reveals Varnish caching information.",
    "x-mod-pagespeed": "x-mod-pagespeed reveals that mod_pagespeed is in use, "
    "which is usually not needed by the client.",
    "x-pingback": "x-pingback advertises a Pingback endpoint, which is rarely used.",
    "x-runtime": "x-runtime reveals the time taken to generate the response, "
    "which is usually not needed by the client.",
    "x-rack-cache": "x-rack-cache reveals Rack::Cache information, "
    "which is usually not needed by the client.",
    "x-content-encoded-by": "x-content-encoded-by reveals the software used to encode the content, "
    "which is usually not needed by the client.",
    "x-backend-server": "x-backend-server reveals the backend server identity.",
}


class UnnecessaryField(HttpListField):
    syntax = False
    list_header = False
    deprecated = False
    no_coverage = True
    valid_in_requests = True
    valid_in_responses = True

    def __init__(self, wire_name: str, message: "HttpMessageLinter") -> None:
        HttpListField.__init__(self, wire_name, message)
        self.reference = "about:blank"
        self.description = UNNECESSARY_FIELDS.get(self.norm_name, "")

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> None:
        add_note(UNNECESSARY_HEADER, header_name=self.wire_name)


class UNNECESSARY_HEADER(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "The %(header_name)s header can probably be removed."
    _text = """\
The `%(header_name)s` header adds little value, contributes to unnecessary bandwidth,
and may increase security risk by exposing details of the back-end system.

Consider removing it."""
