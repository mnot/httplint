"""
Regex for RFC5322

These regex are directly derived from the ABNF in RFC5322, Section 3 (RFC 5322 has no
collected-ABNF appendix): Sections 3.2 (lexical tokens) and 3.4 (addresses). They are the
generating grammar; the obsolete syntax in Section 4 (the obs-* rules) is not implemented, and
each rule's obs-* alternative is left out.

Several rules are written in a flattened form to avoid exponential backtracking; those are
marked where they occur.

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name

from .rfc5234 import ALPHA, CRLF, DIGIT, VCHAR, WSP

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

ctext = r"[\x21-\x27\x2a-\x5b\x5d-\x7e]"

# ccontent        =   ctext / quoted-pair / comment
#
# The comment rule, and the CFWS and phrase rules below, are written as flat repetitions of
# single tokens rather than as nested repetitions of FWS, CFWS and atom. The RFC's nesting is
# ambiguous (e.g., "a" can be one atom or two), which makes backtracking exponential on
# non-matching input. The accepted language is the same, except that a run of FWS here may hold
# more than one CRLF (as obs-FWS, in Section 4.2, does).

# FWS             =   ([*WSP CRLF] 1*WSP) /  obs-FWS

FWS = rf"(?: (?: {WSP}* {CRLF} )? {WSP}{{1,}} )"

# One unit of a run of FWS; a CRLF is only valid when followed by WSP.

fws_unit = rf"(?: {WSP} | {CRLF} {WSP} )"

# comment         =   "(" *([FWS] ccontent) [FWS] ")"
#
# A regular expression can't recurse, so the nesting is unrolled: a comment can contain
# comments to two further levels, and those can't contain any.

comment_0 = rf"(?: \( (?: {fws_unit} | {ctext} | {quoted_pair} )* \) )"

comment_1 = rf"(?: \( (?: {fws_unit} | {ctext} | {quoted_pair} | {comment_0} )* \) )"

comment = rf"(?: \( (?: {fws_unit} | {ctext} | {quoted_pair} | {comment_1} )* \) )"

# CFWS            =   (1*([FWS] comment) [FWS]) / FWS

CFWS = rf"(?: (?: {fws_unit} | {comment} ){{1,}} )"

# quoted-string   =  [CFWS]
#                    DQUOTE *([FWS] qcontent) [FWS] DQUOTE
#                    [CFWS]

quoted_string_core = rf"(?: \" (?: {FWS}? {qcontent} )* {FWS}? \" )"

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

atom = rf"(?: {CFWS}? {atext}+ {CFWS}? )"

# specials        =   "(" / ")" /        ; Special characters that do
#                     "<" / ">" /        ;  not appear in atext
#                     "[" / "]" /
#                     ":" / ";" /
#                     "@" / "\" /
#                     "," / "." /
#                     DQUOTE

specials = r"[()<>\[\]:;@\\,.\x22]"

# word            =   atom / quoted-string

word = rf"(?: {atom} | {quoted_string} )"

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

mailbox_core = rf"(?: {name_addr} | {addr_spec} )"

# mailbox, as a whole field value (From). The lookarounds stop the leading and trailing CFWS from
# sharing whitespace with a caller's own \s* padding, which would otherwise cost quadratic time
# on a long run of whitespace. They cover space, tab and CRLF folds (a CRLF followed by WSP). A
# bare CRLF is deliberately not covered: it can't be CFWS, so only the caller's \s* can absorb
# it. They also mean that this form can't be used for a mailbox inside a list; use mailbox_core.

mailbox = rf"""(?:
    (?<! [ \t] ) (?! (?<= \r\n ) [ \t] )
    {mailbox_core}
    (?! [ \t] | \r\n [ \t] )
)"""

# mailbox-list    =   (mailbox *("," mailbox)) / obs-mbox-list

mailbox_list = rf"(?: {mailbox_core} (?: , {mailbox_core} )* )"

# group-list      =   mailbox-list / CFWS / obs-group-list

group_list = rf"(?: {mailbox_list} | {CFWS} )"

# group           =   display-name ":" [group-list] ";" [CFWS]

group = rf"(?: {display_name} : (?: {group_list} )? ; {CFWS}? )"

# address         =   mailbox / group

address = rf"(?: {mailbox_core} | {group} )"

# address-list    =   (address *("," address)) / obs-addr-list

address_list = rf"(?: {address} (?: , {address} )* )"

# unstructured    =   (*([FWS] VCHAR) *WSP) / obs-unstruct

unstructured = rf"(?: (?: {FWS}? {VCHAR} )* {WSP}* )"
