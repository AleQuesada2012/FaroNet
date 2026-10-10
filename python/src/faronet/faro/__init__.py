"""Future Raspberry Pi optical transmitter/receiver and GPIO control.

The inspected Pi 3 Model B rev 1.2 environment is recorded in hardware docs.
The selected backend is official libgpiod v2 with BCM GPIO numbering.
Validate Python line I/O, receiver circuit and pin roles before hardware
implementation; identify the second Pi's controller during bring-up.
No hardware is initialized when this package is imported.
"""
