# FaroNet

FaroNet connects participants through an optical link and a mesh, with a
gateway for explicitly public services outside the mesh.

## Language

**Faro**:
The physical device that transmits and receives the optical link and provides
its local activity and panic controls.
_Avoid_: Node when referring specifically to the optical device.

**Node**:
A participant in the FaroNet mesh that can originate, receive, or forward
messages. A Node and a Faro are distinct roles even when colocated.
_Avoid_: Faro when referring to the mesh participant.

**Gateway**:
A FaroNet participant serving as the boundary between the mesh and services
outside it. Explicitly public messages can cross this boundary.
_Avoid_: Edge when referring to the mesh-side bridge.

**Edge**:
The public application service outside the FaroNet mesh, reached through a
Gateway.
_Avoid_: Gateway when referring to the public service.

**DispositivoLuzAdaptador**:
The boundary through which a Node communicates with its Faro.
_Avoid_: Treating it as the mesh routing service.

**Faro frame**:
A unit exchanged between neighboring Faros over the optical link.
_Avoid_: Message when referring to a single unit of link transport.

**Private conversation**:
A one-to-one exchange whose message contents remain private within FaroNet.
_Avoid_: Public topic for this exchange.

**Private topic**:
A topic whose messages remain within FaroNet.
_Avoid_: Public topic for content that must stay within the mesh.

**Public topic**:
A topic whose explicitly public messages may be exposed outside FaroNet.
_Avoid_: Private topic for content published to clearnet.

**Dead drop**:
An exchange point for opaque encrypted blobs identified through a shared
secret, without exposing their plaintext to the exchange service.
_Avoid_: Public topic for the encrypted-blob exchange.
