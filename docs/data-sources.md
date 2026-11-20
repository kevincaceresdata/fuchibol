# Fuentes de datos y política de uso

## 1. Video de transmisión (fuente primaria)
- **Primera Nacional (Argentina):** transmisiones oficiales en 1920x1080 (LPF Play / TyC Sports Play).
- El video se procesa solo en local (`data/real/` y `*.mp4` están en `.gitignore`); ningún fotograma ni clip con derechos de transmisión se sube al repositorio.

## 2. Datos públicos de contraste (FotMob y Sofascore)
Verificación empírica sobre partidos de Primera Nacional 2026:

| Campo | FotMob (`matchDetails`) | Sofascore (`lineups` / `incidents` / `shotmap`) |
|---|---|---|
| Marcador y minutos de gol | Sí | Sí (con goleador) |
| Tarjetas y cambios | Minuto sin nombre en ascenso | Completo (`playerIn`, `playerOut`, minuto) |
| Alineaciones y dorsales | No disponible en varios partidos de ascenso | Completo (`substitute`, `jerseyNumber`, `position`, `minutesPlayed`) |
| Mapa de remates (`shotmap`) | No | Sí (`x` = % distancia al arco atacado, `y` = 0..100, `shotType`) |
| xG / PPDA | No confiable / ausente en ascenso | No se informa en el PDF de `rivalkit` |

## 3. Términos y límites
- El repositorio no redistribuye bases de datos de terceros: `data/example/` es 100 % sintético (`scripts/make_example_data.py`).
- Los escudos opcionales en `data/real/<partido>/assets/` provienen de Wikimedia Commons para uso educativo/no comercial, citados en portada y página 2, y están excluidos por `.gitignore`.
