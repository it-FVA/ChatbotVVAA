"""API HTTP del asistente de contenido · Vivir Agradecidos (fase 0, 21/10/2026).

Correr en local (desde la raíz del repo):   uvicorn api.main:app --reload
Documentación interactiva:                  http://127.0.0.1:8000/docs

Fase 0: login, sesión, chat con streaming y lecturas. Fase 1 (21/10, noche; api/recortes.py): «Mis recortes» con el editor
visual (editar, borrar, estilo por defecto). No publica ni aprueba todavía (fases 2 y 3 del plan
analisis/plan-interfaz-propia-2026-10.md, repo fva-transcripcion). Streamlit sigue en producción y no se toca.
"""
import os, json, logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import config, auth, roles as _roles, chat as _chat

log = logging.getLogger("api")
config.cargar()                      # variables de entorno (y secrets.toml en local) ANTES de importar nucleo/db
import nucleo                        # noqa: E402
import db                            # noqa: E402


@asynccontextmanager
async def _vida(app):
    """El corpus (fragmentos.jsonl + embeddings) se carga UNA vez al arrancar y queda en memoria del proceso."""
    if os.environ.get("API_CARGAR_CORPUS", "1") != "0":
        frs, _ = nucleo.cargar()
        log.info("Corpus cargado: %d fragmentos", len(frs))
    yield


app = FastAPI(title="Asistente · Vivir Agradecidos", version="0.2 (fase 1)", lifespan=_vida)

# (21/10, despliegue) La web en Vercel y la API en Render son dominios distintos: CORS con credenciales para los
# orígenes de CORS_ORIGENES (separados por coma). En local no se define y no hace falta (proxy de Vite).
_ORIGENES = [o.strip() for o in os.environ.get("CORS_ORIGENES", "").split(",") if o.strip()]
if _ORIGENES:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=_ORIGENES, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

from . import recortes as _recortes   # noqa: E402  (importa db: va después de config.cargar())
from . import cuentas as _cuentas     # noqa: E402  (22/10: usuarios, lista blanca, administración)
app.include_router(_recortes.router)
from . import chat_rutas as _chat_rutas   # noqa: E402  (22/10, fase 2: renombrar/borrar conversaciones, descargas, pedir recorte, pieza a borrador/aprobación)
app.include_router(_chat_rutas.router)
app.include_router(_cuentas.router)
from . import salud as _salud          # noqa: E402
app.include_router(_salud.router)
from . import proyectos as _proyectos   # noqa: E402  (22/10: carpetas colaborativas, compartir, «compartidos conmigo»)
app.include_router(_proyectos.router)


# ---------------- Modelos de entrada ----------------
class Login(BaseModel):
    usuario: str
    clave: str


class LoginGoogle(BaseModel):
    id_token: str


class Mensaje(BaseModel):
    texto: str
    stream: bool = False


# ---------------- Salud: GET /salud, /salud/servicios y /salud/historial viven en api/salud.py (22/10) ----------------


# ---------------- Login y sesión ----------------
@app.post("/login")
def login(datos: Login, resp: Response):
    """(22/10) Primero la tabla `usuarios` (hash); si no está ahí, la lista de secrets (transición)."""
    if not config.usuarios() and not db.disponible():
        raise HTTPException(503, "Falta configurar la lista de usuarios ([usuarios] en secrets o USUARIOS_JSON).")
    r = auth.login_clave(datos.usuario, datos.clave)
    if not r:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    usuario = r["usuario"] if isinstance(r, dict) else datos.usuario.strip()
    if isinstance(r, dict):
        db.marcar_login(r["id"])
    auth.emitir(resp, usuario, "clave")
    return auth.yo({"usuario": usuario, "origen": "clave"})


@app.post("/login/google")
def login_google(datos: LoginGoogle, resp: Response):
    email = auth.verificar_google(datos.id_token)
    fila, ok, rol_tabla, motivo = auth.admitir_google(email)
    if not ok:
        raise HTTPException(403, f"La cuenta {email} no está habilitada: no es del dominio de la Fundación ni está en la lista blanca. Pedile a un admin que la agregue.")
    usuario = fila["usuario"] if fila else email
    if fila:
        db.marcar_login(fila["id"])
    auth.emitir(resp, usuario, "google", rol_tabla)
    return dict(auth.yo({"usuario": usuario, "origen": "google", "rol_tabla": rol_tabla}), admitido_por=motivo)


@app.post("/logout")
def logout(resp: Response):
    auth.cerrar(resp)
    return {"ok": True}


@app.get("/yo")
def yo(s=Depends(auth.sesion)):
    return auth.yo(s)


# ---------------- Conversaciones ----------------
@app.get("/conversaciones")
def conversaciones(usuario=Depends(auth.usuario_actual)):
    """Como la barra lateral: [{id, titulo, actualizado}], más recientes primero, sin la papelera."""
    if not db.disponible():
        return []
    return db.listar_conversaciones(usuario)


@app.get("/conversaciones/{cid}")
def conversacion(cid: str, usuario=Depends(auth.usuario_actual), s=Depends(auth.sesion)):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay conversaciones guardadas.")
    r = _proyectos.conversacion_accesible(cid, usuario)      # (22/10) propia, o compartida conmigo (directo o por un proyecto)
    if not r:
        raise HTTPException(404, "No existe esa conversación (o no es tuya).")
    c, permiso = r
    c["compartida"] = None if permiso == "dueño" else {"por": c.get("usuario"), "permiso": permiso}
    c["mensajes"] = db.normalizar(c.get("mensajes"))
    idioma = config.idioma(usuario)
    for m in c["mensajes"]:
        if m.get("mats"):
            m["tarjetas"] = _chat.tarjetas(m["mats"], idioma, m.get("content", ""))
    return c


def _guardar(usuario, cid, titulo, mensajes):
    """Como app.guardar: crea (con título de nucleo.titular) o actualiza. Devuelve (id, titulo)."""
    if not mensajes or not db.disponible():
        return cid, titulo
    try:
        if cid:
            db.actualizar_conversacion(cid, titulo or "Conversación", mensajes)
            return cid, titulo
        titulo = nucleo.titular(mensajes)
        return db.crear_conversacion(usuario, titulo, mensajes), titulo
    except Exception as e:
        log.warning("No pude guardar la conversación: %s", e)
        return cid, titulo


def _sse(nombre, datos):
    return f"event: {nombre}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


@app.post("/conversaciones/{cid}/mensajes")
def mensaje(cid: str, datos: Mensaje, request: Request, usuario=Depends(auth.usuario_actual)):
    """Manda un mensaje. cid = 'nueva' abre una conversación nueva. Con stream=true (o Accept: text/event-stream)
    responde Server-Sent Events: estado → fuentes → pieza → texto (deltas) → fin {conversacion_id, titulo, mensaje}.
    Sin streaming, responde el JSON del evento fin."""
    texto = (datos.texto or "").strip()
    if not texto:
        raise HTTPException(400, "Falta el texto.")
    idioma = config.idioma(usuario)
    conv_id, titulo, mensajes = None, None, []
    if cid != "nueva":
        if not db.disponible():
            raise HTTPException(503, "Sin Supabase: no hay conversaciones guardadas.")
        r = _proyectos.conversacion_accesible(cid, usuario, editar=True)   # (22/10) compartida con permiso «editar» también
        if not r:
            raise HTTPException(404, "No existe esa conversación (o no es tuya, ni la tenés para editar).")
        c = r[0]
        conv_id, titulo, mensajes = c["id"], c.get("titulo"), db.normalizar(c.get("mensajes"))
    # (8/10, app.py) si el último mensaje de la persona es el mismo, no se duplica
    ultimo = mensajes[-1] if mensajes else None
    if not (ultimo and ultimo.get("role") == "user" and " ".join(ultimo.get("content", "").split()) == " ".join(texto.split())):
        mensajes.append({"role": "user", "content": texto})
    historial = _chat.historial_de(mensajes)
    nota = idioma if idioma != "es" else None

    def _cerrar(fin):
        m = {"role": "assistant", "content": fin["texto"], "mats": fin["mats"], "pieza": fin["pieza"]}
        mensajes.append(m)
        nuevo_id, nuevo_titulo = _guardar(usuario, conv_id, titulo, mensajes)
        return {"conversacion_id": nuevo_id, "titulo": nuevo_titulo, "texto": fin["texto"], "pieza": fin["pieza"],
                "query": fin["query"], "tarjetas": _chat.tarjetas(fin["mats"], idioma, fin["texto"]),
                "mensaje": m}

    quiere_sse = datos.stream or "text/event-stream" in (request.headers.get("accept") or "")
    if not quiere_sse:
        return _cerrar(_chat.responder(historial, nota, usuario))

    def _eventos():
        yield _sse("inicio", {"conversacion_id": conv_id, "titulo": titulo})
        try:
            for nombre, d in _chat.generar(historial, nota, usuario):
                if nombre == "fin":
                    yield _sse("fin", _cerrar(d))
                else:
                    yield _sse(nombre, d)
        except Exception as e:
            log.exception("chat")
            yield _sse("error", {"detalle": str(e)})

    return StreamingResponse(_eventos(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------- Mis publicaciones (los recortes están en api/recortes.py desde la fase 1) ----------------
GRUPOS = {"Pendientes": ("a_aprobar",), "Aprobadas": ("pendiente", "programada"),
          "Publicadas": ("publicada", "PUBLICADO", "draft", "lista"), "Borradores": ("borrador",),
          "Rechazadas": ("rechazada", "cancelada"), "Pruebas": ("prueba", "simulada", "simulado")}


@app.get("/publicaciones")
def publicaciones(request: Request, todos: bool = False, usuario=Depends(auth.usuario_actual)):
    """Como «Mis publicaciones» (publicar_ui.mis_publicaciones): las piezas de la persona con las solapas
    por estado. todos=1 (solo aprobadores): el registro completo (Panel admin → Registro)."""
    if todos:
        auth.aprobador(request)
        return {"piezas": db.listar_registro() if db.disponible() else [], "grupos": GRUPOS}
    if not db.disponible():
        return {"piezas": [], "grupos": GRUPOS, "solapas": {}}
    mias = [p for p in db.listar_mias(usuario) if p.get("estado") != "subida"]
    solapas = {"Todas": [p["id"] for p in mias]}
    for n, estados in GRUPOS.items():
        solapas[n] = [p["id"] for p in mias if p.get("estado") in estados]
    return {"piezas": mias, "grupos": GRUPOS, "solapas": solapas, "eliminables": list(db.ELIMINABLES)}


# ---------------- Autorizados (login con Google) ----------------
@app.get("/autorizados")
def autorizados(usuario=Depends(auth.aprobador)):
    """Lista de emails autorizados fuera del dominio (solo lectura por ahora; el alta desde el panel es de otra fase)."""
    if not db.disponible():
        return []
    try:
        return db.listar_autorizados()
    except RuntimeError as e:
        if "autorizados" in str(e):
            raise HTTPException(503, "Falta crear la tabla autorizados en Supabase (api/migraciones/autorizados_login_google.sql).")
        raise
