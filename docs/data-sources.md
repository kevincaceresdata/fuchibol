# Fuentes de datos

Estado verificado el **2026-11-13**, para la muestra Godoy Cruz F32-F36
(Primera Nacional 2026). El kit solo consume lo que el analista etiqueta a
mano desde video; esta nota registra de donde sale ese video y que otras
fuentes publicas existen para contrastar.

## Video de los partidos

**LPF Play (oficial de AFA).** Unica fuente con imagen oficial de Primera
Nacional. Desde el 15/10/2026 la cobertura completa requiere Plan Plus
(~ARS 15.000/mes). Disponibilidad de repeticiones on-demand de fechas
anteriores: verificar dentro de la plataforma con usuario.

**Streams de YouTube no oficiales: verificados NO utilizables para
etiquetado.** El 2026-11-13 se inspeccionaron frames de los cinco partidos
de la muestra y sus alternativas:

- SomosGodoyCruz ("EN VIVO CON IMAGENES", F32 y F34): transmision de radio
  con imagen de cabina y tribuna; sin imagen de juego.
- El Ascenso x3 (F33 y F36): camara fija hacia tribuna; el campo ocupa una
  fraccion inferior del cuadro y los jugadores no permiten ubicar zonas.
  En F36 ademas se superpone otro partido en pantalla.
- Stream oficial del club (F33): relato en vivo desde un bar.
- "Backup" F34 (canal de la liga): resumen oficial de ~4 minutos.
- Backup F36 (Argentina FC / Ascenso Mirasol): noticiero web con
  formaciones en grafico.
- Backup F32: highlights oficiales de 3-4 minutos.

Conclusion: ningun stream gratuito de esta muestra permite etiquetar la
cuadricula de 18 zonas. Riesgo adicional habitual de estos canales: bajas
por copyright. Etiquetar pronto si se los usa para contexto.

## Sitios de datos publicos (consulta manual solamente)

El kit no incluye scrapers y este proyecto no copia datos de estos sitios;
la consulta es manual, para contrastar totales (goles, cambios, tarjetas)
antes de enviar un informe.

| Sitio | Que expone para Primera Nacional (verificado 2026-11-13) |
|---|---|
| Sofascore | Marcador, alineaciones, cambios con minuto, tarjetas, algunos remates ("off target"), penales perdidos, rachas. |
| FotMob | Igual que Sofascore; sus fichas de liga listan estadisticas Opta: posesion, remates, corners, grandes chances y **xG**. |
| ESPN / TyC Sports | Marcador, goleadores, formaciones y minuto a minuto narrado. |
| ScoreBat | Highlights oficiales por gol. |

Implicacion para el informe: los datos publicos **si** cubren eventos basicos
con minuto, y FotMob ya publica xG de la categoria. La nota de limitaciones
del PDF se redacta en consecuencia: las metricas avanzadas no se informan
por decision metodologica (el etiquetado manual no las calcula), no porque
los portales no las publiquen.

## Terminos de servicio (pendiente)

Lectura manual de los ToS de Sofascore, FotMob y ESPN sobre scraping, reuso
y atribucion: **pendiente** (tarea 1.1 del plan, manual). Hasta que se
complete, la regla operativa es la del kit: consulta manual, sin copiar
datos, sin automatizacion.

## Fuentes del ejemplo

`data/example/` es 100% sintetico: generado por `scripts/make_example_data.py`
(semilla fija 2026), equipos y jugadores ficticios ("Atlético Ejemplo",
"Jugador 01"...). Se commitea para que el repositorio corra y se pueda
publicar sin datos reales. `data/real/` esta en `.gitignore` y nunca se
commitea.
