# FaroNet: montaje en protoboard (revisión 7)

Abrir [faronet-breadboard-review.html](faronet-breadboard-review.html).
Contiene el plano interactivo (clic en un agujero para resaltar su red),
la tabla de pines de la Pi, la lista de piezas, las orientaciones, los
únicos agujeros de la mitad F–J y el montaje por etapas con sus pruebas de
multímetro. El plano solo está en [faronet-breadboard.svg](faronet-breadboard.svg).

**Un Faro por protoboard, sin RGB.** RGB, R13–R15 y GPIO5/6/13 quedan fuera
del diseño de forma definitiva. El circuito es el básico de la revisión 6:
mismos componentes, valores, redes y pines de la Pi. Cambia solo la
colocación.

## Por qué se rediseñó la colocación

- **Numeración de F–J invertida.** En el tablero del equipo, la mitad F–J
  imprime los números de columna al revés. Casi todo va en la mitad A–E; solo
  usan F–J las patas inferiores del botón, las cuatro tiras justo debajo del
  LM393 y el emisor IR en las dos últimas tiras del borde derecho. Esos
  agujeros se ubican por referencia física, no por el número impreso. Las
  columnas del plano son las de la mitad A–E.
- **Emisor y receptor en filas espejo.** D1 va en h62/h63 y Q2 en c62/c63.
  Al girar el segundo Faro 180°, D1 de cada uno queda a la misma altura que
  Q2 del otro ([colocación de los dos Faros](faronet-facing-layout.svg)).
- **Bloques de izquierda a derecha:** LEDs (columnas 3–14), pánico (18–20),
  trimpot RV1 apartado (40–42), LM393 (48–53) y emisor (56–63). 26 jumpers
  en lugar de 35.
- **Errores ya vistos:** el validador rechaza Q1, D1 o Q2 invertidos, el
  botón girado 90°, un cable una columna corrido, una pieza sobre un agujero
  ocupado y cualquier extremo en F–J fuera de los tres puntos de referencia.

## Piezas con polaridad

- **Q1 2N2222:** C–B–E: mirando su cara plana, de izquierda a derecha,
  colector, base y emisor. Va en d59–d60–d61 con la cara plana hacia el canal
  central. Confirma la base con el modo diodo antes de insertarlo.
- **D1 LED IR:** ánodo (pata larga) en h62, cátodo en h63, lente a la derecha.
- **Q2 PT333:** emisor (pin 1, pata larga según Everlight) en c62, colector en
  c63, lente a la derecha.
- **U1 LM393:** muesca a la derecha; pin 1 en e53 y pin 8 justo debajo.
- **D2/D3:** pata larga en c7/c14, pata corta en el riel GND de arriba.
- **C1 100 µF:** franja (−) en el riel GND de abajo.
- **S1:** DTS-6 girado 90°; parejas internas 1–2 (GND, e20/f20) y 3–4
  (PANIC, e18/f18). En reposo e18–e20 no suenan; al pulsar, sí. La huella de
  6,5×4,5 mm requiere ajustar las patas a 7,62×5,08 mm sin forzar.
- **RV1:** vertical RM063 con extremos en d40 y d42 y cursor en c41. Su
  ranura de ajuste (donde entra el destornillador) mira hacia el canal
  central; la fila e frente a ella queda libre. Si es el horizontal RM065, el
  cursor va en b41, que queda libre para eso. Medir fuera del circuito:
  extremos ≈10 kΩ constantes, cursor variable.

Q1, Q2, D1, S1 y RV1 se comprueban con el multímetro antes de conectar la Pi.
El emisor IR sigue sin modelo exacto: R1 = 330 Ω es provisional, sujeto a la
corriente medida.

## Archivos

- `circuit-reference.json`: netlist y pines de la Pi (la autoridad eléctrica).
- `generate_layout.py`: coloca cada terminal y genera el SVG, la guía HTML y
  `layout-data.json`.
- `validate_layout.py`: regenera todo, comprueba el plano, inyecta errores
  conocidos para confirmar que se rechazan y escribe `validation-report.json`.

```bash
python3 validate_layout.py
```

La validación comprueba conexiones y reglas de colocación del modelo. Trata
A–E y F–J como clips separados en cada columna y cada riel como dos mitades
de 25 agujeros puenteadas. No acredita funcionamiento analógico, alcance,
velocidad ni BER. Medir tensiones y calificar el enlace antes de pasar el
circuito a perfboard o PCB soldada. Los cuerpos dibujados son ilustrativos,
no una plantilla mecánica a escala. Los PDFs consultados están en `sources/`.

Pi 2 Model B v1.1 y Pi 3 Model B usan el mismo header de 40 pines; las ocho
conexiones conservan sus pines físicos y números BCM.
