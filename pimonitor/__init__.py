"""
pimonitor package

Runtime components:
  - pimonitor.kano_hat: Kano hat LED ring + button abstraction
  - pimonitor.monitor:  ServiceMonitor and CLI entrypoint
"""

from .monitor import ServiceMonitor, main  # noqa: F401


