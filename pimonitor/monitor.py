#!/usr/bin/env python3
"""
LED Ring Service Monitor for Raspberry Pi

Monitors services and shows status on the Kano hat WS2812B LED ring.
"""

import time
import json
import subprocess
import requests
import socket
import random
from pathlib import Path
from threading import Event, Thread, Lock
import signal
import sys
import math
from urllib.parse import urlparse

try:
    from rpi_ws281x import Color
except ImportError:
    print("Warning: rpi_ws281x not installed. Install with: uv pip install --system rpi_ws281x")
    # Create a dummy Color function for fallback
    def Color(r: int, g: int, b: int) -> int:  # type: ignore[misc]
        return (r << 16) | (g << 8) | b

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("Warning: RPi.GPIO not installed. Install with: uv pip install --system RPi.GPIO")
    GPIO = None

from .kano_hat import get_hat, LED_COUNT as HAT_LED_COUNT


# LED strip configuration
LED_COUNT = HAT_LED_COUNT  # Number of LED pixels provided by the Kano hat
# Note: LED hardware is managed by the Kano hat abstraction (kano_hat.py),
# so individual LED strip constants are not needed here.

# Button configuration
# Note: The actual button is on GPIO 3 (managed by kano_hat.py).
# This constant is only used as a dummy channel parameter for button_callback.
BUTTON_PIN = 3  # Dummy channel value for button callback (actual GPIO is in kano_hat.py)

# Breathing animation configuration
BREATHING_MIN_BRIGHTNESS = 5    # Minimum brightness during breathing (0-255)
BREATHING_MAX_BRIGHTNESS = 40   # Maximum brightness during breathing (0-255)
BREATHING_SPEED = 0.015         # Speed of breathing animation (lower = slower)
OK_ROTATION_SPEED = 0.2         # Comet rotation speed (radians per frame)

# Error animation brightness configuration (kept much dimmer than full power)
ERROR_MIN_BRIGHTNESS = 30       # Minimum brightness during error pulses (0-255)
ERROR_MAX_BRIGHTNESS = 120      # Maximum brightness during error pulses (0-255)

# Internet-down animation configuration (glitchy pattern with contrast)
INTERNET_MIN_BRIGHTNESS = 0     # Minimum brightness (can be 0 for black pixels)
INTERNET_MAX_BRIGHTNESS = 100   # Maximum brightness for internet-down wave
INTERNET_WAVE_SPEED = 0.2       # Speed of the internet-down wave animation
INTERNET_WAVE_THRESHOLD = 0.15   # Wave values below this become black (0-1)

# Colors
COLOR_OK = Color(0, 255, 0)        # Green
COLOR_ERROR = Color(255, 0, 0)      # Red
COLOR_OFF = Color(0, 0, 0)          # Off

CONFIG_FILE = "led-monitor-cfg.json"


class ServiceMonitor:
    def __init__(self, config_file: str = CONFIG_FILE, enable_hat: bool = True) -> None:
        """
        Function: __init__

        Tiny description:
          Construct the service monitor and initialise hardware + config.

        Input parameters:
          - config_file: Path to the JSON configuration file to use.

        Output parameters:
          - None. The instance is ready for `monitor_loop()`.

        Longer description:
          Sets up internal state, initialises the Kano hat abstraction
          (LED ring + button) and loads the monitoring configuration from
          disk. Any errors in hat initialisation result in a safe fallback
          to a demo mode without LED or button control.
        """
        self.config_file = config_file
        self.enable_hat = enable_hat
        self.config: dict = {}
        self.last_config_mtime = 0.0
        self.running = Event()
        self.running.set()
        self.alert_active = False
        self.alert_acknowledged = False
        self.breathing_phase = 0.0
        self.ok_phase = 0.0
        # Internet connectivity state and animation phase.
        self.internet_ok: bool = True
        self.internet_phase: float = 0.0
        # Track recent glitch positions and counts (for decreasing probability on repeats)
        self.glitch_counts: dict[int, int] = {}  # LED index -> number of recent glitches
        self.last_glitch_time: float = 0.0

        # Track failing services and which ones have been snoozed via the
        # button so that we only pulse when new failures appear.
        self.failed_services: set[str] = set()
        self.snoozed_failed_services: set[str] = set()
        # Short-lived visual feedback when the button is pressed.
        self.ack_flash_pending: bool = False
        
        # Thread-safe state for service checks running in background
        self.service_statuses_lock = Lock()
        self.service_statuses: dict = {}
        self.check_in_progress = False

        # Initialize Kano hat (LED ring + button) using local abstraction.
        # The abstraction takes care of setting up both the rpi_ws281x strip
        # and the GPIO configuration for the button on BCM 3.
        self.hat = None
        if enable_hat:
            try:
                self.hat = get_hat()
            except Exception as exc:
                # Fall back to demo mode if hardware initialisation fails.
                print(f"Warning: Failed to initialise Kano hat: {exc}")
                self.hat = None

        # For reliability on BCM 3 (which has special hardware behaviour), we
        # poll the button state instead of relying on edge-detection callbacks.
        # This matches the approach used in the standalone button tests.
        if enable_hat and GPIO and self.hat:
            print("Button support enabled (polling mode)")
            self.last_button_state: bool = self.hat.read_button()
            self.last_button_event_time: float = time.time()
        else:
            if not GPIO:
                print("Running without button support (GPIO missing)")
            elif not enable_hat:
                print("Running without hat support (enable_hat=False)")
            else:
                print("Running without button support (hat not available)")
            self.last_button_state = False  # type: ignore[assignment]
            self.last_button_event_time = 0.0  # type: ignore[assignment]

        # Load initial config
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                self.config = json.loads(config_path.read_text())
                self.last_config_mtime = config_path.stat().st_mtime
                print(f"Config loaded: {len(self.config.get('services', []))} services")
            else:
                print(f"Config file not found: {self.config_file}")
                self.create_default_config()
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Error loading config: {exc}")

    def create_default_config(self) -> None:
        """Create a default configuration file."""
        default_config = {
            "check_interval": 30,
            "led_count": 24,
            "services": [
                {
                    "name": "internet",
                    "type": "ping",
                    "target": "8.8.8.8",
                },
                {
                    "name": "pihole",
                    "type": "http",
                    "target": "http://localhost/admin/api.php",
                },
                {
                    "name": "tailscale",
                    "type": "systemd",
                    "target": "tailscaled",
                },
            ],
        }
        try:
            Path(self.config_file).write_text(json.dumps(default_config, indent=2))
            self.config = default_config
            print(f"Created default config at {self.config_file}")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Error creating default config: {exc}")

    def check_config_changes(self) -> bool:
        """Check if config file has been modified and reload if needed."""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                current_mtime = config_path.stat().st_mtime
                if current_mtime > self.last_config_mtime:
                    print("Config file changed, reloading...")
                    self.load_config()
                    return True
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Error checking config: {exc}")
        return False

    def check_ping(self, target: str, timeout: int = 2) -> bool:
        """
        Function: check_ping

        Tiny description:
          Check if a host is reachable using ICMP ping.

        Input parameters:
          - target: Hostname or IP address to ping.
          - timeout: Timeout in seconds for the ping command.

        Output parameters:
          - Boolean. True if the host responds to a single ping, False otherwise.

        Longer description:
          Uses the system `ping` command to send a single ICMP echo request to
          the target host. A successful response (exit code 0) is treated as
          "up". Any non-zero exit code, timeout, or exception is treated as
          "down". This is mainly useful for simple connectivity checks such as
          internet reachability.
        """
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout), target],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout + 1,
            )
            return result.returncode == 0
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Ping check failed for {target}: {exc}")
            return False

    def check_tcp(self, target: str, timeout: int = 5) -> bool:
        """
        Function: check_tcp

        Tiny description:
          Check if a TCP port is accepting connections.

        Input parameters:
          - target: Host and port in the form `host:port` or `tcp://host:port`.
          - timeout: Connection timeout in seconds.

        Output parameters:
          - Boolean. True if a TCP connection can be established, False otherwise.

        Longer description:
          Opens a TCP connection to the specified host and port using
          `socket.create_connection`. This is useful for services such as
          RustDesk that expose a plain TCP listener or a WebSocket endpoint
          where a successful handshake is enough to consider the service "up",
          without having to interpret HTTP status codes.
        """
        host = ""
        port: int | None = None

        try:
            if "://" in target:
                parsed = urlparse(target)
                host = parsed.hostname or ""
                port = parsed.port
            else:
                # Allow "host:port" shorthand.
                if ":" in target:
                    host, port_str = target.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = None

            if not host or port is None:
                print(f"TCP check has invalid target format: {target}")
                return False

            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception as exc:  # pragma: no cover - defensive
            print(f"TCP check failed for {target}: {exc}")
            return False

    def check_internet(self) -> bool:
        """
        Function: check_internet

        Tiny description:
          Check whether this device currently has internet connectivity.

        Input parameters:
          - None. Uses the optional `internet_probe` section from the config.

        Output parameters:
          - Boolean. True if the configured probe succeeds, False otherwise.

        Longer description:
          Reads the optional `internet_probe` block from `led-monitor-cfg.json`
          and runs either a ping or HTTP(S) reachability check against a known
          always-up endpoint (for example, 1.1.1.1). This result is stored in
          `self.internet_ok` and drives a dedicated “internet down” LED
          animation that takes precedence over per-service failure patterns.
          If no `internet_probe` is configured, the function assumes internet is
          OK so existing behaviour is preserved.
        """
        probe = self.config.get("internet_probe")
        if not probe:
            # No explicit probe configured; assume internet is OK.
            self.internet_ok = True
            return True

        probe_type = str(probe.get("type", "ping")).lower()
        target = str(probe.get("target", "")).strip()

        try:
            timeout = int(probe.get("timeout", 3))
        except (TypeError, ValueError):
            timeout = 3

        if not target:
            print("Internet probe is misconfigured: empty target")
            self.internet_ok = False
            return False

        print(f"Checking internet via {probe_type} to {target}...", end=" ")

        if probe_type == "ping":
            is_ok = self.check_ping(target, timeout=timeout)
        elif probe_type == "http":
            # For internet reachability we expect a healthy endpoint, so we
            # use the normal HTTP semantics (2xx/3xx treated as OK).
            is_ok = self.check_http(
                target,
                timeout=timeout,
                verify=True,
                allow_auth_status=False,
            )
        else:
            print(f"Unknown internet probe type: {probe_type}")
            self.internet_ok = False
            return False

        print("✓ OK" if is_ok else "✗ FAILED")
        self.internet_ok = is_ok
        return is_ok

    def check_http(
        self,
        target: str,
        timeout: int = 5,
        verify: bool = True,
        allow_auth_status: bool = False,
    ) -> bool:
        """
        Function: check_http

        Tiny description:
          Perform an HTTP(S) request and decide if the service is "up".

        Input parameters:
          - target: URL to request.
          - timeout: Request timeout in seconds.
          - verify: Whether to verify TLS certificates.
          - allow_auth_status: When True, 401/403 auth responses count as "up".

        Output parameters:
          - Boolean. True if the endpoint is considered healthy, False otherwise.

        Longer description:
          For normal HTTP checks we treat only 2xx and 3xx responses as
          healthy. This ensures that 5xx errors are always treated as "down".
          For some endpoints that always require authentication (e.g. SFTPGo
          with a login page), `allow_auth_status` can be set so that 401/403
          are also considered "up" while still treating 5xx as failures.
        """
        try:
            response = requests.get(target, timeout=timeout, verify=verify)
            status = response.status_code

            # Standard success: any 2xx or 3xx response.
            if 200 <= status < 400:
                return True

            # Optional case: explicit auth-required statuses can be treated as
            # "up but protected" when configured to do so.
            if allow_auth_status and status in (401, 403):
                return True

            # Everything else, including 4xx like 404 and all 5xx, is treated
            # as a failure so that obvious server errors (500, 502, 503, ...)
            # never render as "up".
            return False
        except Exception as exc:  # pragma: no cover - defensive
            print(f"HTTP check failed for {target}: {exc}")
            return False

    def check_systemd(self, service_name: str) -> bool:
        """Check if systemd service is running."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return result.stdout.decode().strip() == "active"
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Systemd check failed for {service_name}: {exc}")
            return False

    def check_service(self, service: dict) -> bool:
        """Check a single service based on its type."""
        service_type = service.get("type", "ping")
        target = service.get("target", "")

        if service_type == "ping":
            return self.check_ping(target)
        if service_type == "tcp":
            return self.check_tcp(target, timeout=5)
        if service_type == "http":
            return self.check_http(target, timeout=5, verify=True)
        if service_type == "http_insecure":
            # Allow endpoints with self‑signed or otherwise invalid TLS
            # certificates, but still honour HTTP status codes so that 5xx
            # (and other obvious errors) are considered "down". Auth‑required
            # codes such as 401/403 are treated as "up but protected".
            return self.check_http(
                target,
                timeout=5,
                verify=False,
                allow_auth_status=True,
            )
        if service_type == "systemd":
            return self.check_systemd(target)

        print(f"Unknown service type: {service_type}")
        return False

    def button_callback(self, channel: int) -> None:
        """Handle button press to acknowledge alerts."""
        print("Button pressed! Acknowledging alert...")
        self.alert_acknowledged = True
        self.alert_active = False
        # Snooze all services that are currently failing so that we only
        # pulse again when a new service goes down.
        self.snoozed_failed_services = set(self.failed_services)
        # Trigger a short, dim acknowledgement flash that is rendered from
        # the main loop so it does not block service checks.
        self.ack_flash_pending = True

    def poll_button(self) -> None:
        """
        Function: poll_button

        Tiny description:
          Poll the hat button and trigger the callback on press events.

        Input parameters:
          - None. Uses internal hat reference and timing state.

        Output parameters:
          - None. May invoke `button_callback` when a press edge is detected.

        Longer description:
          This helper reads the button state using the Kano hat abstraction
          and synthesises a rising-edge event when the state transitions from
          not-pressed to pressed. A simple time-based debounce is applied so
          that very rapid repeats are ignored. Polling avoids the edge-
          detection issues seen on BCM 3 when running under systemd.
        """
        if not GPIO or not self.hat:
            return

        try:
            pressed = self.hat.read_button()
        except Exception:
            return

        now = time.time()
        # Debounce: require at least 0.3s between press events
        min_interval = 0.3

        if pressed and not self.last_button_state:
            if now - self.last_button_event_time >= min_interval:
                self.last_button_event_time = now
                self.button_callback(BUTTON_PIN)

        self.last_button_state = pressed

    def apply_brightness_scale(self, color: int, scale: float) -> int:
        """Scale a color by a brightness factor (0.0 to 1.0)."""
        r = int(((color >> 16) & 0xFF) * scale)
        g = int(((color >> 8) & 0xFF) * scale)
        b = int((color & 0xFF) * scale)
        return Color(r, g, b)

    def get_max_severity(self, service_statuses: dict) -> int:
        """
        Function: get_max_severity

        Tiny description:
          Compute the highest configured severity among failing services.

        Input parameters:
          - service_statuses: Mapping of service name to status dictionaries
                             produced in `monitor_loop()`.

        Output parameters:
          - Integer severity level in the range 0–LED_COUNT. A value of 0
            means there are no failing services.

        Longer description:
          Each service in the JSON configuration can define an optional
          `severity` field indicating how important that service is. This
          helper inspects the current status snapshot and returns the
          maximum severity for services whose `ok` flag is False. The return
          value is clamped to the number of LEDs on the ring so it can be
          used directly when rendering alert patterns.
        """
        if not service_statuses:
            return 0

        try:
            led_total = self.hat.led_count if self.hat else LED_COUNT  # type: ignore[attr-defined]
        except AttributeError:
            led_total = LED_COUNT

        max_severity = 0
        for status in service_statuses.values():
            if status.get("ok"):
                continue
            try:
                severity = int(status.get("severity", 1))
            except (TypeError, ValueError):
                severity = 1
            if severity > max_severity:
                max_severity = severity

        if max_severity <= 0:
            return 0

        return max(1, min(max_severity, led_total))

    def count_failures(self, service_statuses: dict) -> int:
        """
        Function: count_failures

        Tiny description:
          Count how many services are currently failing.

        Input parameters:
          - service_statuses: Mapping of service name to status dictionaries.

        Output parameters:
          - Integer number of services with `ok` set to False.

        Longer description:
          This helper is used purely for LED summary animations so that the
          monitor can briefly indicate how many services are down at the
          start of each check cycle. It ignores services that are missing
          from the snapshot or that do not have an explicit `ok` flag.
        """
        if not service_statuses:
            return 0

        failures = 0
        for status in service_statuses.values():
            if not status.get("ok", False):
                failures += 1
        return failures

    def show_severity_status(self, service_statuses: dict) -> None:
        """
        Function: show_severity_status

        Tiny description:
          Render a static severity bar on the LED ring for current alerts.

        Input parameters:
          - service_statuses: Mapping of service name to status dictionaries.

        Output parameters:
          - None. The LED ring is updated to show severity as a red bar.

        Longer description:
          When one or more services are failing this helper uses
          `get_max_severity()` to determine the highest severity among failing
          services, then lights the whole ring in a static red whose
          brightness encodes that severity. It is used after alerts have been
          snoozed to indicate that something is still down without creating a
          strong sense of urgency.
        """
        if not self.hat:
            return

        severity = self.get_max_severity(service_statuses)
        if severity <= 0:
            return

        try:
            led_total = self.hat.led_count  # type: ignore[attr-defined]
        except AttributeError:
            led_total = LED_COUNT

        sev_norm = max(1, min(severity, 10)) / 10.0
        brightness = int(
            ERROR_MIN_BRIGHTNESS
            + sev_norm * (ERROR_MAX_BRIGHTNESS - ERROR_MIN_BRIGHTNESS)
        )
        color = Color(brightness, 0, 0)

        for idx in range(led_total):
            self.hat.set_led_color(idx, color)

        self.hat.show()

    def failure_animation_step(self, service_statuses: dict) -> None:
        """
        Function: failure_animation_step

        Tiny description:
          Animate per‑service pulses on a red background for failing services.

        Input parameters:
          - service_statuses: Mapping of service name to status dictionaries.

        Output parameters:
          - None. The LED ring is updated with a dim red background and one
            pulsing LED per failing service (up to the ring size).

        Longer description:
          This animation uses a uniform dim red background to indicate that
          something is wrong, and then assigns each failing service to an LED
          slot where it pulses. The pulse **speed** and **intensity** depend
          on the service severity so that more critical failures pulse faster
          and brighter. If there are more failing services than LEDs, they
          share slots, and the brightest pulse wins for that slot.
        """
        if not self.hat:
            return

        failing = [
            (name, status.get("severity", 5))
            for name, status in service_statuses.items()
            if not status.get("ok", False)
        ]
        if not failing:
            return

        try:
            led_total = self.hat.led_count  # type: ignore[attr-defined]
        except AttributeError:
            led_total = LED_COUNT

        # Base brightness for any failure state
        base_brightness = ERROR_MIN_BRIGHTNESS

        # Separate unsnoozed (active alerts) and snoozed failures.
        unsnoozed = [
            (name, sev)
            for name, sev in failing
            if name not in self.snoozed_failed_services
        ]
        snoozed = [
            (name, sev)
            for name, sev in failing
            if name in self.snoozed_failed_services
        ]

        # Start with a dim red background on all LEDs so that any failure state
        # is clearly visible even where no individual service is mapped.
        led_r = [base_brightness for _ in range(led_total)]
        led_g = [0 for _ in range(led_total)]
        led_b = [0 for _ in range(led_total)]

        # Static representation for snoozed failures: deep purple → blue by severity.
        for idx, (_, severity) in enumerate(snoozed):
            led_index = idx % led_total
            try:
                sev = max(1, min(int(severity), 10))
            except (TypeError, ValueError):
                sev = 5
            t = (sev - 1) / 9.0  # 0..1
            # Low severity: darker purple; high severity: brighter blue.
            r = int(40 * (1.0 - t))
            g = 0
            b = int(80 + 80 * t)
            # Static snoozed representation overrides the red background at
            # this LED so that the purple/blue hue is clearly visible.
            led_r[led_index] = r
            led_g[led_index] = g
            led_b[led_index] = b

        # Pulsing representation for unsnoozed failures: orange pulses.
        now = time.time()
        for idx, (_, severity) in enumerate(unsnoozed):
            led_index = idx % led_total

            try:
                sev = max(1, min(int(severity), 10))
            except (TypeError, ValueError):
                sev = 5
            sev_norm = sev / 10.0

            # Pulse frequency (Hz) – more severe → faster.
            freq = 0.4 + 1.2 * sev_norm  # between ~0.4 and 1.6 Hz
            phase = now * freq * 2 * math.pi
            wave = (math.sin(phase) + 1.0) / 2.0  # 0..1

            # Pulse amplitude – more severe → bigger amplitude.
            amplitude = (ERROR_MAX_BRIGHTNESS - base_brightness) * (0.4 + 0.6 * sev_norm)
            pulse_brightness = base_brightness + wave * amplitude

            red_component = int(pulse_brightness)
            green_component = int(pulse_brightness * 0.4)

            # Pulses override any static colour on that LED so that new/unsnoozed
            # alerts are always clearly visible.
            led_r[led_index] = red_component
            led_g[led_index] = green_component
            led_b[led_index] = 0

        for idx in range(led_total):
            self.hat.set_led_color(
                idx,
                Color(int(led_r[idx]), int(led_g[idx]), int(led_b[idx])),
            )

        self.hat.show()

    def breathing_animation_step(self, service_statuses: dict) -> None:
        """
        Function: breathing_animation_step

        Tiny description:
          Animate an all‑OK state using a slow rotating green comet.

        Input parameters:
          - service_statuses: Mapping of service name to status dictionaries.

        Output parameters:
          - None. The LED ring shows a subtle moving green effect.

        Longer description:
          When all services are healthy this animation shows a single "comet"
          of green light circling the ring with a short tail. The comet
          brightness breathes gently over time while the head moves slowly
          around the ring, making the idle state less static without being
          visually noisy.
        """
        if not self.hat or not service_statuses:
            return

        # If anything is down, we do not animate the OK state.
        if any(not status.get("ok", False) for status in service_statuses.values()):
            return

        try:
            led_total = self.hat.led_count  # type: ignore[attr-defined]
        except AttributeError:
            led_total = LED_COUNT

        # Advance comet head position smoothly based on an internal phase so
        # that the motion is independent of timer jitter.
        self.ok_phase += OK_ROTATION_SPEED
        if self.ok_phase >= 2 * math.pi:
            self.ok_phase -= 2 * math.pi
        head_index = int((self.ok_phase / (2 * math.pi)) * led_total) % led_total

        # Breathing component for overall intensity (shared across the wave).
        self.breathing_phase += BREATHING_SPEED
        if self.breathing_phase >= 2 * math.pi:
            self.breathing_phase = 0

        sine_value = math.sin(self.breathing_phase)
        brightness_range = BREATHING_MAX_BRIGHTNESS - BREATHING_MIN_BRIGHTNESS
        base_brightness = BREATHING_MIN_BRIGHTNESS + (sine_value + 1) / 2 * brightness_range

        # Wave pattern: most LEDs lit all the time, but with a moving brightness
        # peak around the ring so it feels like a slow travelling wave.
        for idx in range(led_total):
            # Phase offset around the ring to create a travelling sine wave.
            pos_phase = self.ok_phase + (2 * math.pi * idx / led_total)
            wave = (math.sin(pos_phase) + 1.0) / 2.0  # 0..1

            # Mix global breathing and local wave to keep everything gentle.
            led_brightness = base_brightness * (0.4 + 0.6 * wave)
            scale = max(0.0, min(1.0, led_brightness / 255.0))
            self.hat.set_led_color(idx, self.apply_brightness_scale(COLOR_OK, scale))

        self.hat.show()

    def internet_down_animation_step(self) -> None:
        """
        Function: internet_down_animation_step

        Tiny description:
          Animate a distinct, glitchy pattern with high contrast when internet is down.

        Input parameters:
          - None. Uses internal `internet_phase` state and hat LED count.

        Output parameters:
          - None. Updates the LED ring to show a colorful "glitch" effect.

        Longer description:
          When the dedicated internet probe fails, this animation replaces the
          normal all‑OK or per‑service failure patterns. It renders a shorter
          blue/cyan wave with black gaps (high contrast) that moves around the
          ring, and overlays frequent colorful "glitch" sparkles in vibrant
          cyan, magenta, purple, pink, and teal tones on random LEDs. Glitch
          colors vary in intensity and are chosen from an expanded palette to
          create a playful, varied effect that clearly indicates connectivity
          issues without being aggressive.
        """
        if not self.hat:
            return

        try:
            led_total = self.hat.led_count  # type: ignore[attr-defined]
        except AttributeError:
            led_total = LED_COUNT

        # Advance phase slowly for a calm background motion.
        self.internet_phase += INTERNET_WAVE_SPEED
        if self.internet_phase >= 2 * math.pi:
            self.internet_phase -= 2 * math.pi

        # Clear old glitch counts periodically (every ~2 seconds of animation)
        # This allows glitches to eventually appear in previously used areas
        current_time = time.time()
        if current_time - self.last_glitch_time > 2.0:
            self.glitch_counts.clear()

        # Determine if we should allow glitches this frame (cooldown to prevent constant glitching)
        min_glitch_interval = 0.08  # Minimum seconds between glitch bursts (reduced for more frequency)
        allow_glitches = (current_time - self.last_glitch_time) >= min_glitch_interval

        # Minimum distance between glitches (in LED indices) - reduced to 1
        min_glitch_distance = 1

        for idx in range(led_total):
            phase = self.internet_phase + (2 * math.pi * idx / led_total)
            wave = (math.sin(phase) + 1.0) / 2.0  # 0..1

            # Apply threshold to create shorter wave with black pixels
            if wave < INTERNET_WAVE_THRESHOLD:
                # Below threshold: completely black
                base_brightness = 0
            else:
                # Above threshold: remap to full brightness range for more contrast
                remapped_wave = (wave - INTERNET_WAVE_THRESHOLD) / (1.0 - INTERNET_WAVE_THRESHOLD)
                base_brightness = INTERNET_MIN_BRIGHTNESS + remapped_wave * (
                    INTERNET_MAX_BRIGHTNESS - INTERNET_MIN_BRIGHTNESS
                )

            # Base colour: dark blue/cyan blend, no red (only if wave is above threshold)
            if base_brightness > 0:
                r = 0
                g = int(base_brightness * 0.25)
                b = int(base_brightness * 0.9)
            else:
                r = g = b = 0

            # More frequent glitches with decreasing probability on repeats
            # Base probability is higher, but decreases if LED has glitched recently
            base_glitch_prob = 0.18  # Increased base probability for more frequency
            
            if allow_glitches:
                # Get how many times this LED has glitched recently
                glitch_count = self.glitch_counts.get(idx, 0)
                
                # Reduce probability based on repeat count (exponential decay)
                # 1st glitch: 100% of base prob, 2nd: 50%, 3rd: 25%, 4th: 12.5%, etc.
                repeat_penalty = 0.5 ** glitch_count
                adjusted_prob = base_glitch_prob * repeat_penalty
                
                # Check minimum distance from recent glitches (only if distance > 0)
                too_close = False
                if min_glitch_distance > 0:
                    for glitch_idx, count in self.glitch_counts.items():
                        if count > 0:  # Only check LEDs that have glitched
                            # Calculate circular distance (accounting for ring wrap-around)
                            dist = min(
                                abs(idx - glitch_idx),
                                abs(idx - glitch_idx + led_total),
                                abs(idx - glitch_idx - led_total)
                            )
                            if dist < min_glitch_distance:
                                too_close = True
                                break

                if not too_close and random.random() < adjusted_prob:
                    # Expanded colorful palette with more variety
                    palette = [
                        # Bright cyan
                        (0, 180, 255),
                        # Electric magenta
                        (255, 0, 200),
                        # Purple
                        (150, 0, 255),
                        # Bright blue
                        (0, 100, 255),
                        # Teal
                        (0, 255, 200),
                        # Pink
                        (255, 100, 200),
                        # Violet
                        (200, 0, 255),
                        # Aqua
                        (0, 255, 150),
                    ]
                    gr, gg, gb = random.choice(palette)
                    
                    # Vary the intensity of glitches (some brighter, some dimmer)
                    intensity = random.uniform(0.5, 1.0)
                    r = int(gr * intensity)
                    g = int(gg * intensity)
                    b = int(gb * intensity)
                    
                    # Cap brightness to avoid being too aggressive
                    r = min(r, 180)
                    g = min(g, 180)
                    b = min(b, 200)

                    # Track this glitch (increment count) and update timing
                    self.glitch_counts[idx] = glitch_count + 1
                    self.last_glitch_time = current_time

            self.hat.set_led_color(idx, Color(r, g, b))

        self.hat.show()

    def set_led(self, position: int, color: int) -> None:
        """Set a specific LED to a color."""
        if self.hat:
            self.hat.set_led_color(position, color)

    def clear_leds(self) -> None:
        """Turn off all LEDs."""
        if self.hat:
            self.hat.set_all_leds_color(COLOR_OFF)

    def update_display(self, service_statuses: dict) -> None:
        """Update LED display based on service statuses."""
        if not self.hat:
            return

        all_ok = all(status["ok"] for status in service_statuses.values())

        if all_ok:
            # All services OK - use breathing animation
            self.alert_active = False
            self.alert_acknowledged = False
            self.failed_services.clear()
            self.snoozed_failed_services.clear()
            # Breathing animation is handled in the monitor loop
        else:
            # Some services failed; details are handled in `monitor_loop`
            # where we track new failures and snoozed state.
            if not self.alert_active:
                self.alert_active = True

    def _check_services_background(self) -> None:
        """
        Function: _check_services_background

        Tiny description:
          Run service checks in a background thread without blocking animations.

        Input parameters:
          - None. Uses self.config and self methods.

        Output parameters:
          - None. Updates self.service_statuses and related state via locks.

        Longer description:
          This method runs in a separate thread to perform all service checks
          (including internet connectivity) without blocking the main animation
          loop. It updates service_statuses in a thread-safe manner and handles
          state transitions for failed services and snooze logic.
        """
        try:
            # Check internet connectivity first, if configured.
            self.check_internet()

            services = self.config.get("services", [])
            if not services:
                return

            new_service_statuses = {}
            print(f"\n--- Checking {len(services)} services ---")

            for service in services:
                name = service.get("name", "unknown")
                try:
                    severity = int(service.get("severity", 5))
                except (TypeError, ValueError):
                    severity = 5

                print(f"Checking {name}...", end=" ")
                is_ok = self.check_service(service)

                new_service_statuses[name] = {
                    "ok": is_ok,
                    "severity": severity,
                }

                status_str = "✓ OK" if is_ok else "✗ FAILED"
                print(status_str)

            # Update service_statuses in a thread-safe manner
            with self.service_statuses_lock:
                self.service_statuses = new_service_statuses

            # Update display state (resets flags when everything is OK)
            self.update_display(new_service_statuses)

            # Track failing services and detect new failures so that we
            # only pulse when a new service goes down.
            current_failed = {
                name
                for name, status in new_service_statuses.items()
                if not status.get("ok", False)
            }
            print(f"Failed services this cycle: {sorted(current_failed)}")
            print(
                f"Snoozed failed services: "
                f"{sorted(self.snoozed_failed_services)}"
            )
            new_failures = current_failed - self.failed_services
            self.failed_services = current_failed

            if not current_failed:
                # All services recovered; clear snooze state.
                self.snoozed_failed_services.clear()
            elif new_failures:
                # At least one new service failed; re‑enable pulsing.
                self.alert_active = True
                self.alert_acknowledged = False
                # Do not clear snoozed_failed_services here so that
                # already‑snoozed failures stay snoozed; only the new
                # ones will cause pulsing.

        except Exception as exc:
            print(f"Error in background service check: {exc}")
        finally:
            self.check_in_progress = False

    def monitor_loop(self) -> None:
        """Main monitoring loop."""
        print("Starting service monitor...")

        # Initialize to trigger first check immediately
        last_check_time = 0.0

        while self.running.is_set():
            try:
                # Check for config changes
                self.check_config_changes()

                # Get services from config
                services = self.config.get("services", [])
                check_interval = self.config.get("check_interval", 30)

                current_time = time.time()

                # Start background service check at specified interval (non-blocking)
                if current_time - last_check_time >= check_interval:
                    if not services:
                        print("No services configured")
                        last_check_time = current_time
                        time.sleep(1)
                        continue

                    # Start background thread for service checks if not already running
                    if not self.check_in_progress:
                        self.check_in_progress = True
                        check_thread = Thread(target=self._check_services_background, daemon=True)
                        check_thread.start()
                        last_check_time = current_time

                # Get current service statuses in a thread-safe manner
                with self.service_statuses_lock:
                    service_statuses = self.service_statuses.copy()

                # Continuous animation based on current state (never blocks on checks)
                if service_statuses:
                    # Poll button state on every iteration so that the snooze
                    # behaviour is responsive even while animations are running.
                    self.poll_button()

                    # One-frame acknowledgement flash when the button was just
                    # pressed: very dim neutral white on the whole ring.
                    if self.ack_flash_pending and self.hat:
                        try:
                            led_total = self.hat.led_count  # type: ignore[attr-defined]
                        except AttributeError:
                            led_total = LED_COUNT
                        ack_color = Color(20, 20, 20)
                        for idx in range(led_total):
                            self.hat.set_led_color(idx, ack_color)
                        self.hat.show()
                        self.ack_flash_pending = False
                        time.sleep(0.05)
                        continue

                    # If internet is down (according to the dedicated probe),
                    # show a distinct teal/blue wave that overrides other
                    # patterns so the cause is unambiguous.
                    if not self.internet_ok:
                        self.internet_down_animation_step()
                        time.sleep(0.05)
                    else:
                        all_ok = all(status["ok"] for status in service_statuses.values())

                        if all_ok:
                            # All OK - continuous breathing animation (green-only wave)
                            self.breathing_animation_step(service_statuses)
                            time.sleep(0.05)  # Smooth animation
                        else:
                            # Some services failed - render per-service snoozed vs
                            # unsnoozed state using the failure animation helper.
                            self.failure_animation_step(service_statuses)
                            time.sleep(0.05)
                else:
                    self.poll_button()
                    time.sleep(1)

            except Exception as exc:  # pragma: no cover - defensive
                print(f"Error in monitor loop: {exc}")
                time.sleep(5)

    def shutdown(self) -> None:
        """Clean shutdown."""
        print("\nShutting down...")
        self.running.clear()
        self.clear_leds()

        if self.hat:
            # Show a brief shutdown animation in dim blue around the ring.
            try:
                led_total = self.hat.led_count  # type: ignore[attr-defined]
            except AttributeError:
                led_total = LED_COUNT

            for idx in range(led_total):
                self.hat.set_led_color(idx, Color(0, 0, 50))  # type: ignore[call-arg]
                self.hat.show()
                time.sleep(0.05)

            self.clear_leds()
            self.hat.shutdown()

        if GPIO:
            GPIO.cleanup()
            print("GPIO cleaned up")


def signal_handler(signum, frame) -> None:
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}")
    if hasattr(signal_handler, "monitor"):
        signal_handler.monitor.shutdown()
    sys.exit(0)


def main() -> None:
    """Entry point for the service monitor CLI."""
    monitor = ServiceMonitor()
    signal_handler.monitor = monitor  # type: ignore[attr-defined]
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        monitor.monitor_loop()
    except KeyboardInterrupt:
        monitor.shutdown()


if __name__ == "__main__":
    main()


