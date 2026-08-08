"""
Regex for RFC6838
"""

# pylint: disable=invalid-name

from .rfc5234 import (
    ALPHA,
    DIGIT,
)

SPEC_URL = "https://www.rfc-editor.org/rfc/rfc6838"


#   restricted-name-first  = ALPHA / DIGIT

restricted_name_first = rf"(?: {ALPHA} | {DIGIT} )"

#   restricted-name-chars  = ALPHA / DIGIT / "!" / "#" /
#                            "$" / "&" / "-" / "^" / "_"
#   restricted-name-chars =/ "." ; Characters before first dot always
#                                ; specify a facet name
#   restricted-name-chars =/ "+" ; Characters after last plus always
#                                ; specify a structured syntax suffix

restricted_name_chars = rf"(?: {ALPHA} | {DIGIT} | ! | \# | \$ | & | \- | \^ | _ | \. | \+ )"

#   restricted-name = restricted-name-first *126restricted-name-chars

restricted_name = rf"(?: {restricted_name_first} {restricted_name_chars}{{0,126}} )"

#   type-name = restricted-name

type_name = restricted_name

#   subtype-name = restricted-name

subtype_name = restricted_name

# The longest a type-name or subtype-name can be, per restricted-name above.

RESTRICTED_NAME_MAX_LEN = 127
