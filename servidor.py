"""
UI HTML "piola" para correr LOCAL (demos). Mismo cerebro que la app online (nucleo.py)
y mismo guardado (db.py / Supabase). Login por usuario + barra lateral estilo ChatGPT.

Correr:   python servidor.py   ->   http://localhost:8000
Config (secrets.toml en .streamlit/): OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, [usuarios].
"""
import os, json, secrets as _secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- Config desde secrets.toml ----------------
USUARIOS = {}
def _cargar_secrets():
    global USUARIOS
    p = os.path.join(HERE, ".streamlit", "secrets.toml")
    if not os.path.exists(p):
        return
    try:
        import tomllib
        with open(p, "rb") as f:
            data = tomllib.load(f)
        for k, v in data.items():
            if isinstance(v, dict):
                if k == "usuarios":
                    USUARIOS = {str(a): str(b) for a, b in v.items()}
            else:
                os.environ.setdefault(k, str(v))
    except Exception as e:
        print("No pude leer secrets.toml:", e)

_cargar_secrets()
import nucleo
import db

SESIONES = {}   # token -> usuario


def _a_canonico(mensajes):
    """HTML {rol,texto} -> canónico {role,content} (para guardar igual que Streamlit)."""
    out = []
    for m in (mensajes or []):
        out.append({"role": "user" if m.get("rol") == "u" else "assistant",
                    "content": m.get("texto", ""),
                    "mats": m.get("mats") or [], "query": m.get("query", "")})
    return out


def _a_html(mensajes):
    """Canónico {role,content} -> HTML {rol,texto} (para mostrar en el front)."""
    out = []
    for m in db.normalizar(mensajes):
        out.append({"rol": "u" if m["role"] == "user" else "a",
                    "texto": m["content"], "mats": m.get("mats") or [], "query": m.get("query", "")})
    return out


class H(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body, extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for h, v in (extra_headers or []):
            self.send_header(h, v)
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def _json(self, obj, code=200):
        self._send(code, "application/json", json.dumps(obj))

    def _usuario(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        tok = c["sesion"].value if "sesion" in c else ""
        return SESIONES.get(tok)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or "{}")

    # ---------- GET ----------
    def do_GET(self):
        if self.path == "/logo.png":
            try:
                with open(os.path.join(HERE, "logo.png"), "rb") as fp:
                    return self._send(200, "image/png", fp.read())
            except Exception:
                return self._send(404, "text/plain", "no logo")
        u = self._usuario()
        if self.path == "/" or self.path.startswith("/index"):
            if not u:
                return self._send(200, "text/html; charset=utf-8", LOGIN_PAGE)
            return self._send(200, "text/html; charset=utf-8", APP_PAGE.replace("__USUARIO__", u))
        if self.path == "/api/conversaciones":
            if not u:
                return self._json({"error": "no auth"}, 401)
            try:
                return self._json({"items": db.listar_conversaciones(u) if db.disponible() else []})
            except Exception as e:
                return self._json({"items": [], "error": str(e)})
        if self.path.startswith("/api/conversacion"):
            if not u:
                return self._json({"error": "no auth"}, 401)
            cid = self.path.split("id=", 1)[1] if "id=" in self.path else ""
            conv = db.cargar_conversacion(cid) if (cid and db.disponible()) else None
            if conv:
                conv["mensajes"] = _a_html(conv.get("mensajes"))
            return self._json(conv or {})
        return self._send(404, "text/plain", "no")

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/login":
            d = self._body()
            usr, pw = str(d.get("usuario", "")), str(d.get("clave", ""))
            if usr in USUARIOS and USUARIOS[usr] == pw:
                tok = _secrets.token_hex(16)
                SESIONES[tok] = usr
                return self._send(200, "application/json", json.dumps({"ok": True}),
                                  extra_headers=[("Set-Cookie", f"sesion={tok}; Path=/; HttpOnly; SameSite=Lax")])
            return self._json({"ok": False}, 401)

        u = self._usuario()
        if not u:
            return self._json({"error": "no auth"}, 401)

        if self.path == "/logout":
            c = SimpleCookie(self.headers.get("Cookie", ""))
            SESIONES.pop(c["sesion"].value if "sesion" in c else "", None)
            return self._json({"ok": True})

        d = self._body()
        if self.path == "/api/chat":
            hist = [{"role": "user" if m.get("rol") == "u" else "assistant", "content": m.get("texto", "")}
                    for m in d.get("historial", [])]
            resp, res, query = nucleo.responder(hist)
            return self._json({"respuesta": resp, "resultados": res, "query": query})
        if self.path == "/api/mas":
            res = nucleo.buscar(d.get("query", ""), 6, d.get("excluir", []))
            return self._json({"resultados": res})
        if self.path == "/api/armar":
            return self._json({"draft": nucleo.armar(d.get("fragmentos", []), d.get("canal", "posteo de Instagram"))})
        if self.path == "/api/guardar":
            if not db.disponible():
                return self._json({"conv_id": None, "titulo": None})
            msgs = _a_canonico(d.get("mensajes", []))
            cid = d.get("conv_id")
            try:
                if cid:
                    db.guardar_mensajes(cid, msgs)   # no pisa el título
                    return self._json({"conv_id": cid})
                titulo = nucleo.titular(msgs)
                cid = db.crear_conversacion(u, titulo, msgs)
                return self._json({"conv_id": cid, "titulo": titulo})
            except Exception as e:
                return self._json({"error": str(e)})
        if self.path == "/api/renombrar":
            db.renombrar(d.get("id"), d.get("titulo") or "Conversación")
            return self._json({"ok": True})
        if self.path == "/api/borrar":
            db.borrar_conversacion(d.get("id"))
            return self._json({"ok": True})
        return self._json({}, 404)

    def log_message(self, *a):
        pass


LOGIN_PAGE = r"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ingresar — Vivir Agradecidos</title><style>
*{box-sizing:border-box}body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#f4f2ee;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a}
.box{background:#fff;border:1px solid #ece7dd;border-radius:16px;padding:34px 30px;width:340px;text-align:center;box-shadow:0 6px 30px rgba(0,0,0,.06)}
.box img{width:56px;height:56px;margin-bottom:10px}
.box h1{font-size:18px;margin:0 0 4px}.box p{font-size:13px;color:#666;margin:0 0 20px}
.box input{width:100%;font-family:inherit;font-size:14px;padding:11px 13px;border:1px solid #ddd;border-radius:10px;margin:6px 0;outline:none}
.box input:focus{border-color:#F39C12}
.box button{width:100%;font-family:inherit;font-weight:bold;font-size:14px;color:#fff;background:#F39C12;border:none;padding:12px;border-radius:10px;cursor:pointer;margin-top:10px}
.box button:hover{background:#d98a0f}.err{color:#c0392b;font-size:12.5px;height:16px;margin-top:8px}
</style></head><body>
<div class="box"><img src="/logo.png" alt="logo"><h1>Asistente de contenido</h1><p>Vivir Agradecidos</p>
<input id="u" placeholder="Usuario" autocomplete="username">
<input id="p" type="password" placeholder="Contraseña" autocomplete="current-password">
<button onclick="entrar()">Entrar</button><div class="err" id="err"></div></div>
<script>
async function entrar(){
 const u=document.getElementById('u').value.trim(), p=document.getElementById('p').value;
 const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({usuario:u,clave:p})});
 if(r.ok){location.reload()}else{document.getElementById('err').textContent='Usuario o contraseña incorrectos.'}
}
document.getElementById('p').addEventListener('keydown',e=>{if(e.key==='Enter')entrar()});
</script></body></html>"""


APP_PAGE = r"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asistente de contenido — Vivir Agradecidos</title><style>
:root{--amber:#F39C12;--amber-d:#d98a0f;--tinta:#1a1a1a;--suave:#666;--linea:#ece7dd}
*{box-sizing:border-box}body{margin:0;height:100vh;display:flex;background:#fff;font-family:Arial,Helvetica,sans-serif;color:var(--tinta)}
/* Sidebar */
.side{width:270px;min-width:270px;height:100vh;background:#faf8f4;border-right:1px solid var(--linea);display:flex;flex-direction:column}
.side .top{padding:14px 14px 8px}
.nuevo{width:100%;font-family:inherit;font-size:13.5px;font-weight:bold;color:#fff;background:var(--amber);border:none;padding:11px;border-radius:10px;cursor:pointer}
.nuevo:hover{background:var(--amber-d)}
.lista{flex:1;overflow-y:auto;padding:6px 8px}
.lista .lbl{font-size:11px;color:#999;padding:8px 6px 4px;text-transform:uppercase;letter-spacing:.05em}
.item{position:relative;display:flex;align-items:center;border-radius:9px;cursor:pointer}
.item:hover{background:#efe9df}.item.activo{background:#f2e4cc}
.item .t{flex:1;padding:9px 10px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item .dots{opacity:0;border:none;background:none;color:var(--suave);font-size:17px;cursor:pointer;padding:6px 9px;border-radius:7px;line-height:1}
.item:hover .dots{opacity:1}.item .dots:hover{background:#e2dccf}
.menu{position:absolute;right:6px;top:34px;z-index:20;background:#fff;border:1px solid var(--linea);border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.12);min-width:150px;overflow:hidden;display:none}
.menu.open{display:block}
.menu button{display:flex;gap:8px;width:100%;text-align:left;font-family:inherit;font-size:13px;background:none;border:none;padding:10px 13px;cursor:pointer;color:var(--tinta)}
.menu button:hover{background:#f4f2ee}.menu button.del{color:#c0392b}
.side .foot{border-top:1px solid var(--linea);padding:10px 14px;display:flex;align-items:center;gap:8px;font-size:13px}
.side .foot .u{flex:1;font-weight:bold}
.side .foot a{color:var(--suave);text-decoration:none;font-size:12.5px;cursor:pointer}.side .foot a:hover{color:var(--amber-d)}
/* Main */
.main{flex:1;display:flex;flex-direction:column;height:100vh;overflow:hidden}
.head{display:flex;align-items:center;gap:12px;padding:16px 22px;border-bottom:1px solid var(--linea)}.head img{width:38px;height:38px}
.head .t{font-weight:bold;font-size:16px}.head .s{font-size:12px;color:var(--suave)}
.chat{padding:18px 26px;flex:1;overflow-y:auto}
.msg{margin:10px 0;display:flex}.msg.u{justify-content:flex-end}
.acol{max-width:760px;width:100%}
.bub{max-width:760px;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.5;white-space:pre-wrap}
.msg.a .bub{display:inline-block}
.msg.u .bub{background:var(--amber);color:#fff;border-bottom-right-radius:4px}.msg.a .bub{background:#f6f4f0;border-bottom-left-radius:4px}
.res{border:1px solid var(--linea);border-left:3px solid var(--amber);border-radius:10px;padding:11px 13px;margin:9px 0}
.res .tag{font-size:11px;font-weight:bold;color:var(--amber-d)}.res .ti{font-weight:bold;font-size:13.5px;margin:2px 0}
.res .q{font-size:13px;color:#333;font-style:italic;line-height:1.5}
.res .src{display:inline-block;font-size:12px;font-weight:bold;color:var(--amber-d);text-decoration:none;margin-top:6px}.res .src:hover{text-decoration:underline}
.mas{font-family:inherit;font-size:12px;color:var(--amber-d);background:#fff;border:1px solid var(--linea);border-radius:8px;padding:6px 12px;cursor:pointer;margin:2px 0 6px}.mas:hover{border-color:var(--amber)}
.gen{margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.gen select{font-family:inherit;font-size:12.5px;padding:8px;border:1px solid #ddd;border-radius:8px}
.gen button{font-family:inherit;font-size:13px;font-weight:bold;color:#fff;background:var(--amber);border:none;padding:9px 15px;border-radius:9px;cursor:pointer}.gen button:hover{background:var(--amber-d)}
.draft{margin-top:10px;border:1px dashed var(--amber);border-radius:10px;background:#fffdf8;padding:12px 14px;font-size:13px;line-height:1.6;white-space:pre-wrap}
.draft .lbl{font-size:11px;font-weight:bold;color:var(--amber-d);display:block;margin-bottom:6px}
.inbar{display:flex;gap:8px;padding:14px 22px;border-top:1px solid var(--linea)}
.inbar input{flex:1;font-family:inherit;font-size:14px;padding:12px 14px;border:1px solid #ddd;border-radius:10px;outline:none}
.inbar input:focus{border-color:var(--amber)}.inbar button{font-family:inherit;font-weight:bold;color:#fff;background:var(--amber);border:none;padding:0 18px;border-radius:10px;cursor:pointer}
</style></head><body>
<div class="side">
 <div class="top"><button class="nuevo" onclick="nueva()">➕ Nueva conversación</button></div>
 <div class="lista" id="lista"><div class="lbl">Tus conversaciones</div></div>
 <div class="foot"><span class="u">👤 __USUARIO__</span><a onclick="salir()">Salir</a></div>
</div>
<div class="main">
 <div class="head"><img src="/logo.png" alt="logo"><div><div class="t">Asistente de contenido <span style="color:#666;font-weight:normal">· Br. David</span></div><div class="s">Busca en el material real y arma borradores para cada canal</div></div></div>
 <div class="chat" id="chat"></div>
 <div class="inbar"><input id="q" placeholder="Escribí acá… (una idea, una duda, o pedí material sobre un tema)" autocomplete="off"><button onclick="enviar()">Enviar</button></div>
</div>
<script>
const chat=document.getElementById("chat"), lista=document.getElementById("lista");
let MENS=[], CONV=null;
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")}
const SALUDO='<div class="msg a"><div class="bub">Hola 👋 Contame en qué estás pensando y lo charlamos. Cuando quieras material de Br. David sobre un tema, pedímelo y te lo traigo con su fuente.</div></div>';

function cardHTML(x){return `<div class="res"><div class="tag">${esc(x.tag)} · ${esc(x.autor)}</div><div class="ti">${esc(x.titulo)}</div><div class="q">“${esc(x.texto).slice(0,180)}…”</div>${x.ir?`<a class="src" href="${esc(x.ir)}" target="_blank">Ver fuente ↗</a>`:""}</div>`}
function matsBloque(i){
 const m=MENS[i]; if(!m.mats||!m.mats.length) return "";
 let h='<div style="font-size:11px;color:#999;margin:10px 0 2px">Material encontrado:</div><div>'+m.mats.map(cardHTML).join("")+'</div>';
 h+=`<button class="mas" onclick="mas(${i})">Ver más opciones</button>`;
 h+=`<div class="gen"><select id="canal${i}"><option>posteo de Instagram</option><option>secuencia de 5 posteos de Instagram</option><option>newsletter</option><option>email (asunto y cuerpo)</option><option>mensaje de WhatsApp</option><option>artículo web</option></select><button onclick="armar(${i})">✨ Armar con esto</button></div><div id="draft${i}"></div>`;
 return h;
}
function render(){
 if(!MENS.length){chat.innerHTML=SALUDO;return}
 let html="";
 MENS.forEach((m,i)=>{
  if(m.rol==="u"){html+=`<div class="msg u"><div class="bub">${esc(m.texto)}</div></div>`}
  else{html+=`<div class="msg a"><div class="acol"><div class="bub">${esc(m.texto)}</div>${matsBloque(i)}</div></div>`}
 });
 chat.innerHTML=html; chat.scrollTop=chat.scrollHeight;
}
async function enviar(){
 const q=document.getElementById("q").value.trim(); if(!q)return;
 MENS.push({rol:"u",texto:q}); document.getElementById("q").value=""; render();
 const load=document.createElement("div"); load.className="msg a"; load.innerHTML='<div class="bub" style="color:#999">pensando…</div>'; chat.appendChild(load); chat.scrollTop=chat.scrollHeight;
 try{
  const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({historial:MENS})});
  const d=await r.json();
  MENS.push({rol:"a",texto:d.respuesta,mats:d.resultados||[],query:d.query||""});
  render(); guardar();
 }catch(e){load.remove(); alert("Error: "+e)}
}
async function guardar(){
 try{
  const r=await fetch("/api/guardar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({conv_id:CONV,mensajes:MENS})});
  const d=await r.json(); if(d.conv_id){CONV=d.conv_id} cargarLista();
 }catch(e){}
}
function nueva(){MENS=[];CONV=null;render();cargarLista();document.getElementById("q").focus()}
async function abrir(id){
 const r=await fetch("/api/conversacion?id="+encodeURIComponent(id)); const d=await r.json();
 MENS=d.mensajes||[]; CONV=id; render(); cargarLista();
}
async function cargarLista(){
 try{
  const r=await fetch("/api/conversaciones"); const d=await r.json();
  let h='<div class="lbl">Tus conversaciones</div>';
  (d.items||[]).forEach(c=>{
   const activo = c.id===CONV ? " activo":"";
   h+=`<div class="item${activo}"><div class="t" onclick="abrir('${c.id}')">${esc(c.titulo||"Conversación")}</div>`+
      `<button class="dots" onclick="menu(event,'${c.id}')">⋮</button>`+
      `<div class="menu" id="menu_${c.id}"><button onclick="renombrar('${c.id}',this)">✏️ Renombrar</button><button class="del" onclick="borrar('${c.id}')">🗑️ Borrar</button></div></div>`;
  });
  lista.innerHTML=h;
 }catch(e){}
}
function cerrarMenus(){document.querySelectorAll('.menu.open').forEach(m=>m.classList.remove('open'))}
function menu(ev,id){ev.stopPropagation();const m=document.getElementById("menu_"+id);const abierto=m.classList.contains("open");cerrarMenus();if(!abierto)m.classList.add("open")}
document.addEventListener("click",cerrarMenus);
async function renombrar(id){
 cerrarMenus();
 const nuevo=prompt("Nuevo nombre de la conversación:"); if(nuevo===null)return;
 await fetch("/api/renombrar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id,titulo:nuevo.trim()})});
 cargarLista();
}
async function borrar(id){
 cerrarMenus();
 if(!confirm("¿Borrar esta conversación?"))return;
 await fetch("/api/borrar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id})});
 if(id===CONV){nueva()}else{cargarLista()}
}
async function mas(i){
 try{
  const r=await fetch("/api/mas",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:MENS[i].query, excluir:MENS[i].mats.map(x=>x.doc)})});
  const d=await r.json(); MENS[i].mats=MENS[i].mats.concat(d.resultados||[]); render(); guardar();
 }catch(e){}
}
async function armar(i){
 const canal=document.getElementById("canal"+i).value;
 const dd=document.getElementById("draft"+i); dd.innerHTML='<div style="color:#999;font-size:12px;margin-top:8px">armando borrador…</div>';
 try{
  const r=await fetch("/api/armar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({canal:canal,fragmentos:MENS[i].mats})});
  const j=await r.json();
  dd.innerHTML='<div class="draft"><span class="lbl">Borrador — '+esc(canal)+' (para revisión del equipo)</span>'+esc(j.draft)+'</div>'; chat.scrollTop=chat.scrollHeight;
 }catch(e){dd.innerHTML='<div style="color:#c00;font-size:12px">Error al armar: '+e+'</div>'}
}
async function salir(){await fetch("/logout",{method:"POST"});location.reload()}
document.getElementById("q").addEventListener("keydown",e=>{if(e.key==="Enter")enviar()});
render(); cargarLista();
</script></body></html>"""

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("ATENCIÓN: falta OPENAI_API_KEY (ponela en .streamlit/secrets.toml).")
    if not USUARIOS:
        print("ATENCIÓN: no hay [usuarios] en secrets.toml — nadie va a poder entrar.")
    print("Cargando corpus…")
    nucleo.cargar()
    puerto = int(os.environ.get("PUERTO", "8000"))
    print(f"\n  Servidor local en http://localhost:{puerto}   (Ctrl+C para parar)\n")
    ThreadingHTTPServer(("0.0.0.0", puerto), H).serve_forever()
