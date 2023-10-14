from argparse import ArgumentParser, Namespace
import sys
import time
from typing import List, Tuple

from thor.http.common import HttpMessageHandler, States, Delimiters, no_body_status
from thor.http.error import HttpError, StartLineError, HttpVersionError

from httplint.message import HttpResponse
from httplint.type import RawFieldListType


def main() -> None:
    args = getargs()
    start_time = int(time.time()) if args.now else None
    linter = HttpResponse(start_time=start_time)
    parser = HttpParser(linter)
    parser.handle_input(sys.stdin.read().encode("utf-8"))
    if parser._input_delimit == Delimiters.CLOSE:
        parser.input_end([])


class HttpParser(HttpMessageHandler):
    default_state = States.WAITING

    def __init__(self, message: HttpResponse) -> None:
        self.message = message
        HttpMessageHandler.__init__(self)

    def input_start(
        self,
        top_line: bytes,
        hdr_tuples: RawFieldListType,
        conn_tokens: List[bytes],
        transfer_codes: List[bytes],
        content_length: int,
    ) -> Tuple[bool, bool]:
        version, status_code, status_phrase = self.response_topline(top_line)
        self.message.process_top_line(version, status_code, status_phrase)
        self.message.process_headers(hdr_tuples)
        is_final = not status_code.startswith(b"1")
        allows_body = is_final and (
            status_code not in no_body_status
        )  # and (self.method != b"HEAD")
        return allows_body, is_final

    def input_body(self, chunk: bytes) -> None:
        self.message.feed_content(chunk)

    def input_end(self, trailers: RawFieldListType) -> None:
        self.message.finish_content(True, trailers)
        for note in self.message.notes:
            print(f"* {note}")

    def input_error(self, err: HttpError, close: bool = True) -> None:
        "Indicate an error state."

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


def getargs() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "-i",
        "--input",
        choices=["response", "exchange"],
        default="response",
        dest="input_type",
        help="identify the type of the input",
    )

    parser.add_argument(
        "-n",
        "--now",
        action="store_true",
        dest="now",
        help="Assume that the HTTP exchange happened now",
    )
    return parser.parse_args()
