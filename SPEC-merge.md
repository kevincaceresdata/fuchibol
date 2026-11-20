# Spec: merge (módulo del mapa de capacidades)

## Objetivo
Módulo plano `src/rivalkit/merge.py` (estilo `schema.py`/`tracking.py`, sin clases) que convierte
los candidatos del autotag revisados por el analista en los tres entregables finales: `events.csv`
validado con `game_state` calculado, el log de auditoría JSONL de correcciones humanas frente al
autotag (`corrections.jsonl`) y el XML de intercambio estándar para Sportscode / Nacsport /
Once Sport / LongoMatch. `scripts/tagger_export.py` pasa a ser una fachada CLI del módulo:
re-exporta el contrato (`EVENT_TYPES`, `TEAMS`, `DETAILS`, `convert = convert_events`) y agrega
los flags `-o/--out`, `--xml` y `--corrections` sin romper el uso posicional por defecto. Incluye
el soporte de recuperación (`recovery`) en el vocabulario de `rivalkit.detect.transcribe` y en la
clasificación de `rivalkit.detect.pipeline`.

## Comandos
```
CSV a stdout (por defecto):   .venv\Scripts\python scripts\tagger_export.py events_raw.json > events.csv
CSV a archivo:                .venv\Scripts\python scripts\tagger_export.py events_raw.json -o events.csv
XML Nacsport/Once Sport:      .venv\Scripts\python scripts\tagger_export.py events_raw.json --xml eventos.xml
Log de correcciones:          .venv\Scripts\python scripts\tagger_export.py events_raw.json --corrections autotag.json corrections.jsonl
Test del módulo:              .venv\Scripts\python -m pytest tests/test_merge.py -q
Suite completa:               .venv\Scripts\python -m pytest -q
```

## Estructura (`src/rivalkit/merge.py`)
- `EVENT_TYPES`, `TEAMS`, `DETAILS`, `CSV_FIELDS` — contrato compartido con
  `scripts/tagger_export.py` y `tools/tagger.html`; `recovery` es un tipo de evento de primera
  clase.
- `convert_events(rows)` — descarta candidatos con `status == "rejected"` o
  `verdict == "rejected"` **antes** de validar (una fila rechazada nunca puede fallar el export,
  aunque sus datos sean inválidos), valida `minute (0..120)`, `type`, `team`, `zone (1..18)` y
  `detail` con los mensajes de error exactos heredados de `scripts/tagger_export.py`, ordena por
  `(minute, ts)` y devuelve filas con las claves `CSV_FIELDS` en orden, incluido `game_state`
  (`"winning"` / `"losing"` / `"drawing"`, desde la perspectiva de `"rival"`, calculado antes de
  cada evento; el gol en contra se acredita al `team` que marca el tagger).
- `diff_corrections(before, after, match_window_s=8.0)` — auditoría del revisado contra el
  autotag: empareja cada evento de `after` con el candidato no usado más cercano de `before` en
  `ts` dentro de la ventana `match_window_s` (o mismo `minute` cuando falta `ts` en cualquiera de
  los dos), ignora las filas rechazadas de `after` (un candidato rechazado aparece como
  `"removed"`) y devuelve entradas `{"action", "ts", "minute", "changes"}` con `action` en
  `confirmed | modified | added | removed` y `changes[field] = {"before", "after"}` para los
  campos `type, team, zone, detail, player` que difieren (vacío en `confirmed`; todos los campos
  en `added`/`removed`, de modo que el log es autocontenido). Los `removed` se agregan al final,
  tras la cronología revisada.
- `write_corrections_log(before, after, out_path)` — escribe `diff_corrections` como JSONL (un
  objeto por línea) en `out_path` y devuelve la cantidad de entradas.
- `export_sportscode_xml(rows, out_path)` — filtra rechazados, acepta filas crudas (`type` +
  `ts`) o convertidas (`event_type`, sin `ts`) y escribe
  `<file><ALL_INSTANCES><instance>…` con `ID` secuencial, `start`/`end` en segundos de video con
  dos decimales (`ts` con ventana fija de 15 s; las filas convertidas sin `ts` se posicionan en
  `minute * 60`), `code` con el formato `MM EVENTO EQUIPO` (p. ej. `05 GOAL RIVAL`) y etiquetas
  `Minuto` (`5'`), `Zona` (`Zona 08`, dos dígitos), `Jugador` y `Tipo` (`type/detail`, o el tipo
  solo si no hay detail). Devuelve la cantidad de instancias escritas; los textos dinámicos se
  escapan con `xml.sax.saxutils.escape`.

## Estilo y contratos clave
```python
# rejected candidates never fail the export: the filter runs before validation
if _is_rejected(ev):
    continue
```
- Módulo plano sin clases: funciones puras; el único I/O es hacia las rutas `out_*` explícitas
  (se crean sus directorios padres si faltan).
- Los mensajes de error de validación se preservan byte a byte respecto de
  `scripts/tagger_export.py` (los tests comparan el mensaje completo, no un substring).
- `scripts/tagger_export.py` no valida por su cuenta: importa y re-exporta
  (`convert = convert_events`), de modo que `from scripts.tagger_export import convert` sigue
  siendo idéntico; el CSV a stdout solo se emite en el modo por defecto (sin `-o`, `--xml` ni
  `--corrections`) y los mensajes de estado de los flags van a stderr.
- `main(argv)` acepta `argv[0]` como nombre del script (forma `sys.argv`) o una lista de flags
  pura: si `argv[0]` empieza con `-` se parsea la lista completa.
- Recuperaciones: el vocabulario vive en `rivalkit.detect.transcribe` (`RECOVERY_WORDS`, incluido
  en `KEYWORDS` para que los segmentos se conviertan en candidatos) y
  `classify_commentary_type` lo consulta después de las pelotas paradas (`penal`, córner, tiro
  libre/falta) y de las palabras explícitas de remate (`remate`, `cabeza`, `ataj`, `palos`,
  `afuera`, `arco`) y antes del fallback `("shot", "")`.

## Estrategia de testing
- `tests/test_merge.py` con pytest y `tmp_path`: `game_state` antes de cada evento, orden
  `(minute, ts)`, claves `CSV_FIELDS` en orden, descarte de `status`/`verdict` rechazados
  (incluye una fila rechazada inválida que no debe fallar y el caso "todas rechazadas"), mensajes
  de error exactos parametrizados, diff de correcciones con los cuatro `action`, empareo por
  ventana inclusiva y configurable, empareo por minuto sin `ts`, log JSONL, XML desde filas crudas
  y convertidas, esqueleto vacío válido, y compatibilidad CLI (stdout por defecto, `-o`, `--xml`,
  `--corrections`, flags combinables y re-export del contrato).
- `tests/test_detect_pipeline.py` agrega: las keywords de recuperación en `KEYWORDS`,
  `classify_commentary_type` → `("recovery", "")`, la prioridad pelota parada > palabra de remate >
  recuperación > fallback, y `fuse_candidates` produciendo candidatos `recovery` desde el relato.

## Boundaries
- Always: pytest en verde antes de commitear; preservar los mensajes de error heredados y el
  contrato `from scripts.tagger_export import convert`; codificación UTF-8 explícita al
  leer/escribir JSON, CSV y XML.
- Ask first: cambiar los mensajes de error heredados, el esquema del XML, el ancho de la ventana
  de empareo por defecto (`8.0`) o la ventana de instancia (`15.0`).
- Never: rutas de disco hardcodeadas, commitear datos de `data/real/`, validar de nuevo dentro de
  `scripts/tagger_export.py`, o duplicar el vocabulario de recuperación fuera de
  `rivalkit.detect.transcribe`.

## Criterios de aceptación
- `src/rivalkit/merge.py` existe como módulo plano y `scripts/tagger_export.py` lo re-exporta.
- `python scripts\tagger_export.py events_raw.json > events.csv` produce exactamente el mismo CSV
  que antes; `-o`, `--xml` y `--corrections` funcionan y son combinables.
- `diff_corrections` distingue `confirmed | modified | added | removed` y su log JSONL es
  autocontenido.
- `tests/test_merge.py` y `tests/test_detect_pipeline.py` pasan en verde, con `recovery`
  soportado de punta a punta (KEYWORDS → clasificación → `convert_events` → XML).
