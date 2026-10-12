"""Tiny local web UI (stdlib only) for controlling the lights from a browser."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from . import config
from .aura import MODES, AuraController, AuraError
from .core import apply
from .effects import EFFECTS, EffectRunner


def serve(ctrl: AuraController, host="127.0.0.1", port=8765):
    runner = EffectRunner(ctrl)
    cfg = config.load()
    try:
        apply(ctrl, runner, cfg["last"])
    except (AuraError, ValueError, KeyError) as e:
        print(f"Could not restore last state: {e}")

    page = resources.files("caselight").joinpath("web/index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            elif self.path == "/api/state":
                self._json(200, {
                    "device": {"path": ctrl.info.path, "firmware": ctrl.info.firmware},
                    "zones": [{"name": z.name, "leds": z.led_count, "addressable": z.addressable}
                              for z in ctrl.zones],
                    "hardware_modes": [m for m in MODES if m != "direct"],
                    "software_effects": list(EFFECTS),
                    "last": cfg["last"],
                })
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/apply":
                return self._json(404, {"error": "not found"})
            # Only accept same-origin requests so other websites can't drive the LEDs.
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                return self._json(403, {"error": "cross-origin request refused"})
            try:
                state = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                apply(ctrl, runner, state)
            except (AuraError, ValueError, KeyError, TypeError) as e:
                return self._json(400, {"error": str(e)})
            cfg["last"] = state
            config.save(cfg)
            self._json(200, {"ok": True})

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"caselight UI running at http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()
        httpd.server_close()
