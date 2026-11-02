"""Drive a CsmaLink over the GPIO backend. Both Faros run this same loop; no roles."""

import time

from faronet.dispositivo_luz_adaptador.medium import Delivered, SendResult, Transmit

LINGER_FRAMES = 7  # Stay to re-ACK a retried final frame, as the listener does.


def run_link(io, link, expected, count: int, timeout: float, emit, clock=time.monotonic,
             trace=None) -> dict:
    """Serve the link until our queue settles and `count` peer payloads arrive.

    `expected(index)` gives the peer's synthetic payload for bit-error counting.
    Afterwards linger so a peer retrying its final DATA still gets an ACK.
    """
    start = clock()
    stats = {"sent_acknowledged": 0, "send_failed": 0, "received_unique": 0,
             "payload_bit_errors": 0}
    linger = LINGER_FRAMES * io.frame_seconds + 1
    settled_at = None
    while (now := clock()) - start < timeout:
        if settled_at is None and link.idle and stats["received_unique"] >= count:
            settled_at = now
        if settled_at is not None and now - settled_at >= linger:
            break
        # Collect decoded frames first so an owed ACK is decided before we transmit.
        frame = io.receive(min(max(link.wake_at - now, 0.0005), 0.05))
        if frame is not None and trace is not None:
            trace({"t": round(clock() - start, 2), "rx": frame.kind.name, "seq": frame.sequence})
        actions = link.on_frame(frame, clock()) if frame is not None else []
        actions += link.poll(clock(), *io.channel())
        for action in actions:
            if isinstance(action, Transmit):
                if trace is not None:
                    trace({"t": round(clock() - start, 2), "tx": action.frame.kind.name,
                           "seq": action.frame.sequence})
                io.guard()
                io.transmit(action.frame)
            elif isinstance(action, SendResult):
                stats["sent_acknowledged" if action.acknowledged else "send_failed"] += 1
                emit({"frame": action.sequence, "acknowledged": action.acknowledged,
                      "attempts": action.attempts})
            elif isinstance(action, Delivered):
                index = stats["received_unique"]
                errors = sum((a ^ b).bit_count() for a, b in zip(action.payload, expected(index)))
                errors += abs(len(action.payload) - len(expected(index))) * 8
                stats["received_unique"] += 1
                stats["payload_bit_errors"] += errors
                emit({"received_unique": index + 1, "payload_bit_errors": errors})
    stats["elapsed_seconds"] = round(clock() - start, 3)
    return stats
