from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Protocol,
    Tuple,
    Type,
    Union,
)

if TYPE_CHECKING:
    from http_sf import Token

    from httplint.note import Note
else:
    Token = Any
    Note = Any

# General types
JsonDict = Dict[str, Any]
StrFieldListType = List[Tuple[str, str]]
RawFieldListType = List[Tuple[bytes, bytes]]
FieldDictType = Dict[str, Any]
ParamDictType = Dict[str, Union[str, None]]

# Note-related types
VariableType = Union[str, int, float, bool, None, "Note", Any]


class AddNoteMethodType(Protocol):
    def __call__(self, note: Type["Note"], **vrs: VariableType) -> "Note": ...


# Structured Field types
SFToken = Token
SFItemType = Union[str, int, float, bool, SFToken, tuple[Any, Any]]
SFParamsType = Dict[str, SFItemType]
