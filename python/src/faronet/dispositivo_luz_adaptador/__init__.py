"""Faro frame codec, simulator and manually directed physical smoke-test adapter."""

from faronet.dispositivo_luz_adaptador.frame import Frame, FrameError, FrameType
from faronet.dispositivo_luz_adaptador.simulation import DispositivoLuzAdaptador
from faronet.dispositivo_luz_adaptador.physical import PhysicalDispositivoLuzAdaptador

__all__ = [
    "DispositivoLuzAdaptador", "PhysicalDispositivoLuzAdaptador",
    "Frame", "FrameError", "FrameType",
]
