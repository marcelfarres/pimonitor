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

## Wiring

### LED Ring

```text
LED Ring VCC  →  Pi Pin 2 (5V)
LED Ring GND  →  Pi Pin 6 (GND)
LED Ring DIN  →  Pi Pin 12 (GPIO 18) [via 470Ω resistor]
```

### Button (Optional)

```text
Button Pin 1  →  Pi Pin 11 (GPIO 17)
Button Pin 2  →  Pi Pin 9 (GND)
```

**Note:** GPIO 18 is required (needs PWM support). The button uses an internal pull-up resistor, so wiring is pretty simple.

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

### Severity (Optional)

You can add a `severity` field (1–10) to each service:

- `1` = not a big deal (just a few LEDs light up when it fails)
- `10` = everything is on fire (the whole ring lights up red)

When services go down, it uses the **highest** severity to decide how dramatic the alert should be. So if your NAS (`severity: 10`) goes down, the whole ring lights up red. But if some random service (`severity: 3`) fails, only a small section lights up. Pretty handy for prioritizing what to panic about! 😅

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

On the Kano hat the power button is pre‑wired to **BCM GPIO 3** and is
handled by the `kano_hat.py` helper. If you connect an external button
instead of using the hat button, edit `kano_hat.py`:

```python
BUTTON_PIN = 3  # Change to your GPIO number when not using the hat button
```

### Adjusting LED Count

The Kano hat uses a fixed **10‑LED ring** on GPIO 18. If you connect a
different NeoPixel ring, update both the helper and the config:

**kano_hat.py:**

```python
LED_COUNT = 10  # Change to match your ring size
```

**led-monitor-cfg.json:**

```json
{
  "led_count": 10  // Match your ring
}
```

## How It Works

### What the LEDs Mean

- 🟢 **Green breathing** = Everything's fine, go back to sleep
- 🔴 **Red pulsing** = Something's broken! (and it wants your attention)
- 🔴 **Red static** = Something's still broken, but you've acknowledged it
- 🔵 **Blue flash** = You pressed the button (nice!)

### Button Behavior

1. Service breaks → Red pulsing starts (annoying, right?)
2. Press the button → Pulsing stops, quick blue flash to confirm
3. Red LED stays on (so you know something's still down, but it's not nagging you)
4. Everything recovers → Back to the peaceful green breathing animation

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
{"name": "internet", "type": "ping", "target": "1.1.1.1"}
```

### Pi-hole Web Interface

```json
{"name": "pihole", "type": "http", "target": "http://localhost/admin/api.php"}
```

### Pi-hole Service

```json
{"name": "pihole", "type": "systemd", "target": "pihole-FTL"}
```

### Tailscale

```json
{"name": "tailscale", "type": "systemd", "target": "tailscaled"}
```

### Docker

```json
{"name": "docker", "type": "systemd", "target": "docker"}
```

### Custom Web Service

```json
{"name": "my_app", "type": "http", "target": "http://localhost:8080/health"}
```

## Troubleshooting

### LEDs Don't Light Up

1. Double-check your wiring (GPIO 18 to DIN, don't forget the 470Ω resistor!)
2. Make sure LED_COUNT matches your actual ring size
3. Try running with sudo: `sudo python3 led-monitor.py`
4. Check your power supply (needs 5V with enough amperage)

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

1. Verify wiring (GPIO 17 to button, button to GND)
2. Check GPIO pin matches your hardware
3. Test with: `sudo python3 test_button.py`
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

```bash
# Stop service
sudo systemctl stop led-monitor.service

# Update files (if using git)
git pull

# Restart
sudo systemctl start led-monitor.service
```

## Files

- **pimonitor/** - Python package with main monitor code
- **led-monitor.py** - Thin wrapper to run `pimonitor.monitor.main()`
- **led-monitor-cfg.json.example** - Example service configuration (copy to `led-monitor-cfg.json`)
- **led-monitor.service.example** - Example systemd service file (copy and edit paths)
- **led-monitor-web.service.example** - Example web status service file
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
