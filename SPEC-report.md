# Spec: report (módulo del mapa de capacidades)

## Objetivo
Informe PDF A4 de 8 páginas, en español, listo para entregar a un club: datos del
etiquetado (events/lineup/match) + notas del analista (notes.toml), con identidad
visual del club analizado (rival). Debe poder generarse con un solo comando y verse
profesional impreso o en pantalla.

## Comandos
```
.venv\Scripts\python -m rivalkit MATCH_DIR --notes MATCH_DIR\notes.toml -o informe.pdf
Test: .venv\Scripts\python -m pytest -q   (66 tests)
```

## Estructura (9 paginas: portada + 8 de contenido)
0. Portada (fondo azul profundo, escudo, rival y marcador)
1. Resumen (hero del partido + lectura del analista + caja de datos de muestra)
2. Identidad y alineación (plantilla, local/visitante, observaciones)
3. Con pelota (mapa de remates por zona + goles por minuto/tipo/estado)
4. Sin pelota y transiciones (presión proxy + remates recibidos + goles en contra)
5. Pelota parada (mapas por zona y tipo, ofensiva/defensiva)
6. Jugadores clave (notas + datos de titularidades/minutos/goles)
7. Plan de partido (instrucciones numeradas + clips de referencia)
8. Fuentes y limitaciones (leyenda de zonas + partidos analizados)

## Sistema visual (decisiones de diseño aprobadas)
- Paleta en `charts.PALETTE`: azul Almagro `#1B3C8C`, azul profundo `#0E1E4E` (banda),
  celeste `#7C9BE0` (acentos), ámbar `#DF9A2E` (solo datos del oponente), neutros fríos.
- Banda de encabezado por página: título en blanco, subtítulo (club) celeste, filete
  celeste inferior, escudo del club en chip blanco a la derecha.
- Hero en página 1: escudos de ambos equipos + marcador + competencia/fecha/condición.
- Tablas: celdas con encabezado azul (texto blanco), rayado de filas, valores
  numericos alineados a la derecha, "—" para dato ausente; sin monospace.
- Barras: azul, valor sobre la barra, etiquetas rotadas 30°, texto secundario `#5B6472`.
- Cancha de zonas: cmap "Blues", celdas vacías `#EDF1F6`, bordes `#B9C2CE`.

## Convención de assets (sin cambios al CLI)
La carpeta del partido puede tener `assets/logo.png` (escudo del rival) y
`assets/opponent_logo.png` (escudo del oponente). Si no existen, el PDF se genera
igual sin escudos. Los escudos NO se commitean (carpeta gitignoreada); fuente:
Wikimedia Commons, uso educativo/no comercial, crédito en página 1.

## Boundaries
- Always: 9 paginas (portada + 8); tests en verde antes de entregar; textos en español
  neutro; nunca inventar datos (secciones sin datos muestran "Sin datos").
- Ask first: cambiar la estructura de 8 páginas, agregar dependencias nuevas.
- Never: commitear escudos o datos reales; usar logos con fines comerciales.

## Criterios de aceptación
- `python -m rivalkit ... -o` genera 9 paginas (portada + 8) sin errores.
- 66 tests en verde.
- Ningún solapamiento de títulos/etiquetas a 90 dpi.
- Con y sin assets/, el PDF genera.
