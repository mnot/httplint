"""
Regex for RFC5987

These regex are directly derived from the ABNF in RFC8187, Section 3.2.1. RFC 8187 obsoletes
RFC 5987; the module keeps its old name so that existing imports keep working.

The ABNF is the same as RFC 5987's, except that RFC 5987's charset rule also listed
"ISO-8859-1" (which mime-charset already matches, so the language is the same) and that RFC 5987
also defined the parameter rules (parmname, reg-parameter, ext-parameter), which RFC 8187 dropped.

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name  # names mirror ABNF rule names

from .rfc5234 import ALPHA, DIGIT, HEXDIG
from .rfc5646 import Language_Tag

SPEC_URL = "https://www.rfc-editor.org/rfc/rfc8187"


#  language      = <Language-Tag, see [RFC5646], Section 2.1>

language = Language_Tag

#  pct-encoded   = "%" HEXDIG HEXDIG
#                ; see [RFC3986], Section 2.1

pct_encoded = rf"(?: % {HEXDIG} {HEXDIG} )"

#  attr-char     = ALPHA / DIGIT
#                / "!" / "#" / "$" / "&" / "+" / "-" / "."
#                / "^" / "_" / "`" / "|" / "~"
#                ; token except ( "*" / "'" / "%" )

attr_char = rf"""(?:
                  {ALPHA} | {DIGIT}
                | !  | \# | \$ | &  | \+ | -  | \.
                | \^ | _  | `  | \| | ~
)"""

#  value-chars   = *( pct-encoded / attr-char )

value_chars = rf"(?: (?: {pct_encoded} | {attr_char} )* )"

#  mime-charsetc = ALPHA / DIGIT
#                / "!" / "#" / "$" / "%" / "&"
#                / "+" / "-" / "^" / "_" / "`"
#                / "{" / "}" / "~"
#                ; as <mime-charset> in Section 2.3 of [RFC2978]
#                ; except that the single quote is not included
#                ; SHOULD be registered in the IANA charset registry

mime_charsetc = rf"""(?:
                  {ALPHA} | {DIGIT}
                | !  | \# | \$ | %  | &
                | \+ | -  | \^ | _  | `
                | \{{ | \}} | ~
)"""

#  mime-charset  = 1*mime-charsetc

mime_charset = rf"(?: {mime_charsetc}+ )"

#  charset       = "UTF-8" / mime-charset

charset = rf"(?: UTF-8 | {mime_charset} )"

#  ext-value     = charset  "'" [ language ] "'" value-chars
#                ; like RFC 2231's <extended-initial-value>
#                ; (see [RFC2231], Section 7)

ext_value = rf"(?: {charset} ' (?: {language} )? ' {value_chars} )"
