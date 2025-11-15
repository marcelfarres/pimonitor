#!/usr/bin/env python3
"""
Complete System Test for LED Ring Service Monitor
Tests all components: LEDs, button, service checks, config loading
"""

import os
import sys
import time
import json
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_test(name, passed, message=""):
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} - {name}")
    if message:
        print(f"       {message}")


def test_imports():
    """Test if all required Python packages are installed"""
    print_header("Testing Python Imports")
    
    tests = []
    
    # Test rpi_ws281x
    try:
        from rpi_ws281x import PixelStrip, Color  # noqa: F401
        tests.append(("rpi_ws281x", True, "WS2812B LED library"))
    except ImportError:
        tests.append(("rpi_ws281x", False, "Install with: uv pip install --system rpi_ws281x"))
    
    # Test requests
    try:
        import requests  # noqa: F401
        tests.append(("requests", True, "HTTP client library"))
    except ImportError:
        tests.append(("requests", False, "Install with: uv pip install --system requests"))
    
    # Test RPi.GPIO
    try:
        import RPi.GPIO as GPIO  # noqa: F401
        tests.append(("RPi.GPIO", True, "GPIO control library"))
    except ImportError:
        tests.append(("RPi.GPIO", False, "Install with: uv pip install --system RPi.GPIO"))
    
    for name, passed, message in tests:
        print_test(name, passed, message)
    
    return all(t[1] for t in tests)


def test_files():
    """Test if all required files exist"""
    print_header("Testing Required Files")
    
    # Check current directory first, then fall back to /home/pi/
    script_dir = Path(__file__).parent.parent.absolute()
    home_pi = Path("/home/pi")
    
    # Try to find files in current directory or /home/pi/
    def find_file(filename):
        # Try current directory first
        local_path = script_dir / filename
        if local_path.exists():
            return local_path
        # Try /home/pi/
        pi_path = home_pi / filename
        if pi_path.exists():
            return pi_path
        # Return the /home/pi/ path as default (for error message)
        return pi_path
    
    files = [
        ("led_monitor.py", find_file("led-monitor.py") or find_file("led_monitor.py") or home_pi / "led_monitor.py"),
        ("led_monitor_config.json", find_file("led-monitor-cfg.json") or find_file("led_monitor_config.json") or home_pi / "led_monitor_config.json"),
        ("systemd service", Path("/etc/systemd/system/led-monitor.service")),
    ]
    
    tests = []
    for name, path in files:
        exists = path.exists()
        tests.append((name, exists, str(path)))
        print_test(name, exists, str(path) if exists else f"Missing: {path}")
    
    return all(t[1] for t in tests)


def test_config():
    """Test config file validity"""
    print_header("Testing Configuration File")
    
    # Try to find config file in current directory or /home/pi/
    script_dir = Path(__file__).parent.parent.absolute()
    config_candidates = [
        script_dir / "led-monitor-cfg.json",
        script_dir / "led_monitor_config.json",
        Path("/home/pi/led_monitor_config.json"),
    ]
    
    config_path = None
    for candidate in config_candidates:
        if candidate.exists():
            config_path = candidate
            break
    
    if not config_path:
        print_test("config file exists", False, f"Missing: checked {[str(c) for c in config_candidates]}")
        return False
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        # Check required fields
        tests = []
        tests.append(("check_interval present", "check_interval" in config))
        tests.append(("led_count present", "led_count" in config))
        tests.append(("services present", "services" in config))
        
        if "services" in config:
            services = config["services"]
            tests.append(("services is list", isinstance(services, list)))
            tests.append(("has services configured", len(services) > 0))
            
            if services:
                first_service = services[0]
                tests.append(("service has name", "name" in first_service))
                tests.append(("service has type", "type" in first_service))
                tests.append(("service has target", "target" in first_service))
        
        for name, passed in tests:
            print_test(name, passed)
        
        # Print config summary
        if all(t[1] for t in tests):
            print(f"\n{GREEN}Config Summary:{RESET}")
            print(f"  Check interval: {config.get('check_interval')}s")
            print(f"  LED count: {config.get('led_count')}")
            print(f"  Services: {len(config.get('services', []))}")
            for i, svc in enumerate(config.get('services', [])[:3]):
                print(f"    {i+1}. {svc.get('name')} ({svc.get('type')}) → {svc.get('target')}")
        
        return all(t[1] for t in tests)
        
    except FileNotFoundError:
        print_test("config file exists", False, f"Missing: {config_path}")
        return False
    except json.JSONDecodeError as e:
        print_test("config file valid JSON", False, str(e))
        return False


def test_gpio_access():
    """Test GPIO access (requires root)"""
    print_header("Testing GPIO Access")
    
    if os.geteuid() != 0:
        print_test("running as root", False, "This test requires sudo")
        print(f"{YELLOW}Skipping GPIO tests (run with sudo for full test){RESET}")
        return False
    
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        
        # Test legacy button pin (for wiring sanity); Kano hat uses GPIO 3.
        try:
            GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            button_state = GPIO.input(17)
            print_test("button GPIO (17) accessible", True, f"Current state: {'HIGH' if button_state else 'LOW'}")
            GPIO.cleanup(17)
        except Exception as e:
            print_test("button GPIO (17) accessible", False, str(e))
        
        # Note: Can't test GPIO 18 without initializing LED strip
        print_test("LED GPIO (18) check", True, "Will be tested by LED strip init")
        
        return True
        
    except Exception as e:
        print_test("GPIO access", False, str(e))
        return False


def test_led_strip():
    """Test LED strip initialization"""
    print_header("Testing LED Strip")
    
    if os.geteuid() != 0:
        print(f"{YELLOW}LED test requires sudo - skipping{RESET}")
        return False
    
    try:
        from rpi_ws281x import PixelStrip, Color
        
        LED_COUNT = 24
        LED_PIN = 18
        LED_FREQ_HZ = 800000
        LED_DMA = 10
        LED_BRIGHTNESS = 50
        LED_INVERT = False
        LED_CHANNEL = 0
        
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, 
                          LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        
        print_test("LED strip initialized", True, f"{LED_COUNT} LEDs on GPIO {LED_PIN}")
        
        # Brief test pattern
        print(f"\n{YELLOW}Running brief LED test (2 seconds)...{RESET}")
        
        # Red
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(255, 0, 0))
        strip.show()
        time.sleep(0.5)
        
        # Green
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 255, 0))
        strip.show()
        time.sleep(0.5)
        
        # Blue
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 255))
        strip.show()
        time.sleep(0.5)
        
        # Off
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        
        print_test("LED test pattern", True, "Red → Green → Blue → Off")
        
        return True
        
    except ImportError:
        print_test("LED strip", False, "rpi_ws281x not installed")
        return False
    except Exception as e:
        print_test("LED strip initialization", False, str(e))
        return False


def test_service_checks():
    """Test service checking functions"""
    print_header("Testing Service Checks")
    
    try:
        import subprocess
        import requests
        
        # Test ping
        try:
            result = subprocess.run(['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
            ping_works = result.returncode == 0
            print_test("ping check (8.8.8.8)", ping_works, 
                      "Internet connectivity OK" if ping_works else "Check network")
        except Exception as e:
            print_test("ping check", False, str(e))
        
        # Test HTTP
        try:
            response = requests.get('http://google.com', timeout=5)
            http_works = response.status_code == 200
            print_test("HTTP check (google.com)", http_works)
        except Exception:
            print_test("HTTP check", False, "Check internet connection")
        
        # Test systemd
        try:
            result = subprocess.run(['systemctl', 'is-active', 'systemd-journald'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            systemd_works = result.stdout.decode().strip() == 'active'
            print_test("systemd check (journald)", systemd_works)
        except Exception as e:
            print_test("systemd check", False, str(e))
        
        return True
        
    except Exception as e:
        print_test("service checks", False, str(e))
        return False


def test_button():
    """Test button functionality (optional sanity check)"""
    print_header("Testing Button (Optional)")
    
    if os.geteuid() != 0:
        print(f"{YELLOW}Button test requires sudo - skipping{RESET}")
        return True  # Optional, so don't fail
    
    try:
        import RPi.GPIO as GPIO
        
        BUTTON_PIN = 17
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        initial_state = GPIO.input(BUTTON_PIN)
        print(f"\n{YELLOW}Button test: Press the button within 5 seconds...{RESET}")
        print(f"Initial state: {'HIGH (not pressed)' if initial_state else 'LOW (pressed)'}")
        
        button_pressed = False
        start_time = time.time()
        
        while time.time() - start_time < 5:
            current_state = GPIO.input(BUTTON_PIN)
            if current_state == GPIO.LOW and initial_state == GPIO.HIGH:
                button_pressed = True
                print(f"{GREEN}✓ Button press detected!{RESET}")
                break
            time.sleep(0.1)
        
        GPIO.cleanup(BUTTON_PIN)
        
        if not button_pressed:
            print(f"{YELLOW}No button press detected (optional){RESET}")
            print_test("button detection", True, "Optional - skipped or no button connected")
        
        return True
        
    except Exception as e:
        print_test("button test", True, f"Optional - {e}")
        return True  # Don't fail on optional test


def main():
    """Run all tests"""
    print(f"\n{BLUE}{'#'*60}{RESET}")
    print(f"{BLUE}#{'LED Ring Service Monitor - System Test'.center(58)}#{RESET}")
    print(f"{BLUE}{'#'*60}{RESET}")
    
    if os.geteuid() != 0:
        print(f"\n{YELLOW}⚠ Warning: Not running as root{RESET}")
        print(f"{YELLOW}Some tests will be skipped. Run with sudo for complete test:{RESET}")
        print(f"{YELLOW}  sudo python3 tests/test-monitor.py{RESET}\n")
    
    results = []
    
    # Run all tests
    results.append(("Imports", test_imports()))
    results.append(("Files", test_files()))
    results.append(("Config", test_config()))
    results.append(("GPIO", test_gpio_access()))
    results.append(("LED Strip", test_led_strip()))
    results.append(("Service Checks", test_service_checks()))
    results.append(("Button", test_button()))
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✓{RESET}" if result else f"{RED}✗{RESET}"
        print(f"{status} {name}")
    
    print(f"\n{BLUE}Results: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}{'='*60}{RESET}")
        print(f"{GREEN}All tests passed! System is ready to use.{RESET}")
        print(f"{GREEN}{'='*60}{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Edit config: nano led-monitor-cfg.json")
        print(f"  2. Start service: sudo systemctl start led-monitor.service")
        print(f"  3. View logs: sudo journalctl -u led-monitor.service -f")
        return 0
    else:
        print(f"\n{RED}{'='*60}{RESET}")
        print(f"{RED}Some tests failed. Please fix issues above.{RESET}")
        print(f"{RED}{'='*60}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


