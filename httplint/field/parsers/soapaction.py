from httplint.field.singleton_field import SingletonField
from httplint.types import RequestLinterProtocol


class soapaction(SingletonField[RequestLinterProtocol]):
    canonical_name = "SoapAction"
    description = """\
The `SOAPAction` request header is used by SOAP, which isn't really HTTP. Stop it."""
    reference = "http://www.w3.org/TR/2000/NOTE-SOAP-20000508/#_Toc478383528"
    syntax = False
    deprecated = False
    no_coverage = True
