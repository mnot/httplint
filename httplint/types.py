from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Union,
    Protocol,
    Type,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from httplint.note import Note

StrFieldListType = List[Tuple[str, str]]
RawFieldListType = List[Tuple[bytes, bytes]]
FieldDictType = Dict[str, Any]
ParamDictType = Dict[str, Union[str, None]]


VariableType = Any


class AddNoteMethodType(Protocol):
    def __call__(self, note: Type["Note"], **vrs: VariableType) -> "Note": ...
