"""
Regex for RFC9112
"""

# pylint: disable=invalid-name, line-too-long

from .rfc3986 import absolute_URI
from .rfc3986 import host as uri_host
from .rfc3986 import port, query
from .rfc5234 import (
    CRLF,
    DIGIT,
    HEXDIG,
    HTAB,
    OCTET,
    SP,
    VCHAR,
)

# RFC 9112 refers to these rules, which RFC 9110 defines (and uri-host, port, which RFC 3986
# does); they are imported, not redefined, so that there is one transcription of each.
from .rfc9110 import (
    BWS,
    OWS,
    RWS,
    absolute_path,
    field_name,
    field_value,
    list_rule,
    obs_text,
    quoted_string,
    token,
    transfer_coding,
)

SPEC_URL = "http://httpwg.org/specs/rfc9112"

#   field-line = field-name ":" OWS field-value OWS

field_line = rf"(?: {field_name} : {OWS} {field_value} {OWS} )"

#   obs-fold = OWS CRLF RWS
#            ; obsolete line folding

obs_fold = rf"(?: {OWS} {CRLF} {RWS} )"

## Chunked Encoding

#   chunk-size = 1*HEXDIG

chunk_size = rf"(?: {HEXDIG}+ )"

#   chunk-ext-name = token

chunk_ext_name = token

#   chunk-ext-val = token / quoted-string

chunk_ext_val = rf"(?: {token} | {quoted_string} )"

#   chunk-ext = *( BWS ";" BWS chunk-ext-name [ BWS "=" BWS chunk-ext-val ] )

chunk_ext = rf"(?: (?: {BWS} \; {BWS} {chunk_ext_name} (?: {BWS} \= {BWS} {chunk_ext_val} )? )* )"

#   chunk-data = 1*OCTET

chunk_data = rf"{OCTET}+"

#   chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF

chunk = rf"(?: {chunk_size} (?: {chunk_ext} )? {CRLF} {chunk_data} {CRLF} )"

#   last-chunk = 1*"0" [ chunk-ext ] CRLF

last_chunk = rf"(?: (?: 0 )+ (?: {chunk_ext} )? {CRLF} )"

#   trailer-section = *( field-line CRLF )

trailer_section = rf"(?: {field_line} {CRLF} )*"

#   chunked-body = *chunk last-chunk trailer-section CRLF
#
# This is a faithful transcription, but it must not be used to match a body. The ABNF says
# chunk-data is "1*OCTET ; a sequence of chunk-size octets", and the length is prose, not
# ABNF: OCTET+ can contain CRLF, so a body can be split into chunks in many ways and matching
# backtracks exponentially when it fails (several seconds at 12 chunks). Chunked bodies are
# decoded by counting octets, not by regular expression.

chunked_body = rf"(?: (?: {chunk} )* {last_chunk} {trailer_section} {CRLF} )"


## Transfer-Encoding

#   Transfer-Encoding = #transfer-coding
#                     ; defined in [HTTP], Section 10.1.4
#
# transfer-coding (and its transfer-parameter) is defined by RFC 9110 and imported above. The
# RFC 7230 form, "chunked / compress / deflate / gzip / transfer-extension", matched a
# registered name by two routes, so a long list that failed to match backtracked exponentially.

Transfer_Encoding = list_rule(transfer_coding)

## Message

#   HTTP-name = %s"HTTP"
#             ; case-sensitive (RFC 9112 Appendix A has %x48.54.54.50 ; HTTP)

HTTP_name = r"(?-i:HTTP)"

#   HTTP-version = HTTP-name "/" DIGIT "." DIGIT

HTTP_version = rf"(?: {HTTP_name} / {DIGIT} \. {DIGIT} )"

#   method = token

method = token

#   absolute-form = absolute-URI

absolute_form = absolute_URI

#   asterisk-form = "*"

asterisk_form = r"\*"

#   authority-form = uri-host ":" port

authority_form = rf"(?: {uri_host} : {port} )"

#   origin-form = absolute-path [ "?" query ]

origin_form = rf"(?: {absolute_path} (?: \? {query} )? )"

#   request-target = origin-form / absolute-form / authority-form / asterisk-form

request_target = rf"(?: {origin_form} | {absolute_form} | {authority_form} | {asterisk_form} )"

#   request-line = method SP request-target SP HTTP-version

request_line = rf"(?: {method} {SP} {request_target} {SP} {HTTP_version} )"

#   status-code = 3DIGIT

status_code = rf"(?: {DIGIT}{{3}} )"

#   reason-phrase = 1*( HTAB / SP / VCHAR / obs-text )

reason_phrase = rf"(?: (?: {HTAB} | {SP} | {VCHAR} | {obs_text} )+ )"

#   status-line = HTTP-version SP status-code SP [ reason-phrase ]

status_line = rf"(?: {HTTP_version} {SP} {status_code} {SP} (?: {reason_phrase} )? )"

#   start-line = request-line / status-line

start_line = rf"(?: {request_line} | {status_line} )"

#   message-body = *OCTET

message_body = rf"(?: {OCTET}* )"

#   HTTP-message = start-line CRLF
#                  *( field-line CRLF )
#                  CRLF
#                  [ message-body ]

HTTP_message = rf"(?: {start_line} {CRLF} (?: {field_line} {CRLF} )* {CRLF} (?: {message_body} )? )"
