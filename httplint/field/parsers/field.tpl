#!/usr/bin/env python

from httplint.fields import HttpField
from httplint.fields._test import HttpTest
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType

class SHORT_NAME(HttpField):
    canonical_name = "SHORT_NAME"
    description = """\
FIXME
"""
    reference = None
    syntax = False
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> ...:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        return


class SHORT_NAME_NOTE(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary =  "FIXME"
    _text ="""\
FIXME"""


class SHORT_NAMETest(HeaderTest):
    name = 'SHORT_NAME'
    inputs = ['FIXME']
    expected_out = ('FIXME')
    expected_notes = []
