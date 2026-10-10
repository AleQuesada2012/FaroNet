"""Local demonstrations using synthetic data, anonymous counters and fake stores."""

from faronet.dispositivo_luz_adaptador import DispositivoLuzAdaptador
from faronet.dispositivo_luz_adaptador.simulation import Fault, FaultPlan, SimulatedLink
from faronet.gateway.auth import GatewayRequest, ReplayError, sign_request, verify_and_admit
from faronet.gateway.testing import FakeNonceStore

SCENARIOS = {
    "clean": FaultPlan(),
    "lost-data": FaultPlan(data=(Fault.DROP,)),
    "corrupt-data": FaultPlan(data=(Fault.CORRUPT,)),
    "lost-ack": FaultPlan(ack=(Fault.DROP,)),
    "duplicate-data": FaultPlan(data=(Fault.DUPLICATE,)),
    "stale-ack": FaultPlan(ack=(Fault.STALE_SESSION,)),
    "retry-exhaustion": FaultPlan(ack=(Fault.DROP,) * 3),
}


def simulate(scenario: str) -> int:
    names = SCENARIOS if scenario == "all" else (scenario,)
    for name in names:
        link = SimulatedLink(b'FAKE0001', b'FAKE0002', b'SESSION1')
        adapter_a = DispositivoLuzAdaptador(link, b'FAKE0001')
        adapter_b = DispositivoLuzAdaptador(link, b'FAKE0002')
        result = adapter_a.send(b'synthetic request', SCENARIOS[name])
        if result.acknowledged:
            link.grant_turn(b'FAKE0002')
            reply = adapter_b.send(b'synthetic reply')
            if not reply.acknowledged:
                raise RuntimeError("Synthetic reply was not acknowledged")
        print(
            f"{name}: acknowledged={result.acknowledged} attempts={result.attempts} "
            f"receiver_acceptances={len(result.deliveries)} "
            f"duplicates={result.duplicate_observations} "
            f"virtual_half_bits={result.elapsed_half_bits}"
        )
    print("Simulation only: known clock, scripted turns, no GPIO or measured bitrate.")
    return 0


def authentication() -> int:
    # Public synthetic fixture, never a real deployment key.
    secret = bytes(range(32))
    request = GatewayRequest(
        'faronet-test', 'gateway-test', 'POST', '/v1/relay',
        '1791561600', '00' * 16, b'synthetic body',
    )
    signature = sign_request(request, secret)
    store = FakeNonceStore()

    def admit() -> None:
        verify_and_admit(
            request, signature, secret, expected_audience='faronet-test',
            expected_key_id='gateway-test', clock=lambda: 1791561600, store=store,
        )

    admit()
    try:
        admit()
    except ReplayError:
        print("Synthetic authentication: first admission accepted; replay rejected.")
        print("Offline fake store only; no HTTP request or deployed replay guarantee.")
        return 0
    raise RuntimeError("Authentication demonstration did not reject a replay")
