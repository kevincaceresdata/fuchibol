# Feature: autotag-pipeline

Pipeline completo: video de un partido → eventos validados → zonas medidas → informe PDF.
Marco: Spec-Driven Development (ver CAPABILITY-MAP.md en la raíz, que es el índice aprobado de módulos).
Logbook ODD: este archivo. Specs: SPEC-<module>.md en la raíz (una por módulo del mapa).

## Specs
Ver CAPABILITY-MAP.md (módulos: schema ✅ · detect · review · merge · tracking · report ✅)
SPEC-report.md ✅ escrito e implementado (portada + 8 páginas, branding, tablas).

## Tasks
- [x] Capability map en uso (aprobación de facto: Kevin trabajó sobre él sin objeciones)
- [x] SPEC-report.md escrito, implementado y commiteado
- [x] Tagger v2 probado por Kevin (bugs encontrados y corregidos por uso real)
- [ ] Mover pipeline autotag de %TEMP% al repo (src/rivalkit/detect/) + SPEC-detect.md
      scripts en C:\Users\k3vca\AppData\Local\Temp\opencode\autotag\: analyze.py (diff/peaks/sheet),
      classify_digits.py, strips.py, matrix.py, transcribe.py, merge_shotmap.py, goal analysis
- [ ] Revisión humana de Kevin: PENDIENTES_REVISION.md (5 puntos; el penal del 56' primero)
- [ ] PDF definitivo: acentos en textos del report ("Condicion" → "Condición" etc.)
- [ ] Carta de presentación para Almagro + carpeta de entrega (PDF + carta + CV)
- [ ] Colab nocturno: tracking completo + Whisper large + cortes de cámara
- [ ] Ronda de 6 mails (Ferro, Morón, Temperley, T. Suárez, Godoy Cruz) con el PDF
- [ ] Merge/push de feat/almagro-report (decisión de Kevin)

## Log
L1 (2026-11-17): Kevin pidió "todo el proyecto dentro del marco SDD". Mapa de capacidades
creado en CAPABILITY-MAP.md. Investigación de validación: SoccerNet (eventos desde
transmisión ~50% mAP → fusión+hombre), SkillCorner (broadcast tracking comercial),
post básquet single-cam (mismo patrón que nuestro tracking), hackathon Barça/Metrica
(posesión automática 0.61 SpellF1 → la estimamos con heurísticas honestas).
Paralelo operativo: revisión de tiras del partido f36 (22 eventos revisados, barrido
de cobertura al ~50%), transcripción Whisper corriendo en local.
L2 (2026-11-18): Partido f36 taggeado y validado por 5 fuentes: marcador (flip de dígitos
exacto), audio (picos RMS), tiras de frames (22 eventos revisados: 4 borrados, 2 reclasif,
9 confirmados, 9 flaggeados + 3 córners nuevos del barrido), transcripción Whisper (108 hits,
"ES PENAL" del 56' + nombres) y APIs FotMob/Sofascore (alineaciones XI con minutos, golesadores
Gagliardi 6' / Orlando 43' / J.C. Vega 62', 4 tarjetas, shotmap fusionado → 40 eventos).
Arqueros resueltos: AGR amarillo (Acosta), ALM rosa. Dos Vegas (J.C. AGR #10 vs Facundo ALM #9).
Calibración: goles 3/3, pelotas paradas ~85%, remates abiertos ~40%.
L3 (2026-11-18): Informe 9 páginas con branding Almagro (azul #1B3C8C/negro): portada a página
completa con escudo real (Wikimedia), banda con escudo por página, hero card con marcador,
tablas reales (encabezado azul, zebra, "—"), solapamientos corregidos, escudos en assets/
(gitignored). Kevin: "se ve horrible" la tabla monospace → reemplazada por ax.table estilada.
PDF final: data/real/almagro-f36-agropecuario/Informe-Tecnico-Almagro-F36-Agropecuario.pdf
L4 (2026-11-19): Commits de unidad de trabajo en rama feat/almagro-report:
b57c7f8 (tagger v2 + player passthrough, 581 ins) y 34d83ec (branding + SDD artifacts, 469 ins).
Working tree limpio. Roadmap pendiente arriba. Para retomar: mem_search "autotag" +
leer este archivo + PENDIENTES_REVISION.md.
