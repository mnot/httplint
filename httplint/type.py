from typing import Any, Callable, Dict, List, Tuple

StrFieldListType = List[Tuple[str, str]]
RawFieldListType = List[Tuple[bytes, bytes]]
FieldDictType = Dict[str, Any]
ParamDictType = Dict[str, str]
AddNoteMethodType = Callable[..., None]
