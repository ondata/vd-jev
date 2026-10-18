import http.server
import json
import threading
import time

import pytest


class FakeJev:
    'Loopback HTTP server that plays scripted answers and records the requests it gets.'

    def __init__(self):
        self.replies = []    # list of (status, headers, body, delay); body is a dict or bytes
        self.requests = []   # list of dict(path, headers, body)
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                fake.requests.append(dict(path=self.path, headers=dict(self.headers),
                                          body=json.loads(self.rfile.read(length))))
                status, headers, body, delay = fake.replies.pop(0)
                if delay:
                    time.sleep(delay)
                if isinstance(body, dict):
                    body = json.dumps(body).encode('utf-8')
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:  # the client gave up first, as in the timeout test
                    pass

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/api/v1/systemone'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reply(self, body, status=200, headers=None, delay=0):
        self.replies.append((status, headers or {}, body, delay))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fakejev():
    fake = FakeJev()
    yield fake
    fake.close()
