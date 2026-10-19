"""
Panel de revisión de conversaciones (para tomar feedback de los popes).
Uso LOCAL:  streamlit run admin.py
Lee todo desde Supabase (usa SUPABASE_URL / SUPABASE_KEY del secrets.toml).

Circuito de revisión:
- Por defecto muestra SOLO las conversaciones no revisadas.
- Podés dejar una nota y marcarla como "revisada" (deja de aparecer).
- El botón "Guardar NO revisadas en carpeta" escribe revision/no-revisadas.json,
  un archivo chico que Claude puede leer (en vez del historial completo).
"""
import os, json, pathlib
import streamlit as st
import db

st.set_page_config(page_title="Conversaciones — Panel", page_icon="🗂️", layout="wide")

os.environ["SUPABASE_URL"] = st.secrets.get("SUPABASE_URL", "")
os.environ["SUPABASE_KEY"] = st.secrets.get("SUPABASE_KEY", "")

HERE = pathlib.Path(__file__).parent
EXPORT_DIR = HERE / "revision"          # gitignored — no se sube a GitHub

st.title("🗂️ Panel de conversaciones")

if not db.disponible():
    st.error("Faltan las credenciales de Supabase en el secrets.toml.")
    st.stop()


@st.cache_data(ttl=20, show_spinner="Cargando conversaciones…")
def cargar_lista(solo_no_revisadas):
    return db.listar_todas(solo_no_revisadas=solo_no_revisadas)


if st.button("🔄 Actualizar"):
    st.cache_data.clear()

solo = st.toggle("Mostrar solo NO revisadas", value=True)
items = cargar_lista(solo)
usuarios = sorted({c.get("usuario") for c in items if c.get("usuario")})

izq, der = st.columns([1, 2.3], gap="large")

with izq:
    filtro = st.selectbox("Filtrar por pope", ["(todos)"] + usuarios)
    visibles = [c for c in items if filtro == "(todos)" or c.get("usuario") == filtro]
    st.caption(f"{len(visibles)} conversaciones")

    if st.button("💾 Guardar NO revisadas en carpeta (para Claude)", use_container_width=True):
        try:
            EXPORT_DIR.mkdir(exist_ok=True)
            datos = db.exportar_no_revisadas()
            for c in datos:
                c["mensajes"] = db.normalizar(c.get("mensajes"))
            destino = EXPORT_DIR / "no-revisadas.json"
            destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success(f"Guardé {len(datos)} conversaciones en revision/no-revisadas.json")
        except Exception as e:
            st.error(f"No pude exportar: {e}")

    if st.button("✅ Aplicar revisadas marcadas por Claude", use_container_width=True):
        archivo = EXPORT_DIR / "marcar-revisadas.json"
        if not archivo.exists():
            st.warning("No encontré revision/marcar-revisadas.json (Claude todavía no lo dejó).")
        else:
            try:
                marcas = json.loads(archivo.read_text(encoding="utf-8"))
                n = 0
                for m in marcas:
                    if m.get("id"):
                        db.marcar_revisada(m["id"], True, m.get("nota"))
                        n += 1
                st.cache_data.clear()
                st.success(f"Marqué {n} conversaciones como revisadas.")
                st.rerun()
            except Exception as e:
                st.error(f"No pude aplicar: {e}")

    st.download_button("⬇️ Descargar TODO (JSON)",
                       data=json.dumps(db.exportar_todas(), ensure_ascii=False, indent=2),
                       file_name="conversaciones-todas.json", mime="application/json")
    st.divider()
    for c in visibles:
        fecha = (c.get("actualizado") or "")[:16].replace("T", " ")
        marca = "✅" if c.get("revisado") else "•"
        etiqueta = f"{marca} 👤 {c.get('usuario')} · {(c.get('titulo') or 'Conversación')[:32]}"
        if st.button(etiqueta, key="sel_" + str(c["id"]), use_container_width=True):
            st.session_state.sel = c["id"]
        st.caption(f"  {fecha}")

with der:
    cid = st.session_state.get("sel")
    if not cid:
        st.info("Elegí una conversación de la izquierda para leerla.")
    else:
        conv = db.cargar_conversacion(cid)
        if not conv:
            st.warning("No encontré esa conversación (quizás se borró).")
        else:
            st.subheader(conv.get("titulo") or "Conversación")
            estado = "✅ revisada" if conv.get("revisado") else "🔸 sin revisar"
            st.caption(f"Estado: {estado}")

            nota = st.text_area("Nota de revisión (feedback, qué ajustar, etc.)",
                                value=conv.get("nota") or "", key="nota_" + str(cid))
            b1, b2, b3 = st.columns(3)
            if b1.button("✅ Marcar revisada", key="rev_" + str(cid),
                         type="primary", use_container_width=True):
                db.marcar_revisada(cid, True, nota)
                st.cache_data.clear()
                st.rerun()
            if b2.button("↩️ Marcar NO revisada", key="unrev_" + str(cid),
                         use_container_width=True):
                db.marcar_revisada(cid, False, nota)
                st.cache_data.clear()
                st.rerun()
            if b3.button("💾 Solo guardar nota", key="nota_btn_" + str(cid),
                         use_container_width=True):
                db.marcar_revisada(cid, conv.get("revisado", False), nota)
                st.success("Nota guardada.")

            st.download_button("⬇️ Descargar ESTA conversación (JSON)",
                               data=json.dumps({"titulo": conv.get("titulo"),
                                                "mensajes": db.normalizar(conv.get("mensajes"))},
                                               ensure_ascii=False, indent=2),
                               file_name="conversacion.json", mime="application/json",
                               key="dl_" + str(cid))
            st.divider()
            for m in db.normalizar(conv.get("mensajes")):
                with st.chat_message("user" if m["role"] == "user" else "assistant"):
                    st.markdown(m.get("content", ""))
                    for r in (m.get("mats") or []):
                        ir = r.get("ir") or ""
                        linea = f"**{r.get('tag','')}** · {r.get('autor','')} — *{r.get('titulo','')}*"
                        if ir:
                            linea += f" · [fuente]({ir})"
                        st.caption(linea)
