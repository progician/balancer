from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import cast
from urllib.request import Request, urlopen

class BalancerRequestHandler(BaseHTTPRequestHandler):
    @property
    def balancer(self):
        return cast(Balancer, self.server)

    def _proxy_request(self) -> None:
        address = self.balancer.take_next()
        content_length = int(self.headers.get('content-length', '0'))
        data = None
        if content_length > 0:
            data = self.rfile.read(content_length)
    
        req = Request(
            url=address,
            data=data,
            headers={ k: v for k, v in self.headers.raw_items()},
            method=self.command,
        )
        resp = urlopen(req)
        self.send_response(resp.code)
        for key, value in resp.headers.items():
            self.send_header(key, value)
        self.end_headers()

        body = resp.read()
        self.wfile.write(body)
        self.wfile.flush()

    def do_GET(self) -> None:
        self._proxy_request()

    def do_POST(self) -> None:
        self._proxy_request()


class Balancer(HTTPServer):
    def __init__(self, port: int, proxy_addresses: list[str]) -> None:
        super().__init__(server_address=("localhost", port), RequestHandlerClass=BalancerRequestHandler)
        self.proxy_addresses = proxy_addresses
        self.current_index = 0

    def take_next(self) -> str:
        res = self.proxy_addresses[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_addresses)
        return res
