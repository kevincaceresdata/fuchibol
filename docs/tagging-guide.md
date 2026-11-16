# Guia de etiquetado

Como etiquetar un partido de principio a fin para que el kit lo acepte y
el informe sea honesto. Leela completa antes de etiquetar el primer partido.

## La idea en una frase

Miras el video del partido pausando en cada accion y anotas filas en
`events.csv` (lo que pasa) y `lineup.csv` (quien juega). Todo se registra
**desde la perspectiva del equipo analizado**: en `team`, `rival` es el
equipo del informe y `opponent` el otro.

## La cuadricula de zonas (la pieza clave)

6 bandas de profundidad (de tu arco al arco rival) x 3 carriles. La numeracion
corre por carril, de tu arco hacia el rival:

```
              arco propio                                arco rival
Carril izq      1     4     7     |     10     13     16
Carril centro   2     5     8     |     11     14     17   <- 17 ~ punto penal rival
Carril der      3     6     9     |     12     15     18
              campo propio (1-9)  |     campo rival (10-18)
```

Reglas que no se negocian:

- **Siempre como si el equipo analizado atacara de izquierda a derecha.**
  No inviertas las zonas en el segundo tiempo, aunque en el video el equipo
  juegue para el otro lado.
- Bandas y carriles se juzgan desde la posicion del balon, no desde donde
  mira la camara. Con pan de camara, fijate la referencia de las lineas del
  campo.
- Zonas 13-15: borde y media punta del area rival. Zona 17: punto penal
  rival. Zona 8: punto penal propio.

## Archivos por partido

Cada carpeta (`data/<partido>/`) tiene exactamente tres archivos.

### match.csv

Una sola fila de metadatos. Ya viene precargado en `data/real/`; no hace
falta tocarlo salvo correccion de marcador (el validador cruza sus goles
contra los `goal` de `events.csv`).

### events.csv

Columnas: `minute,event_type,team,zone,game_state,player,detail`

| Columna | Regla |
|---|---|
| `minute` | Entero 0-120. Reloj `mm:ss` se registra como `mm+1`. Descuento del 1er tiempo: `45`. Descuento del 2do y alargue: `91` o mas. |
| `event_type` | `shot` (remate que NO fue gol), `goal`, `corner`, `free_kick`, `penalty` (penal ejecutado), `recovery` (recuperacion en la zona indicada). |
| `team` | `rival` = equipo del informe, `opponent` = el otro. Siempre. |
| `zone` | Entero 1-18 segun la cuadricula, en direccion del ataque del equipo que hace el evento. |
| `game_state` | Resultado ANTES del evento, desde el equipo del informe: `winning` / `drawing` / `losing`. |
| `player` | Libre; puede quedar vacio. |
| `detail` | Opcional. Solo estos valores: gol `open_play`/`set_piece`/`penalty`/`own_goal`; remate `on_target`/`off_target`/`blocked`; corner y tiro libre `direct`/`crossed`/`short`. |

Convenciones:

- **Gol**: se anota una sola vez, como `goal`. Nunca tambien como `shot`.
- **Penal convertido**: dos filas — una `penalty` (si se quiere) mas una
  `goal` con `detail=penalty`.
- **Autogol**: `goal` con `detail=own_goal` y `team` = el equipo que se
  beneficia (así el cruce de goles da). Los autogoles no entran al mapa de
  remates.
- **Recoveries**: etiquetalas para los DOS equipos; alimentan el proxy de
  presion (recuperaciones del rival en zonas 10-18) y el volumen de
  recuperacion del rival.
- Los goles de `events.csv` deben coincidir con `rival_goals` /
  `opponent_goals` de `match.csv`; el validador lo cruza y lo dice.

### lineup.csv

Columnas: `player,shirt_number,position,starter,minute_in,minute_out`

- 11 titulares con `starter=true` y minutos vacios.
- Suplentes con `false` y `minute_in` del ingreso (y `minute_out` si salio).
- Un titular que sale: `minute_out` con `minute_in` vacio.
- `position` es texto libre (DF/MF/FW, o como lo use el club); el informe
  muestra la posicion mas frecuente por jugador.

## Flujo de trabajo sugerido por partido

1. **Antes de arrancar**: anota el 11 inicial en `lineup.csv` (sale de la
   previa o de la pantalla de formaciones).
2. **Pasada lineal del video**, pausando en cada evento. Atajos de vida en
   YouTube: espacio = pausa; flechas = ±5 s; `,` / `.` = frame a frame con
   el video pausado (oro para fijar la zona).
3. **Cambios**: anota minuto de entrada y salida apenas pasan; se olvidan
   despues.
4. **Validar**: corre el validador (abajo). Corrige y repite.
5. **Cronometra**: agrega una columna extra `tagging_minutes` si queres
   registrar cuanto te llevo (el lector ignora columnas desconocidas).
   Saber cuanto cuesta un partido decide si la cadencia semanal es viable.

## Validar

```powershell
.venv\Scripts\python -c "from pathlib import Path; from rivalkit.schema import load_matches; fs=[p for p in Path('data/real').iterdir() if p.is_dir()]; d=load_matches(fs); print(f'OK: {len(d.matches)} partidos, {len(d.events)} eventos')"
```

Todos los errores aparecen juntos, con archivo, fila y columna. Errores de
formato de fecha: usar `YYYY-MM-DD`.

## Consejos de Excel y Google Sheets

- El lector acepta CSV separado por comas o por `;`, en UTF-8 (ideal:
  "CSV UTF-8" de Excel) o cp1252; no pelees con la codificacion.
- Las celdas se recortan y los valores de enumeracion se aceptan en
  mayusculas (`TRUE`, `Home`), pero graba en minusculas para tu propia
  cordura.
- Data > Validacion de datos > Lista, con `shot,goal,corner,free_kick,penalty,recovery`
  y similares, evita el 90% de los errores de tipeo.
- Podes agregar columnas propias (`tagging_minutes`, `notas`); se ignoran.

## El archivo de notas (notes.toml)

Un solo archivo de notas por informe, en espanol neutro. Claves en ingles,
texto en espanol:

```toml
[summary]                       # REQUERIDO
identity = """Bloque medio 4-4-2, salida corta por la izquierda."""   # guia: hasta 2 renglones
weaknesses = ["...", "...", "..."]                                    # guia: hasta 3
threats = ["...", "...", "..."]                                       # guia: hasta 3

[plan]                          # REQUERIDO
instructions = ["...", "..."]
clips = ["m02 18:40 - presion tras saque de arco", "https://..."]     # opcional

[observations]                  # opcional, cualquier subconjunto de las 7 secciones
identity_and_lineup = "..."
in_possession = "..."
out_of_possession = "..."
set_pieces = "..."
key_players = "..."
match_plan = "..."
sources = "..."

[[key_players]]                 # opcional; la seccion siempre aparece en el informe
name = "Jugador 09"
note = "..."
```

Las caps ("hasta 2 renglones", "hasta 3") son orientacion de maquetado: el
kit nunca recorta ni rechaza texto mas largo; si algo se pasa de pagina,
el comando avisa por consola. El texto se imprime exactamente como esta.
