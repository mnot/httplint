import re
import sys

from httplint import syntax

def check_regex() -> None:
    """Grab all the regex in this module."""
    for module_name in syntax.__all__:
        full_name = f"httplint.syntax.{module_name}"
        __import__(full_name)
        module = sys.modules[full_name]
        for attr_name in dir(module):
            attr_value = getattr(module, attr_name, None)
            if isinstance(attr_value, bytes):
                try:
                    re.compile(attr_value, re.VERBOSE)
                except re.error as why:
                    print("*", module_name, attr_name, why)


if __name__ == "__main__":
    check_regex()
