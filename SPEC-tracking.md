# Spec: tracking (módulo del mapa de capacidades)

## Objetivo
Módulo plano `src/rivalkit/tracking.py` (un solo archivo, estilo `schema.py`/`charts.py`/`report.py`)
que convierte un clip de transmisión en posiciones de jugadores medibles: tracking YOLO + ByteTrack
en píxeles, filtro de césped HSV, homografía a metros `105x68`, clasificación de camisetas
(árbitro / equipo oscuro / equipo claro) y ventana temporal que resume zona, ocupación del área y
arco más cercano. Re-exporta los helpers ya probados de `rivalkit.detect.analyze_goals`
(`W`, `H`, `zone_of`, `team_of_patch`, `analyze_goal_rows`) en lugar de duplicarlos.

## Comandos
```
Test del módulo:  .venv\Scripts\python -m pytest tests/test_tracking.py -q
Suite completa:   .venv\Scripts\python -m pytest -q
Uso programático (sin CLI propio; el orquestador S6 lo consume):
    from rivalkit.tracking import track_clip
    track_clip(Path("clip.mp4"), Path("tracks.csv"))
```

## Estructura (`src/rivalkit/tracking.py`)
- `is_grass(hsv_patch, min_green_fraction=0.15)` — fracción de píxeles verdes (hue 32..100,
  sat > 20, HSV de OpenCV con hue 0..180) que excede el umbral; valida que un recorte esté
  sobre césped y no sobre un plano o el público.
- `project_points(pixel_points, correspondences)` — homografía plana 3x3 por DLT/SVD (numpy
  puro) desde `>= 4` correspondencias `(x_px, y_px, x_m, y_m)`; proyecta cada punto de píxel a
  metros redondeados a 2 decimales.
- `classify_tracks(track_rgb_samples, track_hues=None)` — pista con hue mediana 5..22 =
  `"referee"`; el resto se separa por 2-means determinista (rng semilla 7) sobre el RGB medio:
  el centroide de menor suma de canales es `"dark_team"` y el otro `"light_team"`; con menos de
  2 pistas restantes no se etiqueta equipo.
- `window_zone(rows, frame_start, frame_end, team=None)` — filtra `frame` en la ventana
  (inclusiva), `class == "player"`, `0 <= x_m <= 105`, `0 <= y_m <= 68` (y `team` si se pide);
  devuelve `{"zone": moda de las zonas 1..18 (empate → mediana baja) | None, "count": filas que
  matchearon, "box_players": jugadores a <= 16.5 m de la línea de gol más cercana, "goal_end":
  lado ("L"/"R") del jugador más profundo | None}`.
- `track_clip(video_path, out_csv, model_path="yolov8s.pt", imgsz=960)` — importa `cv2`,
  `ultralytics.YOLO` y `supervision` solo dentro de la función; corre ByteTrack sobre personas
  (clase 0) y escribe `tracks.csv` con columnas `frame,track_id,class,x1,y1,x2,y2,x,y` donde
  `(x, y)` es el pie (centro inferior del bbox); devuelve la cantidad de frames procesados.

## Estilo y contratos clave
```python
# shortcut: callers pass one fixed calibration per camera angle instead of
# recalibrating per frame; recalibrate when the broadcast angle changes.
def project_points(pixel_points, correspondences): ...
```
- Imports perezosos: `cv2` / `ultralytics` / `supervision` solo dentro de `track_clip`, así la
  suite corre sin GPU ni pesos YOLO (los tests inyectan stubs vía monkeypatch).
- Sin CLI propio: se consume programáticamente; el orquestador del módulo `merge` (S6) lo llama.
- `class` es constante `"player"`: el filtro `classes=[0]` de YOLO deja solo personas.

## Estrategia de testing
- `tests/test_tracking.py` con pytest y `tmp_path`: parches HSV sintéticos (umbral de fracción,
  bordes de hue 32..100 y saturación > 20), correspondencias exactas (mapeo afín de esquinas
  1920x1080 → 105x68 y homografía proyectiva recuperada por DLT), muestras RGB/hue por pista
  (ventana de árbitro 5..22, 2-means determinista), filas de tracking sintéticas (moda y empate
  de zona, área, arco, filtro por equipo) y stubs de cv2/ultralytics/supervision para `track_clip`
  sin video ni pesos reales.
- Se verifica que importar `rivalkit.tracking` no arrastra `cv2`/`ultralytics`/`supervision`.

## Boundaries
- Always: pytest en verde antes de commitear; funciones puras separadas del I/O de video;
  reutilizar por re-exportación los helpers de `rivalkit.detect.analyze_goals`.
- Ask first: agregar dependencias obligatorias a `pyproject.toml` (cv2/ultralytics/supervision
  son opcionales y siguen fuera), cambiar la numeración de las 18 zonas.
- Never: commitear videos, pesos YOLO o datos de `data/real/`; descargar modelos dentro de la
  suite de tests.

## Criterios de aceptación
- `src/rivalkit/tracking.py` existe como módulo plano y re-exporta `W`, `H`, `zone_of`,
  `team_of_patch`, `analyze_goal_rows`.
- `tests/test_tracking.py` cubre `is_grass`, `project_points`, `classify_tracks`, `window_zone` y
  `track_clip` (con stubs) y pasa en verde.
