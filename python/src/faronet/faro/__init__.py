"""Raspberry Pi optical bring-up, current pin profile and optional GPIO backend.

The inspected Pi 3 Model B rev 1.2 environment is recorded in hardware docs.
The selected backend is official libgpiod v2 with BCM GPIO numbering.
Pin roles follow the revision-6 breadboard reference. Physical line I/O and
receiver operation still require validation; identify B's controller separately.
No hardware is initialized when this package is imported.
"""
