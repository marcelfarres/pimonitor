#!/usr/bin/env python3
"""
Simple HTTP status page for the LED service monitor.

This script runs a very small HTTP server that exposes the current status of
all configured services in `led-monitor-cfg.json`. It reuses the same
check logic as the LED monitor, but runs without touching the Kano hat
hardware.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Any
import json
import html

from pimonitor.monitor import ServiceMonitor, CONFIG_FILE


class StatusHandler(BaseHTTPRequestHandler):
    """
    Function: StatusHandler

    Tiny description:
      HTTP request handler that renders a simple HTML status page.

    Input parameters:
      - Standard BaseHTTPRequestHandler attributes (path, headers, etc.).

    Output parameters:
      - HTTP responses containing either an HTML table or JSON summary.

    Longer description:
      For GET requests to `/` or `/status`, this handler runs the same
      service checks as the LED monitor and returns a compact summary of
      each service's state, including name, type, target, and severity.
      The root path returns an HTML page optimised for quick viewing on a
      phone or desktop browser.
    """

    monitor: ServiceMonitor  # set by server bootstrap

    def _collect_status(self) -> List[Dict[str, Any]]:
        """Run checks for all services and return their status."""
        # Always reload config so that the status view reflects the latest
        # `led-monitor-cfg.json` contents without needing to restart the web
        # service after edits.
        self.monitor.load_config()
        services = self.monitor.config.get("services", [])
        results: List[Dict[str, Any]] = []

        for service in services:
            name = service.get("name", "unknown")
            service_type = service.get("type", "http")
            target = service.get("target", "")
            try:
                severity = int(service.get("severity", 5))
            except (TypeError, ValueError):
                severity = 5

            ok = self.monitor.check_service(service)
            results.append(
                {
                    "name": name,
                    "type": service_type,
                    "target": target,
                    "severity": severity,
                    "ok": ok,
                }
            )
        return results

    def _send_json(self, data: Any) -> None:
        """Send a JSON response."""
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, rows: List[Dict[str, Any]]) -> None:
        """Render a very small HTML status page."""
        body_rows = []
        for row in rows:
            name = html.escape(str(row["name"]))
            service_type = html.escape(str(row["type"]))
            target = html.escape(str(row["target"]))
            severity = int(row["severity"])
            ok = bool(row["ok"])

            status_text = "OK" if ok else "DOWN"
            status_class = "ok" if ok else "down"

            body_rows.append(
                f"<tr class='{status_class}'>"
                f"<td>{name}</td>"
                f"<td>{service_type}</td>"
                f"<td><code>{target}</code></td>"
                f"<td>{severity}</td>"
                f"<td>{status_text}</td>"
                "</tr>"
            )

        body_html = "\n".join(body_rows)
        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>LED Monitor Status</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111;
      color: #eee;
      margin: 0;
      padding: 1rem;
    }}
    h1 {{
      font-size: 1.4rem;
      margin-bottom: 0.5rem;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      max-width: 960px;
      margin-top: 0.5rem;
      font-size: 0.9rem;
    }}
    th, td {{
      border-bottom: 1px solid #333;
      padding: 0.4rem 0.6rem;
      text-align: left;
    }}
    th {{
      background: #222;
      position: sticky;
      top: 0;
    }}
    tr.ok td {{
      color: #9be7a3;
    }}
    tr.down td {{
      color: #ffb3b3;
    }}
    code {{
      font-family: "JetBrains Mono", "Fira Code", monospace;
      font-size: 0.8rem;
    }}
    .badge {{
      display: inline-block;
      padding: 0.1rem 0.4rem;
      border-radius: 0.3rem;
      font-size: 0.75rem;
      background: #333;
    }}
    .badge.ok {{
      background: #135d18;
      color: #9be7a3;
    }}
    .badge.down {{
      background: #5d1313;
      color: #ffb3b3;
    }}
  </style>
</head>
<body>
  <h1>LED Monitor Status</h1>
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Type</th>
        <th>Target</th>
        <th>Severity</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {body_html}
    </tbody>
  </table>
</body>
</html>
"""
        payload = html_doc.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        """Handle GET requests for / and /status."""
        if self.path in ("/status.json", "/status.json/"):
            rows = self._collect_status()
            self._send_json(rows)
            return

        if self.path not in ("/", "/status", "/status/"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found\n")
            return

        rows = self._collect_status()
        self._send_html(rows)


def main() -> None:
    """
    Function: main

    Tiny description:
      Run the HTTP status server on port 8081.

    Input parameters:
      - None (reads configuration from CONFIG_FILE).

    Output parameters:
      - None. Blocks serving requests until interrupted.

    Longer description:
      Creates a `ServiceMonitor` instance with hat support disabled so that
      it can reuse the same service-check logic as the LED monitor without
      touching GPIO or the LED ring. The server listens on 0.0.0.0:8081 and
      serves both HTML and JSON status views.
    """
    monitor = ServiceMonitor(config_file=CONFIG_FILE, enable_hat=False)
    StatusHandler.monitor = monitor  # type: ignore[assignment]

    addr = ("0.0.0.0", 8081)
    httpd = HTTPServer(addr, StatusHandler)
    print("Status web server listening on http://0.0.0.0:8081/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()


