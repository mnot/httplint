
from httplint.message import HttpRequest, HttpResponse
from httplint.note import Notes


__version__ = "0.0.1"


def lint_request(request: HttpRequest) -> Notes:
    pass

def lint_response(response:HttpResponse, request:HttpRequest=None) -> Notes:
    pass
