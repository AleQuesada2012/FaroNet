# FaroNet: montaje revisado en protoboard

Abrir [faronet-breadboard-review.html](faronet-breadboard-review.html).
Contiene la comparación con los archivos recibidos, los dos planos,
tablas de conexiones, búsqueda por agujero/pieza, resaltado de redes,
exportación CSV, guías de orientación y pruebas de puesta en marcha.

**S1 y RV1 ya aparecen dentro del tablero (revisión 6).** Son huellas
candidatas: el equipo identifica tentativamente el botón como DTS-644R,
y AD8289 es el código MicroJPM del trimpot de 10 kΩ, no un fabricante.
La foto de referencia corresponde visualmente al estilo vertical RM063.
La sección «Botón y RV1» incluye un [detalle de contactos](faronet-button-trimpot.svg),
fuentes y pruebas de multímetro antes de conectar la Pi.

- S1: vista superior de ficha DTS-6 girada 90° horario. 1=e16 y 2=f16,
  GND; 3=e14 y 4=f14, PANIC. 1–2 y 3–4 son parejas internas permanentes;
  pulsar une ambas. El modelo valida esas uniones, sin cerrar el contacto
  en reposo. Huella original 6,5×4,5 mm frente a rejilla 7,62×5,08 mm:
  ajustar suavemente las porciones libres de las patas solo si es práctico.
  No forzar ni asumir que encaja sin ajuste. Si no asienta, usar jumpers.
- Pi físico18/GPIO24 ahora llega a **d14**, dejando e14 a S1.
- RV1 vertical RM063: extremo1=d43/VBIAS, cursor2=c44/VTH,
  extremo3=d45/GND; ajuste hacia j. Jumper b47↔b43 para VBIAS.
  R6 ahora termina en e44; jumper a44↔a36 para VTH.
- Si la pieza real es el RM065 horizontal de la otra ficha, colocar solo
  el cursor en **b44** en lugar de c44; el clip y el resto del circuito
  son los mismos. El plan principal dibuja únicamente el estilo vertical.
- Se eliminan los cinco jumpers a terminales externos y se añade uno local:
  ahora hay 35 jumpers básicos o 42 con RGB por Faro.

Verificar las parejas liberadas/pulsadas de S1 y los extremos/cursor de RV1
fuera del circuito. Los números de las fichas pueden no estar impresos.
Para RV1, extremos ≈10 kΩ constantes al girar; cursor–extremo variable.
No se presupone sentido de giro. Los PDFs de fabricante consultados están
en `sources/`, con sus enlaces de procedencia en la guía y el netlist.

**Pi 2 Model B v1.1 y Pi 3 Model B usan el mismo header de 40 pines.**
Todas las conexiones del Faro conservan sus pines físicos y números BCM.
Los dos SVG están rotulados «Raspberry Pi 2/3 B» y la sección «Pi 2 / Pi 3»
de la guía compara las once conexiones, incluidos RGB y alimentación.
No se modifica el cableado ni la lista de componentes por este cambio de Pi.
La revisión de sistema operativo, librerías y temporización queda para
la fase de software; esta actualización solo aclara el hardware.

**Frente óptico hacia el este (revisión 4):** Q2/PT333 va ahora con E en
c60 y C en c61; D1 mantiene A en i60 y K en i61. Ambos cuerpos se orientan
horizontales, con sus lentes hacia la derecha y el frente despejado.
Q2 deja c40/c41; c41 ahora es el extremo local de un jumper SENSE desde
b61. Su tierra se lleva de a60 a TG:49. R4 y el LM393 mantienen sus lugares.
Se añade un jumper por Faro; valores, GPIO y componentes no cambian.

[Colocación de los dos Faros](faronet-facing-layout.svg): construir ambos
con el mismo plano, girar el segundo montaje completo 180° y alinear cada
D1 con el Q2 del otro Faro a la misma altura. Los bordes plásticos no
determinan por sí solos la alineación de las lentes. La guía incluye el
detalle de montaje y distingue orientación de lente de dirección de luz.

- [Básico, sin RGB](faronet-breadboard-basic.svg): un Faro por protoboard.
- [Básico más RGB](faronet-breadboard-rgb.svg): mismo núcleo, añade tres
  resistencias de 1 kΩ y un RGB de cuatro patas, **cátodo común confirmado
  por el equipo**. L1 rojo, L2 común/GND, L3 verde, L4 azul, conservando
  la orientación usada durante la prueba. En el tablero van a d23–d26.
  GPIO5/físico29, GPIO6/físico31 y GPIO13/físico33 controlan rojo, verde
  y azul a través de R13/R14/R15. HIGH enciende y LOW apaga.
  U2/LS125, C4 y R16–R18 ya no se montan. El DL410 queda fuera.

La revisión conserva los GPIO y las funciones del circuito anterior.
`circuit-reference.json` registra esa referencia con la actualización del
RGB de cátodo común identificado por el equipo. No cambia los archivos
recibidos. Los HTML anteriores llevan un aviso de que su RGB con LS125
está sustituido por esta revisión. El inventario y la identificación del
equipo prevalecen sobre las suposiciones de los documentos recibidos.

El circuito RGB usa las salidas de 3,3 V; nunca 5 V con este cableado.
Inicializar las tres salidas en LOW antes de probar colores. Repetir la
identificación con el otro RGB antes de usarlo en el segundo Faro.

`layout-data.json` contiene direcciones, piezas y cables. El modelo trata
a–e y f–j como clips separados en cada columna, y los cuatro rieles como
dos mitades de 25 agujeros que se puentean. Las direcciones de riel
(T3/TG/B5/BG) se cuentan por separado de las columnas 1–63.

W04 une **TG:4 con BG:4**, exclusivamente GND superior e inferior.
Su trazado visual rodea el borde izquierdo para no aparentar conexiones
con otros agujeros. T3:4 (+3,3 V) y B5:4 (+5 V) no reciben este jumper.
Las conexiones eléctricas y cantidades no cambian por este ajuste visual.

`validation-report.json` registra las comprobaciones de continuidad y
rechazo de errores deliberados. Para regenerar y comprobar, ejecutar
`python3 validate_layout.py` desde esta carpeta. Solo se ejecuta nuestro
generador, nunca el recibido de terceros.

La validación comprueba conexiones del modelo. No acredita funcionamiento
analógico, alcance, velocidad ni BER. Contrastar el tablero y los terminales
reales, medir tensiones/corrientes y calificar el enlace antes de trasladar
el circuito a perfboard/PCB soldada. Los cuerpos dibujados son ilustrativos,
no una plantilla mecánica a escala.

Q1 usa E–B–C según la orientación indicada por el equipo, cara plana hacia j.
PT333 usa pin1 emisor/largo y pin2 colector/corto según Everlight; comprobar
que corresponde a las piezas reales. El emisor IR sigue sin modelo exacto:
primera prueba con 1 kΩ; 330 Ω es provisional, sujeto a corriente medida.
