import http.server
import json
import threading
import time

import pytest


class FakeJev:
    'Loopback HTTP server that plays scripted answers and records the requests it gets.'

    def __init__(self):
        self.replies = []    # list of (status, headers, body, delay); body is a dict or bytes
        self.responder = None  # if set, called with the request body when no scripted reply is left
        self.requests = []   # list of dict(path, headers, body)
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                fake.requests.append(dict(path=self.path, headers=dict(self.headers),
                                          body=json.loads(self.rfile.read(length))))
                if fake.replies:
                    status, headers, body, delay = fake.replies.pop(0)
                else:
                    status, headers, body, delay = fake.responder(fake.requests[-1]['body'])
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
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/api/alpha/decisions'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reply(self, body, status=200, headers=None, delay=0):
        self.replies.append((status, headers or {}, body, delay))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def deterministic_answer(body):
    'A plausible Jev reply that depends only on the request, so parallel runs give the same output.'
    question = body['questions']['answer']
    n = len(body['state'])
    if question['type'] == 'noul':
        answer = {'type': 'noul', 'noul': round((n % 10) / 10, 2)}
    elif question['type'] == 'choice':
        labels = list(question['criteria'])
        pick = labels[n % len(labels)]
        answer = {'type': 'choice', 'choice': pick, 'probabilities': {l: (0.9 if l == pick else 0.1 / (len(labels)-1)) for l in labels}, 'confidence': 0.9}
    else:
        levels = question['criteria']
        answer = {'type': 'score', 'score': float(n % len(levels)), 'legend': {str(i): l for i, l in enumerate(levels)}, 'confidence': 0.8}
    return 200, {}, {'answers': {'answer': answer}, 'usage': {'cost': 0.00001}}, 0


@pytest.fixture
def fakejev():
    fake = FakeJev()
    yield fake
    fake.close()
