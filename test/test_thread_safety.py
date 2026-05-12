"""
Test that Note._get_detail is safe when called concurrently from multiple threads.

The Markdown instance used to be a class-level attribute shared across all Note
instances.  Concurrent calls to _get_detail would race on reset()/convert(),
corrupting output or raising exceptions.
"""

import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from httplint.note import Note, Notes, categories, levels


class NOTE_A(Note):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "Note A"
    _text = "Value is `%(value)s`."


class NOTE_B(Note):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "Note B"
    _text = "Other is `%(other)s`."


def _make_note(note_cls, **vars):
    notes = Notes({"field_name": "X-Test"})
    return notes.add("test", note_cls, **vars)


class NoteThreadSafetyTest(unittest.TestCase):
    """Concurrent detail rendering must not corrupt output or raise."""

    WORKERS = 32
    ITERATIONS = 200

    def _render(self, i):
        if i % 2 == 0:
            note = _make_note(NOTE_A, value=f"item-{i}")
            detail = note.detail
            self.assertIn(f"item-{i}", detail)
        else:
            note = _make_note(NOTE_B, other=f"thing-{i}")
            detail = note.detail
            self.assertIn(f"thing-{i}", detail)
        return detail

    def test_concurrent_detail_rendering(self):
        """Many threads rendering different notes concurrently must all succeed."""
        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            futures = [pool.submit(self._render, i) for i in range(self.ITERATIONS)]
            for future in as_completed(futures):
                future.result()  # raises if the worker raised


if __name__ == "__main__":
    unittest.main()
