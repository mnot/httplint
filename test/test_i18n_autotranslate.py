"""Tests for tools/i18n/autotranslate.py. No real model is ever called: a fake stands in."""

import contextlib
import io
import os
import tempfile
import unittest
from typing import Any, Callable, Dict, List, Optional, Tuple

from babel.messages.catalog import Catalog

from tools.i18n import autotranslate
from tools.i18n.autotranslate import (
    DEFAULT_TEMPERATURE,
    PROMPT_END,
    PROMPT_START,
    build_parser,
    protect,
    Result,
    restore,
    supports_option,
    token_error,
    translate,
)
from tools.i18n.utils import load_catalog, save_catalog

TEXT_MARK = "Here is the text to translate:\n\n"
OLD_PROMPT = (
    "You are translating short strings and messages for use in a HTTP linting tool. "
    "Translate the following text to language code 'fr'. When they appear, retain "
    "embeddded variables as they are. Do not translate HTTP protocol element names "
    "(such as header field names). Acronyms (such as 'IMS' and 'INM') should be "
    "retained. Return ONLY the translation, NO OTHER TEXT AT ALL. "
    "Here is the text to translate:\n\n"
)

SAMPLES = [
    "The `Content-Type` header declares `%(declared_charset)s`.",
    "Use `bytes */<length>` (e.g., `0.5`), or `a\nmulti-line span`, please.",
    "See [its\ndefinition](%(ref_uri)s) for more.%(position)s",
    "See [RFC 9112 Section 3.2](https://www.rfc-editor.org/rfc/rfc9112.html#section-3.2).",
    "Visit https://example.org/a, https://example.org/b; or https://example.org/c.",
    "([`Link`](https://example.org/x)), `%(a)s`, `%(b)s`: 50%% done.",
    "Nothing to protect here.",
    "``double `tick` span`` and `single`",
]


def text_of(prompt: str) -> str:
    return prompt.split(TEXT_MARK, 1)[1]


class FakeResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class FakeModel:
    """Records prompts and options; `reply` maps a prompt to the reply text."""

    class Options:  # llm models expose a pydantic class; model_fields is what we use
        model_fields = {"temperature": None}

    def __init__(self, reply: Callable[[str], str]) -> None:
        self.reply = reply
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def prompt(self, prompt: str, **options: Any) -> FakeResponse:
        self.calls.append((prompt, options))
        return FakeResponse(self.reply(prompt))


class FakeModelWithoutTemperature(FakeModel):
    class Options:
        model_fields = {"max_tokens": None}

    def prompt(self, prompt: str, **options: Any) -> FakeResponse:
        if options:  # a real llm model raises on options it doesn't have
            raise ValueError(f"unexpected options {options}")
        return super().prompt(prompt)


def faithful(prompt: str) -> str:
    """A 'translation' that keeps everything (tokens included) but adds a prefix."""
    return "FR: " + text_of(prompt)


def ask_for(model: FakeModel) -> Callable[[str], str]:
    return lambda prompt: model.prompt(prompt).text()


class ProtectTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        for text in SAMPLES:
            masked, spans = protect(text)
            self.assertEqual(restore(masked, spans), text, text)

    def test_protected_text_is_gone(self) -> None:
        masked, spans = protect(
            "Use `a\nb` and [x](https://e.org/p) and %(v)s and https://e.org/q."
        )
        for secret in ("`", "https://", "%(", "a\nb"):
            self.assertNotIn(secret, masked)
        self.assertEqual(len(spans), 4)

    def test_multiline_code_span(self) -> None:
        masked, spans = protect("Use `bytes */\n<length>` here")
        self.assertEqual(spans, ["`bytes */\n<length>`"])
        self.assertEqual(masked, "Use @@1@@ here")

    def test_link_text_stays_translatable(self) -> None:
        masked, spans = protect("See [its definition](%(ref_uri)s) now")
        self.assertEqual(masked, "See [its definition]@@1@@ now")
        self.assertEqual(spans, ["(%(ref_uri)s)"])

    def test_code_in_link_text(self) -> None:
        masked, spans = protect("[`Link`](https://e.org/x)")
        self.assertEqual(masked, "[@@1@@]@@2@@")
        self.assertEqual(spans, ["`Link`", "(https://e.org/x)"])

    def test_url_keeps_trailing_punctuation_outside(self) -> None:
        masked, spans = protect("a https://e.org/x, b https://e.org/y.")
        self.assertEqual(masked, "a @@1@@, b @@2@@.")
        self.assertEqual(spans, ["https://e.org/x", "https://e.org/y"])

    def test_adjacent_placeholders_and_percent(self) -> None:
        masked, spans = protect("%(a)s%(b)s 50%% (%(c)s)")
        self.assertEqual(masked, "@@1@@@@2@@ 50@@3@@ (@@4@@)")
        self.assertEqual(restore(masked, spans), "%(a)s%(b)s 50%% (%(c)s)")

    def test_unbalanced_backtick_is_left_alone(self) -> None:
        masked, spans = protect("a `broken and `%(v)s` b")
        self.assertEqual(restore(masked, spans), "a `broken and `%(v)s` b")

    def test_blank_line_ends_a_code_span_search(self) -> None:
        # an unclosed backtick must not pair with one in a later paragraph
        text = "Odd `tick here.\n\nNext paragraph with `code` here."
        self.assertEqual(protect(text)[1], ["`code`"])

    def test_restore_ignores_unknown_tokens(self) -> None:
        self.assertEqual(restore("a @@5@@ b", ["x"]), "a @@5@@ b")

    def test_nothing_to_protect_gives_the_old_prompt(self) -> None:
        masked, spans = protect("Plain text.")
        self.assertEqual((masked, spans), ("Plain text.", []))
        prompt = autotranslate.build_prompt("fr", masked, False, None)
        self.assertEqual(prompt, OLD_PROMPT + "Plain text.")

    def test_prompt_mentions_tokens_only_when_needed(self) -> None:
        prompt = autotranslate.build_prompt("fr", "A @@1@@", True, None)
        self.assertIn("copy each one exactly", prompt)
        self.assertTrue(prompt.startswith(PROMPT_START.format(lang="fr")))
        self.assertTrue(prompt.endswith(PROMPT_END.format(text="A @@1@@")))


class TokenErrorTest(unittest.TestCase):
    MASKED = "A @@1@@ and @@2@@"

    def test_ok(self) -> None:
        self.assertIsNone(token_error(self.MASKED, "Un @@2@@ et @@1@@", 2))

    def test_missing(self) -> None:
        self.assertIn("missing @@2@@", token_error(self.MASKED, "Un @@1@@", 2) or "")

    def test_duplicated(self) -> None:
        error = token_error(self.MASKED, "Un @@1@@ et @@2@@ @@2@@", 2)
        self.assertIn("repeated @@2@@", error or "")

    def test_invented(self) -> None:
        error = token_error(self.MASKED, "Un @@1@@ et @@2@@ @@3@@", 2)
        self.assertIn("invented @@3@@", error or "")

    def test_reformatted_token_is_missing(self) -> None:
        self.assertIn("missing", token_error(self.MASKED, "Un @@ 1 @@ et @@2@@", 2) or "")

    def test_added_backticks(self) -> None:
        error = token_error(self.MASKED, "Un `@@1@@` et @@2@@", 2)
        self.assertIn("backticks", error or "")


class TranslateTest(unittest.TestCase):
    MSGID = (
        "The `Content-Type` header says `%(declared_charset)s`; "
        "see [its definition](%(ref_uri)s) or https://example.org/x."
    )

    def run_translate(
        self,
        reply: Callable[[str], str],
        msgid: Optional[str] = None,
        rules: Optional[List[autotranslate.Rule]] = None,
    ) -> Tuple[Optional[str], int, str, FakeModel]:
        model = FakeModel(reply)
        self.res = translate(ask_for(model), "fr", msgid or self.MSGID, rules)
        return self.res.text, self.res.retries, self.res.error, model

    def test_good_translation_passes_through(self) -> None:
        result, retries, _, model = self.run_translate(faithful)
        self.assertEqual(result, "FR: " + self.MSGID)
        self.assertEqual(retries, 0)
        self.assertEqual(len(model.calls), 1)

    def test_model_sees_masked_text_and_token_sentence(self) -> None:
        _, _, _, model = self.run_translate(faithful)
        prompt = model.calls[0][0]
        for secret in ("Content-Type", "declared_charset", "ref_uri", "example.org"):
            self.assertNotIn(secret, prompt)
        self.assertIn("copy each one exactly", prompt)

    def test_plain_text_prompt_is_unchanged(self) -> None:
        result, _, _, model = self.run_translate(faithful, "Nothing special here at all.")
        self.assertEqual(model.calls[0][0], OLD_PROMPT + "Nothing special here at all.")
        self.assertEqual(result, "FR: Nothing special here at all.")

    def test_missing_token_is_retried_with_the_error(self) -> None:
        replies = iter(["Sans jeton @@1@@ seulement", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        result, retries, _, model = self.run_translate(reply)
        self.assertEqual(result, "FR: " + self.MSGID)
        self.assertEqual(retries, 1)
        self.assertNotIn("rejected", model.calls[0][0])
        self.assertIn("rejected: missing @@2@@", model.calls[1][0])
        self.assertTrue(model.calls[1][0].endswith(TEXT_MARK + text_of(model.calls[0][0])))

    def test_duplicated_and_invented_tokens_are_rejected(self) -> None:
        for bad in ("@@1@@ @@1@@ @@2@@ @@3@@ @@4@@", "@@1@@ @@2@@ @@3@@ @@4@@ @@5@@"):
            result, retries, error, model = self.run_translate(lambda p, b=bad: b)
            self.assertIsNone(result, bad)
            self.assertEqual(len(model.calls), 3)
            self.assertTrue(error)

    def test_validation_failure_is_retried(self) -> None:
        # tokens are fine, but a sentence repeats: caught by the i18n-check logic
        msgid = "The `%(directive)s` cache directive requires a value, which was not given."
        repeated = (
            "@@1@@ exige une valeur. Aucune valeur n'a été fournie. Aucune valeur n'a été fournie."
        )
        replies = iter([repeated, None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        result, retries, _, model = self.run_translate(reply, msgid)
        self.assertEqual(retries, 1)
        self.assertEqual(result, "FR: " + msgid)
        self.assertIn("rejected: DUPLICATED_TEXT", model.calls[1][0])

    def test_retry_exhaustion(self) -> None:
        result, retries, error, model = self.run_translate(lambda p: "Rien @@1@@")
        self.assertIsNone(result)
        self.assertEqual(retries, 2)
        self.assertEqual(len(model.calls), 3)
        self.assertIn("missing", error)

    def test_custom_rule_error_reaches_the_prompt(self) -> None:
        def no_prefix(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
            return ["do not start with FR"] if msgstr.startswith("FR") else []

        replies = iter(["FR: @@1@@ @@2@@ @@3@@ @@4@@", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else "Voir " + text_of(prompt)

        _, retries, _, model = self.run_translate(reply, rules=[no_prefix])
        self.assertEqual(retries, 1)
        self.assertIn("rejected: do not start with FR.", model.calls[1][0])

    def test_whitespace_copied_from_msgid(self) -> None:
        msgid = "\n  Some `code` text here, long enough to pass.\n\n"
        # the model drops the whitespace, as the maintainer's run showed
        result, _, _, _ = self.run_translate(lambda p: "FR: " + text_of(p).strip(), msgid)
        self.assertEqual(result, "\n  FR: " + msgid.strip() + "\n\n")
        self.assertEqual(autotranslate.match_whitespace("a\n", " b "), "b\n")

    def test_invented_token_without_spans_is_rejected(self) -> None:
        result = translate(lambda p: "Texte @@1@@", "fr", "Plain text.")
        self.assertIsNone(result.text)
        self.assertIn("invented", result.error)

    def test_literal_token_in_msgid(self) -> None:
        msgid = "A literal @@1@@ here and `x` in the text."
        result, _, _, model = self.run_translate(faithful, msgid)
        self.assertEqual(result, "FR: " + msgid)
        self.assertIn("@@@1@@@", model.calls[0][0])

    def test_error_in_prompt_is_truncated(self) -> None:
        def noisy(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
            return ["LINK_MISMATCH extra: " + "u" * 3000]

        _, _, error, model = self.run_translate(faithful, rules=[noisy])
        self.assertLessEqual(len(error), autotranslate.MAX_ERROR)
        self.assertNotIn("u" * 250, model.calls[1][0])
        self.assertIn("rejected: LINK_MISMATCH extra: uuu", model.calls[1][0])

    def test_advisory_failure_keeps_the_last_candidate_as_fuzzy(self) -> None:
        def advisory(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
            return ["SUSPICIOUS_LENGTH length ratio 0.10"]

        self.run_translate(faithful, rules=[advisory])
        self.assertEqual(
            self.res, Result("FR: " + self.MSGID, 2, "SUSPICIOUS_LENGTH length ratio 0.10", True)
        )

    def test_variable_and_syntax_failures_are_blanked(self) -> None:
        for kind in ("BAD_VARIABLE Missing: %(x)s", "SYNTAX_ERROR Stray '%'"):
            self.run_translate(faithful, rules=[lambda i, o, lang, k=kind: [k]])
            self.assertEqual(self.res, Result(None, 2, kind, False))

    def test_i18n_check_rule_uses_the_language(self) -> None:
        msgid = "A message that is long enough for the length check to apply."
        rule = autotranslate.i18n_check_rule
        # ratio 0.3 is fine for ja, too short for the default range
        self.assertEqual(rule(msgid, "x" * 18, "ja"), [])
        self.assertTrue(rule(msgid, "x" * 18, "fr"))
        # ratio 1.8 is fine for the default range, too long for ja
        self.assertTrue(rule(msgid, "x" * 105, "ja"))
        self.assertEqual(rule(msgid, "x" * 105, "fr"), [])

    def test_empty_reply_is_retried(self) -> None:
        replies = iter(["", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        result, retries, _, _ = self.run_translate(reply)
        self.assertEqual(retries, 1)
        self.assertIsNotNone(result)


class TemperatureTest(unittest.TestCase):
    def test_supports_option(self) -> None:
        self.assertTrue(supports_option(FakeModel(faithful), "temperature"))
        self.assertFalse(supports_option(FakeModelWithoutTemperature(faithful), "temperature"))
        self.assertFalse(supports_option(object(), "temperature"))

    def test_default(self) -> None:
        self.assertEqual(build_parser().parse_args([]).temperature, 0.2)
        self.assertEqual(DEFAULT_TEMPERATURE, 0.2)
        self.assertEqual(build_parser().parse_args(["--temperature", "0"]).temperature, 0.0)


class FileTest(unittest.TestCase):
    """autotranslate_file() on a real PO file with a fake model."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "messages.po")
        catalog = Catalog(locale="fr")
        catalog.add("Good `Content-Type` message, %(x)s.", "")
        catalog.add("Bad `Link` message that never works, %(y)s.", "vieux", flags=["fuzzy"])
        save_catalog(self.path, catalog)

    def run_file(self, model: FakeModel, **kwargs: Any) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            autotranslate.autotranslate_file(self.path, "fr", "fake", 0, model=model, **kwargs)
        return out.getvalue()

    def test_left_empty_is_reported_and_never_written(self) -> None:
        def reply(prompt: str) -> str:
            if "never" in text_of(prompt):
                return "garbage"  # no tokens at all
            return faithful(prompt)

        output = self.run_file(FakeModel(reply))
        messages = {m.id: m for m in load_catalog(self.path) if m.id}
        good = messages["Good `Content-Type` message, %(x)s."]
        bad = messages["Bad `Link` message that never works, %(y)s."]
        self.assertEqual(good.string, "FR: Good `Content-Type` message, %(x)s.")
        self.assertEqual(bad.string, "")
        self.assertNotIn("fuzzy", bad.flags)
        self.assertIn("1 entries left empty", output)
        self.assertIn("missing", output)  # the last error is listed with the msgid
        self.assertIn("Bad `Link` message that never works", output)

    def test_advisory_failure_is_kept_as_fuzzy_and_listed(self) -> None:
        catalog = load_catalog(self.path)
        catalog.add("A plain message that is long enough to measure.", "")
        save_catalog(self.path, catalog)

        def reply(prompt: str) -> str:
            return "Court." if "plain message" in prompt else faithful(prompt)

        output = self.run_file(FakeModel(reply))
        entry = {m.id: m for m in load_catalog(self.path)}[
            "A plain message that is long enough to measure."
        ]
        self.assertEqual(entry.string, "Court.")
        self.assertIn("fuzzy", entry.flags)
        self.assertIn("1 entries kept as fuzzy", output)
        self.assertIn("SUSPICIOUS_LENGTH", output)

    def test_temperature_passed_when_supported(self) -> None:
        model = FakeModel(faithful)
        self.run_file(model, temperature=0.3)
        self.assertTrue(model.calls)
        for _, options in model.calls:
            self.assertEqual(options, {"temperature": 0.3})

    def test_temperature_omitted_when_unsupported(self) -> None:
        model = FakeModelWithoutTemperature(faithful)
        output = self.run_file(model, temperature=0.3)
        self.assertTrue(model.calls)
        for _, options in model.calls:
            self.assertEqual(options, {})
        self.assertIn("no temperature option", output)
        self.assertNotIn("left empty", output)


if __name__ == "__main__":
    unittest.main()
