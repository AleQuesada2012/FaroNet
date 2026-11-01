# BOM del Faro (revisión 7 soldada)

Lista de materiales del dispositivo de transmisión ("Faro") con costo
aproximado en colones, para la versión soldada en perfboard del circuito de
[revisión 7](breadboard/README.md). Los valores eléctricos vienen de
[`circuit-reference.json`](breadboard/circuit-reference.json); el único
cambio para la versión soldada es **R6 = 47 kΩ** (más histéresis, decisión
del equipo del 31 de octubre de 2026; la protoboard usa 100 kΩ). El valor
final de R6 se confirma al medir la placa soldada.

## Cómo leer los precios

- Base: la lista de compras del equipo ("Team Parts List redes", consulta
  del 14 de octubre de 2026) y consultas a MicroJPM del 31 de octubre de
  2026 (S1 y la base DIP8). Tipo de cambio de referencia: **₡455 por US$1**.
- **DBU y H2ElectronicsCR** publican precios en colones con impuestos.
  **CRCibernética** publica base sin IVA: el subtotal ya suma el 13 %.
  **MicroJPM** publica en USD y no confirma si incluye IVA: el subtotal usa
  lo publicado y aparte se muestra una reserva del 13 %, como en la lista
  del equipo.
- Son precios de referencia por función. Varias piezas instaladas se
  compraron antes (MJ Electrónica) o no tienen modelo identificado (el LED
  IR); se costean con el artículo equivalente de la lista. No incluyen
  envío.

## Por Faro: componentes de la placa

| Ref. | Cant. | Descripción | Proveedor | Código / referencia | Unit. CRC | Subtotal CRC |
| --- | ---: | --- | --- | --- | ---: | ---: |
| D1 | 1 | LED emisor IR 940 nm, 5 mm (referencia Vishay TSAL4400; pieza física sin modelo identificado) | DBU | TSAL4400 | ₡850,00 | ₡850,00 |
| Q1 | 1 | Transistor NPN 2N2222, TO-92 (referencia PN2222A) | MicroJPM | AD44592 | ₡136,50 | ₡136,50 |
| Q2 | 1 | Fototransistor IR Everlight PT333-3B | DBU | PT333-3B | ₡190,00 | ₡190,00 |
| U1 | 1 | Comparador dual LM393, DIP8 | MicroJPM | AD16960 | ₡341,25 | ₡341,25 |
| U1 (base) | 1 | Socket DIP8 para U1 (retirable sin desoldar) | MicroJPM | AD7480 | ₡182,00 | ₡182,00 |
| RV1 | 1 | Trimpot 10 kΩ, umbral del receptor | MicroJPM | AD8289 | ₡318,50 | ₡318,50 |
| C1 | 1 | Electrolítico 100 µF (en uso: 63 V del inventario; referencia 35 V) | MicroJPM | AD9792 | ₡136,50 | ₡136,50 |
| C2, C3 | 2 | Cerámico 100 nF / 50 V | MicroJPM | AD17288 | ₡91,00 | ₡182,00 |
| D2 | 1 | LED verde 5 mm, indicador TX (referencia Broadcom HLMP-3507) | H2ElectronicsCR | HLMP-3507 | ₡191,00 | ₡191,00 |
| D3 | 1 | LED amarillo 5 mm, indicador RX (referencia Lite-On LTL-307YLC) | H2ElectronicsCR | LTL-307YLC | ₡196,00 | ₡196,00 |
| S1 | 1 | Pulsador táctil 6 × 6 mm, 4 pines, NA (pánico) | MicroJPM | AD595 | ₡113,75 | ₡113,75 |
| R1 | 1 | Resistencia 330 Ω ¼ W (corriente del LED IR) | MicroJPM | 330 Ω ¼ W | ₡18,20 | ₡18,20 |
| R2, R8, R10, R11 | 4 | Resistencia 1 kΩ ¼ W | MicroJPM | 1 kΩ ¼ W | ₡22,75 | ₡91,00 |
| R3, R4, R12 | 3 | Resistencia 10 kΩ ¼ W | MicroJPM | 10 kΩ ¼ W | ₡18,20 | ₡54,60 |
| R5 | 1 | Resistencia 4,7 kΩ ¼ W (pull-up de OPT_RX a 3,3 V) | MicroJPM | 4.7 kΩ ¼ W | ₡18,20 | ₡18,20 |
| R6 | 1 | Resistencia 47 kΩ ¼ W (histéresis; 100 kΩ en protoboard) | MicroJPM | 47 kΩ ¼ W | ₡22,75 | ₡22,75 |
| R9 | 1 | Resistencia 2,2 kΩ ¼ W (divisor VBIAS) | MicroJPM | 2.2 kΩ ¼ W | ₡18,20 | ₡18,20 |
| PCB | 1 | Perfboard doble cara 8 × 12 cm | CRCibernética | Perfboard 8 × 12 | ₡887,25 + IVA | ₡1 002,59 |
| J1 | 1 | Header macho 1 × 40, 2,54 mm (se usan 8 contactos hacia la Pi) | MicroJPM | AD112 | ₡227,50 | ₡227,50 |
| Cableado | 1 | Alambre sólido 22 AWG, 1 m (estimado por placa) | MicroJPM | 22 AWG, 1 m | ₡364,00 | ₡364,00 |

**Subtotal por Faro: ₡4 654,54** (reserva de IVA MicroJPM: ₡289,28).

## Por nodo: computadora y alimentación

| Ref. | Cant. | Descripción | Proveedor | Código / referencia | Unit. CRC | Subtotal CRC |
| --- | ---: | --- | --- | --- | ---: | ---: |
| Pi | 1 | Raspberry Pi 3 Model B (Faro A) / Pi 2 Model B (Faro B) | Existente | — | — | no costeado |
| SD | 1 | Tarjeta microSD con el sistema operativo | Existente | — | — | no costeado |
| Fuente | 1 | Fuente Micro-USB 5 V / 2,5 A con cable | CRCibernética | Fuente 5 V 2,5 A | ₡2 707,25 + IVA | ₡3 059,19 |
| Cables | 8 | Jumpers Dupont hembra (de la Pi a J1) | Existente | — | — | no costeado |

La Raspberry Pi, la microSD y los jumpers ya eran del equipo; no se
compraron para el proyecto y no se costean aquí. La Pi se conecta a la
placa con jumpers sobre el header J1, por lo que se retira sin desoldar.

**Subtotal por nodo (costeado): ₡3 059,19.**

## Totales

| Concepto | Un Faro | Dos Faros |
| --- | ---: | ---: |
| Placa del Faro | ₡4 654,54 | ₡9 309,08 |
| Fuente de alimentación | ₡3 059,19 | ₡6 118,38 |
| **Total** | **₡7 713,73** | **₡15 427,46** |
| Reserva posible IVA MicroJPM | ₡289,28 | ₡578,56 |
| **Total con reserva** | **₡8 003,01** | **₡16 006,02** |

## Fuera del BOM del Faro

- **Herramientas y consumibles** de montaje: cautín (propio), soldadura
  (prestada; respaldo de 20 g en CRCibernética ₡899,76), multímetro
  (prestado), soporte de cautín y pilas AAA (comprados). No forman parte del
  dispositivo.
- **Compras para mejoras no implementadas**, según la lista del equipo:
  LED RGB y 74HCT27 (el RGB se retiró del diseño el 30 de octubre de 2026),
  láser M57, fotodiodo BPW24R, TLC272, LM311, LCD con backpack I²C y
  buzzers. No están en el circuito y no se costean como parte del Faro.
- **Piezas de la protoboard** (protoboard MB-102 y jumpers): sirvieron solo
  para el prototipo; el Faro entregado va soldado.
