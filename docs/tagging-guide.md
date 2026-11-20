# Guía de etiquetado (`rivalkit`)

Cada partido vive en una carpeta con tres CSV en UTF-8 (`match.csv`, `events.csv`, `lineup.csv`) y opcionalmente `assets/logo.png` (escudo del equipo analizado) y `assets/opponent_logo.png`.

## Cuadrícula de 18 zonas (6 bandas x 3 carriles)

Siempre desde la perspectiva del equipo analizado (`rival`), atacando de izquierda a derecha en ambos tiempos:

```
              Banda 1   Banda 2   Banda 3   Banda 4   Banda 5   Banda 6
             (arco propio)                                    (arco rival)
Carril 1 (izq)    1         4         7        10        13        16
Carril 2 (cent)   2         5         8        11        14        17
Carril 3 (der)    3         6         9        12        15        18
```

- Zonas `1..9`: campo propio (`2` = área propia central).
- Zonas `10..18`: campo contrario (`17` = área rival central / punto penal; `13..15` = frontal del área).

## `match.csv` (exactamente 1 fila de datos)

Columnas: `match_id,date,rival_team,opponent,venue,rival_goals,opponent_goals,competition`

- `date`: `YYYY-MM-DD`
- `venue`: `home` | `away`
- `rival_goals`, `opponent_goals`: enteros `>= 0` (deben coincidir con los eventos `goal` de `events.csv`).

## `events.csv`

Columnas: `minute,event_type,team,zone,game_state,player,detail`

- `minute`: `0..120` (reloj `MM:SS` → minuto `MM + 1`).
- `event_type`: `shot` | `goal` | `corner` | `free_kick` | `penalty` | `recovery`
- `team`: `rival` | `opponent`
- `zone`: `1..18`
- `game_state`: marcador **antes** del evento desde la perspectiva de `rival` (`winning` | `drawing` | `losing`). `scripts/tagger_export.py` lo calcula solo desde `events_raw.json`.
- `detail` permitido por tipo (o vacío):
  - `goal`: `open_play` | `set_piece` | `penalty` | `own_goal`
  - `shot`: `on_target` | `off_target` | `blocked`
  - `corner` / `free_kick`: `direct` | `crossed` | `short`

## `lineup.csv` (exactamente 11 titulares `starter=true`)

Columnas: `player,shirt_number,position,starter,minute_in,minute_out`

- Titulares: `starter=true`, `minute_in` vacío, `minute_out` si salió.
- Suplentes: `starter=false`, `minute_in` con el minuto de ingreso (vacío si no entró).

## `notes.toml`

Secciones obligatorias: `[summary]` (`identity`, `weaknesses`, `threats`) y `[plan]` (`instructions`, opcional `clips`). Opcionales: `[observations]` (`identity_and_lineup`, `in_possession`, `out_of_possession`, `set_pieces`, `key_players`, `match_plan`, `sources`) y `[[key_players]]` (`name`, `note`). Si `name` coincide con `player` en `lineup.csv`, la página 7 agrega sus titularidades, minutos y goles automáticamente.
