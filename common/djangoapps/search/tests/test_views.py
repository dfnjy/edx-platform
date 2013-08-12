"""
Basic test for views in search
"""

import search.views as views
from django.test import TestCase
import threading
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from collections import namedtuple
import requests
from search.models import SearchResults


class StubServer(HTTPServer):
    """
    Based on Will Daly's implementation of a stub server up at
    http://blog.will-daly.com/2013/06/05/stub-http-server/
    """

    def __init__(self):
        address = ('127.0.0.1', 9201)
        HTTPServer.__init__(self, address, StubRequestHandler)
        self.start()

        self.requests = []
        self.request = namedtuple("Request", "request_type path content")

        self.header_dict = {}
        self.status_code = 200
        self.content = ""

    def start(self):
        """
        Starts the server
        """

        server_thread = threading.Thread(target=self.serve_forever)
        server_thread.daemon = True
        server_thread.start()

    def stop(self):
        """
        Cleanly stops the server
        """

        self.shutdown()
        self.socket.close()

    def log_request(self, request_type, path, content):
        """
        Keeps track of the request and alters content if a search request is launched
        """

        self.requests.append(self.request(request_type, path, content))
        if path.endswith("_search"):
            self.content = "{}"

    def set_response(self, header_dict, status_code, content):
        """
        Set server response
        """

        self.header_dict = header_dict
        self.status_code = status_code
        self.content = content


class StubRequestHandler(BaseHTTPRequestHandler):
    """
    Object that actually handles the requests for the Server
    """

    def do_POST(self):
        """
        Handling for a POST request
        """

        self.server.log_request('POST', self.path, self.content())
        self._send_server_response()

    def do_GET(self):
        """
        Handling for a GET request
        """

        self.server.log_request('GET', self.path, self.content())
        self._send_server_response()

    def content(self):
        """
        Returns request content
        """

        try:
            length = int(self.headers.getheader('content-length'))
        except (TypeError, ValueError):
            return ""
        self.rfile.read(length)

    def _send_server_response(self):
        """
        Sends the Server's current response to the client
        """

        self.send_response(self.server.status_code)
        for (key, value) in self.server.header_dict.items():
            self.send_header(key, value)

        self.end_headers()
        self.wfile.write(self.server.content)


class ViewTest(TestCase):
    """
    Basic test class for base view case. A small test, but one that adresses some blind spots of tests
    """

    def setUp(self):
        self.stub = StubServer()
        self.url = "http://127.0.0.1:9201"

    def test_stub_server(self):
        check = requests.get("http://127.0.0.1:9201")
        self.assertEqual(check.status_code, 200)

    def test_basic_view(self):
        fake_request = namedtuple("Request", "GET")
        response = views._find(fake_request({}), "test-course", self.url)
        self.assertFalse(response["results"])
        self.assertEqual(response["old_query"], "*.*")
        self.assertTrue(isinstance(response['data'], SearchResults))

    def tearDown(self):
        self.stub.stop()
