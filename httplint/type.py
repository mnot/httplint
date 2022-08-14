from typing import Any, Callable, Dict, List, Tuple, Union

StrFieldListType = List[Tuple[str, str]]
RawFieldListType = List[Tuple[bytes, bytes]]
FieldDictType = Dict[str, Any]
ParamDictType = Dict[str, str]
AddNoteMethodType = Callable[..., None]

VariableType = Union[str, int]
