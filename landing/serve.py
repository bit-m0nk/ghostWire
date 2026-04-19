#!/usr/bin/env python3
"""
GhostWire — Public Landing Page Server
A minimal standalone server for the project landing page.
Served separately from the VPN dashboard (different port, or via reverse proxy at /).

Run:   python3 landing/serve.py  (or mount via nginx)
"""
import os
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "jinja2", "--quiet"])
    from jinja2 import Environment, FileSystemLoader

LANDING_DIR = Path(__file__).parent
PORT = int(os.environ.get("LANDING_PORT", 8090))

jinja = Environment(loader=FileSystemLoader(str(LANDING_DIR / "templates")), autoescape=True)


class LandingHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            html = jinja.get_template("index.html").render()
            data = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), LandingHandler)
    print(f"👻 Landing page at http://0.0.0.0:{PORT}")
    server.serve_forever()
