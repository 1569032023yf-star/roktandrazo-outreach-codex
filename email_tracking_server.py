"""First-party email tracking HTTP server.

Endpoints:
  GET  /o/<token>.gif           — open tracking pixel
  GET  /c/<token>/<link_id>     — click tracking redirect
  POST /events/provider/<name>  — external provider webhook
  GET  /healthz                 — health check

Privacy:
  - No cookies set
  - No client info returned
  - Invalid tokens still return 1x1 GIF (no error leakage)
  - IP hashed with salt before storage
  - No precise geolocation
"""

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from email_engagement.provider import load_provider


# ── Configuration ────────────────────────────────────────────

DB_PATH = os.environ.get("WORKBUDDY_BD_DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "bd_leads.db"
)
BIND_HOST = os.environ.get("EMAIL_TRACKING_BIND_HOST", "127.0.0.1")
BIND_PORT = int(os.environ.get("EMAIL_TRACKING_BIND_PORT", "8750"))

# 1x1 transparent GIF (43 bytes)
PIXEL_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class TrackingHandler(BaseHTTPRequestHandler):
    """HTTP handler for tracking endpoints."""

    # ── GET routes ─────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/o/"):
            self._handle_open(path)
        elif path.startswith("/c/"):
            self._handle_click(path)
        elif path == "/healthz":
            self._healthz()
        else:
            # Return pixel for any unrecognized path — no error leakage
            self._serve_pixel()

    def _handle_open(self, path):
        """GET /o/<token>.gif — open tracking pixel."""
        try:
            token = path.split("/o/")[1].replace(".gif", "")
        except (IndexError, ValueError):
            self._serve_pixel()
            return

        provider = load_provider()
        token_hash = provider.hash_token(token)

        user_agent = self.headers.get("User-Agent", "")
        # Extract IP from X-Forwarded-For or direct
        ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not ip:
            ip = self.client_address[0] if self.client_address else ""

        # Write event (ignore DB errors — still serve pixel)
        try:
            conn = get_conn()
            provider.record_open(
                conn, token_hash,
                user_agent=user_agent,
                ip_address=ip,
            )
            conn.close()
        except Exception:
            pass  # Never fail on DB error — pixel must always be served

        self._serve_pixel()

    def _handle_click(self, path):
        """GET /c/<token>/<link_id> — click tracking redirect.

        Only redirects to pre-registered HTTPS targets.
        Returns 400 for unregistered or non-HTTPS targets.
        """
        parts = path.split("/")
        try:
            # path: /c/<token>/<link_id>
            if len(parts) >= 4:
                token = parts[2]
                link_id = int(parts[3])
            else:
                self._json_error(400, "Invalid click path")
                return
        except (ValueError, IndexError):
            self._json_error(400, "Invalid click parameters")
            return

        provider = load_provider()
        token_hash = provider.hash_token(token)
        user_agent = self.headers.get("User-Agent", "")
        ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not ip:
            ip = self.client_address[0] if self.client_address else ""

        # Resolve link target
        try:
            conn = get_conn()
            c = conn.cursor()

            # Find tracking message
            c.execute(
                """SELECT id FROM email_tracking_messages
                   WHERE tracking_token_hash=? AND tracking_enabled=1""",
                (token_hash,),
            )
            msg = c.fetchone()
            if not msg:
                conn.close()
                self._json_error(410, "Tracking disabled or expired")
                return

            # Look up registered link
            c.execute(
                """SELECT original_url FROM email_tracking_link_registry
                   WHERE tracking_message_id=? AND id=?""",
                (msg["id"], link_id),
            )
            link_row = c.fetchone()
            if not link_row:
                conn.close()
                self._json_error(404, "Link not found")
                return

            target_url = link_row["original_url"]

            # Security: only allow HTTPS targets
            if not target_url.startswith("https://"):
                conn.close()
                self._json_error(400, "Only HTTPS targets allowed")
                return

            # Record click
            provider.record_click(
                conn, token_hash, link_id,
                user_agent=user_agent,
                ip_address=ip,
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # If DB fails but we have the target, still redirect
            # (don't punish user for our tracking failure)
            if "target_url" in dir() and target_url:
                pass
            else:
                self._json_error(500, "Internal error")
                return

        # 302 redirect
        self.send_response(302)
        self.send_header("Location", target_url)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    # ── POST routes ────────────────────────────────────────

    def do_POST(self):
        """POST /events/provider/<name> — external webhook receiver."""
        if self.path.startswith("/events/"):
            self._handle_webhook()
        else:
            self._json_error(404, "Not found")

    def _handle_webhook(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_error(400, "Invalid JSON")
            return

        # Extract plan_entry_id from metadata (external provider should carry it)
        metadata = data.get("metadata", {}) or {}
        plan_entry_id = metadata.get("plan_entry_id", "")
        event_type = data.get("type", data.get("event_type", "unknown"))

        if not plan_entry_id:
            self._json_error(400, "Missing plan_entry_id in metadata")
            return

        # Map to our event
        mapped_type = {
            "email.opened": "open_signal",
            "email.clicked": "click_signal",
            "email.delivered": "delivery",
            "email.bounced": "bounce",
            "email.complained": "complaint",
            "email.unsubscribed": "unsubscribe",
        }.get(event_type, event_type)

        try:
            conn = get_conn()
            c = conn.cursor()
            c.execute(
                """SELECT id FROM email_tracking_messages
                   WHERE plan_entry_id=? AND tracking_enabled=1""",
                (plan_entry_id,),
            )
            msg = c.fetchone()
            if not msg:
                conn.close()
                self._json_error(404, "No active tracking for plan_entry_id")
                return

            provider = load_provider()
            method = getattr(provider, f"record_{mapped_type.split('_')[0]}", None)
            if method:
                method(conn, msg["id"])
                conn.commit()

            conn.close()
        except Exception as e:
            self._json_error(500, str(e))
            return

        self._json_ok({"status": "recorded", "event_type": mapped_type})

    # ── Helpers ────────────────────────────────────────────

    def _serve_pixel(self):
        """Always return 1x1 transparent GIF."""
        self.send_response(200)
        self.send_header("Content-Type", "image/gif")
        self.send_header("Content-Length", str(len(PIXEL_GIF)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(PIXEL_GIF)

    def _healthz(self):
        self._json_ok({"status": "ok"})

    def _json_ok(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, code, message):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default stderr logging (use file-based logging in production)."""
        pass


def main():
    server = HTTPServer((BIND_HOST, BIND_PORT), TrackingHandler)
    print(f"Email tracking server: http://{BIND_HOST}:{BIND_PORT}")
    print(f"  GET  /o/<token>.gif      — open pixel")
    print(f"  GET  /c/<token>/<link_id> — click redirect")
    print(f"  POST /events/provider/<n> — external webhook")
    print(f"  GET  /healthz             — health check")
    print(f"Provider: {load_provider().name}")
    print(f"DB: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
