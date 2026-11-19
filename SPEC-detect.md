# Spec: detect (módulo del mapa de capacidades)

## Objetivo
Pipeline de detección asistida y enriquecimiento de eventos a partir del video de transmisión
(1920x1080, LPF Play / TyC Sports Play), audio extraído y mapa de remates público (Sofascore).
Rescata al repositorio (`src/rivalkit/detect/`) los scripts del pipeline `autotag` sin rutas
locales hardcodeadas, con funciones puras testeables y CLI por submódulo.

## Comandos
```
Diff de marcador:     .venv\Scripts\python -m rivalkit.detect.analyze diff --workdir WORKDIR
Picos de audio:       .venv\Scripts\python -m rivalkit.detect.analyze peaks --workdir WORKDIR
Planilla de recortes: .venv\Scripts\python -m rivalkit.detect.analyze sheet --workdir WORKDIR st 1 2 3
Flips de dígitos:     .venv\Scripts\python -m rivalkit.detect.classify_digits --workdir WORKDIR
Tiras de 12 frames:   .venv\Scripts\python -m rivalkit.detect.strips --video MATCH.mp4 --events events_raw.json --out WORKDIR\strips
Transcripción:        .venv\Scripts\python -m rivalkit.detect.transcribe --audio WORKDIR\audio.wav --out-dir WORKDIR
Fusión de shotmap:    .venv\Scripts\python -m rivalkit.detect.merge_shotmap --shots shotmap.json --events events_raw.json
Matriz de zonas:      .venv\Scripts\python -m rivalkit.detect.matrix --events MATCH_DIR\events.csv -o MATCH_DIR\matriz_eventos.png
Análisis de goles:    .venv\Scripts\python -m rivalkit.detect.analyze_goals --lab-dir LAB_DIR
Test:                 .venv\Scripts\python -m pytest -q
```

## Estructura del proyecto (`src/rivalkit/detect/`)
- `__init__.py` — Re-exporta helpers puros del paquete `rivalkit.detect`.
- `analyze.py` — Detección de cambios en recortes del marcador (`diff_events`), picos de prominencia RMS en dB (`audio_peaks`) y hojas de contacto (`contact_sheet`).
- `classify_digits.py` — Clasificación por plantillas MSE de dígitos izquierdo/derecho del marcador (`build_templates`, `find_flips`) con suavizado modal (ventana 5).
- `strips.py` — Tiras de revisión humana-equivalente de 12 frames (`t-9..t+2` por evento, y barrido de cobertura cada 10 min) y mosaico de imágenes (`tile_images`).
- `transcribe.py` — Re-muestreo 8 kHz → 16 kHz en memoria (evita `decode_audio` de PyAV 19), transcripción con `faster-whisper` y filtrado de keywords de relato (`match_keywords`).
- `merge_shotmap.py` — Conversión de coordenadas Sofascore a las 18 zonas de `rivalkit` (`zone_for`), estimación de timestamp (`ts_for`) y fusión sin duplicar goles ni remates ya etiquetados (`merge_shots`).
- `matrix.py` — Matriz visual 6x3 de eventos por zona y equipo (`render_matrix`).
- `analyze_goals.py` — Cruce de tracking (YOLO + homografía) con muestreo HSV de camiseta/arquero (`team_of_patch`, `zone_of`, `analyze_goal_rows`).

## Estilo y contratos clave
```python
def zone_for(is_home: bool, x: float, y: float) -> int:
    """Sofascore x=% desde el arco atacado (0=línea de gol), y=0..100 → zona rivalkit 1..18."""
    band = int(x / 100 * 6) if is_home else int((100 - x) / 100 * 6)
    lane = 2 - min(2, max(0, int(y / 100 * 3)))
    return min(5, max(0, band)) * 3 + lane + 1
```
- **Imports perezosos (lazy imports):** `cv2` y `faster_whisper` solo se importan dentro de las funciones que abren video o modelo, para que la suite de tests corra sin GPU ni binarios pesados.
- **Cero rutas personales:** Ningún archivo bajo `src/rivalkit/detect/` contiene rutas absolutas de usuario (`C:\Users\...`); todo entra por argumentos de función o flags de CLI.

## Estrategia de testing
- Tests unitarios y de integración rápida en `tests/test_detect.py` con `pytest` y `tmp_path`.
- Se prueban con fixtures sintéticos: crops de marcador con cambio de dígito, WAV sintético con pico de amplitud, clasificación de plantillas y flips `0-0 → 1-0`, grilla de tiras, filtrado de keywords de relato, mapeo de zonas y fusión de `shotmap`, matriz 6x3 PNG y clasificación HSV + zona métrica (`105x68 m`).

## Boundaries
- **Always:** Correr `pytest -q` antes de commitear; mantener funciones puras separadas del I/O de video; codificación UTF-8 explícita al leer/escribir JSON y CSV.
- **Ask first:** Agregar dependencias obligatorias a `pyproject.toml` o cambiar la numeración de las 18 zonas de `schema.py`.
- **Never:** Hardcodear rutas de disco local, commitear videos/WAVs o datos de `data/real/`.

## Criterios de aceptación
- Los 7 submódulos existen en `src/rivalkit/detect/` sin rutas hardcodeadas.
- `tests/test_detect.py` cubre los algoritmos de cada submódulo y toda la suite pasa en verde.
- `src/rivalkit/report.py` tiene todos los acentos/tildes corregidos en español y referencia consistente a la página 9 de limitaciones.
