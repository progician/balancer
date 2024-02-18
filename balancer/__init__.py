from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen

class BalancerRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        address = self.server.take_next()
        content_length = int(self.headers.get('content-length', '0'))
        data = None
        if content_length > 0:
            data = self.rfile.read(content_length)
    
        req = Request(
            url=address,
            data=data,
            headers=self.headers,
        )
        resp = urlopen(req)
        self.send_response(resp.code)
        for key, value in req.headers.items():
            self.send_header(key, value)
        self.end_headers()

        self.wfile.write(resp.read())
        self.wfile.flush()


class Balancer(HTTPServer):
    def __init__(self, port: int, proxy_addresses: list[str]) -> None:
        super().__init__(server_address=("localhost", port), RequestHandlerClass=BalancerRequestHandler)
        self.proxy_addresses = proxy_addresses
        self.current_index = 0

    def take_next(self) -> str:
        res = self.proxy_addresses[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_addresses)
        return res
