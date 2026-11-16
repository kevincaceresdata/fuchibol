# Publicacion publica (public post)

Version publica para LinkedIn, pensada como pieza de portfolio abierta.
Se publica con el repositorio en publico y el PDF de muestra como
documento adjunto o carrusel de capturas. Espanol neutro.

---

Llevo {{TIEMPO}} trabajando en esto y hoy lo puedo mostrar: un kit propio
para producir informes de rival (opposition analysis) para clubes del
ascenso argentino.

La motivacion: en Primera Nacional, B Metro y Federal A hay analistas de
video, pero los datos publicos de la categoria son finos. Los cuerpos
tecicos valoran material corto, claro y honesto. Este kit convierte video
etiquetado a mano en un PDF de 8 paginas A4: mapa de remates por zonas,
goles por intervalo y estado del partido, pelota parada, alineaciones,
jugadores clave y plan de partido.

Decisiones que me costaron y valen la pena contar:

- Validacion exhaustiva de los CSV a mano: ningun dato mal cargado llega
  a un grafico, y todos los errores salen juntos con fila y columna.
- Sin xG ni PPDA: el video etiquetado no las calcula, y mentir con
  metricas bonitas destruye confianza. Lo que se aproxima va marcado como
  proxy, con su definicion.
- La nota de limitaciones es obligatoria en cada informe: muestra,
  metodologia y decisiones quedan declaradas ante quien lo lea.
- Todo el pipeline es codigo abierto, con tests (57) y datos de ejemplo
  sinteticos: el repositorio corre sin usar datos de ningun club real.

El repositorio: {{REPO_URL}}. El PDF de muestra esta adjunto.

Si trabajas en un club del ascenso y este formato te sirve, escribime.

#AnalisisDeDatos #Futbol #Ascenso

---

Notas de uso:

- Publicar solo cuando el repositorio este en publico y el README impecable;
  el post mira hacia el repo.
- Adjuntar el PDF o 3-4 capturas de paginas distintas del informe.
- No etiquetar clubes: el post es sobre el metodo, no sobre un cliente.
