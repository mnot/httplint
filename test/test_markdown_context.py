import inspect
import unittest

from httplint.util import f_num, markdown_context


def _lines(text: str, index: int, context_chars: int = 20) -> list[str]:
    return str(markdown_context(text, index, context_chars)).strip("\n").split("\n")


class MarkdownContextPointerTest(unittest.TestCase):
    def test_single_line(self) -> None:
        self.assertEqual(_lines("abcdef", 3), ["    abcdef", "       ^"])

    def test_index_at_end(self) -> None:
        self.assertEqual(_lines("abc", 3), ["    abc", "       ^"])

    def test_pointer_in_last_line_of_multiline_excerpt(self) -> None:
        # The pointer column is relative to its own line, not the whole excerpt.
        self.assertEqual(_lines("ab\ncdef", 5), ["    ab", "    cdef", "      ^"])

    def test_pointer_in_earlier_line(self) -> None:
        self.assertEqual(_lines("abcd\nef", 2), ["    abcd", "      ^", "    ef"])

    def test_pointer_after_trailing_newline(self) -> None:
        self.assertEqual(_lines("ab\n", 3), ["    ab", "    ", "    ^"])

    def test_pointer_on_second_line_start(self) -> None:
        self.assertEqual(_lines("ab\ncd", 3), ["    ab", "    cd", "    ^"])

    def test_context_window(self) -> None:
        text = "x" * 30 + "\n" + "y" * 30
        # index 35 is column 4 of the second line; the excerpt starts 20 before it.
        lines = _lines(text, 35)
        self.assertEqual(lines[-1].index("^"), len("    ") + 4)
        self.assertEqual(lines[-2], "    " + "y" * 24)

    def test_other_line_breaks(self) -> None:
        self.assertEqual(_lines("ab cdef", 5), ["    ab", "    cdef", "      ^"])
        self.assertEqual(_lines("ab\r\ncdef", 6), ["    ab", "    cdef", "      ^"])


class FNumTest(unittest.TestCase):
    def test_no_by1024(self) -> None:
        self.assertNotIn("by1024", inspect.signature(f_num).parameters)
        digits = "".join(ch for ch in f_num(2**200) if ch.isdigit())
        self.assertEqual(digits, str(2**200))


if __name__ == "__main__":
    unittest.main()
