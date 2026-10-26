"""Tests for the report-only heuristics in tools/i18n/check.py."""

import unittest

from babel.messages.catalog import Catalog

from tools.i18n import heuristics
from tools.i18n.check import CRITICAL_ISSUES, CatalogChecker, IssueType


class LinkMismatchTest(unittest.TestCase):
    def test_same_links(self) -> None:
        msgid = "See [RFC 9110](https://example.com/rfc9110) and https://example.org/x."
        msgstr = "Voir [RFC 9110](https://example.com/rfc9110) et https://example.org/x."
        self.assertIsNone(heuristics.link_mismatch(msgid, msgstr))

    def test_dropped_link(self) -> None:
        msgid = "A [Structured Field](https://example.com/sf) is bad."
        msgstr = "Un champ structuré est mauvais."
        self.assertIn("https://example.com/sf", heuristics.link_mismatch(msgid, msgstr) or "")

    def test_changed_link(self) -> None:
        msgid = "See [x](https://example.com/a)."
        msgstr = "Voir [x](https://example.com/b)."
        details = heuristics.link_mismatch(msgid, msgstr)
        self.assertIn("missing", details or "")
        self.assertIn("extra", details or "")

    def test_placeholder_target(self) -> None:
        msgid = "See [its definition](%(ref_uri)s) for more."
        self.assertIsNone(heuristics.link_mismatch(msgid, "Voir [sa définition](%(ref_uri)s)."))

    def test_broken_markdown_placeholder_target(self) -> None:
        msgid = "See [its definition](%(ref_uri)s) for more."
        msgstr = "詳細は[定義] (%(ref_uri)s) を参照。"
        self.assertIn("%(ref_uri)s", heuristics.link_mismatch(msgid, msgstr) or "")

    def test_trailing_punctuation_ignored(self) -> None:
        self.assertIsNone(
            heuristics.link_mismatch("See https://example.com/a.", "Voir https://example.com/a,")
        )


class TokenChangedTest(unittest.TestCase):
    def test_token_kept(self) -> None:
        self.assertIsNone(
            heuristics.token_changed(
                "The `Cache-Control` header has `max-age=0`.",
                "L'en-tête Cache-Control a max-age=0.",
            )
        )

    def test_header_name_translated(self) -> None:
        details = heuristics.token_changed(
            "The `Access-Control-Max-Age` header is bad.",
            "Access-控制-Max-Age 头不正确。",
        )
        self.assertIn("Access-Control-Max-Age", details or "")

    def test_value_translated(self) -> None:
        details = heuristics.token_changed(
            "It should almost always be `bytes`.", "Il devrait être `octets`."
        )
        self.assertIn("bytes", details or "")

    def test_case_matters(self) -> None:
        self.assertIsNotNone(
            heuristics.token_changed("Use `Content-Type`.", "Utilisez content-type.")
        )

    def test_field_line(self) -> None:
        self.assertIsNone(
            heuristics.token_changed(
                "Send `Cache-Control: no-store`.", "Envoyez `Cache-Control: no-store`."
            )
        )
        self.assertIsNotNone(
            heuristics.token_changed(
                "Send `Cache-Control: no-store`.", "Envoyez `Contrôle-Cache: no-store`."
            )
        )

    def test_status_code_only_needs_code(self) -> None:
        self.assertIsNone(
            heuristics.token_changed(
                "The `404 (Not Found)` status.", "Le statut `404 (Introuvable)`."
            )
        )
        self.assertIsNotNone(
            heuristics.token_changed("The `404 (Not Found)` status.", "Le statut introuvable.")
        )

    def test_ignored_spans(self) -> None:
        # placeholders (BAD_VARIABLE's job), bare punctuation, prose from unpaired backticks
        self.assertIsNone(
            heuristics.token_changed(
                "The `%(name)s` key, `*`, and `a b c d e f g` appear.", "La clé."
            )
        )


class DuplicatedTextTest(unittest.TestCase):
    def test_repeated_placeholder(self) -> None:
        msgid = "The `%(key)s` key has an invalid value; %(details)s."
        msgstr = "La clé `%(key)s` a une valeur non valide ; %(details)s.\nDétails : %(details)s"
        self.assertIn("%(details)s", heuristics.duplicated_text(msgid, msgstr) or "")

    def test_repeated_sentence(self) -> None:
        msgid = "The header is invalid. It must be a number."
        msgstr = (
            "L'en-tête est invalide. Il doit être un nombre. "
            "L'en-tête est invalide. Il doit être un nombre."
        )
        self.assertIn("repeated sentence", heuristics.duplicated_text(msgid, msgstr) or "")

    def test_repeated_paragraph(self) -> None:
        msgid = "First line here.\n\nSecond line here."
        msgstr = "Première ligne ici.\n\nDeuxième ligne ici.\n\nPremière ligne ici."
        self.assertIsNotNone(heuristics.duplicated_text(msgid, msgstr))

    def test_cjk_repeat(self) -> None:
        msgid = "The header is invalid."
        msgstr = "ヘッダーは無効です。ヘッダーは無効です。"
        self.assertIsNotNone(heuristics.duplicated_text(msgid, msgstr))

    def test_repeat_also_in_msgid_is_fine(self) -> None:
        msgid = "The value is wrong. The value is wrong."
        msgstr = "La valeur est fausse. La valeur est fausse."
        self.assertIsNone(heuristics.duplicated_text(msgid, msgstr))

    def test_placeholder_repeated_in_msgid_is_fine(self) -> None:
        msgid = "%(method)s here, and %(method)s there."
        msgstr = "%(method)s ici, et %(method)s là."
        self.assertIsNone(heuristics.duplicated_text(msgid, msgstr))

    def test_short_repeats_ignored(self) -> None:
        self.assertIsNone(heuristics.duplicated_text("Yes. No.", "Oui. Oui."))


class SuspiciousLengthTest(unittest.TestCase):
    MSGID = "The response is missing a Content-Type header field."  # 52 characters

    def test_normal(self) -> None:
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, "A" * 60, "fr"))

    def test_too_short_latin(self) -> None:
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "La requête a expiré.", "fr"))

    def test_too_long_latin(self) -> None:
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "x" * 200, "es"))

    def test_cjk_is_shorter(self) -> None:
        msgstr = "Content-Type ヘッダーがありません。"  # ratio 0.46
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, msgstr, "ja"))
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, msgstr, "fr"))

    def test_cjk_too_short(self) -> None:
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "無効です。", "ja"))

    def test_region_suffix(self) -> None:
        msgstr = "响应缺少 Content-Type 头。"
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, msgstr, "zh_Hans"))

    def test_short_msgid_skipped(self) -> None:
        self.assertIsNone(heuristics.suspicious_length("Bad value.", "x" * 100, "fr"))


class PreambleTest(unittest.TestCase):
    def test_chatter(self) -> None:
        for msgstr in (
            "Here is the translation: L'en-tête est invalide.",
            "Sure! L'en-tête est invalide.",
            "Translation: L'en-tête est invalide.",
            "Voici la traduction : L'en-tête est invalide.",
            "Aquí está la traducción: El encabezado no es válido.",
            "以下是翻译：标头无效。",
            "翻訳: ヘッダーは無効です。",
            "```\nL'en-tête est invalide.\n```",
        ):
            with self.subTest(msgstr=msgstr):
                self.assertIsNotNone(heuristics.preamble("The header is invalid.", msgstr))

    def test_think_tags(self) -> None:
        self.assertIsNotNone(
            heuristics.preamble("The header is invalid.", "<think>hmm</think>L'en-tête.")
        )

    def test_normal(self) -> None:
        self.assertIsNone(heuristics.preamble("The header is invalid.", "L'en-tête est invalide."))

    def test_msgid_with_same_start_is_fine(self) -> None:
        self.assertIsNone(
            heuristics.preamble("Here is how it works.", "Here is how it works, in French.")
        )


class CatalogReportingTest(unittest.TestCase):
    """The new checks report issues but never fail the build."""

    @staticmethod
    def catalog() -> Catalog:
        catalog = Catalog(locale="fr")
        catalog.add(
            "The `Sunset` header indicates that this resource is gone, which is bad.",
            "La requête a expiré.",
            locations=[("x.py", 1)],
        )
        catalog.add("Fine string.", "Chaîne correcte.")
        return catalog

    def test_flags_reported(self) -> None:
        issues = CatalogChecker().check_catalog(self.catalog(), "fr")
        kinds = {i.issue_type for i in issues}
        self.assertEqual(kinds, {IssueType.TOKEN_CHANGED, IssueType.SUSPICIOUS_LENGTH})

    def test_not_critical(self) -> None:
        for issue_type in (
            IssueType.LINK_MISMATCH,
            IssueType.TOKEN_CHANGED,
            IssueType.DUPLICATED_TEXT,
            IssueType.SUSPICIOUS_LENGTH,
            IssueType.PREAMBLE,
        ):
            self.assertNotIn(issue_type, CRITICAL_ISSUES)
        self.assertEqual(set(CRITICAL_ISSUES), {IssueType.BAD_VARIABLE, IssueType.SYNTAX_ERROR})

    def test_empty_skipped(self) -> None:
        catalog = Catalog(locale="fr")
        catalog.add("The `Sunset` header indicates that it is all bad, really.", "")
        self.assertEqual(
            [i.issue_type for i in CatalogChecker().check_catalog(catalog, "fr")],
            [IssueType.MISSING],
        )


if __name__ == "__main__":
    unittest.main()
