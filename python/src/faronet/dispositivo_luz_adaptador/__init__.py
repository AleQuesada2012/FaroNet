"""Faro frame codec and simulated adapter; physical GPIO integration is pending."""

from faronet.dispositivo_luz_adaptador.frame import Frame, FrameError, FrameType
from faronet.dispositivo_luz_adaptador.simulation import DispositivoLuzAdaptador

__all__ = ["DispositivoLuzAdaptador", "Frame", "FrameError", "FrameType"]
