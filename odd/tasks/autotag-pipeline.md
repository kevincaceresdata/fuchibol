# Feature: autotag-pipeline

Pipeline completo: video de un partido → eventos validados → zonas medidas → informe PDF.
Marco: Spec-Driven Development (ver CAPABILITY-MAP.md en la raíz, que es el índice aprobado de módulos).
Logbook ODD: este archivo. Specs: SPEC-<module>.md en la raíz (una por módulo del mapa).

## Specs
Ver CAPABILITY-MAP.md (módulos: schema ✅ · detect · review · merge · tracking · report)

## Tasks
- [ ] Aprobación del capability map por Kevin (gate SDD)
- [ ] SPEC-detect.md → review
- [ ] SPEC-review.md → review
- [ ] SPEC-merge.md → review
- [ ] SPEC-tracking.md → review
- [ ] SPEC-report.md → review
- [ ] Implementación por módulo en orden de dependencias

## Log
L1 (2026-11-17): Kevin pidió "todo el proyecto dentro del marco SDD". Mapa de capacidades
creado en CAPABILITY-MAP.md. Investigación de validación: SoccerNet (eventos desde
transmisión ~50% mAP → fusión+hombre), SkillCorner (broadcast tracking comercial),
post básquet single-cam (mismo patrón que nuestro tracking), hackathon Barça/Metrica
(posesión automática 0.61 SpellF1 → la estimamos con heurísticas honestas).
Paralelo operativo: revisión de tiras del partido f36 (22 eventos revisados, barrido
de cobertura al ~50%), transcripción Whisper corriendo en local.
