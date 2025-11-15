#!/usr/bin/env python3
"""
LED Ring Test Script
Quick test to verify your LED ring is working correctly
"""

import os
import time
import sys

try:
    from rpi_ws281x import PixelStrip, Color
except ImportError:
    print("ERROR: rpi_ws281x not installed!")
    print("Install with: uv pip install --system rpi_ws281x")
    sys.exit(1)

# LED configuration - ADJUST THESE FOR YOUR SETUP
LED_COUNT = 10          # Number of LEDs in your ring (10 RGBW LEDs)
LED_PIN = 18            # GPIO pin (must be PWM capable)
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 100    # 0-255 (increased for better visibility)
LED_INVERT = False
LED_CHANNEL = 0


def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    if pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    pos -= 170
    return Color(0, pos * 3, 255 - pos * 3)


def test_all_leds(strip):
    """Test each LED individually."""
    print(f"\nTesting all {strip.numPixels()} LEDs individually...")
    for i in range(strip.numPixels()):
        # Turn on current LED in white
        strip.setPixelColor(i, Color(255, 255, 255))
        strip.show()
        print(f"LED {i} ON", end="\r")
        time.sleep(0.1)
        # Turn off
        strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        time.sleep(0.05)
    print("\nAll LEDs tested!           ")


def test_colors(strip):
    """Test RGB colors."""
    print("\nTesting colors...")
    colors = [
        (Color(255, 0, 0), "Red"),
        (Color(0, 255, 0), "Green"),
        (Color(0, 0, 255), "Blue"),
        (Color(255, 255, 0), "Yellow"),
        (Color(255, 0, 255), "Magenta"),
        (Color(0, 255, 255), "Cyan"),
        (Color(255, 255, 255), "White"),
    ]
    
    for color, name in colors:
        print(f"  {name}... (3 seconds)")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, color)
        strip.show()
        time.sleep(3)  # Longer display time
    
    # Clear
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


def test_rainbow(strip):
    """Rainbow animation."""
    print("\nRainbow animation (5 seconds)...")
    start_time = time.time()
    
    while time.time() - start_time < 5:
        for i in range(strip.numPixels()):
            color = wheel((int(i * 256 / strip.numPixels()) + int(time.time() * 100)) & 255)
            strip.setPixelColor(i, color)
        strip.show()
        time.sleep(0.02)
    
    # Clear
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


def test_service_positions(strip):
    """Show typical service LED positions."""
    print("\nShowing service positions for your LED count...")
    
    # Calculate even spacing for 4 services
    spacing = strip.numPixels() // 4
    positions = [0, spacing, spacing * 2, spacing * 3]
    
    print(f"For {strip.numPixels()} LEDs, suggested positions:")
    print(f"  Service 1 (Internet): LED {positions[0]} - Red")
    print(f"  Service 2 (Pi-hole):  LED {positions[1]} - Green")
    print(f"  Service 3 (Tailscale): LED {positions[2]} - Blue")
    print(f"  Service 4 (Custom):   LED {positions[3]} - Yellow")
    
    colors = [
        Color(255, 0, 0),    # Red
        Color(0, 255, 0),    # Green
        Color(0, 0, 255),    # Blue
        Color(255, 255, 0),  # Yellow
    ]
    
    for pos, color in zip(positions, colors):
        strip.setPixelColor(pos, color)
    
    strip.show()
    time.sleep(5)
    
    # Clear
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


def main():
    print("=" * 50)
    print("LED Ring Test Script")
    print("=" * 50)
    print("\nConfiguration:")
    print(f"  LED Count: {LED_COUNT}")
    print(f"  GPIO Pin: {LED_PIN}")
    print(f"  Brightness: {LED_BRIGHTNESS}/255")
    
    print("\nInitializing LED strip...")
    try:
        strip = PixelStrip(
            LED_COUNT,
            LED_PIN,
            LED_FREQ_HZ,
            LED_DMA,
            LED_INVERT,
            LED_BRIGHTNESS,
            LED_CHANNEL,
        )
        strip.begin()
        print("✓ LED strip initialized successfully!")
    except Exception as exc:
        print(f"✗ Failed to initialize LED strip: {exc}")
        print("\nMake sure you:")
        print("  1. Run this script with sudo")
        print("  2. Have correct wiring (GPIO 18 to DIN)")
        print("  3. Have 5V power connected to LED ring")
        sys.exit(1)
    
    try:
        # Run tests
        test_all_leds(strip)
        time.sleep(1)
        
        test_colors(strip)
        time.sleep(1)
        
        test_rainbow(strip)
        time.sleep(1)
        
        test_service_positions(strip)
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        print("=" * 50)
        print("\nIf all tests passed, your LED ring is ready!")
        print("You can now run the main monitoring script.")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    finally:
        # Clean up - turn off all LEDs
        print("\nCleaning up...")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        print("LEDs turned off. Test complete!")


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERROR: This script must be run with sudo!")
        print("Usage: sudo python3 tests/led-ring-test.py")
        sys.exit(1)
    
    main()


