import binascii
import hashlib
from typing import List, Dict, Any, Callable, Optional, TYPE_CHECKING
import weakref
import zlib

import brotli


from httplint.note import Note, levels, categories
from httplint.util import f_num, display_bytes

if TYPE_CHECKING:
    from httplint.message import HttpMessageLinter


class GzipProcessor:
    def __init__(
        self, message: "HttpMessageLinter", next_processor: Callable[[bytes], None]
    ) -> None:
        self.message = message
        self.next_processor = next_processor
        self._gzip_processor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._in_gzip = False
        self._gzip_header_buffer = b""
        self.ok = True

    def __call__(self, chunk: bytes) -> None:
        if not self.ok:
            return

        if not self._in_gzip:
            self._gzip_header_buffer += chunk
            try:
                chunk = self._read_gzip_header(self._gzip_header_buffer)
                self._in_gzip = True
                self._gzip_header_buffer = b""
            except IndexError:
                return  # not a full header yet
            except IOError as gzip_error:
                self.message.notes.add(
                    "field-content-encoding",
                    BAD_GZIP,
                    gzip_error=str(gzip_error),
                )
                self.ok = False
                self._gzip_header_buffer = b""
                return

            # Since _read_gzip_header strips the header, 'chunk' is now the payload start.
            # We clear the buffer.
            self._gzip_header_buffer = b""

        max_chunk_size = 1024 * 1024
        try:
            decompressed = self._gzip_processor.decompress(chunk, max_chunk_size)
            if decompressed:
                self.next_processor(decompressed)

            while self._gzip_processor.unconsumed_tail:
                tail = self._gzip_processor.unconsumed_tail
                decompressed = self._gzip_processor.decompress(tail, max_chunk_size)
                if decompressed:
                    self.next_processor(decompressed)
                else:
                    break

        except zlib.error as zlib_error:
            self.message.notes.add(
                "field-content-encoding",
                BAD_ZLIB,
                zlib_error=str(zlib_error),
                ok_zlib_len=f_num(self.message.content_length),
                chunk_sample=display_bytes(chunk),
            )
            self.ok = False

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
        method = content[2]
        if method != 8:
            raise IOError("Unknown compression method")
        flag = content[3]

        offset = 10

        if flag & gz_flags["FEXTRA"]:
            if len(content) < offset + 2:
                raise IndexError("Header not complete yet")
            # Read & discard the extra field, if present
            xlen = content[offset] + 256 * content[offset + 1]
            offset += 2
            if len(content) < offset + xlen:
                raise IndexError("Header not complete yet")
            offset += xlen

        if flag & gz_flags["FNAME"]:
            # Read and discard a null-terminated string
            while True:
                if len(content) <= offset:
                    raise IndexError("Header not complete yet")
                st1 = content[offset]
                offset += 1
                if st1 == 0:
                    break

        if flag & gz_flags["FCOMMENT"]:
            # Read and discard a null-terminated string
            while True:
                if len(content) <= offset:
                    raise IndexError("Header not complete yet")
                st2 = content[offset]
                offset += 1
                if st2 == 0:
                    break

        if flag & gz_flags["FHCRC"]:
            if len(content) < offset + 2:
                raise IndexError("Header not complete yet")
            offset += 2

        return content[offset:]


class BrotliProcessor:
    def __init__(
        self, message: "HttpMessageLinter", next_processor: Callable[[bytes], None]
    ) -> None:
        self.message = message
        self.next_processor = next_processor
        self._brotli_processor = brotli.Decompressor()
        self.ok = True

    def __call__(self, chunk: bytes) -> None:
        if not self.ok:
            return

        try:
            chunk = self._brotli_processor.process(chunk)
            if chunk:
                self.next_processor(chunk)
        except brotli.error as brotli_error:
            self.message.notes.add(
                "field-content-encoding",
                BAD_BROTLI,
                brotli_error=str(brotli_error),
                ok_brotli_len=f_num(self.message.content_length),
                chunk_sample=display_bytes(chunk),
            )
            self.ok = False


class ContentEncodingProcessor:
    def __init__(self, message: "HttpMessageLinter") -> None:
        self.message = weakref.proxy(message)
        self.processors: List[Callable[[bytes], None]] = []

        self.length: int = 0
        self.hash: Optional[bytes] = None
        self._hash_processor = hashlib.new("md5")

        self.decode_ok: bool = True  # turn False if we have a problem

        # Pipeline is built lazily to ensure headers are parsed
        self.pipeline: Optional[Callable[[bytes], None]] = None

    def feed_content(self, chunk: bytes) -> None:
        if self.decode_ok:
            if self.pipeline is None:
                self._build_pipeline()
            if self.pipeline:
                self.pipeline(chunk)

    def finish_content(self) -> None:
        self.hash = self._hash_processor.digest()

    def _build_pipeline(self) -> None:
        # Build the pipeline
        # The sink handles the final decoded content
        # Use weakref to avoid cycle: self -> pipeline -> processor -> self._sink_process -> self
        self_ref = weakref.ref(self)

        def sink(chunk: bytes) -> None:
            obj = self_ref()
            if obj:
                obj._sink_process(chunk)  # pylint: disable=protected-access

        self.pipeline = sink

        content_codings = self.message.headers.parsed.get("content-encoding", [])

        # We iterate forward regarding processing order.
        # See init comments in previous version.

        for coding in content_codings:
            if coding in ["gzip", "x-gzip"]:
                self.pipeline = GzipProcessor(self.message, self.pipeline)
            elif coding == "br":
                self.pipeline = BrotliProcessor(self.message, self.pipeline)
            else:
                pass

    def _sink_process(self, chunk: bytes) -> None:
        self._hash_processor.update(chunk)
        self.length += len(chunk)
        for processor in self.processors:
            processor(chunk)


    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = self.__dict__.copy()
        for key in ["_hash_processor", "pipeline", "processors"]:
            if key in state:
                del state[key]
        return state


class BAD_GZIP(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "This message was compressed, but the GZIP header wasn't \
valid."
    _text = """\
GZip-compressed responses have a header that contains metadata. Here, that header wasn't valid;
the error encountered was "`%(gzip_error)s`"."""


class BAD_ZLIB(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "This message was compressed using GZip, but the data was corrupt."
    _text = """\
GZip-compressed responses use zlib compression to reduce the number of bytes transferred on the
wire. However, this response could not be decompressed; the error encountered was
"`%(zlib_error)s`".

%(ok_zlib_len)s bytes were decompressed successfully before this; the erroneous chunk starts with (in hex):

    %(chunk_sample)s
"""


class BAD_BROTLI(Note):
    category = categories.CONNEG
    level = levels.BAD
    _summary = "This message was compressed using Brotli, but the data was corrupt."
    _text = """\
Brotli-compressed responses use brotli compression to reduce the number of bytes transferred on the
wire. However, this response could not be decompressed; the error encountered was
"`%(brotli_error)s`".

%(ok_brotli_len)s bytes were decompressed successfully before this; the erroneous chunk starts with (in hex):

    %(chunk_sample)s
"""
