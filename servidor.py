"""
UI HTML "piola" para correr LOCAL (demos). Usa el mismo cerebro que la app online (nucleo.py).
Correr:   python servidor.py    ->   abrir http://localhost:8000
La API key la lee de .streamlit/secrets.toml (el mismo que usás para la app local).
"""
import os, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))


def _cargar_secrets():
    p = os.path.join(HERE, ".streamlit", "secrets.toml")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_secrets()
import nucleo  # después de cargar la key


class H(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, "text/html; charset=utf-8", PAGE)
        elif self.path == "/logo.png":
            try:
                with open(os.path.join(HERE, "logo.png"), "rb") as fp:
                    self._send(200, "image/png", fp.read())
            except Exception:
                self._send(404, "text/plain", "no logo")
        else:
            self._send(404, "text/plain", "no")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or "{}")
        if self.path == "/api/chat":
            hist = [{"role": "user" if m.get("rol") == "u" else "assistant", "content": m.get("texto", "")}
                    for m in data.get("historial", [])]
            resp, res, query = nucleo.responder(hist)
            self._send(200, "application/json", json.dumps({"respuesta": resp, "resultados": res, "query": query}))
        elif self.path == "/api/mas":
            res = nucleo.buscar(data.get("query", ""), 6, data.get("excluir", []))
            self._send(200, "application/json", json.dumps({"resultados": res}))
        elif self.path == "/api/armar":
            draft = nucleo.armar(data.get("fragmentos", []), data.get("canal", "posteo de Instagram"))
            self._send(200, "application/json", json.dumps({"draft": draft}))
        else:
            self._send(404, "application/json", "{}")

    def log_message(self, *a):
        pass


PAGE = r"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asistente de contenido — Vivir Agradecidos</title><style>
:root{--amber:#F39C12;--amber-d:#d98a0f;--tinta:#1a1a1a;--suave:#666;--linea:#ece7dd;--fondo:#f4f2ee}
*{box-sizing:border-box}body{margin:0;height:100vh;background:var(--fondo);font-family:Arial,Helvetica,sans-serif;color:var(--tinta)}
.wrap{max-width:100%;margin:0;height:100vh;padding:0}.card{background:#fff;border:none;border-radius:0;height:100vh;display:flex;flex-direction:column;overflow:hidden}
.head{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--linea)}.head img{width:38px;height:38px}
.head .t{font-weight:bold;font-size:16px}.head .s{font-size:12px;color:var(--suave)}
.badge{margin-left:auto;font-size:11px;font-weight:bold;color:var(--amber-d);background:#fdf1dd;border:1px solid #f6d9a6;padding:4px 9px;border-radius:20px}
.chat{padding:18px 24px;flex:1;overflow-y:auto}
.msg{margin:10px 0;display:flex}.msg.u{justify-content:flex-end}
.bub{max-width:760px;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.5}
.msg.u .bub{background:var(--amber);color:#fff;border-bottom-right-radius:4px}.msg.a .bub{background:#f6f4f0;border-bottom-left-radius:4px}
.res{border:1px solid var(--linea);border-left:3px solid var(--amber);border-radius:10px;padding:11px 13px;margin:9px 0}
.res .tag{font-size:11px;font-weight:bold;color:var(--amber-d)}.res .ti{font-weight:bold;font-size:13.5px;margin:2px 0}
.res .q{font-size:13px;color:#333;font-style:italic;line-height:1.5}
.res .src{display:inline-block;font-size:12px;font-weight:bold;color:var(--amber-d);text-decoration:none;margin-top:6px}
.res .src:hover{text-decoration:underline}
.mas{font-family:inherit;font-size:12px;color:var(--amber-d);background:#fff;border:1px solid var(--linea);border-radius:8px;padding:6px 12px;cursor:pointer;margin:2px 0 6px}.mas:hover{border-color:var(--amber)}
.gen{margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.gen select{font-family:inherit;font-size:12.5px;padding:8px;border:1px solid #ddd;border-radius:8px}
.gen button{font-family:inherit;font-size:13px;font-weight:bold;color:#fff;background:var(--amber);border:none;padding:9px 15px;border-radius:9px;cursor:pointer}
.gen button:hover{background:var(--amber-d)}
.draft{margin-top:10px;border:1px dashed var(--amber);border-radius:10px;background:#fffdf8;padding:12px 14px;font-size:13px;line-height:1.6;white-space:pre-wrap}
.draft .lbl{font-size:11px;font-weight:bold;color:var(--amber-d);display:block;margin-bottom:6px}
.inbar{display:flex;gap:8px;padding:14px 20px;border-top:1px solid var(--linea)}
.inbar input{flex:1;font-family:inherit;font-size:14px;padding:11px 14px;border:1px solid #ddd;border-radius:10px;outline:none}
.inbar input:focus{border-color:var(--amber)}.inbar button{font-family:inherit;font-weight:bold;color:#fff;background:var(--amber);border:none;padding:0 18px;border-radius:10px;cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:7px;padding:0 20px 14px}.chips span{font-size:12px;color:var(--suave);border:1px solid var(--linea);border-radius:20px;padding:5px 11px;cursor:pointer}
.chips span:hover{border-color:var(--amber);color:var(--amber-d)}.foot{font-size:11.5px;color:var(--suave);text-align:center;padding:12px 20px;border-top:1px solid var(--linea);background:#faf8f4}
</style></head><body><div class="wrap"><div class="card">
<div class="head"><img src="/logo.png" alt="Vivir Agradecidos"><div><div class="t">Asistente de contenido <span style="color:#666;font-weight:normal">· Br. David</span></div>
<div class="s">Busca en el material real y arma borradores para cada canal</div></div><div class="badge">demo local</div></div>
<div class="chat" id="chat"><div class="msg a"><div class="bub">Hola 👋 Contame en qué estás pensando y lo charlamos. Cuando quieras material de Br. David sobre un tema, pedímelo y te lo traigo con su fuente.</div></div></div>
<div class="chips" id="chips"><span>la gratitud como camino</span><span>el asombro</span><span>vivir el presente</span><span>donar tiempo al prójimo</span></div>
<div class="inbar"><input id="q" placeholder="Escribí acá… (una idea, una duda, o pedí material sobre un tema)" autocomplete="off"><button onclick="buscar()">Enviar</button></div>
<div class="foot">Fundado solo en el material real de la Fundación. Los borradores son para revisión del equipo.</div></div></div>
<script>
const chat=document.getElementById("chat");
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function card(x){return `<div class="res"><div class="tag">${esc(x.tag)} · ${esc(x.autor)}</div><div class="ti">${esc(x.titulo)}</div><div class="q">“${esc(x.texto).slice(0,180)}…”</div>${x.ir?`<a class="src" href="${esc(x.ir)}" target="_blank">Ver fuente ↗</a>`:""}</div>`}
function bub(role,html){const d=document.createElement("div");d.className="msg "+role;d.innerHTML='<div class="bub">'+html+'</div>';chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
let HIST=[]; let NRESP=0; let MATS={}; let QRY={}; let SHOWN={};
async function buscar(){
 const q=document.getElementById("q").value.trim(); if(!q)return;
 HIST.push({rol:"u",texto:q}); bub("u",esc(q)); document.getElementById("q").value="";
 const load=bub("a",'<span style="color:#999">pensando…</span>');
 try{
  const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({historial:HIST})});
  const d=await r.json(); load.remove();
  HIST.push({rol:"a",texto:d.respuesta});
  let h='<div style="white-space:pre-wrap">'+esc(d.respuesta)+'</div>';
  if(d.resultados && d.resultados.length){ NRESP++; const idx=NRESP; MATS[idx]=d.resultados.slice(); QRY[idx]=d.query||""; SHOWN[idx]=d.resultados.map(x=>x.doc);
   h+='<div style="font-size:11px;color:#999;margin:10px 0 2px">Material encontrado:</div>';
   h+='<div id="mat'+idx+'">'+d.resultados.map(card).join("")+'</div>';
   h+=`<button class="mas" onclick="mas(${idx})">Ver más opciones</button>`;
   h+=`<div class="gen"><select id="canal${idx}"><option>posteo de Instagram</option><option>secuencia de 5 posteos de Instagram</option><option>newsletter</option><option>email (asunto y cuerpo)</option><option>mensaje de WhatsApp</option><option>artículo web</option></select><button onclick="armar(${idx})">✨ Armar con esto</button></div><div id="draft${idx}"></div>`;
  }
  bub("a",h);
 }catch(e){load.remove();bub("a","Error: "+e)}
}
async function armar(idx){
 const canal=document.getElementById("canal"+idx).value;
 const d=document.getElementById("draft"+idx); d.innerHTML='<div style="color:#999;font-size:12px;margin-top:8px">armando borrador…</div>';
 try{
  const r=await fetch("/api/armar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({canal:canal, fragmentos:MATS[idx]})});
  const j=await r.json();
  d.innerHTML='<div class="draft"><span class="lbl">Borrador — '+esc(canal)+' (para revisión del equipo)</span>'+esc(j.draft)+'</div>';
  chat.scrollTop=chat.scrollHeight;
 }catch(e){d.innerHTML='<div style="color:#c00;font-size:12px">Error al armar: '+e+'</div>'}
}
async function mas(idx){
 try{
  const r=await fetch("/api/mas",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:QRY[idx], excluir:SHOWN[idx]})});
  const d=await r.json();
  const cont=document.getElementById("mat"+idx);
  d.resultados.forEach(x=>{cont.insertAdjacentHTML("beforeend",card(x)); MATS[idx].push(x); SHOWN[idx].push(x.doc);});
 }catch(e){}
}
document.querySelectorAll("#chips span").forEach(s=>s.onclick=()=>{document.getElementById("q").value=s.textContent;buscar()});
document.getElementById("q").addEventListener("keydown",e=>{if(e.key==="Enter")buscar()});
</script></body></html>"""

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("ATENCIÓN: falta OPENAI_API_KEY (ponela en .streamlit/secrets.toml).")
    print("Cargando corpus…")
    nucleo.cargar()
    puerto = int(os.environ.get("PUERTO", "8000"))
    print(f"\n  Servidor local en http://localhost:{puerto}   (Ctrl+C para parar)\n")
    ThreadingHTTPServer(("0.0.0.0", puerto), H).serve_forever()
