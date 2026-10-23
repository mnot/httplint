import sys
import time
from argparse import ArgumentParser, Namespace

from httplint.cli.http_parser import HttpCliParser, modes
from httplint.i18n import set_locale


def main() -> None:
    args = getargs()
    with set_locale(args.locale):
        start_time = time.time() if args.now else None
        parser = HttpCliParser(args, start_time)
        parser.handle_input(sys.stdin.buffer.read())
        if parser.failed:
            sys.exit(1)


def getargs() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "-i",
        "--input",
        type=modes,
        metavar="{request,response}",
        choices=list(modes),
        default=modes.RESPONSE,
        dest="mode",
        help="The input mode (default: response)",
    )

    parser.add_argument(
        "-n",
        "--now",
        action="store_true",
        dest="now",
        help=(
            "Assume that the HTTP exchange happened now. Without it, a two-digit year in an "
            "obsolete date is resolved against the time linting runs, so the result for a "
            "year near the 50-year line depends on when it is run."
        ),
    )

    parser.add_argument(
        "-l",
        "--locale",
        dest="locale",
        help="Locale to use for output",
    )
    return parser.parse_args()
