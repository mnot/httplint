from .rfc5234 import ALPHA, CRLF, DIGIT, VCHAR, WSP

# pylint: disable=invalid-name


# qtext           =  %d33 /             ; Printable US-ASCII
#                    %d35-91 /          ;  characters not including
#                    %d93-126 /         ;  "\" or the quote character
#                    obs-qtext

qtext = r"[\x21\x23-\x5b\x5d-\x7e]"

# quoted-pair     =   ("\" (VCHAR / WSP)) / obs-qp

quoted_pair = rf"(?: \\ (?: {VCHAR} | {WSP} ) )"

# qcontent        =   qtext / quoted-pair

qcontent = rf"(?: {qtext} | {quoted_pair} )"

# ctext           =   %d33-39 /          ; Printable US-ASCII
#                     %d42-91 /          ;  characters not including
#                     %d93-126 /         ;  "(", ")", or "\"
#                     obs-ctext

ctext = r"[\x21-\x27\x2a-\x5b\x5d\x7e]"

# ccontent        =   ctext / quoted-pair / comment
#
# The comment rule, and the CFWS and phrase rules below, are written as flat repetitions of
# single tokens rather than as nested repetitions of FWS, CFWS and atom. The RFC's nesting is
# ambiguous (e.g., "a" can be one atom or two), which makes backtracking exponential on
# non-matching input; the accepted language is the same. Nested comments are not supported.

# FWS             =   ([*WSP CRLF] 1*WSP) /  obs-FWS

FWS = rf"(?: (?: {WSP}* {CRLF} )? {WSP}{{1,}} )"

# One unit of a run of FWS; a CRLF is only valid when followed by WSP.

fws_unit = rf"(?: {WSP} | {CRLF} {WSP} )"

# comment         =   "(" *([FWS] ccontent) [FWS] ")"

comment = rf"(?: \( (?: {fws_unit} | {ctext} | {quoted_pair} )* \) )"

# CFWS            =   (1*([FWS] comment) [FWS]) / FWS

CFWS = rf"(?: (?: {fws_unit} | {comment} ){{1,}} )"

# quoted-string   =  [CFWS]
#                    DQUOTE *([FWS] qcontent) [FWS] DQUOTE
#                    [CFWS]

quoted_string_core = rf"(?: \" (?: {FWS}? {qcontent} )* \" )"

quoted_string = rf"(?: {CFWS}? {quoted_string_core} {CFWS}? )"

# atext           =   ALPHA / DIGIT /    ; Printable US-ASCII
#                    "!" / "#" /        ;  characters not including
#                    "$" / "%" /        ;  specials.  Used for atoms.
#                    "&" / "'" /
#                    "*" / "+" /
#                    "-" / "/" /
#                    "=" / "?" /
#                    "^" / "_" /
#                    "`" / "{" /
#                    "|" / "}" /
#                    "~"

atext = rf"(?: {ALPHA} | {DIGIT} | [!#$%&'*+\-/=?^_`{{|}}~] )"

# atom            =   [CFWS] 1*atext [CFWS]
# word            =   atom / quoted-string
# phrase          =   1*word / obs-phrase
#
# Flattened; see above. Trailing CFWS is left to angle-addr, which allows it. obs-phrase is
# not supported.

phrase = rf"(?: (?: {CFWS}? (?: {atext} | {quoted_string_core} ) ){{1,}} )"

# display-name    =   phrase

display_name = phrase

# dot-atom-text   =   1*atext *("." 1*atext)

dot_atom_text = rf"(?: {atext}+ (?: \. {atext}+ )* )"

# dot-atom        =   [CFWS] dot-atom-text [CFWS]

dot_atom = rf"(?: {CFWS}? {dot_atom_text} {CFWS}? )"

# local-part      =   dot-atom / quoted-string / obs-local-part

local_part = rf"(?: {dot_atom} | {quoted_string} )"

# dtext           =   %d33-90 /          ; Printable US-ASCII
#                     %d94-126 /         ;  characters not including
#                     obs-dtext          ;  "[", "]", or "\"

dtext = r"[\x21-\x5a\x5e-\x7e]"

# domain-literal  =   [CFWS] "[" *([FWS] dtext) [FWS] "]" [CFWS]

domain_literal = rf"(?: {CFWS}? \[ (?: {FWS}? {dtext} )* {FWS}? \] {CFWS}? )"

# domain          =   dot-atom / domain-literal / obs-domain

domain = rf"(?: {dot_atom} | {domain_literal} )"

# addr-spec       =   local-part "@" domain

addr_spec = rf"(?: {local_part} @ {domain} )"

# angle-addr      =   [CFWS] "<" addr-spec ">" [CFWS] /
#                     obs-angle-addr

angle_addr = rf"(?: {CFWS}? \< {addr_spec} \> {CFWS}? )"

# name-addr       =   [display-name] angle-addr

name_addr = rf"(?: {display_name}? {angle_addr} )"

# mailbox         =   name-addr / addr-spec
#
# The lookarounds stop the leading and trailing CFWS from sharing whitespace with a caller's own
# \s* padding, which would otherwise cost quadratic time on a long run of whitespace. They cover
# space, tab and CRLF folds (a CRLF followed by WSP). A bare CRLF is deliberately not covered: it
# can't be CFWS, so only the caller's \s* can absorb it.

mailbox = rf"""(?:
    (?<! [ \t] ) (?! (?<= \r\n ) [ \t] )
    (?: {name_addr} | {addr_spec} )
    (?! [ \t] | \r\n [ \t] )
)"""
