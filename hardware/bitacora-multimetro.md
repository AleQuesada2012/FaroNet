# Bitácora de pruebas con multímetro

Entregable del enunciado: continuidad, ausencia de cortos entre VCC y GND
antes de energizar y voltajes medidos en puntos clave. Multímetros del
equipo: XL830L, Truper y MY-64.

- **Parte 1:** lo medido en la protoboard del Faro B (revisión 7), con
  fecha. Los valores los reportó Angie durante el montaje y la
  depuración. Las de Faro A están en la [revisión 7a de la protoboard](breadboard/README.md)
  y en [MERGER.md](../MERGER.md).
- **Parte 2:** la hoja que se llena al soldar cada perfboard, antes y después
  de energizar. Las posiciones F·C son las de la
  [hoja de soldadura](perfboard/soldering-sheet.md). Un valor esperado no es
  una medición: cada casilla se llena con lo que marque el multímetro.

## Parte 1 · Faro B en protoboard (revisión 7)

Columnas A–E del plano. Pines físicos de la Pi entre paréntesis.

### 26 de octubre: botón de pánico S1

| Prueba | Resultado | Conclusión |
| --- | --- | --- |
| Continuidad entre las parejas de S1, sin pulsar | No suena | Abierto en reposo, correcto |
| La misma, pulsado | Suena | Cierra al pulsar, correcto |
| Pin 1 (3V3) a pin 18 (PANIC), sin pulsar | No suena (una primera lectura «suena» era el pin 20) | Sin corto de 3V3 a PANIC |

### 31 de octubre: emisor IR (Q1 2N2222, D1, R1 330 Ω)

| Prueba | Resultado | Conclusión |
| --- | --- | --- |
| Voltajes con TX en alto: base de Q1, pata derecha, pata izquierda, ambas patas de D1 | 2,92 V · 2,52 V · 4,37 V · 4,5 V | El emisor de Q1 no llegaba a GND (2,52 V), así que D1 no tenía corriente |
| Pata derecha de Q1 (emisor) a pin 39 (GND), continuidad | No suena; por el riel de la protoboard, el modo diodo marca 1465 | Contacto malo en el riel de GND |
| Corrección: cable directo b61 → pin 39 | D1 se ve encendido en la cámara | Emisor a GND, corregido |
| Jumper de prueba b59 → pin 39 que había quedado puesto | D1 siempre encendido; se retiró | Ya conmuta con TX |
| Cable a61 a pin 39 y pata derecha | Ambos suenan | Continuidad final correcta |

### 31 de octubre y 1 de noviembre: receptor (LM393 U1, Q2 PT333, RV1)

| Prueba | Resultado | Conclusión |
| --- | --- | --- |
| Pin 8 de U1 (VCC) | 5 V | Alimentación del comparador correcta |
| Pin 39 (GND) a pin 8 de U1, continuidad | Suena un instante y luego marca valores | Es la carga de C2 (100 nF), no un corto |
| Pines 1 y 17 de la Pi | 3,3 V | Riel de 3V3 correcto |
| Pin 1 de U1 (OPT_RX) | 4,8–4,9 V | **Peligroso para el GPIO** (máximo 3,3 V): se apagó la Pi y se retiró el cable a la Pi (pin 13) |
| Prueba aislada del comparador (casos A y B) | Salida 3,3 V / 0 V según el caso | El comparador conmuta; la falla venía del circuito |
| LM393N de repuesto | Mismo síntoma | Se descarta U1 dañado |
| VBIAS (divisor R8 1 kΩ / R9 2,2 kΩ) | 2,2 V en todas las condiciones (esperado 3,3 × 2,2 / 3,2 ≈ 2,27 V) | Divisor correcto |
| RV1: extremos d40 y d42, cursor c41 | d40 2,9 V en ambos topes, d42 0 V, c41 entre 0 y 2,9 V | Más tarde, todas las patas marcaban 2,92 V al girarlo: los extremos no hacían contacto |
| Jumper macho-macho en d40 | 2,08 V | Contacto de la tira dudoso |
| Corrección: RV1 reinsertado en b40, b42 y cursor a41; W23 movido al cursor | `rx` cambia al girar RV1 | Umbral ajustable, corregido |
| Q2 con el control remoto de TV | `rx` pasa de 0 a 1 | Fototransistor y comparador funcionan |

Prueba funcional del mismo día: el loopback óptico pasó 10/10 tramas a 2,
3 y 10 ms de medio bit (tabla en [optical-bringup.md](../docs/optical-bringup.md)).

## Parte 2 · Perfboard soldada (llenar al soldar cada Faro)

**Estado al 1 de noviembre:** la perfboard se soldó (fotos en
`hardware/IMG_3085.HEIC` y `hardware/IMG_3086.HEIC`), pero esta hoja no se
llenó por falta de tiempo antes de la entrega. Las casillas vacías no son
mediciones.

Una columna por Faro. Medir **con la Pi desconectada** hasta la sección C.

### A · Continuidad sin energía (cada red, de punta a punta)

| Red | Puntos (F·C) | Esperado | Faro A | Faro B |
| --- | --- | --- | --- | --- |
| GND izquierda ↔ derecha | F1·C7 ↔ F1·C28 y F24·C7 ↔ F24·C28 | Suena | | |
| GND a la Pi | F23·C7 ↔ pin 6; F2·C28 ↔ pin 9 | Suena | | |
| 3V3 | Pin 1 (F23·C14) ↔ F16·C22 ↔ R5.1 (F16·C23) | Suena | | |
| 5V | Pin 2 (F23·C21) ↔ U1.8 (F15·C23) ↔ R1.1 (F4·C21) | Suena | | |
| VBIAS | R8.2 (F17·C24) ↔ RV1 extremo (F19·C25) ↔ C3.1 (F23·C25) | Suena | | |
| VTH | U1.3 (F13·C26) ↔ cursor RV1 (F18·C26) | Suena | | |
| SENSE | U1.2 (F14·C26) ↔ Q2.C (F20·C32) | Suena | | |
| OPT_RX | U1.1 (F15·C26) ↔ F15·C27 (pin 13) | Suena | | |
| TX | F9·C30 (pin 11) ↔ R2 (F9·C29) | Suena | | |
| Emisor de Q1 a GND | Q1.E (F7·C31) ↔ riel C28 | Suena | | |
| PANIC | Pin 18 (F13·C9) ↔ S1.3 (F10·C8) ↔ S1.4 (F13·C8) | Suena | | |

### B · Aislamiento sin energía (no debe sonar)

| Entre | Esperado | Faro A | Faro B |
| --- | --- | --- | --- |
| 5V y GND | No suena; en Ω sube mientras carga C1 (100 µF) | | |
| 3V3 y GND | No suena | | |
| 5V y 3V3 | No suena | | |
| OPT_RX y 5V | No suena | | |
| PANIC y GND, sin pulsar | No suena (pulsado: suena) | | |
| Pads vecinos en cada fila soldada | Sin puentes de estaño (revisar con lupa) | | |

### C · Componentes antes de energizar

| Prueba | Esperado | Faro A | Faro B |
| --- | --- | --- | --- |
| Q1 modo diodo, base → emisor y base → colector | ≈ 0,6–0,7 V; al revés, OL | | |
| D1 y D2/D3 en modo diodo | Conducen solo con la punta roja en el ánodo | | |
| RV1 entre extremos | ≈ 10 kΩ, constante al girar | | |
| U1 en su zócalo, muesca orientada | Según la hoja | | |

### D · Voltajes con la Pi conectada y encendida (punta negra en GND)

| Punto | Esperado | Faro A | Faro B |
| --- | --- | --- | --- |
| Riel 3V3 (C14) | 3,3 V | | |
| Riel 5V (C21) | ≈ 5,0 V | | |
| U1.8 (VCC) | ≈ 5,0 V | | |
| VBIAS (R8.2, F17·C24) | ≈ 2,2–2,3 V | | |
| VTH (cursor RV1) al girarlo de tope a tope | 0 V a ≈ VBIAS | | |
| SENSE (U1.2): en reposo y con IR delante | Baja con luz IR | | |
| OPT_RX (pin 13) en alto | **≤ 3,3 V** (si pasa de 3,4 V, apagar y revisar R5) | | |
| OPT_RX en bajo | ≈ 0 V | | |
| PANIC sin pulsar / pulsado | 3,3 V / 0 V | | |
| Caída en R1 con TX encendido (F4·C21 ↔ F4·C29) | Anotar; I(D1) = V ÷ 330 Ω | | |
| LED_TX / LED_RX encendidos (pines 15/16) | ≈ 3,3 V en la salida | | |

Después: `gpio-calibrate` para fijar RV1 y `optical-loopback --count 100` para
medir el `ber` y la tasa efectiva, con luz ambiente normal, a tres distancias.
