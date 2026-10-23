from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from httplint.note import Note
from httplint.types import AddNoteMethodType, VariableType

_Entry = Tuple[Optional[AddNoteMethodType], Type[Note], Optional[Any], Dict[str, VariableType]]


class DeferredNotes:
    """
    Notes collected while parsing a field value, to be emitted later (typically from `evaluate()`,
    as children of a summary note, or after other notes so they sort after them).
    """

    def __init__(self) -> None:
        self._entries: List[_Entry] = []

    def defer(self, note: Type[Note], category: Optional[Any] = None, **vrs: VariableType) -> Any:
        "Record `note` to be added to whatever `emit()` is given (returns None; fits add_note)."
        self._entries.append((None, note, category, vrs))

    def via(self, add_note: AddNoteMethodType) -> AddNoteMethodType:
        """
        Return an add_note-style callable that records notes to be added with `add_note`, rather
        than with the one given to `emit()`; for add_note methods tied to a particular subject.
        """

        def deferred_add_note(
            note: Type[Note], category: Optional[Any] = None, **vrs: VariableType
        ) -> Any:
            self._entries.append((add_note, note, category, vrs))

        return deferred_add_note

    def __contains__(self, note: Type[Note]) -> bool:
        return self.has(note)

    def __len__(self) -> int:
        return len(self._entries)

    def has(self, *notes: Type[Note]) -> bool:
        "Whether any of `notes` has been deferred."
        return any(entry[1] in notes for entry in self._entries)

    def emit(self, add_note: Optional[Callable[..., Any]] = None) -> None:
        """
        Add the deferred notes, in the order they were recorded, using `add_note` (for example
        `parent.add_child`) unless they were recorded with `via()`.
        """
        for adder, note, category, vrs in self._entries:
            target = adder or add_note
            if target is None:
                raise ValueError("no add_note to emit deferred notes with")
            if category is None:
                target(note, **vrs)
            else:
                target(note, category=category, **vrs)
