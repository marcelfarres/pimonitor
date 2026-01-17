# LED Ring Service Monitor

A fun little project to monitor your self-hosted services (Pi-hole, Tailscale, etc.) with visual LED ring indicators on Raspberry Pi. Started as a one-evening project for fun and grew from there! 🎉

## About

This started as a simple way to monitor Pi-hole at home, but turned into a pretty useful service monitoring tool. It works with the **Kano Computer Kit** hardware (originally from [Adafruit](https://www.adafruit.com/product/3257)) - basically a Raspberry Pi hat with a programmable LED ring and button. Now you can see at a glance if all your services are running, without checking logs or dashboards.

## Features

- 🟢 **Breathing animation** when everything's OK (gentle pulsing green - very zen)
- 🔴 **Red pulsing alert** when something breaks (hard to miss!)
- 🔘 **Button to snooze** alerts (press it to stop the pulsing, but keep the status visible)
- ⚙️ **Multiple service types**: ping, HTTP endpoints, systemd services, TCP ports
- 🔄 **Live config reload** - just edit the config file, no restart needed
- ⚡ **Fast setup** with UV (way faster than pip)

## What You'll Need

- Raspberry Pi 3 (or any Pi with GPIO)
- **Kano Computer Kit hat** (has a 10-LED ring and button built in) - originally from [Adafruit Product #3257](https://www.adafruit.com/product/3257)
- OR a standalone WS2812B LED ring (12, 16, 24, or 60 LEDs work fine)
- Push button (optional - for snoozing alerts, but the Kano hat already has one)
- 470Ω resistor (only if you're using a standalone LED ring)
- 5V power supply (2-3A should be plenty for LED rings)

## Setup

### Using the Kano Hat (Easiest!)

If you have the **Kano Computer Kit hat**, it's super simple:

1. Just plug it directly onto the Raspberry Pi GPIO header
2. That's it! No wiring needed - the hat handles everything (LEDs on GPIO 18, button on GPIO 3)

The hat is designed to be plug-and-play, so you can skip all the wiring instructions below.

### Using a Standalone LED Ring (Manual Wiring)

If you're using a standalone WS2812B LED ring instead of the Kano hat, you'll need to wire it up manually:

**LED Ring Wiring:**

```text
LED Ring VCC  →  Pi Pin 2 (5V)
LED Ring GND  →  Pi Pin 6 (GND)
LED Ring DIN  →  Pi Pin 12 (GPIO 18) [via 470Ω resistor]
```

**Button Wiring (Optional):**

```text
Button Pin 1  →  Pi Pin 11 (GPIO 17)
Button Pin 2  →  Pi Pin 9 (GND)
```

**Note:** GPIO 18 is required (needs PWM support). If using an external button, it uses an internal pull-up resistor, so wiring is pretty simple.

## Installation

### 1. Install Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install system packages
sudo apt-get install -y python3 python3-dev curl

# Install UV package manager (fast and reliable)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Install Python packages
uv pip install --system -r requirements.txt
```

### 2. Configure Services

Copy the example configuration file and edit it to match your setup:

```bash
cp led-monitor-cfg.json.example led-monitor-cfg.json
nano led-monitor-cfg.json
```

```json
{
  "check_interval": 30,
  "led_count": 24,
  "services": [
    { "name": "internet", "type": "ping", "target": "8.8.8.8" },
    { "name": "pihole", "type": "systemd", "target": "pihole-FTL" },
    { "name": "tailscale", "type": "systemd", "target": "tailscaled" }
  ]
}
```

**Service Types:**

- `ping` - Check network connectivity (e.g., "8.8.8.8", "192.168.1.1")
- `http` - Check web endpoints with TLS verification (e.g., "<http://localhost/admin/api.php>")
- `http_insecure` - Check web endpoints without TLS verification (for self-signed certs)
- `tcp` - Check TCP port connectivity (e.g., "host:port" or "tcp://host:port")
- `systemd` - Check systemd services (e.g., "pihole-FTL", "tailscaled")

### Service Categorization

For better organization, you can categorize services in comments using prefixes:

- `[Service]` - HTTP/HTTPS services running on specific ports (web applications, APIs, etc.)
- `[NAS]` - Network Attached Storage devices (TrueNAS, Synology, etc.) - use `http` or `http_insecure` to check web management interface
- `[Router]` - Network routers/firewalls - use `http_insecure` for web interfaces or `ping` for basic connectivity
- `[Tailnet Machine]` - Physical computers in Tailscale network - use `ping` for basic connectivity or `tcp` for specific ports (SSH, RDP, etc.)

**Example with categorization:**

```json
{
  "name": "jellyfin",
  "type": "http",
  "target": "http://server:8096/",
  "severity": 8,
  "comment": "[Service] Jellyfin - Media server"
},
{
  "name": "truenas",
  "type": "http",
  "target": "http://truenas.local/ui/dashboard",
  "severity": 10,
  "comment": "[NAS] TrueNAS Scale - Main storage system"
},
{
  "name": "pfsense",
  "type": "http_insecure",
  "target": "https://192.168.1.1/",
  "severity": 10,
  "comment": "[Router] pfSense - Firewall/router web interface"
},
{
  "name": "lab-windows",
  "type": "ping",
  "target": "lab-w.example.ts.net",
  "severity": 5,
  "comment": "[Tailnet Machine] Lab Windows PC - Tailscale network"
}
```

### Severity (Optional)

You can add a `severity` field (1–10) to each service:

- `1-3` = Low severity → **Yellow** pulsing LED
- `4-7` = Medium severity → **Orange** pulsing LED  
- `8-10` = High severity → **Red** pulsing LED

Each failing service gets its own LED with a color that matches its severity level. Higher severity services pulse faster and brighter to draw more attention. When you acknowledge a failure (press the button), that service's LED changes to a static purple/blue color, but new failures will use different LEDs so you can see all issues at once. Pretty handy for prioritizing what to panic about! 😅

### 3. Test

```bash
# Test LED ring hardware
sudo python3 tests/led-ring-test.py

# Test the monitor (Ctrl+C to stop)
sudo python3 led-monitor.py
```

### 4. Install as Service

```bash
# Copy and edit service file (update paths to match your installation)
cp led-monitor.service.example led-monitor.service
nano led-monitor.service  # Update WorkingDirectory and ExecStart paths

# Copy service file to systemd
sudo cp led-monitor.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable led-monitor.service
sudo systemctl start led-monitor.service

# Check status
sudo systemctl status led-monitor.service
```

## Configuration

### Customizing the Breathing Animation

Want to tweak how it looks? Edit `pimonitor/monitor.py`:

```python
BREATHING_MIN_BRIGHTNESS = 30   # Minimum brightness (0-255)
BREATHING_MAX_BRIGHTNESS = 120  # Maximum brightness (0-255)
BREATHING_SPEED = 0.02          # Animation speed (lower = slower)
```

**Some presets I've tried:**

- Subtle (for nighttime): `MIN=40, MAX=100, SPEED=0.01`
- Strong (bright room): `MIN=20, MAX=200, SPEED=0.05`
- Slow (very zen): `MIN=30, MAX=120, SPEED=0.008`

### Changing Button GPIO

If you're using the **Kano hat**, the button is already wired to **BCM GPIO 3** - no changes needed!

If you're using a **standalone button** instead, edit `pimonitor/kano_hat.py`:

```python
BUTTON_PIN = 3  # Change to your GPIO number when not using the hat button
```

### Adjusting LED Count

**If using the Kano hat:** It has a fixed **10-LED ring** - no changes needed!

**If using a standalone LED ring:** Update both files to match your ring size:

**pimonitor/kano_hat.py:**

```python
LED_COUNT = 10  # Change to match your ring size (12, 16, 24, 60, etc.)
```

**led-monitor-cfg.json:**

```json
{
  "led_count": 10  // Match your ring size
}
```

## How It Works

### What the LEDs Mean

- 🟢 **Green breathing** = Everything's fine, go back to sleep
- 🟡 **Yellow pulsing** = Low severity service down (severity 1-3)
- 🟠 **Orange pulsing** = Medium severity service down (severity 4-7)
- 🔴 **Red pulsing** = High severity service down (severity 8-10)
- 🟣 **Purple/Blue static** = Service is down but acknowledged (snoozed)
- 🔵 **Blue flash** = You pressed the button (acknowledgement confirmed)
- 🔴 **Red background** = Dim red on all LEDs indicates failure state

**Severity Colors:**

- Each failing service gets its own LED with a color based on severity
- Yellow (1-3): Less critical issues
- Orange (4-7): Moderate importance
- Red (8-10): Critical services
- Colors pulse to draw attention, with higher severity pulsing faster and brighter

### Button Behavior

1. Service breaks → Colored pulsing starts (yellow/orange/red based on severity)
2. Press the button → Pulsing stops for that service, quick dim flash to confirm
3. Service LED changes to static purple/blue (acknowledged but still down)
4. **New failures** get their own LEDs and pulse (won't override acknowledged ones)
5. Everything recovers → Back to the peaceful green breathing animation

### Managing the Service

```bash
# View logs
sudo journalctl -u led-monitor.service -f

# Restart service
sudo systemctl restart led-monitor.service

# Stop service
sudo systemctl stop led-monitor.service

# Check status
sudo systemctl status led-monitor.service
```

### Updating Config

Super easy - just edit the config file and save. Changes apply automatically, no restart needed:

```bash
nano led-monitor-cfg.json
# Save and exit - that's it!
```

## Monitoring Examples

### Internet Connectivity

```json
{"name": "internet", "type": "ping", "target": "8.8.8.8", "severity": 5, "comment": "Internet connectivity check"}
```

### HTTP Services (Web Applications)

```json
{"name": "webapp", "type": "http", "target": "http://localhost:8080/health", "severity": 5, "comment": "[Service] Web Application - Health check endpoint"}
{"name": "api", "type": "http", "target": "http://api.example.com/v1/status", "severity": 7, "comment": "[Service] API Server - Status endpoint"}
{"name": "dashboard", "type": "http", "target": "http://dashboard.example.com/", "severity": 3, "comment": "[Service] Dashboard - Web interface"}
```

### Systemd Services

```json
{"name": "webserver", "type": "systemd", "target": "nginx", "severity": 8, "comment": "Nginx web server"}
{"name": "database", "type": "systemd", "target": "postgresql", "severity": 10, "comment": "PostgreSQL database"}
{"name": "vpn", "type": "systemd", "target": "vpn-service", "severity": 7, "comment": "VPN service"}
```

### NAS Devices

```json
{"name": "nas-main", "type": "http", "target": "http://nas.local/ui/dashboard", "severity": 10, "comment": "[NAS] Main NAS - Storage system web interface"}
{"name": "nas-backup", "type": "http_insecure", "target": "https://192.168.1.100:5001/", "severity": 10, "comment": "[NAS] Backup NAS - Offsite storage with self-signed cert"}
```

### Routers and Firewalls

```json
{"name": "firewall", "type": "http_insecure", "target": "https://192.168.1.1/", "severity": 10, "comment": "[Router] Firewall - Router web interface with self-signed cert"}
{"name": "router", "type": "ping", "target": "router.example.ts.net", "severity": 10, "comment": "[Router] Router - Network connectivity check"}
```

### Tailnet Machines (Physical Computers)

```json
{"name": "workstation-01", "type": "ping", "target": "workstation-01.example.ts.net", "severity": 5, "comment": "[Tailnet Machine] Workstation 01 - Tailscale network connectivity"}
{"name": "server-02", "type": "tcp", "target": "server-02.example.ts.net:22", "severity": 7, "comment": "[Tailnet Machine] Server 02 - SSH access (port 22)"}
```

### TCP Port Checks

```json
{"name": "ssh", "type": "tcp", "target": "server.example.com:22", "severity": 4, "comment": "[Service] SSH - Secure shell access"}
{"name": "database", "type": "tcp", "target": "db.example.com:5432", "severity": 10, "comment": "[Service] PostgreSQL - Database connection (port 5432)"}
```

### Services with Self-Signed Certificates

```json
{"name": "internal-service", "type": "http_insecure", "target": "https://internal.example.com:8443/", "severity": 8, "comment": "[Service] Internal Service - Web UI with self-signed certificate"}
```

## Troubleshooting

### LEDs Don't Light Up

**If using the Kano hat:**

1. Make sure the hat is fully seated on the GPIO header
2. Try running with sudo: `sudo python3 led-monitor.py`
3. Check that the Pi has enough power (use a good quality power supply)

**If using a standalone LED ring:**

1. Double-check your wiring (GPIO 18 to DIN, don't forget the 470Ω resistor!)
2. Make sure LED_COUNT matches your actual ring size
3. Try running with sudo: `sudo python3 led-monitor.py`
4. Check your power supply (needs 5V with enough amperage - LED rings can be power-hungry)

### Service Won't Start

```bash
# Check logs
sudo journalctl -u led-monitor.service -n 50

# Test manually
sudo python3 led-monitor.py

# Verify packages
uv pip list | grep -E "rpi-ws281x|requests|RPi"

# Reinstall if needed
uv pip install --system --force-reinstall rpi_ws281x requests RPi.GPIO
```

### Button Not Working

**If using the Kano hat:**

1. Make sure the hat is fully seated on the GPIO header
2. The button should work automatically (it's on GPIO 3)
3. Test with: `sudo python3 tests/test-button-detailed.py`
4. Check logs for "Button pressed!" message

**If using a standalone button:**

1. Verify wiring (GPIO pin to button, button to GND)
2. Check GPIO pin matches your hardware (default is GPIO 3 in kano_hat.py)
3. Test with: `sudo python3 tests/test-button-detailed.py`
4. Check logs for "Button pressed!" message

### Pi-hole Check Fails

Try systemd instead of HTTP:

```json
{"name": "pihole", "type": "systemd", "target": "pihole-FTL"}
```

Find correct service name:

```bash
systemctl list-units | grep -i pihole
```

### False Errors

- Some services are just slow - increase the timeout if needed
- Double-check service names: `systemctl list-units | grep <service>`
- Make sure your network is actually working for HTTP/ping checks

## Updating

### Update Packages

```bash
uv pip install --system --upgrade rpi_ws281x requests RPi.GPIO
sudo systemctl restart led-monitor.service
```

### Update Script

The easiest way to update and redeploy is using the helper script:

```bash
# Update code (if using git)
git pull

# Redeploy and restart the service
./redeploy-led-monitor.sh
```

This script will:

- Copy the latest service file to systemd
- Reload systemd daemon
- Restart the service
- Show you the service status

## Files

- **pimonitor/** - Python package with main monitor code
- **led-monitor.py** - Thin wrapper to run `pimonitor.monitor.main()`
- **led-monitor-cfg.json.example** - Example service configuration (copy to `led-monitor-cfg.json`)
- **led-monitor.service.example** - Example systemd service file (copy and edit paths)
- **led-monitor-web.service.example** - Example web status service file
- **redeploy-led-monitor.sh** - Helper script to redeploy and restart the service
- **requirements.txt** - Python dependencies
- **tests/led-ring-test.py** - LED hardware test
- **tests/test-monitor.py** - Complete system test

## Technical Details

### GPIO Pins Used

- GPIO 18 (Pin 12) - LED data (PWM required)
- GPIO 3  (Pin 5)  - Kano hat power button (via `kano_hat.py`)

### Python Dependencies

- `rpi_ws281x` - WS2812B LED control
- `requests` - HTTP endpoint checking
- `RPi.GPIO` - Button input handling

### Performance

- Check interval: configurable (default 30s, but you can change it)
- Breathing animation: updates every 50ms (smooth!)
- CPU usage: barely anything (<1% on a Pi 3)
- Memory: tiny (~20MB)

## License

Free to use and modify however you want. It's a fun project, go wild! 🎉

---

**Having issues?** Try the test scripts or check the logs:

```bash
sudo python3 led-ring-test.py      # Test LED hardware
sudo python3 test-monitor.py       # Test complete system
sudo journalctl -u led-monitor.service -f  # View live logs
```
