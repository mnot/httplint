import hashlib
from typing import Any, List, Dict, Tuple

from .util import f_num
from .field_section import FieldSection
from .note import Notes, Note, levels, categories
from .type import RawFieldListType


class HttpMessage:
    """
    Base class for HTTP message state.
    """

    max_sample_size = 1024 * 1024  # How much of the content to keep for later

    def __init__(self, notes: Notes = None) -> None:
        self.notes = notes or Notes()

        self.version: str = ""
        self.base_uri: str = ""
        self.headers = FieldSection()
        self.trailers = FieldSection()

        self.content_sample: List[Tuple[int, bytes]] = []
        self.content_len: int = 0
        self.content_hash: bytes = None
        self._hash_processor = hashlib.new("md5")

        self.transfer_length: int = 0
        self.complete: bool = False

    def process_headers(self, headers: RawFieldListType) -> None:
        """
        Feed a list of (bytes name, bytes value) header tuples in and process them.
        """
        self.headers.process(headers, self)

    def feed_content(self, chunk: bytes) -> None:
        """
        Feed a chunk of the content in. Can be called 0 to many times.

        Each processor in content_processors will be run over the chunk.
        """
        if self.content_len < self.max_sample_size:
            self.content_sample.append((self.content_len, chunk))
        self.content_len += len(chunk)
        self._hash_processor.update(chunk)
        ## content encoding stuff here

    def finish_content(self, complete: bool, trailers: RawFieldListType = None) -> None:
        """
        Signal that the content is done. Complete should be True if we
        know it's complete according to message framing.
        """
        self.complete = complete
        self.content_hash = self._hash_processor.digest()
        self.trailers.process(trailers, self)

        if self.can_have_content():
            if "content-length" in self.headers.parsed:
                if self.content_len == self.headers.parsed["content-length"]:
                    self.notes.add("header-content-length", CL_CORRECT)
                else:
                    self.notes.add(
                        "header-content-length",
                        CL_INCORRECT,
                        content_length=f_num(self.content_len),
                    )

    def can_have_content(self) -> bool:
        "Say whether this message can have content."
        return True

    def __repr__(self) -> str:
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        return f"<{', '.join(status)} at {id(self):#x}>"

    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = self.__dict__.copy()
        for key in [
            "_hash_processor",
        ]:
            if key in state:
                del state[key]
        return state


class CL_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = "The Content-Length header is correct."
    text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. REDbot has checked the length of the content and found the `Content-Length`
to be correct."""


class CL_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(response)s's Content-Length header is incorrect."
    text = """\
`Content-Length` is used by HTTP to delimit messages; that is, to mark the end of one message and
the beginning of the next. REDbot has checked the length of the content and found the `Content-Length`
is not correct. This can cause problems not only with connection handling, but also caching, since
an incomplete response is considered uncacheable.

The actual content size sent was %(content_length)s bytes."""
