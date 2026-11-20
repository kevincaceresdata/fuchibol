# Rivalkit

Kit de reportes de rival ("rival reports") para clubes del fútbol argentino:
convierte partidos etiquetados desde video (a mano o con el pipeline asistido
`rivalkit.detect` + `rivalkit.tracking`) en un PDF de 9 páginas A4 (portada +
8 secciones), listo para leer en minutos por un cuerpo técnico.

Sirve dos propósitos a la vez:

1. **Pie de portfolio**: un pipeline Python chico, probado y legible
   (validación exhaustiva de CSV, detección asistida, tracking YOLO +
   homografía, agregación, gráficos, PDF con identidad visual, CLI y tests).
2. **Herramienta de outreach semanal**: un comando produce el informe del
   próximo rival a partir de los CSV etiquetados.

## Cómo funciona

```
video.mp4 --> rivalkit.detect + rivalkit.tracking + tools/tagger.html
   --> events_raw.json --> scripts/tagger_export.py --> data/<match>/*.csv
   --> rivalkit.schema (valida) --> rivalkit.charts (agrega y dibuja)
   --> rivalkit.report (9 páginas A4) --> informe.pdf
```

Pipeline plano, un modulo por etapa, sin frameworks ni servicios. Los datos
se validan como texto antes de que pandas los toque: ninguna fila invalida
llega a un grafico, y todos los errores se reportan juntos con archivo,
fila y columna.

## Inicio rapido

Requisitos: Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
```

Generar el informe de ejemplo (equipos ficticios, datos sinteticos):

```powershell
.venv\Scripts\python -m rivalkit data/example/m* --notes data/example/notes.toml -o rival-report.pdf
```

El PDF tiene exactamente 9 páginas A4 (portada + 8 de contenido). Si la carpeta
del partido incluye `assets/logo.png` (y opcionalmente `assets/opponent_logo.png`),
el informe incorpora los escudos en la portada, banda superior y tarjeta del
partido. Si falta algún dato obligatorio o un CSV tiene errores, el comando
lista todos los errores y **no escribe** el PDF.

## Comandos

| Comando | Qué hace |
|---|---|
| `python -m rivalkit <carpetas> --notes notas.toml -o salida.pdf` | Genera el informe PDF (9 páginas A4) |
| `.venv\Scripts\python -m pytest -q` | Corre la suite completa de tests |
| `.venv\Scripts\python -m rivalkit.detect.pipeline --workdir DIR` | Fusiona marcador (`flips.json`), audio (`peaks.json`), relato (`transcript.jsonl`), tracking (`pitch_positions.csv`) y `shotmap.json` en `events_raw.json` |
| `.venv\Scripts\python scripts/make_example_data.py` | Regenera el dataset de ejemplo de forma idéntica (semilla fija) |
| `tools\tagger.html` + `scripts\tagger_export.py` | Etiquetado y revisión por tiras sobre video local: exporta `events_raw.json` y convierte a `events.csv` con `game_state` calculado |

Contrato de la CLI: exit 0 con el PDF escrito; exit 1 con todos los errores
listados y el output intacto si la entrada es invalida; exit 2 por uso
incorrecto de argumentos. Con menos de 5 partidos el informe sale igual, con
un aviso visible de muestra reducida.

## Formato de datos

Cada partido es una carpeta con `match.csv`, `events.csv` y `lineup.csv`.
La ubicacion se registra en una **cuadricula de 18 zonas** (6 bandas de
profundidad x 3 carriles), siempre desde la perspectiva del equipo analizado
y como si atacara de izquierda a derecha. El esquema completo, las
convenciones de minutos, los detalles permitidos por evento y los consejos
para etiquetar en Excel estan en `docs/tagging-guide.md`.

Las notas del analista viven en un solo `notes.toml` por informe: resumen
(identidad, debilidades, amenazas), plan de partido, observaciones por
seccion y jugadores clave. El texto se renderiza tal como esta escrito.

## Politica de datos

- Este repositorio **no contiene** video, datos scrapeados ni datos de
  clubes reales. El dataset de ejemplo es sintetico y commiteado; los datos
  reales van en `data/real/`, que esta en `.gitignore`.
- Los sitios de datos publicos se consultan solo manualmente; el kit no
  incluye scrapers. Ver `docs/data-sources.md`.
- Toda metrica que necesite datos de evento completos se muestra como
  **proxy** (indicador aproximado) y con su definicion. El informe nunca
  informa xG, xGA ni PPDA.

## Limitaciones del enfoque

Los datos se etiquetan a mano por una sola persona, sin verificacion cruzada;
las ubicaciones son zonas de una cuadricula, no coordenadas; y el informe
describe solo la muestra analizada. El PDF lleva esta nota siempre, en la
pagina 8, sin opcion de omitirla.
