from typing import Tuple


def split_params_off(value: str) -> Tuple[str, str]:
    """
    Split ``value`` at its first ';' (quoted or not) into (head, parameter text); empty if none.
    Not ``split_params`` (utils.py), which splits a parameter list into its ``name=value`` items.
    """
    head, _, param_str = value.partition(";")
    return head, param_str
