from httplint.field import HttpField
from httplint.note import Note, categories, levels
from httplint.types import AddNoteMethodType


class x_meta_mssmarttagspreventparsing(HttpField):
    canonical_name = "X-Meta-MSSmartTagsPreventParsing"
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        add_note(SMART_TAG_NO_WORK)


class SMART_TAG_NO_WORK(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "The %(field_name)s header doesn't have any effect on smart tags."
    _text = """\
This header doesn't have any effect on Microsoft Smart Tags, except in certain beta versions of
IE6. To turn them off, you'll need to make changes in the HTML content itself."""
