from .message import HttpMessage
from .note import Note, categories, levels


class HttpResponse(HttpMessage):
    """
    A HTTP Response message.
    """

    def __init__(self) -> None:
        HttpMessage.__init__(self)
        self.status_code = None  # type: int
        self.status_phrase = ""
        self.is_head_response = False

    def process_top_line(self, line: bytes) -> None:
        version, status_code, status_phrase = line.split(b" ", 2)
        self.version = version.decode("ascii", "replace")
        try:
            self.status_code = int(status_code.decode("ascii", "replace"))
        except UnicodeDecodeError:
            pass
        except ValueError:
            pass
        try:
            self.status_phrase = status_phrase.decode("ascii", "strict")
        except UnicodeDecodeError:
            self.status_phrase = status_phrase.decode("ascii", "replace")
            self.notes.add("status", STATUS_PHRASE_ENCODING)

    def can_have_content(self) -> bool:
        if self.is_head_response:
            return False
        if self.status_code in ["304"]:
            return False
        return True


class STATUS_PHRASE_ENCODING(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The status phrase contains non-ASCII characters."
    text = """\
The status phrase can only contain ASCII characters. REDbot has detected (and possibly removed)
non-ASCII characters in it."""
