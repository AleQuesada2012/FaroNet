# Faro en perfboard (revisión 7, placa soldada)

Placa azul de 7 × 9 cm del equipo: una sola cara de cobre, 32 columnas
impresas × 24 filas, rieles en C7, C14, C21 y C28, y el resto en parejas de
dos agujeros por fila. Las piezas van por el lado impreso; se suelda por el
lado de cobre (el mismo patrón volteado de arriba abajo).

Cambios frente a la protoboard: R6 = 47 kΩ, R10 y R11 = 330 Ω, dos puentes
de GND (F1 y F24, C7 ↔ C28) más un segundo GND de la Pi (pin 9) al riel C28,
y la Pi se conecta con jumpers hembra cortados soldados a la placa.

D1 (F4–F5) y Q2 (F20–F21) salen por el borde derecho, a unos 4 cm entre sí;
sus filas centrales suman 25, así que un segundo Faro girado 180° queda
emisor frente a receptor. Cubrir D1 y Q2 con funda negra (termoencogible).

Abrir **[guia.html](guia.html)**: los dos lados dibujados, el montaje por
etapas con casillas, las pruebas de continuidad y aislamiento sin energía y
el primer encendido.

- `perfboard-componentes.svg`, `perfboard-cobre.svg`: los dos lados.
- `soldering-sheet.md`: la misma información en texto, con un mapa.
- `board.py`: modelo de la placa y validador; `layout.py`: la colocación;
  `check.py`: prueba la netlist y que se rechacen 13 errores típicos;
  `render.py` y `guide.py`: regeneran todo (`python3 guide.py`).
