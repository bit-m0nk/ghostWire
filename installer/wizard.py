#!/usr/bin/env python3
"""
GhostWire — Web Installer Wizard
Runs as a lightweight Flask-like server BEFORE the main app is installed.
Uses only Python stdlib + Jinja2 (guaranteed available after: pip install jinja2).

Start it with:
    sudo python3 installer/wizard.py

It listens on :8080 and guides the admin through setup, then calls install.sh.
"""
import html
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("[!] Jinja2 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "jinja2", "--quiet"])
    from jinja2 import Environment, FileSystemLoader

WIZARD_DIR  = Path(__file__).parent
INSTALL_DIR = Path("/opt/ghostwire")
INSTALL_SH  = WIZARD_DIR.parent / "install.sh"
PORT        = int(os.environ.get("WIZARD_PORT", 8080))

jinja = Environment(
    loader=FileSystemLoader(str(WIZARD_DIR / "templates")),
    autoescape=True,
)

# ── Module-level server handle (set in main, used by shutdown thread) ────────
_server: "HTTPServer | None" = None

# ── Shared state (wizard is single-user by design) ────────────────────────────
_state = {
    "step": "welcome",          # welcome | config | installing | done | error
    "log_lines": [],
    "config": {},
    "error": "",
    "done_url": "",
}
_lock = threading.Lock()


def _detect_ips():
    local = ""
    public = "unknown"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local = s.getsockname()[0]
        s.close()
    except Exception:
        local = "127.0.0.1"
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=4) as r:
            public = r.read().decode().strip()
    except Exception:
        public = local
    return local, public


_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mGKHF]')

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)

def _append_log(line: str):
    with _lock:
        # Strip ANSI colour codes first, then HTML-escape for safe injection
        clean = html.escape(_strip_ansi(line))
        _state["log_lines"].append(clean)
        if len(_state["log_lines"]) > 500:
            _state["log_lines"] = _state["log_lines"][-500:]


def _run_install(cfg: dict):
    """Runs install.sh non-interactively by passing all answers via env vars."""
    # Derive ddns_hostname from whichever provider field was filled in
    provider = cfg.get("ddns_provider", "dynu")
    if provider == "noip":
        ddns_hostname = cfg.get("noip_hostname", "")
    else:
        ddns_hostname = cfg.get("dynu_hostname", "")
    # Fall back to the explicit ddns_hostname field (populated by hidden JS field)
    if not ddns_hostname:
        ddns_hostname = cfg.get("ddns_hostname", "")

    env = {**os.environ}
    env.update({
        "GW_NONINTERACTIVE": "1",
        "GW_BRAND":          cfg.get("vpn_brand", "GhostWire"),
        "GW_ADMIN_USER":     cfg.get("admin_user", "admin"),
        "GW_ADMIN_PASS":     cfg.get("admin_pass", ""),
        "GW_PANEL_PORT":     cfg.get("panel_port", "8080"),
        "GW_VPN_SUBNET":     cfg.get("vpn_subnet", "10.10.0.0/24"),
        "GW_PUBLIC_IP":      cfg.get("public_ip", ""),
        "GW_LOCAL_IP":       cfg.get("local_ip", ""),
        "GW_USE_DDNS":       "true" if cfg.get("use_ddns") else "false",
        "GW_DDNS_PRIMARY":   cfg.get("ddns_provider", ""),
        "GW_DDNS_HOSTNAME":  ddns_hostname,
        "GW_DYNU_USERNAME":  cfg.get("dynu_username", ""),
        "GW_DYNU_PASS":      cfg.get("dynu_pass", ""),
        "GW_NOIP_HOSTNAME":  cfg.get("noip_hostname", ""),
        "GW_NOIP_USERNAME":  cfg.get("noip_username", ""),
        "GW_NOIP_PASS":      cfg.get("noip_pass", ""),
    })

    try:
        proc = subprocess.Popen(
            ["bash", str(INSTALL_SH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _append_log(line)
        proc.wait()

        # ── Post-install patch: fix strawberry graphiql= → graphql_ide= ──────
        schema_file = INSTALL_DIR / "backend/app/domains/graphql/schema.py"
        if schema_file.exists():
            original = schema_file.read_text()
            if "graphiql=True" in original:
                patched = original.replace(
                    "graphiql=True",
                    'graphql_ide="graphiql"'
                )
                schema_file.write_text(patched)
                _append_log("[fix] Patched GraphQLRouter: graphiql= → graphql_ide= (strawberry ≥0.235)")

        if proc.returncode == 0:
            port = cfg.get("panel_port", "8080")
            with _lock:
                _state["step"]     = "done"
                _state["done_url"] = f"http://{cfg.get('local_ip','localhost')}:{port}"
            # Give the browser a moment to fetch the done page, then
            # shut the wizard down so it releases port 8080.
            def _delayed_shutdown():
                time.sleep(8)
                if _server:
                    _server.shutdown()
            threading.Thread(target=_delayed_shutdown, daemon=True).start()
        else:
            with _lock:
                _state["step"]  = "error"
                _state["error"] = f"install.sh exited with code {proc.returncode}"
    except Exception as e:
        with _lock:
            _state["step"]  = "error"
            _state["error"] = str(e)


# ── HTTP handler ──────────────────────────────────────────────────────────────

class WizardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silence default access log

    def _send(self, body: str, status: int = 200, ct: str = "text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _render(self, tpl: str, **ctx) -> str:
        return jinja.get_template(tpl).render(**ctx)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/" or path == "/wizard":
            step = _state["step"]
            if step == "welcome":
                local_ip, public_ip = _detect_ips()
                self._send(self._render("wizard_welcome.html",
                    local_ip=local_ip, public_ip=public_ip))
            elif step == "config":
                self._send(self._render("wizard_config.html",
                    cfg=_state["config"]))
            elif step == "installing":
                self._send(self._render("wizard_installing.html",
                    log_lines=_state["log_lines"]))
            elif step == "done":
                self._send(self._render("wizard_done.html",
                    done_url=_state["done_url"]))
            elif step == "error":
                self._send(self._render("wizard_error.html",
                    error=_state["error"],
                    log_lines=_state["log_lines"]))
        elif path == "/status":
            with _lock:
                payload = json.dumps({
                    "step":      _state["step"],
                    "log_lines": _state["log_lines"][-50:],
                    "done_url":  _state["done_url"],
                    "error":     _state["error"],
                })
            self._send(payload, ct="application/json")
        elif path.startswith("/static/"):
            self._serve_static(path[8:])
        else:
            self._send("Not found", 404)

    def _serve_static(self, name: str):
        safe = re.sub(r"[^a-zA-Z0-9._-]", "", name)
        p = WIZARD_DIR / "static" / safe
        if p.exists():
            ct = "text/css" if safe.endswith(".css") else "application/javascript"
            self._send(p.read_text(), ct=ct)
        else:
            self._send("Not found", 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        params = dict(urllib.parse.parse_qsl(body))

        if path == "/start":
            with _lock:
                _state["step"] = "config"
                local_ip, public_ip = _detect_ips()
                _state["config"] = {
                    "local_ip":  local_ip,
                    "public_ip": public_ip,
                }
            self._redirect("/")

        elif path == "/install":
            provider = params.get("ddns_provider", "dynu")
            if provider == "noip":
                ddns_hostname = params.get("noip_hostname", "")
            else:
                ddns_hostname = params.get("dynu_hostname", "")
            # Fall back to explicit hidden field (populated by JS sync)
            if not ddns_hostname:
                ddns_hostname = params.get("ddns_hostname", "")

            cfg = {
                "vpn_brand":     params.get("vpn_brand", "GhostWire"),
                "admin_user":    params.get("admin_user", "admin"),
                "admin_pass":    params.get("admin_pass", ""),
                "panel_port":    params.get("panel_port", "8080"),
                "vpn_subnet":    params.get("vpn_subnet", "10.10.0.0/24"),
                "public_ip":     params.get("public_ip", _state["config"].get("public_ip", "")),
                "local_ip":      params.get("local_ip",  _state["config"].get("local_ip", "")),
                "use_ddns":      params.get("use_ddns") == "on",
                "ddns_provider": provider,
                "ddns_hostname": ddns_hostname,
                "dynu_hostname": params.get("dynu_hostname", ""),
                "dynu_username": params.get("dynu_username", ""),
                "dynu_pass":     params.get("dynu_pass", ""),
                "noip_hostname": params.get("noip_hostname", ""),
                "noip_username": params.get("noip_username", ""),
                "noip_pass":     params.get("noip_pass", ""),
            }
            with _lock:
                _state["step"]      = "installing"
                _state["config"]    = cfg
                _state["log_lines"] = []

            t = threading.Thread(target=_run_install, args=(cfg,), daemon=True)
            t.start()
            self._redirect("/")

        elif path == "/reset":
            with _lock:
                _state["step"]      = "welcome"
                _state["log_lines"] = []
                _state["error"]     = ""
            self._redirect("/")
        else:
            self._send("Not found", 404)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _server
    if os.geteuid() != 0:
        print("[!] The installer wizard should be run as root (sudo python3 wizard.py)")
    _server = HTTPServer(("0.0.0.0", PORT), WizardHandler)
    local_ip, _ = _detect_ips()
    print(f"\n👻 GhostWire Installer Wizard")
    print(f"   Open in your browser: http://{local_ip}:{PORT}\n")
    try:
        _server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Wizard stopped.")


if __name__ == "__main__":
    main()
