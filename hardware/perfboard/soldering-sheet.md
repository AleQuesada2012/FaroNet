# Hoja de soldadura (generada por `guide.py`)

F = fila 1–24 desde el borde con los números impresos; C = columna 1–32 impresa.
Rieles: C7 GND, C14 3V3, C21 5V, C28 GND. Piezas por el lado impreso; se suelda
por el lado de cobre. «Puente de cobre» = alambre desnudo o pata cortada entre dos
pads vecinos del lado de cobre (no ocupa agujero). La guía con dibujos es `guia.html`.

## 1 · Alimentación y puentes de GND

| Qué | Dónde |
| --- | --- |
| C1 · 100 µF / 63 V | + → F11·C21, − → F11·C22 |
| Cable aislado GND | F1·C7 ↔ F1·C28 |
| Cable aislado GND | F24·C7 ↔ F24·C28 |
| Puente de cobre GND | F12·C22 ↔ F11·C22 |
| Cable de la Pi · pin 1 (3V3) | F23·C14 |
| Cable de la Pi · pin 2 (5V) | F23·C21 |
| Cable de la Pi · pin 6 (GND) | F23·C7 |
| Cable de la Pi · pin 9 (GND) | F2·C28 |

## 2 · LED verde y amarillo

| Qué | Dónde |
| --- | --- |
| R10 · 330 Ω | 1 → F3·C2, 2 → F3·C5 |
| D2 · LED verde TX | A → F3·C6, K → F3·C7 |
| R11 · 330 Ω | 1 → F6·C2, 2 → F6·C5 |
| D3 · LED amarillo RX | A → F6·C6, K → F6·C7 |
| Cable de la Pi · pin 15 (LED_TX) | F3·C1 |
| Cable de la Pi · pin 16 (LED_RX) | F6·C1 |

## 3 · Botón de pánico

| Qué | Dónde |
| --- | --- |
| S1 · Pulsador DTS-6 / DTS-644R candidato · verificar pieza | 1 → F10·C6, 2 → F13·C6, 3 → F10·C8, 4 → F13·C8 |
| R12 · 10 kΩ | 1 → F10·C14, 2 → F10·C9 |
| Puente de cobre GND | F10·C6 ↔ F10·C7 |
| Cable de la Pi · pin 18 (PANIC) | F13·C9 |

## 4 · Emisor IR

| Qué | Dónde |
| --- | --- |
| R1 · 330 Ω | 1 → F4·C21, 2 → F4·C29 |
| D1 · LED IR | A → F4·C32, K → F5·C32 |
| Q1 · 2N2222 A331 | C → F5·C31, B → F6·C31, E → F7·C31 |
| R3 · 10 kΩ | 1 → F6·C32, 2 → F7·C32 |
| R2 · 1 kΩ | 1 → F9·C29, 2 → F6·C29 |
| Puente de cobre IR_A | F4·C30 ↔ F4·C31 |
| Puente de cobre Q_BASE | F6·C31 ↔ F6·C30 |
| Puente de cobre GND | F7·C31 ↔ F7·C30 |
| Puente de cobre GND | F7·C29 ↔ F7·C28 |
| Cable de la Pi · pin 11 (TX) | F9·C30 |

## 5 · Receptor

| Qué | Dónde |
| --- | --- |
| U1 · LM393 DIP8 | 5 → F12·C23, 6 → F13·C23, 7 → F14·C23, 8 → F15·C23, 4 → F12·C26, 3 → F13·C26, 2 → F14·C26, 1 → F15·C26 |
| C2 · 100 nF / 50 V | 1 → F12·C21, 2 → F12·C22 |
| R5 · 4,7 kΩ | 1 → F16·C23, 2 → F16·C26 |
| R8 · 1 kΩ | 1 → F17·C23, 2 → F17·C24 |
| R6 · 47 kΩ | 1 → F16·C27, 2 → F17·C27 |
| RV1 · Trimpot 10 kΩ · AD8289 candidato / estilo RM063 | 1 → F19·C25, 2 → F18·C26, 3 → F19·C27 |
| R4 · 10 kΩ | 1 → F20·C25, 2 → F20·C30 |
| Q2 · PT333 | C → F20·C32, E → F21·C32 |
| R9 · 2,2 kΩ | 1 → F22·C25, 2 → F22·C28 |
| C3 · 100 nF / 50 V | 1 → F23·C25, 2 → F23·C28 |
| Cable aislado 3V3 | F16·C14 ↔ F16·C22 |
| Cable aislado VTH | F13·C27 ↔ F18·C27 |
| Cable aislado SENSE | F14·C27 ↔ F20·C31 |
| Puente de cobre GND | F12·C23 ↔ F12·C24 |
| Puente de cobre GND | F12·C25 ↔ F12·C26 |
| Puente de cobre GND | F12·C27 ↔ F12·C28 |
| Puente de cobre 5V | F15·C22 ↔ F15·C21 |
| Puente de cobre VBIAS | F13·C23 ↔ F13·C24 |
| Puente de cobre VBIAS | F13·C24 ↔ F14·C24 |
| Puente de cobre VBIAS | F14·C24 ↔ F15·C24 |
| Puente de cobre VBIAS | F15·C24 ↔ F16·C24 |
| Puente de cobre VBIAS | F16·C24 ↔ F17·C24 |
| Puente de cobre VBIAS | F17·C24 ↔ F18·C24 |
| Puente de cobre VBIAS | F18·C24 ↔ F19·C24 |
| Puente de cobre VBIAS | F19·C24 ↔ F20·C24 |
| Puente de cobre VBIAS | F20·C24 ↔ F21·C24 |
| Puente de cobre VBIAS | F21·C24 ↔ F22·C24 |
| Puente de cobre VBIAS | F22·C24 ↔ F23·C24 |
| Puente de cobre 3V3 | F16·C22 ↔ F17·C22 |
| Puente de cobre OPT_RX | F15·C27 ↔ F16·C27 |
| Puente de cobre VTH | F17·C26 ↔ F18·C26 |
| Puente de cobre GND | F19·C27 ↔ F19·C28 |
| Puente de cobre SENSE | F20·C30 ↔ F20·C31 |
| Puente de cobre GND | F21·C31 ↔ F21·C30 |
| Puente de cobre GND | F21·C29 ↔ F21·C28 |
| Cable de la Pi · pin 13 (OPT_RX) | F15·C27 |

## Mapa (lado de componentes)

```
       1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16   17   18   19   20   21   22   23   24   25   26   27   28   29   30   31   32  
  1    ·    ·    ·    ·    ·    ·   GND   ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·   GND   ·    ·    ·    ·  
  2    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    9    ·    ·    ·    ·  
  3   15  R10.1(R10)(R10)R10.2D2.A D2.K   ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·  
  4    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·  R1.1  (R1) (R1) (R1) (R1) (R1) (R1) (R1)R1.2   ·    ·  D1.A 
  5    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·  Q1.C D1.K 
  6   16  R11.1(R11)(R11)R11.2D3.A D3.K   ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |  R2.2   ·  Q1.B R3.1 
  7    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |   (R2)  ·  Q1.E R3.2 
  8    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |   (R2)  ·    ·    ·  
  9    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |  R2.1  11    ·    ·  
 10    ·    ·    ·    ·    ·  S1.1  (S1)S1.3 R12.2(R12)(R12)(R12)(R12)R12.1  ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·  
 11    ·    ·    ·    ·    ·   (S1) (S1) (S1)  ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·  C1.+ C1.−   ·    ·    ·    ·    ·    |    ·    ·    ·    ·  
 12    ·    ·    ·    ·    ·   (S1) (S1) (S1)  ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·  C2.1 C2.2 IN2+  (U1) (U1) GND   ·    |    ·    ·    ·    ·  
 13    ·    ·    ·    ·    ·  S1.2  (S1)S1.4  18    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·  IN2−  (U1) (U1)IN1+  VTH   |    ·    ·    ·    ·  
 14    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·  OUT2  (U1) (U1)IN1− SENSE  |    ·    ·    ·    ·  
 15    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·   VCC  (U1) (U1)OUT1  13    |    ·    ·    ·    ·  
 16    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·   3V3   ·    ·    ·    ·    ·    ·    |   3V3 R5.1  (R5) (R5)R5.2 R6.1   |    ·    ·    ·    ·  
 17    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·  R8.1 R8.2   ·    ·  R6.2   |    ·    ·    ·    ·  
 18    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·  curso VTH   |    ·    ·    ·    ·  
 19    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·  extre(RV1)extre  |    ·    ·    ·    ·  
 20    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·  R4.1  (R4) (R4) (R4) (R4)R4.2 SENSEQ2.C 
 21    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·  Q2.E 
 22    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·  R9.1  (R9) (R9)R9.2   ·    ·    ·    ·  
 23    ·    ·    ·    ·    ·    ·    6    ·    ·    ·    ·    ·    ·    1    ·    ·    ·    ·    ·    ·    2    ·    ·    ·  C3.1  (C3) (C3)C3.2   ·    ·    ·    ·  
 24    ·    ·    ·    ·    ·    ·   GND   ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·    |    ·    ·    ·    ·    ·    ·   GND   ·    ·    ·    ·  
```

Validado: todas las redes de `circuit-reference.json` unidas y sin cortos; 13 errores típicos rechazados por `check.py`.
