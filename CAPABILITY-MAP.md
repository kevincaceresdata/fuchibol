# Capability Map: autotag-pipeline

Pipeline completo: video de un partido → eventos validados → zonas medidas → informe PDF.
Este mapa es el índice aprobado de módulos; cada módulo tiene su SPEC-<id>.md.
Metodología: Spec-Driven Development (fases SPECIFY → PLAN → TASKS → IMPLEMENT, cada una con revisión humana).

| Module id | Responsibility | Depends on |
|---|---|---|
| schema | Contrato match/events/lineup + validación (ya existe en src/rivalkit, 66 tests) | — |
| detect | Video + audio → candidatos de eventos con evidencia: flips de marcador (exactos en goles), picos de audio, cortes de cámara, keywords de transcripción | schema |
| review | Confirmación humana: film strips por candidato, import/export en tools/tagger.html, veredictos → events_raw.json | detect |
| merge | Candidatos + veredictos + geometría de tracking → events.csv validado + corrections.log (aprendizaje de umbrales) | review, tracking |
| tracking | Posiciones de jugadores por frame (YOLO + homografía) → zonas medidas, fases de posesión, transiciones; modo local (clips) y modo Colab (partido completo) | schema |
| report | Extensión del reporte actual: matrices de zonas, diagramas de gol, anexos (tracking + frames) | merge |

Build order: schema (hecho) → detect → review → merge → tracking → report

Estado SDD: SPEC-report.md redactado e implementado (módulo report, branding incluido).
Los demás módulos se especifican al aprobar este mapa.

Notas:
- Ningún dato real se commitea: data/real/ sigue gitignoreado; el código es genérico para cualquier partido.
- El tagger.html actual se conserva como UI humana; review le suma las tiras.
- tracking depende de schema (zonas) pero no de detect; por eso puede construirse en paralelo a review/merge.

Referencias validadas (investigación 2026-11-17):
- SoccerNet (CVPRW 2018): detección de eventos desde transmisión sigue siendo problema abierto; modelo puro ~50% mAP. Justifica fusión de señales + confirmación humana.
- SkillCorner: tracking desde cámara única/broadcast es producto comercial usado por 350+ clubes (River, Racing). Valida tracking por broadcast.
- Qazi Ammar Arshad (LinkedIn 2026): pipeline básquet single-cam YOLO+ByteTrack+calibración; el desafío real son cortes de cámara y oclusiones.
- Hadi Sotudeh / Barça x Metrica hackathon: posesión automática desde tracking = 0.61 SpellF1 con data SkillCorner. Posesión es problema duro incluso pro; nuestro módulo la estima con heurísticas honestas. Dato útil: tiempo efectivo de juego (~48%). Repo: github.com/hadisotudeh/more-than-a-hack-2027. Dataset abierto SkillCorner + kloppy como ecosistema de referencia.
