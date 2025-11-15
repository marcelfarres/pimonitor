#!/usr/bin/env python3
"""
Kano hat integration helpers.

This module provides a small abstraction layer for the CK2 Lite hat used by
Kano. It exposes a simple API for:
  - Initialising the 10‑LED ring on GPIO 18 using rpi_ws281x
  - Registering and reading the hat button on GPIO 3 (BCM)

The implementation is deliberately lightweight and inspired by Kano's original
code in their `kano-peripherals` repository, in particular:
  - `libs/pi_hat/library/src/power_button.c`
  - `libs/pi_hat/library/include/pins.h`
  - `libs/pi_hat/library/python/kano_pi_hat/kano_hat_leds.py`
"""

from typing import Callable, List, Optional
import time

try:
    from rpi_ws281x import PixelStrip, Color
except ImportError:  # pragma: no cover - hardware specific
    PixelStrip = None  # type: ignore[assignment]
    Color = None  # type: ignore[assignment]

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover - hardware specific
    GPIO = None  # type: ignore[assignment]


# LED configuration taken from Kano's `KanoHatLeds` implementation
LED_COUNT = 10          # Number of LEDs on the Kano ring
LED_PIN = 18            # Data line on the hat (BCM 18 / physical pin 12)
LED_FREQ_HZ = 800_000   # Standard WS2812 / NeoPixel frequency
LED_DMA = 10            # DMA channel used by rpi_ws281x
LED_BRIGHTNESS = 50     # Overall brightness 0–255
LED_INVERT = False      # Signal inversion flag
LED_CHANNEL = 0         # PWM channel

# Button configuration derived from Kano's `pins.h` and `power_button.c`
# POWER_PIN = 3; wiringPiSetupGpio() means BCM numbering is used.
BUTTON_PIN = 3          # Hat button GPIO (BCM 3 / physical pin 5)
BUTTON_BOUNCE_MS = 200  # Debounce time in milliseconds


class KanoHat:
    """
    Class: KanoHat

    Tiny controller for the Kano hat button and 10‑LED ring.

    Inputs:
      - led_count: Number of addressable LEDs on the ring.
      - brightness: Initial brightness for the LED ring (0–255).

    Outputs:
      - Provides methods to register button callbacks, read the button state,
        and manipulate individual LEDs or the whole ring.

    Description:
      This class owns the underlying PixelStrip instance (if available) and
      configures the GPIO for the hat button. It mirrors the wiring described
      in Kano's original C and Python code but uses only rpi_ws281x and
      RPi.GPIO so that it works on a plain Raspberry Pi OS install.
    """

    def __init__(self, led_count: int = LED_COUNT, brightness: int = LED_BRIGHTNESS) -> None:
        """
        Function: __init__

        Tiny description:
          Construct a KanoHat controller and prepare internal state.

        Input parameters:
          - led_count: Number of LEDs on the ring to control.
          - brightness: Initial brightness for the ring (0–255).

        Output parameters:
          - None. The instance is created and ready for `initialise()`.

        Longer description:
          The constructor stores configuration values and prepares containers
          for the underlying PixelStrip instance and button callback tracking,
          but it does not touch hardware directly. Hardware initialisation is
          deferred to `initialise()` so that unit tests can construct the
          object without requiring GPIO access.
        """
        self.led_count: int = led_count
        self.brightness: int = max(0, min(255, brightness))

        self._strip: Optional[PixelStrip] = None
        self._button_callbacks: List[Callable[[int], None]] = []
        self._gpio_initialised: bool = False

    def initialise(self) -> None:
        """
        Function: initialise

        Tiny description:
          Set up the LED strip and configure the hat button GPIO.

        Input parameters:
          - None. Uses configuration stored on the instance.

        Output parameters:
          - None. On success, hardware is ready to use. Failures are logged
            via printed warnings and leave the instance in a safe state.

        Longer description:
          This method performs all hardware‑touching initialisation in a
          safe, idempotent way:
            1. If rpi_ws281x is available, a PixelStrip is created for the
               configured LED count and pin, brightness is applied, and the
               strip is started.
            2. If RPi.GPIO is available, the BCM pin numbering mode is set
               up and the button GPIO (BCM 3) is configured as an input with
               a pull‑down resistor, matching Kano's original C library.
        """
        # Initialise LED strip (if the library is available)
        if PixelStrip and not self._strip:
            strip = PixelStrip(
                self.led_count,
                LED_PIN,
                LED_FREQ_HZ,
                LED_DMA,
                LED_INVERT,
                self.brightness,
                LED_CHANNEL,
            )
            strip.begin()
            self._strip = strip

        # Initialise GPIO for button (if the library is available)
        if GPIO and not self._gpio_initialised:
            GPIO.setmode(GPIO.BCM)
            # Use pull-down in software; a physical pull-up is present on this
            # channel, so this effectively creates a strong edge when the
            # button is pressed. This mirrors the behaviour used in the
            # dedicated button test script which proved reliable in practice.
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            self._gpio_initialised = True

    def register_button_callback(self, callback: Callable[[int], None]) -> None:
        """
        Function: register_button_callback

        Tiny description:
          Register a function to be called when the hat button is pressed.

        Input parameters:
          - callback: Function taking a single `int` channel parameter, as
                      required by RPi.GPIO event callbacks.

        Output parameters:
          - None. The callback is stored and wired into GPIO events if
            button GPIO support is available.

        Longer description:
          This method mirrors the behaviour of `register_power_off_cb` in
          Kano's original C library. It attaches the given callback to a
          rising‑edge GPIO event on BCM 3 with a debounce interval. Multiple
          callbacks can be registered and will all be invoked by GPIO.
        """
        if not GPIO:
            print("Warning: GPIO not available, button callbacks disabled")
            return

        self.initialise()

        # Register once with GPIO, track all callbacks locally. Use FALLING
        # edges (HIGH → LOW) to match the working configuration from the
        # standalone button tests and to avoid edge-detection issues seen with
        # RISING on this special pin.
        if not self._button_callbacks:
            GPIO.add_event_detect(
                BUTTON_PIN,
                GPIO.FALLING,
                callback=self._dispatch_button_callbacks,
                bouncetime=BUTTON_BOUNCE_MS,
            )

        self._button_callbacks.append(callback)

    def _dispatch_button_callbacks(self, channel: int) -> None:
        """
        Function: _dispatch_button_callbacks

        Tiny description:
          Internal GPIO event handler to fan out to user callbacks.

        Input parameters:
          - channel: GPIO channel provided by RPi.GPIO.

        Output parameters:
          - None. All registered callbacks are invoked in sequence.

        Longer description:
          RPi.GPIO allows only one callback per `add_event_detect` call. To
          support multiple listeners, this internal function is registered
          with GPIO and then calls each user‑supplied callback in turn. Any
          exceptions are caught and printed so that one failing callback does
          not break the rest.
        """
        for cb in list(self._button_callbacks):
            try:
                cb(channel)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"Error in button callback: {exc}")

    def read_button(self) -> bool:
        """
        Function: read_button

        Tiny description:
          Read the current state of the hat button.

        Input parameters:
          - None.

        Output parameters:
          - Returns True if the button is currently pressed, False otherwise.

        Longer description:
          This method directly reads the GPIO pin configured for the hat
          button using a pull‑down configuration. The button is considered
          pressed when the pin reads HIGH, in line with Kano's C code which
          registers a rising‑edge interrupt.
        """
        if not GPIO:
            return False

        self.initialise()
        return GPIO.input(BUTTON_PIN) == GPIO.HIGH

    def set_led_color(self, index: int, color: int, auto_show: bool = False) -> None:
        """
        Function: set_led_color

        Tiny description:
          Set a single LED on the ring to a specific packed color value.

        Input parameters:
          - index: Zero‑based LED index on the ring.
          - color: 24‑bit packed color created with `rpi_ws281x.Color`.
          - auto_show: If True, immediately update the strip after setting.

        Output parameters:
          - None. The internal PixelStrip state is updated.

        Longer description:
          This helper mirrors the direct use of `PixelStrip.setPixelColor`
          used elsewhere in the project, but keeps ownership of the strip
          inside this module. It is a thin wrapper so that higher‑level code
          (such as `ServiceMonitor`) does not need to know about the strip
          details and can remain focused on monitoring logic.
        """
        if not self._strip:
            return

        if 0 <= index < self._strip.numPixels():
            self._strip.setPixelColor(index, color)
            if auto_show:
                self._strip.show()

    def set_all_leds_color(self, color: int, auto_show: bool = True) -> None:
        """
        Function: set_all_leds_color

        Tiny description:
          Fill all LEDs on the ring with a single color.

        Input parameters:
          - color: 24‑bit packed color created with `rpi_ws281x.Color`.
          - auto_show: If True, immediately update the strip after setting.

        Output parameters:
          - None. All LED pixels are updated to the same color.

        Longer description:
          This function loops over each pixel in the underlying strip and
          assigns the same packed color value. It is useful for solid fills
          such as turning all LEDs off or displaying a uniform alert color.
        """
        if not self._strip:
            return

        for idx in range(self._strip.numPixels()):
            self._strip.setPixelColor(idx, color)

        if auto_show:
            self._strip.show()

    def show(self) -> None:
        """
        Function: show

        Tiny description:
          Push any pending LED updates to the physical ring.

        Input parameters:
          - None.

        Output parameters:
          - None. The LED ring is updated to reflect the current buffer.

        Longer description:
          This method is a small proxy to `PixelStrip.show()` so that
          higher‑level code does not need to access the underlying strip
          object directly. It can be used after a batch of `set_led_color`
          calls to update the display in one go.
        """
        if self._strip:
            self._strip.show()

    def clear(self, auto_show: bool = True) -> None:
        """
        Function: clear

        Tiny description:
          Turn off all LEDs on the ring.

        Input parameters:
          - auto_show: If True, immediately push the cleared state to the
                       physical LEDs.

        Output parameters:
          - None. All LEDs are set to COLOR_OFF (0, 0, 0).

        Longer description:
          This helper is primarily used during shutdown or when resetting the
          visual state between different animations. It simply sets all
          pixels to zero and optionally updates the hardware.
        """
        if not self._strip:
            return

        for idx in range(self._strip.numPixels()):
            self._strip.setPixelColor(idx, Color(0, 0, 0))  # type: ignore[call-arg]

        if auto_show:
            self._strip.show()

    def shutdown(self) -> None:
        """
        Function: shutdown

        Tiny description:
          Cleanly release hardware resources for the hat.

        Input parameters:
          - None.

        Output parameters:
          - None. The LED ring is cleared and GPIO state is reset.

        Longer description:
          This method is meant to be called from the main application shutdown
          path. It clears the LEDs, removes any button event detection, and
          resets GPIO state so that other processes or tests can safely use
          the same pins afterwards.
        """
        # Clear LEDs
        if self._strip:
            self.clear(auto_show=True)
            self._strip = None

        # Clean up GPIO state
        if GPIO and self._gpio_initialised:
            if GPIO.event_detected(BUTTON_PIN):  # pragma: no cover - best effort
                # Just read the flag to clear it; we do not need the value.
                pass

            try:
                GPIO.remove_event_detect(BUTTON_PIN)
            except Exception:
                # It is safe to ignore errors here if no event was registered.
                pass

            GPIO.cleanup(BUTTON_PIN)
            self._gpio_initialised = False


_GLOBAL_HAT: Optional[KanoHat] = None


def get_hat() -> KanoHat:
    """
    Function: get_hat

    Tiny description:
      Return a lazily‑initialised global KanoHat instance.

    Input parameters:
      - None.

    Output parameters:
      - A `KanoHat` instance, initialised and ready for use.

    Longer description:
      Most applications using this module only ever need a single instance
      controlling the hat hardware. This convenience function creates such
      an instance on first use, calls `initialise()` on it, and then returns
      the same object on subsequent calls. This avoids multiple competing
      owners of the LED ring or button GPIO.
    """
    global _GLOBAL_HAT

    if _GLOBAL_HAT is None:
        _GLOBAL_HAT = KanoHat()
        _GLOBAL_HAT.initialise()

    return _GLOBAL_HAT


