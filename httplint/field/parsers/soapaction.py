from httplint.field import HttpField


class soapaction(HttpField):
    canonical_name = "SoapAction"
    description = """\
The `SOAPAction` request header is used by SOAP, which isn't really HTTP. Stop it."""
    reference = "http://www.w3.org/TR/2000/NOTE-SOAP-20000508/#_Toc478383528"
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False
    no_coverage = True
