import argparse
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from .check import CatalogChecker
from .utils import load_catalog, save_catalog, find_po_files, get_lang_from_path

DEFAULT_MODEL = "mlx-community/aya-expanse-8b-4bit"
DEFAULT_TEMPERATURE = 0.2
RETRIES = 2

# --protect modes. "links": only URLs and Markdown link targets are masked; code spans
# and placeholders stay visible and are checked after translation. "all": everything is
# masked. "all" dropped tokens (header names, noun-phrase variables) in 5% of ja entries.
PROTECT_LINKS = "links"
PROTECT_ALL = "all"
PROTECT_MODES = (PROTECT_LINKS, PROTECT_ALL)
DEFAULT_PROTECT = PROTECT_LINKS

# Spans the model must not touch are swapped for opaque tokens (@@1@@, @@2@@, ...) and
# put back afterwards. ASCII, no Markdown meaning, and not a word the model translates.
# If the msgid already contains the delimiter, a longer one (@@@, ...) is used.
MARK = "@@"
MAX_ERROR = 200
# others are advisory heuristics
HARD_PREFIXES = ("BAD_VARIABLE", "SYNTAX_ERROR", "CODE_SPAN_CHANGED")
MAX_SPAN = 120  # longer spans are cut when named in an error


def token_re(mark: str) -> "re.Pattern[str]":
    return re.compile(re.escape(mark) + r"(\d+)" + re.escape(mark))


def pick_mark(msgid: str) -> str:
    mark = MARK
    while mark in msgid:
        mark += "@"
    return mark


CODE_PATTERN = r"(?P<code>(?P<ticks>`+)(?:(?!\n[ \t]*\n).)+?(?P=ticks)(?!`))"  # may span lines
CODE_RE = re.compile(CODE_PATTERN, re.DOTALL)
VISIBLE_RE = re.compile(CODE_PATTERN + r"|%\(|%%", re.DOTALL)  # what links mode leaves in view
PROTECTED_RE = re.compile(
    CODE_PATTERN + r"""
    | (?<=\])(?P<target>\((?:[^()\s]|\([^()\s]*\))+\))             # [text]<(target)>
    | (?P<url>https?://(?:%\([^)]*\)[a-z]|[^\s<>"'`)\]])+)         # bare URL
    | (?P<var>%\([^)]+\)[-\#0\ +]*[\d.]*[diouxXeEfFgGcrsa]|%%)     # %(name)s, %%
    """,
    re.VERBOSE | re.DOTALL,
)
URL_TRAILING = ".,;:!?"

PROMPT_START = (
    "You are translating short strings and messages for use in a HTTP linting tool. "
    "Translate the following text to language code '{lang}'. "
    "When they appear, retain embeddded variables as they are. "
    "Do not translate HTTP protocol element names (such as header field names). "
    "Acronyms (such as 'IMS' and 'INM') should be retained. "
    "Return ONLY the translation, NO OTHER TEXT AT ALL."
)
TOKEN_SENTENCE = (
    " Tokens like {token} stand for protected text: copy each one exactly, "
    "once, in the same place."
)
VISIBLE_SENTENCE = " Copy text in backticks and %(name)s placeholders exactly, unchanged."
VISIBLE_SENTENCE_PERCENT = (
    " Copy text in backticks, %(name)s placeholders and %% exactly, unchanged."
)
PROMPT_END = " Here is the text to translate:\n\n{text}"


def protect(text: str, mark: str = MARK, mode: str = DEFAULT_PROTECT) -> Tuple[str, List[str]]:
    """
    Replace protected spans with tokens; return the new text and the spans. In links
    mode, only URLs and Markdown link targets are replaced.
    """
    spans: List[str] = []

    def mask(match: "re.Match[str]") -> str:
        span = match.group(0)
        if mode == PROTECT_LINKS and match.lastgroup in ("code", "var"):
            return span
        tail = ""
        if match.lastgroup == "url":
            stripped = span.rstrip(URL_TRAILING)
            span, tail = stripped, span[len(stripped) :]
        spans.append(span)
        return f"{mark}{len(spans)}{mark}{tail}"

    return PROTECTED_RE.sub(mask, text), spans


def token_error(
    masked: str, translation: str, count: int, mark: str = MARK, ticks: bool = True
) -> Optional[str]:
    """Why the translation can't be un-masked (None if it can)."""
    found = [int(n) for n in token_re(mark).findall(translation)]
    missing = [n for n in range(1, count + 1) if n not in found]
    extra = sorted({n for n in found if n < 1 or n > count})
    repeated = sorted({n for n in found if found.count(n) > 1})
    problems = []
    if missing:
        problems.append("missing " + ", ".join(f"{mark}{n}{mark}" for n in missing))
    if repeated:
        problems.append("repeated " + ", ".join(f"{mark}{n}{mark}" for n in repeated))
    if extra:
        problems.append("invented " + ", ".join(f"{mark}{n}{mark}" for n in extra))
    if ticks and translation.count("`") != masked.count("`"):  # links mode: code_span_rule
        problems.append("added backticks")
    if not problems:
        return None
    return "; ".join(problems) + f". Copy every {mark}N{mark} token exactly, once"


def restore(translation: str, spans: List[str], mark: str = MARK) -> str:
    def put(match: "re.Match[str]") -> str:
        n = int(match.group(1))
        return spans[n - 1] if 1 <= n <= len(spans) else match.group(0)

    return token_re(mark).sub(put, translation)


def shorten(text: str) -> str:
    """One line of at most MAX_ERROR characters (errors can echo model output)."""
    parts, pos = [], 0
    for match in CODE_RE.finditer(text):  # code spans are named verbatim in errors
        parts.append(re.sub(r"\s+", " ", text[pos : match.start()]))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(re.sub(r"\s+", " ", text[pos:]))
    text = "".join(parts).strip()
    return text if len(text) <= MAX_ERROR else text[: MAX_ERROR - 3] + "..."


def build_prompt(
    lang: str,
    masked: str,
    tokens: bool,
    error: Optional[str],
    mark: str = MARK,
    visible: bool = False,
    percent: bool = False,
) -> str:
    start = PROMPT_START.format(lang=lang)
    if tokens:
        start += TOKEN_SENTENCE.format(token=f"{mark}1{mark}")
    if visible:
        start += VISIBLE_SENTENCE_PERCENT if percent else VISIBLE_SENTENCE
    if error:
        start += f" Your previous translation was rejected: {shorten(error)}."
    return start + PROMPT_END.format(text=masked)


# A rule takes (msgid, msgstr, lang) and returns short error strings, which go into
# the retry prompt. The retry loop doesn't depend on which rules exist.
Rule = Callable[[str, str, Optional[str]], List[str]]
_CHECKER = CatalogChecker()


def i18n_check_rule(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
    """The `make i18n-check` checks: variables, syntax, links, tokens, length, ..."""
    return [
        f"{i.issue_type.name} {i.details}".strip().replace("\n", " ")
        for i in _CHECKER.check_pair(msgid, msgstr, lang)
    ]


def named(span: str) -> str:
    """A span for an error message; a very long one is cut, keeping its backticks."""
    if len(span) <= MAX_SPAN:
        return span
    ticks = span[: len(span) - len(span.lstrip("`"))]
    return span[: MAX_SPAN - len(ticks) - 3] + "..." + ticks


def text_kept(span: str, msgstr: str) -> bool:
    """The text inside span is in msgstr, as a whole word, outside any code span."""
    inner = span.strip("`").strip()
    if not inner:
        return False
    before = r"(?<![A-Za-z0-9])" if inner[0].isalnum() else ""
    after = r"(?![A-Za-z0-9])" if inner[-1].isalnum() else ""
    return bool(re.search(before + re.escape(inner) + after, CODE_RE.sub(" ", msgstr)))


def code_span_rule(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
    """
    Every backtick span of msgid must be in msgstr, byte for byte (multisets; order is
    free). A span whose text changed or went missing is a hard failure (CODE_SPAN_CHANGED);
    one that kept its text but lost its backticks, or an added span, is advisory.
    Placeholders are checked by BAD_VARIABLE in i18n_check_rule. An odd number of
    backticks in msgid means the spans can't be paired reliably, so there is no verdict.
    """
    if msgid.count("`") % 2:
        return []
    want = Counter(m.group(0) for m in CODE_RE.finditer(msgid))
    got = Counter(m.group(0) for m in CODE_RE.finditer(msgstr))
    errors = []
    for span in list(want - got)[:3]:
        kind = "CODE_SPAN_BACKTICKS" if text_kept(span, msgstr) else "CODE_SPAN_CHANGED"
        errors.append(f"{kind} keep {named(span)} exactly, including the backticks")
    if not errors:
        errors = [
            f"CODE_SPAN_ADDED you added {named(span)}: don't add backticks"
            for span in list(got - want)[:3]
        ]
    return errors


RULES: List[Rule] = [code_span_rule, i18n_check_rule]


def match_whitespace(msgid: str, msgstr: str) -> str:
    """Give msgstr the leading and trailing whitespace of msgid."""
    lead = msgid[: len(msgid) - len(msgid.lstrip())]
    trail = msgid[len(msgid.rstrip()) :]
    return lead + msgstr.strip() + trail


@dataclass
class Result:
    text: Optional[str]  # None: nothing usable
    retries: int = 0
    error: str = ""  # why the last attempt failed
    fuzzy: bool = False  # text failed only advisory checks; keep it for review


def translate(
    ask: Callable[[str], str],
    lang: str,
    msgid: str,
    rules: Optional[List[Rule]] = None,
    mode: str = DEFAULT_PROTECT,
) -> Result:
    """
    Translate msgid with protected spans masked (see PROTECT_*), validating the result with
    the rules and retrying up to RETRIES times. If the last attempt fails only advisory rules,
    its text is returned with fuzzy set; any other failure returns no text.
    """
    mark = pick_mark(msgid)
    masked, spans = protect(msgid, mark, mode)
    visible = mode == PROTECT_LINKS and bool(VISIBLE_RE.search(masked))
    percent = visible and "%%" in masked
    error = ""
    candidate: Optional[str] = None
    advisory = False
    for attempt in range(RETRIES + 1):
        candidate, advisory = None, False
        raw = ask(
            build_prompt(lang, masked, bool(spans), error or None, mark, visible, percent)
        ).strip()
        if not raw:
            error = "the translation was empty"
            continue
        error = token_error(masked, raw, len(spans), mark, mode == PROTECT_ALL) or ""
        if error:
            continue
        text = match_whitespace(msgid, restore(raw, spans, mark))
        problems = [
            p for rule in (RULES if rules is None else rules) for p in rule(msgid, text, lang)
        ]
        if not problems:
            return Result(text, attempt)
        hard = [p for p in problems if p.startswith(HARD_PREFIXES)]
        error = shorten("; ".join(hard or problems))  # advisory noise would crowd out the cause
        candidate = text
        advisory = not hard
    if candidate is not None and advisory:
        return Result(candidate, RETRIES, error, fuzzy=True)
    return Result(None, RETRIES, shorten(error))


def supports_option(model: Any, name: str) -> bool:
    options = getattr(model, "Options", None)
    return name in getattr(options, "model_fields", {})


def autotranslate_file(
    po_file,
    lang,
    model_id,
    rpm,
    temperature=DEFAULT_TEMPERATURE,
    model=None,
    protect_mode=DEFAULT_PROTECT,
):
    catalog = load_catalog(po_file)
    if model is None:
        import llm  # pylint: disable=import-outside-toplevel

        model = llm.get_model(model_id)
    options = {}
    if supports_option(model, "temperature"):
        options["temperature"] = temperature
    else:
        print(f"{model_id} has no temperature option; using its default.")

    def ask(prompt: str) -> str:
        return model.prompt(prompt, **options).text()

    # Identify messages that need translation (empty or fuzzy)
    to_translate = [m for m in catalog if m.id and (not m.string or "fuzzy" in m.flags)]
    count = 0
    left_empty: List[Tuple[Any, str]] = []
    kept_fuzzy: List[Tuple[Any, str]] = []
    errors = []

    print(
        f"Found {len(to_translate)} messages to translate using {model_id} "
        f"(--protect {protect_mode})."
    )

    exception_count = 0
    sleep_time = 60.0 / rpm if rpm > 0 else 0

    for i, message in enumerate(to_translate):
        try:
            if i > 0 and sleep_time > 0:
                time.sleep(sleep_time)

            if isinstance(message.id, str):
                result = translate(ask, lang, message.id, mode=protect_mode)
            else:  # plural entries: unchanged, no masking or validation
                reply = ask(build_prompt(lang, str(message.id), False, None)).strip()
                result = Result(reply or None)
            exception_count = 0

            if result.text and not result.fuzzy:
                message.string = result.text
                if "fuzzy" in message.flags:
                    message.flags.remove("fuzzy")
                count += 1
                sys.stdout.write(".")
            elif result.text:
                message.string = result.text
                message.flags.add("fuzzy")
                kept_fuzzy.append((message.id, result.error))
                sys.stdout.write("?")
            else:
                message.string = ""
                message.flags.discard("fuzzy")
                left_empty.append((message.id, result.error))
                sys.stdout.write("x")
        except KeyboardInterrupt:
            print("\n\nAborting: User interrupted.")
            save_catalog(po_file, catalog)
            sys.exit(1)
        except Exception as e:  # pylint: disable=broad-exception-caught
            exception_count += 1
            sys.stdout.write("E")

            error_msg = str(e)
            if exception_count == 1:
                print(f"\n\nFirst exception encountered: {error_msg}")

            errors.append(f"Error: {error_msg} for {message.id[:40]}...")

            if exception_count >= 3:
                print("\n\nAborting: Too many exceptions encountered.")
                save_catalog(po_file, catalog)
                sys.exit(1)

        sys.stdout.flush()

    save_catalog(po_file, catalog)
    print(f"\nAuto-translated {count} messages.")

    for entries, what in (
        (left_empty, f"left empty (no valid translation; --protect {protect_mode})"),
        (kept_fuzzy, "kept as fuzzy for review (failed advisory checks)"),
    ):
        if entries:
            print(f"\n{len(entries)} entries {what}:")
            for msgid, error in entries:
                print(f"  - {' '.join(str(msgid).split())[:70]}\n      {error}")

    if errors:
        print(f"\nEncountered {len(errors)} errors:")
        # Print first few errors to avoid spamming
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-translate missing strings")
    parser.add_argument("--po_file", help="Path to a single PO file")
    parser.add_argument("--locale_dir", help="Path to locale directory (process all locales)")
    parser.add_argument("--lang", help="Target language code (required for single file)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="LLM model to use (default: %(default)s)",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=0,
        help="Requests per minute (default: 0; 0 or less: unlimited)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature, if the model supports it (default: %(default)s)",
    )
    parser.add_argument(
        "--protect",
        choices=PROTECT_MODES,
        default=DEFAULT_PROTECT,
        help="Text hidden from the model: 'links' (URLs and link targets only; code spans "
        "and placeholders are verified afterwards) or 'all' (everything; it dropped tokens "
        "in 5%% of ja entries) (default: %(default)s)",
    )
    return parser


def main():
    args = build_parser().parse_args()

    if args.locale_dir:
        po_files = find_po_files(args.locale_dir)
        if not po_files:
            print(f"No PO files found in {args.locale_dir}")
            sys.exit(0)
        for po_file in po_files:
            lang = get_lang_from_path(po_file)
            if not lang:
                print(f"Could not determine language for {po_file}, skipping.")
                continue
            print(f"Processing {lang} ({po_file})...")
            autotranslate_file(
                po_file, lang, args.model, args.rpm, args.temperature, protect_mode=args.protect
            )
    elif args.po_file:
        if not args.lang:
            print("Error: --lang is required for single file autotranslate")
            sys.exit(1)
        autotranslate_file(
            args.po_file,
            args.lang,
            args.model,
            args.rpm,
            args.temperature,
            protect_mode=args.protect,
        )
    else:
        print("Error: Either --po_file or --locale_dir must be specified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
