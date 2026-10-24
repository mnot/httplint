from typing import Tuple


def split_params_off(value: str) -> Tuple[str, str]:
    "Split ``value`` at its first ';' (quoted or not) into (head, parameter text); empty if none."
    head, _, param_str = value.partition(";")
    return head, param_str
