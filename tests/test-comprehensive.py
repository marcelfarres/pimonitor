#!/usr/bin/env python3
"""
Comprehensive Diagnostic Test for LED Ring and Button
Tests hardware with detailed diagnostics and longer color displays
"""

import os
import sys
import time
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'


def print_header(text):
    print(f"\n{CYAN}{'='*70}{RESET}")
    print(f"{CYAN}{text.center(70)}{RESET}")
    print(f"{CYAN}{'='*70}{RESET}\n")


def print_status(name, passed, message=""):
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} - {name}")
    if message:
        print(f"       {message}")


def check_root():
    """Check if running as root"""
    print_header("Checking Permissions")
    is_root = os.geteuid() == 0
    print_status("Running as root", is_root, 
                 "sudo required for GPIO/LED access" if not is_root else "OK")
    return is_root


def test_imports():
    """Test if all required packages are installed"""
    print_header("Testing Python Imports")
    
    results = []
    
    # Test rpi_ws281x
    try:
        from rpi_ws281x import PixelStrip, Color  # noqa: F401
        results.append(("rpi_ws281x", True, "LED library available"))
    except ImportError as e:
        results.append(("rpi_ws281x", False, f"Not installed: {e}"))
    
    # Test RPi.GPIO
    try:
        import RPi.GPIO as GPIO  # noqa: F401
        results.append(("RPi.GPIO", True, "GPIO library available"))
    except ImportError as e:
        results.append(("RPi.GPIO", False, f"Not installed: {e}"))
    
    for name, passed, msg in results:
        print_status(name, passed, msg)
    
    return all(r[1] for r in results)


def test_led_strip_detailed():
    """Detailed LED strip test with longer color displays"""
    print_header("LED Strip Detailed Test")
    
    if not check_root():
        print(f"{YELLOW}Skipping LED test - requires sudo{RESET}")
        return False
    
    try:
        from rpi_ws281x import PixelStrip, Color
        
        # Configuration
        LED_COUNT = 24
        LED_PIN = 18
        LED_FREQ_HZ = 800000
        LED_DMA = 10
        LED_BRIGHTNESS = 100  # Increased brightness for visibility
        LED_INVERT = False
        LED_CHANNEL = 0
        
        print(f"Configuration:")
        print(f"  LED Count: {LED_COUNT}")
        print(f"  GPIO Pin: {LED_PIN}")
        print(f"  Brightness: {LED_BRIGHTNESS}/255")
        print(f"  Frequency: {LED_FREQ_HZ} Hz")
        print(f"  DMA Channel: {LED_DMA}")
        
        print(f"\n{YELLOW}Initializing LED strip...{RESET}")
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, 
                          LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        print_status("LED strip initialized", True, f"{LED_COUNT} LEDs on GPIO {LED_PIN}")
        
        # Test 1: All LEDs OFF (should be dark)
        print(f"\n{YELLOW}Test 1: All LEDs OFF (3 seconds){RESET}")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        time.sleep(3)
        
        # Test 2: All LEDs RED (should be bright red)
        print(f"\n{YELLOW}Test 2: All LEDs RED (5 seconds){RESET}")
        print(f"{GREEN}You should see ALL LEDs in BRIGHT RED{RESET}")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(255, 0, 0))
        strip.show()
        time.sleep(5)
        
        # Test 3: All LEDs GREEN
        print(f"\n{YELLOW}Test 3: All LEDs GREEN (5 seconds){RESET}")
        print(f"{GREEN}You should see ALL LEDs in BRIGHT GREEN{RESET}")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 255, 0))
        strip.show()
        time.sleep(5)
        
        # Test 4: All LEDs BLUE
        print(f"\n{YELLOW}Test 4: All LEDs BLUE (5 seconds){RESET}")
        print(f"{GREEN}You should see ALL LEDs in BRIGHT BLUE{RESET}")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 255))
        strip.show()
        time.sleep(5)
        
        # Test 5: All LEDs WHITE
        print(f"\n{YELLOW}Test 5: All LEDs WHITE (5 seconds){RESET}")
        print(f"{GREEN}You should see ALL LEDs in BRIGHT WHITE{RESET}")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(255, 255, 255))
        strip.show()
        time.sleep(5)
        
        # Test 6: Individual LED test (first 5 LEDs)
        print(f"\n{YELLOW}Test 6: Individual LED test (first 5 LEDs){RESET}")
        for led_num in range(min(5, strip.numPixels())):
            print(f"  Lighting LED {led_num} in RED...")
            # Clear all
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(0, 0, 0))
            # Light one
            strip.setPixelColor(led_num, Color(255, 0, 0))
            strip.show()
            time.sleep(2)
        
        # Test 7: Sequential test (chase pattern)
        print(f"\n{YELLOW}Test 7: Sequential chase pattern{RESET}")
        for i in range(strip.numPixels()):
            # Clear all
            for j in range(strip.numPixels()):
                strip.setPixelColor(j, Color(0, 0, 0))
            # Light current
            strip.setPixelColor(i, Color(0, 255, 0))
            strip.show()
            time.sleep(0.2)
        
        # Test 8: Brightness test
        print(f"\n{YELLOW}Test 8: Brightness levels (dim to bright){RESET}")
        for brightness in [10, 50, 100, 150, 200, 255]:
            print(f"  Brightness: {brightness}/255")
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(brightness, 0, 0))
            strip.show()
            time.sleep(1)
        
        # Clear all
        print(f"\n{YELLOW}Clearing all LEDs...{RESET}")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        
        print_status("LED strip detailed test", True, "All color tests completed")
        return True
        
    except Exception as e:
        print_status("LED strip test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_button_detailed():
    """Detailed button test with state change detection"""
    print_header("Button Detailed Test")
    
    if not check_root():
        print(f"{YELLOW}Skipping button test - requires sudo{RESET}")
        return False
    
    try:
        import RPi.GPIO as GPIO
        
        BUTTON_PIN = 17
        
        print("Configuration:")
        print(f"  Button GPIO: {BUTTON_PIN}")
        print(f"  Wiring: Button between GPIO {BUTTON_PIN} and GND")
        print("  Internal pull-up: Enabled (HIGH when not pressed)")
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        initial_state = GPIO.input(BUTTON_PIN)
        print(f"\nInitial button state: {'HIGH (not pressed)' if initial_state else 'LOW (pressed)'}")
        
        # Test 1: Continuous monitoring
        print(f"\n{YELLOW}Test 1: Continuous button monitoring (10 seconds){RESET}")
        print(f"{GREEN}Press and release the button multiple times...{RESET}")
        print("Press Ctrl+C to skip this test\n")
        
        press_count = 0
        last_state = initial_state
        start_time = time.time()
        
        try:
            while time.time() - start_time < 10:
                current_state = GPIO.input(BUTTON_PIN)
                
                # Detect falling edge (button press)
                if last_state == GPIO.HIGH and current_state == GPIO.LOW:
                    press_count += 1
                    print(f"{GREEN}✓ BUTTON PRESSED! (Press #{press_count}){RESET}")
                    time.sleep(0.1)  # Debounce
                
                # Detect rising edge (button release)
                elif last_state == GPIO.LOW and current_state == GPIO.HIGH:
                    print(f"{CYAN}  Button released{RESET}")
                    time.sleep(0.1)  # Debounce
                
                last_state = current_state
                time.sleep(0.05)  # Check every 50ms
                
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Test interrupted by user{RESET}")
        
        GPIO.cleanup(BUTTON_PIN)
        
        if press_count > 0:
            print_status("Button detection", True, f"Detected {press_count} button press(es)")
        else:
            print_status(
                "Button detection",
                False,
                "No button presses detected. Check wiring: GPIO 17 to button, button to GND",
            )
        
        # Test 2: Event detection (callback method)
        print(f"\n{YELLOW}Test 2: Event-based button detection (5 seconds){RESET}")
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        callback_count = [0]  # Use list to modify in callback
        
        def button_callback(channel):
            callback_count[0] += 1
            print(f"{GREEN}✓ Button callback triggered! (Count: {callback_count[0]}){RESET}")
        
        GPIO.add_event_detect(
            BUTTON_PIN,
            GPIO.FALLING,
            callback=button_callback,
            bouncetime=200,
        )
        
        print(f"{GREEN}Press the button...{RESET}")
        time.sleep(5)
        
        GPIO.remove_event_detect(BUTTON_PIN)
        GPIO.cleanup(BUTTON_PIN)
        
        if callback_count[0] > 0:
            print_status("Button callback", True, f"Callback triggered {callback_count[0]} time(s)")
        else:
            print_status("Button callback", False, "No callbacks detected")
        
        return press_count > 0 or callback_count[0] > 0
        
    except Exception as e:
        print_status("Button test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_file():
    """Test configuration file"""
    print_header("Configuration File Test")
    
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
        print_status("Config file", False, f"Not found in: {[str(c) for c in config_candidates]}")
        return False
    
    print_status("Config file found", True, str(config_path))
    
    try:
        import json
        with open(config_path) as f:
            config = json.load(f)
        
        print("\nConfig contents:")
        print(f"  Check interval: {config.get('check_interval')}s")
        print(f"  LED count: {config.get('led_count')}")
        print(f"  Services: {len(config.get('services', []))}")
        
        print_status("Config file valid", True, "JSON is valid")
        return True
        
    except Exception as e:
        print_status("Config file", False, f"Invalid JSON: {e}")
        return False


def main():
    """Run all comprehensive tests"""
    print(f"\n{BLUE}{'#'*70}{RESET}")
    print(f"{BLUE}#{'Comprehensive LED Ring & Button Diagnostic Test'.center(68)}#{RESET}")
    print(f"{BLUE}{'#'*70}{RESET}")
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Config File", test_config_file()))
    results.append(("LED Strip", test_led_strip_detailed()))
    results.append(("Button", test_button_detailed()))
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✓{RESET}" if result else f"{RED}✗{RESET}"
        print(f"{status} {name}")
    
    print(f"\n{BLUE}Results: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}{'='*70}{RESET}")
        print(f"{GREEN}All tests passed! Hardware is working correctly.{RESET}")
        print(f"{GREEN}{'='*70}{RESET}")
    else:
        print(f"\n{RED}{'='*70}{RESET}")
        print(f"{RED}Some tests failed. Review the output above for details.{RESET}")
        print(f"{RED}{'='*70}{RESET}")
        print(f"\n{YELLOW}Troubleshooting tips:{RESET}")
        print("  1. LED not showing colors: Check wiring (GPIO 18 to DIN, 5V power)")
        print("  2. Button not working: Check wiring (GPIO 17 to button, button to GND)")
        print("  3. Run with sudo: sudo python3 tests/test-comprehensive.py")
        print("  4. Check LED count matches your hardware")
        print("  5. Verify power supply (5V, adequate amperage)")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())


