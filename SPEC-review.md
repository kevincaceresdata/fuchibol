# Spec: review (módulo del mapa de capacidades)

## Objetivo
Herramienta de etiquetado y revisión manual de eventos (`tools/tagger.html`): un único archivo
HTML autocontenido, sin dependencias externas de JS, que corre en el navegador sobre el video
de la transmisión. El módulo `review` convierte los candidatos del pipeline autotag
(`rivalkit.detect.pipeline` → `events_raw.json`) en eventos confirmados con jugador y zona
medidos, y exporta en el navegador los tres entregables del flujo de trabajo sin pasar por
Python: JSON crudo, CSV con `game_state` y XML Nacsport/Once.

## Uso
```
Abrir:               tools/tagger.html (doble click; sin servidor ni build)
Cargar lineup:       botón "cargar lineup.csv" (header player,shirt_number,position,starter,minute_in,minute_out)
Importar candidatos: botón "cargar JSON" con el events_raw.json del pipeline
Revisar:             n/p siguiente/anterior · click en fila = editar in-place · ✓ confirmar · ✕ rechazar
Exportar:            Descargar events_raw.json · events.csv · XML Nacsport/Once
Test:                .venv\Scripts\python -m pytest tests/test_tagger_html.py -q
```

## Estructura
- Archivo único (`tools/tagger.html`): `<style>` + marcado + un `<script>` de JS plano (sin frameworks ni CDNs).
- Panel izquierdo: carga de video, transporte (±5s, frame, velocidad) y reloj de mitad `1T`/`2T`.
- Panel derecho: tipo (6 eventos) · equipo · jugador (input con `datalist` + chips de lineup) ·
  cancha de 18 zonas · detalle · minuto · filtros · lista de eventos con badge y acciones ·
  3 botones de exportación.
- Estado persistido en `localStorage`: `rivalkit_tagger_events`, `rivalkit_tagger_offsets`,
  `rivalkit_tagger_names` y `rivalkit_tagger_roster`.

## Contratos clave
- **Zonas:** grilla 6x3 con `band * 3 + lane + 1` (banda 0..5 de arco propio a ataque, carril
  0 arriba), etiquetas de dos dígitos `01..18` — idéntico a `schema.py`.
- **Eventos:** `{minute, ts, type, team, zone, detail, player, status}` con `type` en
  `shot|goal|corner|free_kick|penalty|recovery`, `player: (playerEl.value || "").trim()`
  siempre presente, y `status: "pending" | "confirmed"`: un candidato importado sin `status`
  queda `pending`; un evento manual o una actualización quedan `confirmed`.
- **Edición in-place:** click en una fila busca `video.currentTime = ev.ts`, pausa y carga el
  evento en el formulario (`editingIndex`); Enter actualiza `events[editingIndex]` sin
  duplicar (conserva `ts` salvo el botón "usar ts actual") y marca `status: "confirmed"`;
  Esc o "Nuevo evento" vuelven a modo alta.
- **Cola de revisión:** filtros `Todos`, `Pendientes`, `Goles`, `Remates`, `Pelota parada`
  (corner/tiro libre/penal o gol de pelota parada) y `Recuperos`; atajos `n`/`p` recorren la
  lista visible buscando el `ts` en el video; `p` sigue significando "penal" cuando no hay
  tipo elegido (compatibilidad v2).
- **lineup.csv:** se parsea validando el encabezado completo, se persiste en
  `rivalkit_tagger_roster` y puebla el `datalist` y los chips `#7 Nombre`; un chip elige al
  jugador y marca `draft.team = "rival"` si no había equipo elegido.
- **events.csv:** orden `(minute, ts)`; `game_state` desde la perspectiva del equipo del
  informe calculado ANTES de cada evento (`winning`/`drawing`/`losing`), incrementando el
  marcador después de cada `goal` acreditado a `team` (goles en contra incluidos) — igual que
  `scripts/tagger_export.py`; header `minute,event_type,team,zone,game_state,player,detail`.
- **XML Nacsport/Once:** `<file><ALL_INSTANCES><instance><ID>…</ID><start>…</start><end>…</end>
  <code>…</code><label>…</label></instance></ALL_INSTANCES></file>`, instancias ordenadas por
  `(minute, ts)`, `end = start + 5s`, `code` = tipo y `label` = equipo · tipo · zona ·
  jugador · minuto.

## Estrategia de testing
- `tests/test_tagger_html.py` (pytest) fija los contratos estáticos del archivo: ids de DOM y
  etiquetas exactas, mapa de atajos, fórmula de zonas, claves de `localStorage`, máquina de
  estados de edición, formato de fila (jugador, ts, badge ✓/?) y los tres formatos de
  exportación (header CSV, cálculo de `game_state`, fragmentos XML en orden).
- Al ser un HTML sin dependencias ni runtime de JS en CI, la verificación automatizada es
  estática (regex sobre el fuente); el comportamiento en navegador se valida manualmente con
  el video del partido.

## Boundaries
- **Always:** Mantener el archivo autocontenido (sin `<script src>`); codificación UTF-8;
  `player` y `status` en todo evento guardado; actualizar in-place sin duplicar; correr
  `pytest tests/test_tagger_html.py -q` antes de commitear.
- **Ask first:** Cambiar la numeración de las 18 zonas, el header de `events.csv` o el
  formato XML; agregar cualquier dependencia externa.
- **Never:** Rutas de disco personales dentro del HTML; perder eventos existentes al editar;
  commitear videos o datos de `data/real/`.

## Criterios de aceptación
- Campo `player` con autocompletado (`datalist`) y chips clicables cargados desde
  `lineup.csv`, persistidos en `localStorage`.
- Click en un evento lo carga en el formulario para edición in-place; Enter actualiza sin
  duplicar y marca `status: "confirmed"`; Esc/"Nuevo evento" vuelve a modo alta.
- Cola de revisión: badges ✓/?, botones ✓ (confirmar) y ✕ (rechazar/borrar), atajos `n`/`p`
  que buscan el `ts` en el video, y filtros rápidos sobre la lista.
- Exportación directa en navegador a `events_raw.json`, `events.csv` (con `game_state`
  idéntico a `scripts/tagger_export.py`) y `events_nacsport.xml`.
- `tests/test_tagger_html.py` en verde y las features v2 intactas (6 tipos, 18 zonas, atajos
  `s/g/c/f/p/r`, reloj `1T`/`2T`, persistencia en `localStorage`).
