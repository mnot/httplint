import argparse
import re
import sys
import time
from typing import Any, Callable, List, Optional, Tuple

from .check import CatalogChecker
from .utils import load_catalog, save_catalog, find_po_files, get_lang_from_path

DEFAULT_MODEL = "mlx-community/aya-expanse-8b-4bit"
DEFAULT_TEMPERATURE = 0.2
RETRIES = 2

# Spans the model must not touch are swapped for opaque tokens (@@1@@, @@2@@, ...) and
# put back afterwards. ASCII, no Markdown meaning, and not a word the model translates.
TOKEN_RE = re.compile(r"@@(\d+)@@")

PROTECTED_RE = re.compile(
    r"""
      (?P<code>(?P<ticks>`+)(?:(?!\n[ \t]*\n).)+?(?P=ticks)(?!`))  # `code`, may span lines
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
    " Tokens like @@1@@ stand for protected text: copy each one exactly, "
    "once, in the same place."
)
PROMPT_END = " Here is the text to translate:\n\n{text}"


def protect(text: str) -> Tuple[str, List[str]]:
    """Replace protected spans with tokens; return the new text and the spans."""
    spans: List[str] = []

    def mask(match: "re.Match[str]") -> str:
        span = match.group(0)
        tail = ""
        if match.lastgroup == "url":
            stripped = span.rstrip(URL_TRAILING)
            span, tail = stripped, span[len(stripped) :]
        spans.append(span)
        return f"@@{len(spans)}@@{tail}"

    return PROTECTED_RE.sub(mask, text), spans


def token_error(masked: str, translation: str, count: int) -> Optional[str]:
    """Why the translation can't be un-masked (None if it can)."""
    found = [int(n) for n in TOKEN_RE.findall(translation)]
    missing = [n for n in range(1, count + 1) if n not in found]
    extra = sorted({n for n in found if n < 1 or n > count})
    repeated = sorted({n for n in found if found.count(n) > 1})
    problems = []
    if missing:
        problems.append("missing " + ", ".join(f"@@{n}@@" for n in missing))
    if repeated:
        problems.append("repeated " + ", ".join(f"@@{n}@@" for n in repeated))
    if extra:
        problems.append("invented " + ", ".join(f"@@{n}@@" for n in extra))
    if translation.count("`") != masked.count("`"):
        problems.append("added backticks")
    if not problems:
        return None
    return "; ".join(problems) + ". Copy every @@N@@ token exactly, once"


def restore(translation: str, spans: List[str]) -> str:
    return TOKEN_RE.sub(lambda m: spans[int(m.group(1)) - 1], translation)


def build_prompt(lang: str, masked: str, tokens: bool, error: Optional[str]) -> str:
    start = PROMPT_START.format(lang=lang)
    if tokens:
        start += TOKEN_SENTENCE
    if error:
        start += f" Your previous translation was rejected: {error}."
    return start + PROMPT_END.format(text=masked)


def describe(issues: List[Any]) -> str:
    """One line for the prompt from the i18n-check issues."""
    return "; ".join(f"{i.issue_type.name} {i.details}".strip().replace("\n", " ") for i in issues)


def translate(
    ask: Callable[[str], str], lang: str, msgid: str, checker: CatalogChecker
) -> Tuple[Optional[str], int, str]:
    """
    Translate msgid with protected spans masked, validating the result as i18n-check
    would and retrying up to RETRIES times. Returns (translation or None, retries
    used, last error).
    """
    masked, spans = protect(msgid)
    error: Optional[str] = None
    for attempt in range(RETRIES + 1):
        raw = ask(build_prompt(lang, masked, bool(spans), error)).strip()
        if not raw:
            error = "the translation was empty"
            continue
        error = token_error(masked, raw, len(spans)) if spans else None
        if error is None:
            candidate = restore(raw, spans)
            issues = checker.check_pair(msgid, candidate, lang)
            if not issues:
                return candidate, attempt, ""
            error = describe(issues)
    return None, RETRIES, error or ""


def supports_option(model: Any, name: str) -> bool:
    options = getattr(model, "Options", None)
    return name in getattr(options, "model_fields", {})


def autotranslate_file(po_file, lang, model_id, rpm, temperature=DEFAULT_TEMPERATURE, model=None):
    catalog = load_catalog(po_file)
    if model is None:
        import llm  # pylint: disable=import-outside-toplevel

        model = llm.get_model(model_id)
    options = {}
    if supports_option(model, "temperature"):
        options["temperature"] = temperature
    else:
        print(f"{model_id} has no temperature option; using its default.")
    checker = CatalogChecker()

    def ask(prompt: str) -> str:
        return model.prompt(prompt, **options).text()

    # Identify messages that need translation (empty or fuzzy)
    to_translate = [m for m in catalog if m.id and (not m.string or "fuzzy" in m.flags)]
    count = 0
    left_empty = []
    errors = []

    print(f"Found {len(to_translate)} messages to translate using {model_id}.")

    exception_count = 0
    sleep_time = 60.0 / rpm if rpm > 0 else 0

    for i, message in enumerate(to_translate):
        try:
            if i > 0 and sleep_time > 0:
                time.sleep(sleep_time)

            if isinstance(message.id, str):
                translation, _, _ = translate(ask, lang, message.id, checker)
            else:  # plural entries: unchanged, no masking or validation
                translation = ask(build_prompt(lang, str(message.id), False, None))
                translation = translation.strip() or None
            exception_count = 0

            if translation:
                message.string = translation
                if "fuzzy" in message.flags:
                    message.flags.remove("fuzzy")
                count += 1
                sys.stdout.write(".")
            else:
                message.string = ""
                message.flags.discard("fuzzy")
                left_empty.append(message.id)
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

    if left_empty:
        print(f"\n{len(left_empty)} entries left empty (no valid translation):")
        for msgid in left_empty:
            print(f"  - {' '.join(str(msgid).split())[:70]}")

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
            autotranslate_file(po_file, lang, args.model, args.rpm, args.temperature)
    elif args.po_file:
        if not args.lang:
            print("Error: --lang is required for single file autotranslate")
            sys.exit(1)
        autotranslate_file(args.po_file, args.lang, args.model, args.rpm, args.temperature)
    else:
        print("Error: Either --po_file or --locale_dir must be specified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
