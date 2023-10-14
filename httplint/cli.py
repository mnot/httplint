from argparse import ArgumentParser, Namespace
import sys
import time

from thor.http.common import Delimiters

from httplint.cli_http_parser import HttpParser
from httplint.message import HttpResponse


def main() -> None:
    args = getargs()
    start_time = int(time.time()) if args.now else None
    linter = HttpResponse(start_time=start_time)
    parser = HttpParser(linter)
    parser.handle_input(sys.stdin.read().encode("utf-8"))
    if parser._input_delimit == Delimiters.CLOSE:
        parser.input_end([])


def getargs() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "-i",
        "--input",
        choices=["request", "response", "exchange"],
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
