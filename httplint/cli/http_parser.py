from argparse import Namespace
from enum import Enum
from typing import List, Tuple, Optional

from thor.http.common import HttpMessageHandler, States, Delimiters, no_body_status
from thor.http.error import HttpError, StartLineError, HttpVersionError

from httplint.message import HttpMessageLinter, HttpRequestLinter, HttpResponseLinter
from httplint.types import RawFieldListType


class modes(Enum):
    "Parser modes."
    REQUEST = "request"
    RESPONSE = "response"


class HttpCliParser(HttpMessageHandler):
    default_state = States.WAITING

    def __init__(self, args: Namespace, start_time: Optional[float] = None) -> None:
        self.start_time = start_time
        self.mode = args.mode
        self.linter: HttpMessageLinter
        HttpMessageHandler.__init__(self)

    def handle_input(self, inbytes: bytes) -> None:
        HttpMessageHandler.handle_input(self, inbytes)
        if (
            self._input_delimit == Delimiters.CLOSE
            and self._input_state == States.HEADERS_DONE
        ):
            self.input_end([])

    def input_start(
        self,
        top_line: bytes,
        hdr_tuples: RawFieldListType,
        conn_tokens: List[bytes],
        transfer_codes: List[bytes],
        content_length: int,
    ) -> Tuple[bool, bool]:
        if self.mode == modes.REQUEST:
            self.linter = HttpRequestLinter(start_time=self.start_time)
            method, iri, version = self.request_topline(top_line)
            self.linter.process_request_topline(method, iri, version)
            self.linter.process_headers(hdr_tuples)
            allows_body = bool(content_length and content_length > 0) or (
                transfer_codes != []
            )
            is_final = True
        if self.mode == modes.RESPONSE:
            self.linter = HttpResponseLinter(start_time=self.start_time)
            version, status_code, status_phrase = self.response_topline(top_line)
            self.linter.process_response_topline(version, status_code, status_phrase)
            self.linter.process_headers(hdr_tuples)
            is_final = not status_code.startswith(b"1")
            allows_body = is_final and (
                status_code not in no_body_status
            )  # and (self.method != b"HEAD")
        return allows_body, is_final

    def input_body(self, chunk: bytes) -> None:
        self.linter.feed_content(chunk)

    def input_end(self, trailers: RawFieldListType) -> None:
        self.linter.finish_content(True, trailers)
        for note in self.linter.notes:
            print(f"* {note}")
        self._input_state = States.ERROR

    def input_error(self, err: HttpError, close: bool = True) -> None:
        "Indicate an error state."

    def request_topline(self, top_line: bytes) -> Tuple[bytes, bytes, bytes]:
        try:
            method, req_line = top_line.split(None, 1)
            uri, version = req_line.rsplit(None, 1)
            version = version.rsplit(b"/", 1)[1]
        except (ValueError, IndexError):
            self.input_error(HttpVersionError(top_line.decode("utf-8", "replace")))
            raise ValueError
        return method, uri, version

    def response_topline(self, top_line: bytes) -> Tuple[bytes, bytes, bytes]:
        try:
            proto_version, status_txt = top_line.split(None, 1)
            proto, version = proto_version.rsplit(b"/", 1)
        except (ValueError, IndexError):
            self.input_error(StartLineError(top_line.decode("utf-8", "replace")), True)
            raise ValueError
        if proto != b"HTTP" or version not in [b"1.0", b"1.1", b"2"]:
            self.input_error(HttpVersionError(version.decode("utf-8", "replace")), True)
            raise ValueError
        try:
            status_code, status_phrase = status_txt.split(None, 1)
        except ValueError:
            status_code = status_txt.rstrip()
            status_phrase = b""
        return version, status_code, status_phrase

    def output(self, data: bytes) -> None:
        pass

    def output_done(self) -> None:
        pass
