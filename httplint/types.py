from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    Union,
    runtime_checkable,
)

from http_sf import DisplayString, Token
from http_sf.types import (
    BareItemType,
    InnerListType,
    ParamsType,
)

if TYPE_CHECKING:
    from httplint.note import Note
else:
    Note = Any

# General types
JsonDict = Dict[str, Any]
StrFieldListType = List[Tuple[str, str]]
RawFieldListType = List[Tuple[bytes, bytes]]
FieldDictType = Dict[str, Any]
ParamDictType = Dict[str, Union[str, None]]

# Note-related types
VariableType = Union[str, int, float, bool, None, Note, Any]
NoteListType = List[Note]  # instances
NoteClassListType = List[Type[Note]]  # classes


class AddNoteMethodType(Protocol):
    def __call__(self, note: Type[Note], **vrs: VariableType) -> Note: ...


# Linter Protocols
@runtime_checkable
class NotesProtocol(Protocol):
    def add(
        self,
        subject: str,
        note: Type[Note],
        category: Optional[Any] = None,
        **vrs: VariableType,
    ) -> Note: ...

    def __iter__(self) -> Any: ...


@runtime_checkable
class SectionProtocol(Protocol):
    parsed: Dict[str, Any]
    text: List[Tuple[str, str]]
    handlers: Dict[str, Any]  # Avoiding circularity with HttpField
    is_trailer: bool

    def process(self, raw_fields: RawFieldListType) -> None: ...


@runtime_checkable
class CachingProtocol(Protocol):
    age: int
    store_private: bool
    freshness_lifetime_private: int
    store_shared: bool
    freshness_lifetime_shared: int


@runtime_checkable
class LinterProtocol(Protocol):
    notes: NotesProtocol
    related: Optional[LinterProtocol]
    start_time: Optional[float]
    finish_time: Optional[float]
    version: str
    base_uri: str
    headers: SectionProtocol
    trailers: SectionProtocol
    content_length: int
    content_hash: Optional[bytes]
    content_sample: bytes
    complete: bool
    message_type: Any
    character_encoding: Optional[str]

    def can_have_content(self) -> bool: ...

    def post_checks(self) -> None: ...


@runtime_checkable
class RequestLinterProtocol(LinterProtocol, Protocol):
    method: Optional[str]
    iri: Optional[str]
    uri: Optional[str]


@runtime_checkable
class ResponseLinterProtocol(LinterProtocol, Protocol):
    status_code: Optional[int]
    status_phrase: Optional[str]
    is_head_response: bool
    caching: CachingProtocol


AnyMessageLinterProtocol = Union[RequestLinterProtocol, ResponseLinterProtocol]


# Structured Field types
SFToken = Token
SFDisplayString = DisplayString
SFBareItemType = BareItemType
SFParamsType = ParamsType
SFInnerListType = InnerListType

# Parsed SF types are strictly normalized to (value, params) tuples
SFItemType = Tuple[Union[SFBareItemType, SFInnerListType], SFParamsType]
SFListType = List[SFItemType]
SFDictionaryType = Dict[str, SFItemType]
