from argparse import ArgumentParser, Namespace
import sys
import time

from httplint.cli.http_parser import HttpCliParser, modes
from httplint.i18n import set_locale


def main() -> None:
    args = getargs()
    if args.locale:
        set_locale(args.locale)
    start_time = time.time() if args.now else None
    parser = HttpCliParser(args, start_time)
    parser.handle_input(sys.stdin.read().encode("utf-8", "replace"))


def getargs() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "-i",
        "--input",
        choices=[i.value for i in modes],
        default=modes.RESPONSE,
        dest="mode",
        help="The input mode",
    )

    parser.add_argument(
        "-n",
        "--now",
        action="store_true",
        dest="now",
        help="Assume that the HTTP exchange happened now",
    )

    parser.add_argument(
        "-l",
        "--locale",
        dest="locale",
        help="Locale to use for output",
    )
    return parser.parse_args()
