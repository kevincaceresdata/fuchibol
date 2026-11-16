# Resumen de una pagina (one-page summary)

Documento de una pagina que acompaña al informe de muestra cuando se lo
entrega en mano o por email. Resume que es, como se hizo y que no es.
Espanol neutro, equipo-agnostic (los {{...}} se completan a mano).

---

## Informe de rival: {{RIVAL}} (muestra de {{N}} partidos)

**Que es.** Un PDF de 8 paginas A4 pensado para leer en minutos antes de un
partido: resumen ejecutivo, identidad y alineaciones, comportamiento con y
sin pelota, pelota parada, jugadores clave y plan de partido sugerido.

**Como se hizo.** Los ultimos {{N}} partidos de {{RIVAL}} se etiquetaron a
mano desde el video, evento por evento, con una cuadricula de 18 zonas. Un
kit propio (Python, codigo abierto, testeado) valida los datos, calcula las
agregaciones y compone el PDF en un comando. Las observaciones tacticas son
interpretacion del analista y se muestran separadas de los datos.

**Que no es.** No informa xG, xGA ni PPDA: no se calculan desde el
etiquetado manual, y cualquier metrica que los aproxima va marcada como
proxy con su definicion. La muestra es de {{N}} partidos; con menos de 5
el propio informe lo advierte. Los datos son de una sola persona, sin
verificacion cruzada, y deben validarse con el video antes de usarse.

**Siguiente paso.** Si el formato les sirve, la produccion es semanal:
para el lunes siguiente a cada fecha puedo entregar el informe del proximo
rival, con la profundidad de muestra que definan.

---

Notas de uso:

- Imprimir o exportar junto al PDF de muestra; nunca solo.
- Ajustar {{N}} al numero real de partidos etiquetados de la muestra.
