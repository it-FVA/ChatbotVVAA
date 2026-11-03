"""Frase del día en la web (22/10; partida en routers por tema el 3/11, revisión 5.2 punto 13): el calendario anual (antes en el Panel admin de la app vieja). Misma lógica de
negocio: las reglas de rotación, reparto, foto de fondo y composición de la imagen están en programar_frases.py y db.py y se usan tal
cual (no se duplican); acá solo hay validaciones y la forma JSON que dibuja la pantalla `/frase-del-dia`.

Quién: aprobadores y admins (auth.aprobador; pedido de Franco 22/10: no es parte de Administración). El interruptor `frase_activa` y
la configuración de salida (hora, canales, foto por defecto, estilo, pie) son configuración: el interruptor se cambia desde acá solo
siendo admin; lo demás vive en Administración → Configuración (api/admin_rutas.py).

Rutas:
  GET   /frases/resumen                conteos, interruptor, hasta cuándo hay frases nuevas, qué pasa mañana, avisos (cabecera de frases_ui)
  GET   /frases/proximas?dias=14       un renglón por día: fecha, frase (o null) y estado
  GET   /frases/backlog?q=             validadas sin día y pendientes de validación (con buscador)
  GET   /frases/mes/{aaaa}/{mm}        las frases con fecha en ese mes
  GET   /frases/dia/{fecha}            la frase de ese día con su estado en la cola, si está en la cola/salió (cerrada) y la foto que usaría
  GET   /frases/{id}/previa.jpg        la imagen compuesta (programar_frases.componer con la foto de programar_frases.foto_de_fondo);
                                       ?foto=<url> la arma con esa otra foto sin guardar nada (probar / mostrar una propuesta)
  POST  /frases                        {texto, autor}: agregar una frase (validada, sin día)
  PATCH /frases/{id}                   {texto?, autor?, imagen_url?, estado?, estilo?, quitar_estilo?}: editar texto/autor, foto de fondo (null = la por
                                       defecto), saltar/reprogramar, y (2/11 noche) el diseño de la imagen propio de la frase (pisa el global)
  POST  /frases/{id}/mover             {fecha}: a otro día libre (también asigna una sin día); 409 si está ocupado
  POST  /frases/{id}/sacar             vuelve a «sin día»
  POST  /frases/intercambiar           {id_a, id_b}: se cambian la fecha (si una no tiene día, es «cambiar por otra»)
  POST  /frases/repartir               {modo: orden|azar, desde}: = «Repartir en el año»
  POST  /frases/vaciar                 {confirmo: true}: saca del calendario las que no salieron ni están en la cola
  PUT   /frases/activa                 {activa}: el interruptor (solo admins)
  PUT   /frases/canales                (2/11 tarde, aprobadores) {canales}: por qué canales sale cada día (la tarjeta «Mañana»; = config frase_canales)
  POST  /frases/manana/encolar         (2/11 tarde, aprobadores) encola la frase de mañana por los canales prendidos que falten (p. ej. después de frenarla)
  POST  /frases/manana/frenar          (2/11 tarde, aprobadores) cancela las piezas pendientes de mañana (la frase queda; se puede volver a encolar)
  GET   /frases/mail/estado            (26/10) el canal mail por Perfit: modo, qué falta, la lista, el envío de hoy/mañana y las últimas pruebas
  POST  /frases/mail/prueba            (aprobadores; 2/11 antes solo admins) {fecha?, emails?}: manda la frase de ese día a esos mails ahora
  GET   /frases/mail/previa/{fecha}    (2/11) el mail de ese día armado con la plantilla local (reproducción de la de Perfit): {html, contexto}
  GET   /frases/whatsapp/previa/{fecha} (2/11 tarde) el mensaje al grupo de WhatsApp tal cual saldría (prototipo: texto + imagen embebida, modo)

(2/11, reunión del 2/11) Los creadores de contenido también VEN el calendario (resumen, próximas, mes, día, backlog, vista previa:
auth.usuario_actual) y piden cambios; lo que modifica el calendario sigue siendo de aprobadores:
  GET   /frases/solicitudes            aprobador: las pendientes + las últimas resueltas; creador: las propias
  POST  /frases/solicitudes            {fecha, frase_id? | texto+autor?, imagen_url?, nota?}: «me gustaría que ese día salga esta frase»
                                       y/o «con esta foto de fondo» (2/11 tarde; la foto sola = cambiar la de la frase que ya está ese día)
  POST  /frases/solicitudes/{id}/aceptar   (aprobador) la aplica: crea la frase si es nueva, la mueve al día (o intercambia si está ocupado),
                                       guarda la foto propuesta en la frase
  POST  /frases/solicitudes/{id}/rechazar  (aprobador) {respuesta?}
  POST  /frases/solicitudes/{id}/retirar   (quien la pidió) la saca antes de que la resuelvan

Archivos (todos bajo el prefijo /frases):
  calendario.py   resumen, próximas, backlog, mes, día; crear, editar, mover, sacar, intercambiar, repartir, vaciar
  manana.py       activa, canales, manana/encolar, manana/frenar
  mail.py         mail/estado, mail/prueba, mail/previa/{fecha}
  solicitudes.py  solicitudes (listar, pedir, aceptar, rechazar, retirar)
  previas.py      {id}/previa.jpg, whatsapp/previa/{fecha}
  _comun.py       modelos y helpers compartidos (c._cfg, c._publica…)
Una solapa o una ruta nueva: un router chico acá (o una ruta en el que corresponda) y una línea en `router.include_router`.
"""
from fastapi import APIRouter

from . import calendario, mail, manana, previas, solicitudes

router = APIRouter(prefix="/frases", tags=["frases"])
# los routers con rutas fijas van antes que calendario, que tiene /{fid} (PATCH /{fid}, POST /{fid}/mover…)
for _r in (manana, mail, solicitudes, previas, calendario):
    router.include_router(_r.router)
router.add_api_route("", calendario.crear, methods=["POST"], status_code=201)   # POST /frases: agregar una frase
