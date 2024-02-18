from balancer import Balancer
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen
from threading import Thread

from typing import Generator

import pytest

class StubResponse(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-type", " text/plain")
        self.end_headers()
        self.wfile.write(f"server {self.server.test_index}".encode("utf-8"))


class ServerFixture:
    def __init__(self, instances: int, starting_port = 8081) -> None:
        self.servers = [
            HTTPServer(
                server_address=("localhost", starting_port + i),
                RequestHandlerClass=StubResponse,
            )
            for i in range(instances)
        ]
        for i, server in enumerate(self.servers):
            server.test_index = i

        self.threads = [
            Thread(target=server.serve_forever)
            for server in self.servers
        ]
    
    def start(self) -> None:
        for t in self.threads:
            t.start()

    def stop(self) -> None:
        for server in self.servers:
            server.shutdown()


@pytest.fixture
def server_instances(request: pytest.FixtureRequest) -> Generator[ServerFixture, None, None]:
    fixture = ServerFixture(instances=request.param)
    yield fixture
    fixture.stop()


@pytest.fixture
def balancer(server_instances: ServerFixture) -> Generator[Balancer, None, None]:
    balancer = Balancer(
        port=8080,
        proxy_addresses=[
            f"http://localhost:{8081 + s.test_index}"
            for s in server_instances.servers
        ]
    )
    balancer_thread = Thread(target=balancer.serve_forever)
    balancer_thread.start()

    yield balancer

    balancer.shutdown()
    balancer_thread.join()


@pytest.mark.parametrize("server_instances", [10], indirect=True)
def test_every_request_lands_on_different_server(server_instances: ServerFixture, balancer: Balancer) -> None:
    server_instances.start()
    matches = 0
    for i, _ in enumerate(server_instances.servers):
        with urlopen("http://localhost:8080") as f:
            server_id_response = f.read(32).decode("utf-8")

        if server_id_response == f"server {i}":
            matches += 1

    assert matches == len(server_instances.servers)