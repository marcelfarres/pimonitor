#!/usr/bin/env python3
"""
Detailed Button Detection Test
Step-by-step test to verify button hardware and GPIO configuration
Based on Kano Peripherals approach for reliable GPIO handling
"""

import os
import sys
import time

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'

BUTTON_PIN = 3  # GPIO 3 (BCM numbering) – Kano hat power button

try:
    # Optional visual feedback using the same Kano hat abstraction as the
    # main monitor. This lets us light the ring while running the button
    # test, which is useful when the terminal is not visible.
    from pimonitor.kano_hat import get_hat, LED_COUNT as HAT_LED_COUNT
    from rpi_ws281x import Color
except Exception:  # pragma: no cover - visual feedback is optional
    get_hat = None  # type: ignore[assignment]
    HAT_LED_COUNT = 0  # type: ignore[assignment]
    Color = None  # type: ignore[assignment]


def print_step(step_num, title):
    """Print a test step header"""
    print(f"\n{CYAN}{'='*70}{RESET}")
    print(f"{CYAN}STEP {step_num}: {title}{RESET}")
    print(f"{CYAN}{'='*70}{RESET}\n")


def print_info(message):
    """Print informational message"""
    print(f"{BLUE}ℹ {message}{RESET}")


def print_success(message):
    """Print success message"""
    print(f"{GREEN}✓ {message}{RESET}")


def print_error(message):
    """Print error message"""
    print(f"{RED}✗ {message}{RESET}")


def print_warning(message):
    """Print warning message"""
    print(f"{YELLOW}⚠ {message}{RESET}")


def get_hat_for_test():
    """
    Function: get_hat_for_test

    Tiny description:
      Obtain a Kano hat instance for LED feedback during the button test.

    Input parameters:
      - None.

    Output parameters:
      - Returns a tuple `(hat, led_count)` where `hat` is either a KanoHat
        instance or `None` if the abstraction is not available, and
        `led_count` is the number of LEDs on the ring.

    Longer description:
      This helper wraps access to the optional `kano_hat` module so that
      the button test can provide visual feedback on the LED ring without
      hard‑depending on the hat implementation. When the hat is available,
      the caller can light up LEDs in response to button events; otherwise
      the test behaves as a pure console test.
    """
    if get_hat is None or HAT_LED_COUNT <= 0:  # type: ignore[comparison-overlap]
        return None, 0

    try:
        hat = get_hat()  # type: ignore[call-arg]
        return hat, int(HAT_LED_COUNT)
    except Exception:
        return None, 0


def check_permissions():
    """Step 1: Check if running with proper permissions"""
    print_step(1, "Checking Permissions")
    
    if os.geteuid() != 0:
        print_error("Not running as root (sudo required)")
        print_info("GPIO access requires root privileges")
        print_warning("Run with: sudo python3 tests/test-button-detailed.py")
        return False
    
    print_success("Running as root - GPIO access available")
    return True


def test_imports():
    """Step 2: Test if RPi.GPIO is available"""
    print_step(2, "Testing RPi.GPIO Import")
    
    try:
        import RPi.GPIO as GPIO
        print_success("RPi.GPIO imported successfully")
        return True, GPIO
    except ImportError as e:
        print_error(f"RPi.GPIO not available: {e}")
        print_info("Install with: uv pip install --system RPi.GPIO")
        return False, None


def test_gpio_setup(GPIO):
    """Step 3: Test GPIO pin setup"""
    print_step(3, "Setting Up GPIO Pin")
    
    try:
        print_info(f"Configuring GPIO {BUTTON_PIN} (BCM mode)")
        print_info("Wiring: Hat button is pre-wired on GPIO 3 via the Kano hat")
        print_info("Using internal pull-down resistor (PUD_DOWN)")
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        
        print_success(f"GPIO {BUTTON_PIN} configured successfully")
        return True
    except Exception as e:
        print_error(f"Failed to setup GPIO: {e}")
        return False


def test_initial_state(GPIO):
    """Step 4: Check initial button state"""
    print_step(4, "Checking Initial Button State")
    
    try:
        initial_state = GPIO.input(BUTTON_PIN)
        state_name = "LOW (not pressed)" if initial_state == GPIO.LOW else "HIGH (pressed?)"
        
        print_info(f"Reading GPIO {BUTTON_PIN}...")
        print(f"Current state: {GREEN if initial_state == GPIO.LOW else YELLOW}{state_name}{RESET}")
        
        if initial_state == GPIO.LOW:
            print_success("Button line is LOW when not pressed (expected with pull-down).")
            print_info("This matches Kano's default PUD_DOWN configuration.")
        else:
            print_warning("Button line reads HIGH – ensure it is not being held down.")
            print_info("If the button is not pressed, double-check the hat connection.")
        
        return initial_state
    except Exception as e:
        print_error(f"Failed to read GPIO state: {e}")
        return None


def test_continuous_monitoring(GPIO):
    """Step 5: Continuous state monitoring"""
    print_step(5, "Continuous State Monitoring (10 seconds)")
    
    print_info("Monitoring button state changes...")
    print_info("Press and release the button multiple times")
    print_warning("Press Ctrl+C to skip to next test\n")
    
    last_state = GPIO.input(BUTTON_PIN)
    state_changes = []
    start_time = time.time()

    # Optional LED feedback: light up LEDs one by one on each press so the
    # button interaction is visible even without watching the terminal.
    hat, led_count = get_hat_for_test()
    led_index = 0
    
    try:
        while time.time() - start_time < 10:
            current_state = GPIO.input(BUTTON_PIN)
            
            # Detect state change
            if current_state != last_state:
                timestamp = time.time() - start_time
                if current_state == GPIO.HIGH:
                    state_changes.append(("PRESS", timestamp))
                    print_success(f"[{timestamp:.2f}s] Button PRESSED (LOW → HIGH)")

                    # Visual: light LEDs progressively around the ring.
                    if hat is not None and Color is not None and led_count > 0:
                        led_index = led_index % led_count
                        hat.set_led_color(led_index, Color(0, 0, 255), auto_show=True)
                        led_index += 1
                else:
                    state_changes.append(("RELEASE", timestamp))
                    print_info(f"[{timestamp:.2f}s] Button RELEASED (HIGH → LOW)")
                
                last_state = current_state
            
            time.sleep(0.01)  # Check every 10ms for responsiveness
            
    except KeyboardInterrupt:
        print_warning("\nTest interrupted by user")
    
    print(f"\n{YELLOW}Summary:{RESET}")
    print(f"  Total state changes detected: {len(state_changes)}")
    
    if len(state_changes) > 0:
        print_success("Button state changes detected successfully!")
        for change_type, timestamp in state_changes[:5]:  # Show first 5
            print(f"    {change_type} at {timestamp:.2f}s")
        if len(state_changes) > 5:
            print(f"    ... and {len(state_changes) - 5} more")
    else:
        print_error("No state changes detected")
        print_warning("Possible issues:")
        print_warning("  1. Button not connected correctly")
        print_warning("  2. Button is stuck or faulty")
        print_warning("  3. Wiring issue (GPIO 3 via hat or wiring)")

    # Clear LEDs at the end of the test so the ring is reset.
    if hat is not None:
        try:
            hat.clear(auto_show=True)
        except Exception:
            pass
    
    return len(state_changes)


def test_edge_detection(GPIO):
    """Step 6: Edge detection (falling/rising edges)"""
    print_step(6, "Edge Detection Test (5 seconds)")
    
    print_info("Testing RISING edge detection (button press)")
    print_info("Testing FALLING edge detection (button release)")
    print_warning("Press the button...\n")
    
    press_count = 0
    release_count = 0
    last_state = GPIO.input(BUTTON_PIN)
    start_time = time.time()
    
    try:
        while time.time() - start_time < 5:
            current_state = GPIO.input(BUTTON_PIN)
            
            # Rising edge: LOW → HIGH (button press)
            if last_state == GPIO.LOW and current_state == GPIO.HIGH:
                press_count += 1
                print_success(f"RISING edge detected! (Press #{press_count})")
                time.sleep(0.1)  # Debounce
            
            # Falling edge: HIGH → LOW (button release)
            elif last_state == GPIO.HIGH and current_state == GPIO.LOW:
                release_count += 1
                print_info(f"FALLING edge detected! (Release #{release_count})")
                time.sleep(0.1)  # Debounce
            
            last_state = current_state
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print_warning("\nTest interrupted")
    
    print(f"\n{YELLOW}Edge Detection Results:{RESET}")
    print(f"  Falling edges (presses): {press_count}")
    print(f"  Rising edges (releases): {release_count}")
    
    if press_count > 0:
        print_success("Edge detection working correctly!")
    else:
        print_error("No edges detected")
    
    return press_count, release_count


def test_callback_method(GPIO):
    """Step 7: Callback-based event detection (like Kano Peripherals)"""
    print_step(7, "Callback-Based Event Detection (5 seconds)")
    
    print_info("Using GPIO event detection with callback function")
    print_info("This is the method used in the main monitor script")
    print_warning("Press the button...\n")
    
    callback_count = [0]  # Use list to allow modification in callback
    
    def button_callback(channel):
        """Callback function triggered on button press"""
        callback_count[0] += 1
        timestamp = time.time()
        print_success(f"Callback triggered! (Count: {callback_count[0]}) at {timestamp:.2f}s")
    
    try:
        # Setup event detection on falling edge (button press)
        GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, 
                            callback=button_callback, 
                            bouncetime=200)  # 200ms debounce
        
        print_success("Event detection enabled (FALLING edge, 200ms debounce)")
        
        # Monitor for 5 seconds
        start_time = time.time()
        while time.time() - start_time < 5:
            time.sleep(0.1)
        
        # Clean up
        GPIO.remove_event_detect(BUTTON_PIN)
        
    except Exception as e:
        print_error(f"Callback setup failed: {e}")
        return 0
    
    print(f"\n{YELLOW}Callback Results:{RESET}")
    print(f"  Callbacks triggered: {callback_count[0]}")
    
    if callback_count[0] > 0:
        print_success("Callback method working correctly!")
        print_info("This method will work in the main monitor script")
    else:
        print_error("No callbacks triggered")
        print_warning("Check button wiring and ensure button is being pressed")
    
    return callback_count[0]


def test_wiring_verification(GPIO):
    """Step 8: Wiring verification"""
    print_step(8, "Wiring Verification")
    
    print_info("Verifying button wiring configuration...")
    print(f"\n{YELLOW}Expected Wiring:{RESET}")
    print(f"  GPIO {BUTTON_PIN} (Pin 5) → Button terminal 1")
    print(f"  GND (Pin 9) → Button terminal 2")
    print(f"  When button is pressed: GPIO {BUTTON_PIN} connects to GND")
    print(f"  When button is NOT pressed: GPIO {BUTTON_PIN} is HIGH (pulled up)")
    
    print(f"\n{YELLOW}Testing:{RESET}")
    
    # Test 1: Button not pressed
    print("\n1. Button NOT pressed (release if holding):")
    time.sleep(1)
    state_not_pressed = GPIO.input(BUTTON_PIN)
    if state_not_pressed == GPIO.HIGH:
        print_success(f"   GPIO {BUTTON_PIN} reads HIGH ✓")
    else:
        print_error(f"   GPIO {BUTTON_PIN} reads LOW (should be HIGH)")
        print_warning("   Button might be stuck or wiring issue")
    
    # Test 2: Button pressed
    print("\n2. Button PRESSED (press and hold now):")
    print_warning("   Press and HOLD the button for 2 seconds...")
    time.sleep(2)
    state_pressed = GPIO.input(BUTTON_PIN)
    if state_pressed == GPIO.LOW:
        print_success(f"   GPIO {BUTTON_PIN} reads LOW ✓")
    else:
        print_error(f"   GPIO {BUTTON_PIN} reads HIGH (should be LOW)")
        print_warning("   Button press not detected - check wiring")
    
    print("\n3. Button released:")
    print_warning("   Release the button now...")
    time.sleep(2)
    state_released = GPIO.input(BUTTON_PIN)
    if state_released == GPIO.HIGH:
        print_success(f"   GPIO {BUTTON_PIN} reads HIGH ✓")
    else:
        print_error(f"   GPIO {BUTTON_PIN} still reads LOW")
        print_warning("   Button might be stuck")
    
    # Summary
    print(f"\n{YELLOW}Wiring Verification Summary:{RESET}")
    if state_not_pressed == GPIO.HIGH and state_pressed == GPIO.LOW and state_released == GPIO.HIGH:
        print_success("All wiring tests passed! Button is working correctly.")
        return True
    else:
        print_error("Some wiring tests failed")
        print_warning("Please check:")
        print_warning("  - Button connections to GPIO 3 and GND")
        print_warning("  - Button is momentary (not toggle)")
        print_warning("  - No shorts or loose connections")
        return False


def cleanup(GPIO):
    """Clean up GPIO resources"""
    try:
        GPIO.cleanup(BUTTON_PIN)
        print_success("GPIO cleaned up")
    except Exception:
        pass


def main():
    """Run all button tests step by step"""
    print(f"\n{BLUE}{'#'*70}{RESET}")
    print(f"{BLUE}#{'Detailed Button Detection Test - Step by Step'.center(68)}#{RESET}")
    print(f"{BLUE}{'#'*70}{RESET}")
    print(f"\n{YELLOW}This test will verify button hardware and GPIO configuration{RESET}")
    print(f"{YELLOW}Based on Kano Peripherals GPIO handling approach{RESET}\n")
    
    # Check permissions
    if not check_permissions():
        print(f"\n{RED}Please run with sudo: sudo python3 tests/test-button-detailed.py{RESET}")
        return 1
    
    # Test imports
    success, GPIO = test_imports()
    if not success:
        return 1
    
    results = {}
    
    try:
        # Setup GPIO
        if not test_gpio_setup(GPIO):
            return 1
        
        # Test initial state
        initial_state = test_initial_state(GPIO)
        if initial_state is None:
            return 1
        
        # Continuous monitoring
        results['state_changes'] = test_continuous_monitoring(GPIO)
        
        # Edge detection
        press_count, release_count = test_edge_detection(GPIO)
        results['presses'] = press_count
        results['releases'] = release_count
        
        # Callback method
        results['callbacks'] = test_callback_method(GPIO)
        
        # Wiring verification
        results['wiring_ok'] = test_wiring_verification(GPIO)
        
    finally:
        cleanup(GPIO)
    
    # Final summary
    print(f"\n{CYAN}{'='*70}{RESET}")
    print(f"{CYAN}TEST SUMMARY{RESET}")
    print(f"{CYAN}{'='*70}{RESET}\n")
    
    print(f"State changes detected: {results.get('state_changes', 0)}")
    print(f"Button presses detected: {results.get('presses', 0)}")
    print(f"Button releases detected: {results.get('releases', 0)}")
    print(f"Callbacks triggered: {results.get('callbacks', 0)}")
    print(f"Wiring verification: {'PASS' if results.get('wiring_ok') else 'FAIL'}")
    
    if results.get('presses', 0) > 0 and results.get('wiring_ok'):
        print(f"\n{GREEN}{'='*70}{RESET}")
        print(f"{GREEN}✓ Button is working correctly!{RESET}")
        print(f"{GREEN}The button will work in the main monitor script.{RESET}")
        print(f"{GREEN}{'='*70}{RESET}")
        return 0
    else:
        print(f"\n{RED}{'='*70}{RESET}")
        print(f"{RED}✗ Button test failed or inconclusive{RESET}")
        print(f"{RED}Please check wiring and try again.{RESET}")
        print(f"{RED}{'='*70}{RESET}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Test interrupted by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


