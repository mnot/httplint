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

from http_sf import Token

if TYPE_CHECKING:
    from httplint.note import Note

StrFieldListType = List[Tuple[str, str]]
RawFieldListType = List[Tuple[bytes, bytes]]
FieldDictType = Dict[str, Any]
ParamDictType = Dict[str, Union[str, None]]


VariableType = Union[str, int, None, Token]


class AddNoteMethodType(Protocol):
    def __call__(self, note: Type["Note"], **vrs: VariableType) -> "Note": ...
