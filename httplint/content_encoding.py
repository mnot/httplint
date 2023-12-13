import binascii
import hashlib
from typing import List, Dict, Any, Callable, Optional, TYPE_CHECKING
import zlib

from httplint.note import Note, levels, categories
from httplint.util import f_num, display_bytes

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class ContentEncodingProcessor:
    def __init__(self, message: "HttpMessageLinter") -> None:
        self.message = message
        self.processors: List[Callable[[bytes], None]] = []

        self.length: int = 0
        self.hash: Optional[bytes] = None
        self._hash_processor = hashlib.new("md5")

        self.decode_ok: bool = True  # turn False if we have a problem

        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._in_gzip = False
        self._gzip_header_buffer = b""

    def feed_content(self, chunk: bytes) -> None:
        if self.decode_ok:
            decoded_chunk = self._process_content_codings(chunk)
            for processor in self.processors:
                processor(decoded_chunk)

    def finish_content(self) -> None:
        self.hash = self._hash_processor.digest()

    def _process_content_codings(self, chunk: bytes) -> bytes:
        """
        Decode a chunk according to the message's content-encoding header.

        Currently supports gzip.
        """
        content_codings = self.message.headers.parsed.get("content-encoding", [])
        content_codings.reverse()
        for coding in content_codings:
            if coding in ["gzip", "x-gzip"]:
                if not self._in_gzip:
                    self._gzip_header_buffer += chunk
                    try:
                        chunk = self._read_gzip_header(self._gzip_header_buffer)
                        self._in_gzip = True
                    except IndexError:
                        return b""  # not a full header yet
                    except IOError as gzip_error:
                        self.message.notes.add(
                            "header-content-encoding",
                            BAD_GZIP,
                            gzip_error=str(gzip_error),
                        )
                        self.decode_ok = False
                        return b""
                try:
                    chunk = self._gzip_processor.decompress(chunk)
                except zlib.error as zlib_error:
                    self.message.notes.add(
                        "header-content-encoding",
                        BAD_ZLIB,
                        zlib_error=str(zlib_error),
                        ok_zlib_len=f_num(self.message.content_length),
                        chunk_sample=display_bytes(chunk),
                    )
                    self.decode_ok = False
                    return b""
            else:
                # we can't handle other codecs, so punt on content processing.
                self.decode_ok = False
                return b""
        self._hash_processor.update(chunk)
        self.length += len(chunk)
        return chunk

    @staticmethod
    def _read_gzip_header(content: bytes) -> bytes:
        """
        Parse a string for a GZIP header; if present, return remainder of
        gzipped content.
        """
        # adapted from gzip.py
        gz_flags = {"FTEXT": 1, "FHCRC": 2, "FEXTRA": 4, "FNAME": 8, "FCOMMENT": 16}
        if len(content) < 10:
            raise IndexError("Header not complete yet")
        magic = content[:2]
        if magic != b"\037\213":
            raise IOError(
                f"Not a gzip header (magic is hex {binascii.b2a_hex(magic).decode('ascii')}, "
                "should be 1f8b)"
            )
        method = ord(content[2:3])
        if method != 8:
            raise IOError("Unknown compression method")
        flag = ord(content[3:4])
        content_l = list(content[10:])
        if flag & gz_flags["FEXTRA"]:
            # Read & discard the extra field, if present
            xlen = content_l.pop(0)
            xlen = xlen + 256 * content_l.pop(0)
            content_l = content_l[xlen:]
        if flag & gz_flags["FNAME"]:
            # Read and discard a null-terminated string
            # containing the filename
            while True:
                st1 = content_l.pop(0)
                if not content_l or st1 == 0:
                    break
        if flag & gz_flags["FCOMMENT"]:
            # Read and discard a null-terminated string containing a comment
            while True:
                st2 = content_l.pop(0)
                if not content_l or st2 == 0:
                    break
        if flag & gz_flags["FHCRC"]:
            content_l = content_l[2:]  # Read & discard the 16-bit header CRC
        return bytes(content_l)

    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = self.__dict__.copy()
        for key in ["_hash_processor", "_gzip_processor"]:
            if key in state:
                del state[key]
        return state


class BAD_GZIP(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "%(message)s was compressed using GZip, but the header wasn't \
valid."
    _text = """\
GZip-compressed responses have a header that contains metadata. %(message)s's header wasn't valid;
the error encountered was "`%(gzip_error)s`"."""


class BAD_ZLIB(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "%(message)s was compressed using GZip, but the data was corrupt."
    _text = """\
GZip-compressed responses use zlib compression to reduce the number of bytes transferred on the
wire. However, this response could not be decompressed; the error encountered was
"`%(zlib_error)s`".

%(ok_zlib_len)s bytes were decompressed successfully before this; the erroneous chunk starts with (in hex):

    %(chunk_sample)s
"""
