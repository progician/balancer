from balancer import Balancer
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from threading import Thread

from typing import Generator, cast

import pytest

class StubResponse(BaseHTTPRequestHandler):
    def _respond_with_text(self, text: str) -> None:
        self.send_response(200)
        self.send_header("Content-type", " text/plain")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))
        self.wfile.flush()

    def do_GET(self) -> None:
        server = cast(StubServer, self.server)
        server_index = server.index
        self._respond_with_text(f"server {server_index}")

    def do_POST(self) -> None:
        content_length = int(self.headers.get("content-length", "0"))
        if content_length > 0:
            content = self.rfile.read(content_length).decode("utf-8")
        server = cast(StubServer, self.server)
        server_index = server.index
        self._respond_with_text(f"{content} {server_index}")


class StubServer(HTTPServer):
    def __init__(self, index: int, port: int) -> None:
        self.index = index
        self.port = port
        super().__init__(
            server_address=("localhost", port),
            RequestHandlerClass=StubResponse
        )


class ServerFixture:
    def __init__(self, instances: int, starting_port = 8081) -> None:
        self.servers = [
            StubServer(
                index=i,
                port=starting_port + i,
            )
            for i in range(instances)
        ]

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
            f"http://localhost:{s.port}"
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


@pytest.mark.parametrize("server_instances", [10], indirect=True)
def test_proxy_with_post(server_instances: ServerFixture, balancer: Balancer) -> None:
    server_instances.start()
    arbtirary_content = "hey, yo!"
    matches = 0
    for i, _ in enumerate(server_instances.servers):
        req = Request(
            url="http://localhost:8080",
            data=arbtirary_content.encode("utf-8"),
            headers={"content-length": str(len(arbtirary_content))},
            method="POST",
        )
        resp = urlopen(req)
        server_id_response = resp.read().decode("utf-8")
        if server_id_response == f"{arbtirary_content} {i}":
            matches += 1

    assert matches == len(server_instances.servers)