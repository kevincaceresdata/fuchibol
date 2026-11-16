# Rivalkit

Kit de reportes de rival ("rival reports") para clubes del fútbol argentino:
convierte partidos etiquetados a mano desde video en un PDF de 8 paginas A4,
listo para leer en minutos por un cuerpo tecnico.

Sirve dos propositos a la vez:

1. **Pie de portfolio**: un pipeline Python chico, probado y legible
   (validacion exhaustiva de CSV, agregacion, graficos, PDF, CLI, 66 tests).
2. **Herramienta de outreach semanal**: un comando produce el informe del
   proximo rival a partir de los CSV etiquetados.

## Como funciona

```
video (el analista etiqueta a mano) --> data/<match>/*.csv
   --> rivalkit.schema (valida) --> rivalkit.charts (agrega y dibuja)
   --> rivalkit.report (8 paginas A4) --> informe.pdf
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

El PDF tiene exactamente 8 paginas A4. Si falta algun dato obligatorio o un
CSV tiene errores, el comando lista todos los errores y **no escribe** el PDF.

## Comandos

| Comando | Que hace |
|---|---|
| `python -m rivalkit <carpetas> --notes notas.toml -o salida.pdf` | Genera el informe |
| `.venv\Scripts\python -m pytest` | Corre la suite completa (66 tests) |
| `.venv\Scripts\python scripts/make_example_data.py` | Regenera el dataset de ejemplo de forma identica (semilla fija) |
| `tools\tagger.html` + `scripts\tagger_export.py` | Etiquetado sobre video local: abri el HTML en el navegador, cargá el mp4, exportá `events_raw.json` y convertilo a `events.csv` con game_state calculado |

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
