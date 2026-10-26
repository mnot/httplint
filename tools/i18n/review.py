#!/usr/bin/env python3
"""
Optional LLM review of machine-translated strings.

This is advisory tooling: it asks a language model to judge each translation and writes
a Markdown report. It NEVER changes a msgstr. With --mark-fuzzy it can set the "fuzzy"
flag on entries judged "major", so that `pybabel compile` skips them (falling back to
English) and `make i18n-check` lists them.

The strings are sent to whichever model provider MODEL uses.
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from babel.messages import pofile
from babel.messages.catalog import Catalog, Message

from .utils import find_po_files, get_lang_from_path, load_catalog, save_catalog

# A model call: prompt in, reply text out. Tests substitute a fake.
ModelCall = Callable[[str], str]

CONFIRM_OVER = 50  # more entries than this needs --yes
MAX_CONSECUTIVE_ERRORS = 3
VERDICTS = ("ok", "minor", "major")
LANGUAGE_NAMES = {
    "fr": "French",
    "es": "Spanish",
    "ja": "Japanese",
    "zh": "Chinese",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "ko": "Korean",
    "ru": "Russian",
}


## Selection


def message_id(message: Message) -> str:
    """The (singular) msgid of a message."""
    return message.id[0] if isinstance(message.id, (tuple, list)) else message.id


def entry_key(message: Message) -> Tuple[str, Optional[str]]:
    return (message_id(message), message.context)


def _text(message: Message) -> str:
    """The translated text of a message (all plural forms, joined)."""
    string = message.string
    if isinstance(string, (tuple, list)):
        return "\n".join(s for s in string if s)
    return string or ""


def select_entries(catalog: Catalog, previous: Optional[Catalog] = None) -> List[Message]:
    """
    Messages with a non-empty, non-fuzzy translation. If `previous` is given, only
    those whose translation is new or different from `previous`.
    """
    old: Dict[Tuple[str, Optional[str]], str] = {}
    if previous is not None:
        old = {entry_key(m): _text(m) for m in previous if m.id}
    selected = []
    for message in catalog:
        if not message.id or not _text(message) or "fuzzy" in message.flags:
            continue
        if previous is not None and old.get(entry_key(message)) == _text(message):
            continue
        selected.append(message)
    return selected


class GitError(Exception):
    pass


def load_catalog_at_ref(ref: str, po_path: str) -> Catalog:
    """
    The catalog as committed at git ref `ref`. A file that did not exist at `ref`
    (a new locale) gives an empty catalog, so every entry counts as new.
    """
    directory = os.path.dirname(os.path.abspath(po_path))
    name = os.path.basename(po_path)
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=directory,
        capture_output=True,
        check=False,
    )
    if verify.returncode != 0:
        raise GitError(f"Not a valid git ref (or not in a git repository): {ref}")
    shown = subprocess.run(
        ["git", "show", f"{ref}:./{name}"],
        cwd=directory,
        capture_output=True,
        check=False,
    )
    if shown.returncode != 0:
        return Catalog()
    return pofile.read_po(io.BytesIO(shown.stdout))


## Prompts

SYSTEM_PREAMBLE = (
    "You are an expert technical translator and reviewer for software documentation " "about HTTP."
)


def language_name(lang: str) -> str:
    base = re.split(r"[_\-@.]", lang)[0].lower()
    return LANGUAGE_NAMES.get(base, lang)


def build_backtranslate_prompt(lang: str, msgstr: str) -> str:
    return (
        f"Translate the following {language_name(lang)} text into English. "
        "Keep Markdown formatting, HTTP header names, and placeholders such as "
        "%(name)s exactly as they are. Return ONLY the English translation, with no "
        f"other text.\n\n{msgstr}"
    )


def build_review_prompt(
    lang: str, msgid: str, msgstr: str, backtranslation: Optional[str] = None
) -> str:
    name = language_name(lang)
    parts = [
        f"{SYSTEM_PREAMBLE} Below is a string from httplint, a tool that explains "
        "HTTP messages and their problems to developers, and its translation from "
        f"English into {name} ({lang}). Review the translation.\n\n"
        "Judge it on:\n"
        "1. Meaning fidelity: nothing added, dropped, or contradicted.\n"
        "2. Technical register: the precise terminology a developer would expect, "
        "not literary or colloquial wording.\n"
        "3. HTTP names left untranslated: header field names (such as Cache-Control), "
        "directive, parameter and method names, status codes, and acronyms must stay "
        "in English.\n"
        "4. Markup preserved: Markdown (backticks, links, lists, line breaks) and "
        "placeholders such as %(name)s must be kept exactly.\n",
        f"English original:\n<<<\n{msgid}\n>>>\n",
        f"{name} translation:\n<<<\n{msgstr}\n>>>\n",
    ]
    if backtranslation is not None:
        parts.append(
            "An independent translator, who never saw the original, translated the "
            f"{name} text back into English:\n<<<\n{backtranslation}\n>>>\n"
            "Compare its meaning with the English original and treat any difference "
            "as a possible problem with the translation.\n"
        )
    parts.append(
        "Reply with ONLY a JSON object, with no other text and no code fence:\n"
        '{"verdict": "ok" | "minor" | "major", "problems": ["..."], '
        '"suggestion": "..."}\n'
        '"ok": fine as it is. "minor": understandable but should be improved '
        '(wording, register, small omissions). "major": the meaning is wrong, '
        "missing or contradicted, a header name or acronym was translated, a "
        "placeholder or link was broken, or the text is unusable.\n"
        '"problems" is a list of short English descriptions (empty if "ok"). '
        f'"suggestion" is a corrected {name} translation, or "" if "ok".'
    )
    return "\n".join(parts)


RETRY_SUFFIX = (
    "\n\nYour previous reply was not a valid JSON object in the requested format. "
    "Reply again with ONLY the JSON object."
)


## Parsing

THINK_BLOCK_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.I)


@dataclass
class Verdict:
    verdict: str
    problems: List[str] = field(default_factory=list)
    suggestion: str = ""


def parse_verdict(reply: str) -> Optional[Verdict]:
    """Extract the verdict object from a model reply, or None if there isn't one."""
    text = THINK_BLOCK_RE.sub("", reply or "")
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            data, _ = decoder.raw_decode(text[match.start() :])
        except ValueError:
            continue
        verdict = _verdict_from(data)
        if verdict:
            return verdict
    return None


def _verdict_from(data: object) -> Optional[Verdict]:
    if not isinstance(data, dict):
        return None
    raw = data.get("verdict")
    if not isinstance(raw, str) or raw.strip().lower() not in VERDICTS:
        return None
    problems = data.get("problems", [])
    if isinstance(problems, str):
        problems = [problems]
    if not isinstance(problems, list):
        problems = []
    suggestion = data.get("suggestion", "")
    return Verdict(
        raw.strip().lower(),
        [str(p) for p in problems if p],
        suggestion if isinstance(suggestion, str) else str(suggestion),
    )


## Reviewing


@dataclass
class ReviewResult:
    message: Message
    verdict: Optional[Verdict] = None
    backtranslation: Optional[str] = None
    error: Optional[str] = None

    @property
    def level(self) -> str:
        return self.verdict.verdict if self.verdict else "error"


def review_entry(
    call: ModelCall, lang: str, message: Message, backtranslate: bool = False
) -> ReviewResult:
    """Review one message. Never raises: failures end up in `error`."""
    result = ReviewResult(message)
    msgid = message_id(message)
    msgstr = _text(message)
    try:
        if backtranslate:
            result.backtranslation = call(build_backtranslate_prompt(lang, msgstr)).strip()
        prompt = build_review_prompt(lang, msgid, msgstr, result.backtranslation)
        result.verdict = parse_verdict(call(prompt))
        if result.verdict is None:
            result.verdict = parse_verdict(call(prompt + RETRY_SUFFIX))
        if result.verdict is None:
            result.error = "model reply was not valid JSON (after one retry)"
    except Exception as exc:  # pylint: disable=broad-exception-caught
        result.error = f"{type(exc).__name__}: {exc}"
    return result


class CountingCall:
    """Wraps a ModelCall to count calls."""

    def __init__(self, call: ModelCall) -> None:
        self.call = call
        self.count = 0

    def __call__(self, prompt: str) -> str:
        self.count += 1
        return self.call(prompt)


def llm_model_call(model_id: str) -> ModelCall:
    """A ModelCall backed by the `llm` package (pip install -e .[i18n])."""
    try:
        import llm  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise SystemExit("The 'llm' package is required: run `make venv-i18n`.") from exc
    try:
        model = llm.get_model(model_id)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise SystemExit(
            f"Cannot load model '{model_id}': {exc}\n"
            "For Claude: `llm install llm-anthropic`, then `llm keys set anthropic`, "
            "and use a model id from `llm models`."
        ) from exc

    def call(prompt: str) -> str:
        return model.prompt(prompt).text()

    return call


def review_catalog(
    call: ModelCall,
    lang: str,
    messages: Sequence[Message],
    backtranslate: bool = False,
    progress: Optional[Callable[[ReviewResult], None]] = None,
) -> Tuple[List[ReviewResult], bool]:
    """Review messages in order. Returns (results, aborted)."""
    results: List[ReviewResult] = []
    consecutive_errors = 0
    for message in messages:
        result = review_entry(call, lang, message, backtranslate)
        results.append(result)
        if progress:
            progress(result)
        consecutive_errors = consecutive_errors + 1 if result.error else 0
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            return results, True
    return results, False


## Output


def _fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _block(text: str) -> str:
    fence = _fence(text)
    return f"{fence}\n{text}\n{fence}"


def render_report(
    lang: str, model_id: str, results: Sequence[ReviewResult], aborted: bool = False
) -> str:
    counts = {level: 0 for level in (*VERDICTS, "error")}
    for result in results:
        counts[result.level] += 1
    lines = [
        f"# Translation review: {lang}",
        "",
        f"Model: `{model_id}`. This report is advisory: nothing in the catalog was "
        "changed by the review.",
        "",
        f"Reviewed {len(results)}: {counts['major']} major, {counts['minor']} minor, "
        f"{counts['ok']} ok, {counts['error']} could not be reviewed.",
    ]
    if aborted:
        lines += ["", "The run was aborted after repeated model errors; it is partial."]
    for level, title in (("major", "Major"), ("minor", "Minor"), ("error", "Errors")):
        group = [r for r in results if r.level == level]
        if not group:
            continue
        lines += ["", f"## {title} ({len(group)})"]
        for result in group:
            message = result.message
            lines += ["", f"### Line {message.lineno}", "", "msgid:", ""]
            lines += [_block(message_id(message))]
            lines += ["", "msgstr:", "", _block(_text(message))]
            if result.backtranslation is not None:
                lines += ["", "Back-translation:", "", _block(result.backtranslation)]
            if result.error:
                lines += ["", f"Error: {result.error}"]
            if result.verdict:
                lines += [""] + [f"- {p}" for p in result.verdict.problems]
                if result.verdict.suggestion:
                    lines += ["", "Suggestion:", "", _block(result.verdict.suggestion)]
    return "\n".join(lines) + "\n"


def write_report(path: str, text: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def mark_fuzzy(po_path: str, catalog: Catalog, results: Sequence[ReviewResult]) -> int:
    """
    Set the fuzzy flag on messages judged major, and save the catalog. msgstr is not
    touched. Returns the number of messages flagged.
    """
    flagged = 0
    for result in results:
        if result.level == "major" and "fuzzy" not in result.message.flags:
            result.message.flags.add("fuzzy")
            flagged += 1
    if flagged:
        save_catalog(po_path, catalog)
    return flagged


## Command line


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advisory LLM review of translated strings (never edits msgstr)."
    )
    parser.add_argument("--locale_dir", default="httplint/translations")
    parser.add_argument("--locale", default="all", help="Locale to review, e.g. fr (default: all)")
    parser.add_argument(
        "--model", help="llm model id (required unless --dry-run); see TRANSLATION.md"
    )
    parser.add_argument(
        "--since",
        metavar="REF",
        help="Only review entries whose msgstr is new or changed since git ref REF",
    )
    parser.add_argument("--limit", type=int, help="Review at most N entries per run")
    parser.add_argument(
        "--yes",
        action="store_true",
        help=f"Proceed with more than {CONFIRM_OVER} entries",
    )
    parser.add_argument(
        "--backtranslate",
        action="store_true",
        help="First translate each msgstr back to English (separate call), then compare",
    )
    parser.add_argument(
        "--mark-fuzzy",
        action="store_true",
        help="Set the fuzzy flag on entries judged major (default: off)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be reviewed and the number of model calls; call nothing",
    )
    parser.add_argument(
        "--output",
        help="Report path; with several locales a '-<locale>' is added before the "
        "extension (default: i18n-review-<locale>.md in the current directory)",
    )
    args = parser.parse_args(argv)
    if not args.dry_run and not args.model:
        parser.error("--model is required (there is no default; this may cost money)")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def report_path(args: argparse.Namespace, lang: str, multiple: bool) -> str:
    if not args.output:
        return f"i18n-review-{lang}.md"
    if not multiple:
        return str(args.output)
    root, ext = os.path.splitext(args.output)
    return f"{root}-{lang}{ext}"


def select_locales(args: argparse.Namespace) -> List[Tuple[str, str]]:
    found = []
    for po_file in sorted(find_po_files(args.locale_dir)):
        lang = get_lang_from_path(po_file)
        if lang and args.locale in ("all", lang):
            found.append((lang, po_file))
    return found


def main(argv: Optional[Sequence[str]] = None, call: Optional[ModelCall] = None) -> int:
    """`call` replaces the real model (for tests)."""
    args = parse_args(argv)
    locales = select_locales(args)
    if not locales:
        print(f"No catalog found for locale '{args.locale}' in {args.locale_dir}")
        return 2

    plan: List[Tuple[str, str, Catalog, List[Message]]] = []
    for lang, po_file in locales:
        catalog = load_catalog(po_file)
        previous = None
        if args.since:
            try:
                previous = load_catalog_at_ref(args.since, po_file)
            except GitError as exc:
                print(exc)
                return 2
        selected = select_entries(catalog, previous)
        if args.limit is not None:
            selected = selected[: args.limit]
        plan.append((lang, po_file, catalog, selected))

    total = sum(len(selected) for _, _, _, selected in plan)
    per_entry = 2 if args.backtranslate else 1
    print(
        f"{total} entries to review ({', '.join(f'{l}: {len(s)}' for l, _, _, s in plan)});"
        f" {total * per_entry} model calls, plus retries on malformed replies."
    )

    if args.dry_run:
        for lang, _, _, selected in plan:
            for message in selected:
                print(f"  {lang} line {message.lineno}: {message_id(message)[:60]!r}")
        return 0

    if total > CONFIRM_OVER and not args.yes:
        print(
            f"More than {CONFIRM_OVER} entries: this sends them all to the model "
            "provider and may cost money. Re-run with --yes to proceed, or narrow it "
            "with --since / --limit / --locale."
        )
        return 2

    model_call = CountingCall(call or llm_model_call(args.model))
    multiple = len(plan) > 1
    exit_code = 0
    for lang, po_file, catalog, selected in plan:
        if not selected:
            print(f"{lang}: nothing to review.")
            continue
        print(f"{lang}: reviewing {len(selected)} entries...", flush=True)

        def progress(result: ReviewResult) -> None:
            sys.stdout.write({"ok": ".", "minor": "m", "major": "M"}.get(result.level, "E"))
            sys.stdout.flush()

        results, aborted = review_catalog(model_call, lang, selected, args.backtranslate, progress)
        print()
        path = report_path(args, lang, multiple)
        write_report(path, render_report(lang, args.model or "", results, aborted))
        counts = {lvl: sum(1 for r in results if r.level == lvl) for lvl in (*VERDICTS, "error")}
        print(
            f"{lang}: {counts['major']} major, {counts['minor']} minor, "
            f"{counts['ok']} ok, {counts['error']} errors. Report: {path}"
        )
        if args.mark_fuzzy:
            flagged = mark_fuzzy(po_file, catalog, results)
            print(f"{lang}: marked {flagged} entries fuzzy in {po_file}")
        if aborted:
            print(f"{lang}: aborted after {MAX_CONSECUTIVE_ERRORS} consecutive errors.")
            exit_code = 1
            break
    print(f"{model_call.count} model calls made.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
