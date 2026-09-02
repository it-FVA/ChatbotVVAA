"""
Panel de revisión de conversaciones (para tomar feedback de los popes).
Uso LOCAL:  streamlit run admin.py
Lee todo desde Supabase (usa SUPABASE_URL / SUPABASE_KEY del secrets.toml).
"""
import os, json
import streamlit as st
import db

st.set_page_config(page_title="Conversaciones — Panel", page_icon="🗂️", layout="wide")

os.environ["SUPABASE_URL"] = st.secrets.get("SUPABASE_URL", "")
os.environ["SUPABASE_KEY"] = st.secrets.get("SUPABASE_KEY", "")

st.title("🗂️ Panel de conversaciones")

if not db.disponible():
    st.error("Faltan las credenciales de Supabase en el secrets.toml.")
    st.stop()


@st.cache_data(ttl=20, show_spinner="Cargando conversaciones…")
def cargar_lista():
    return db.listar_todas()


@st.cache_data(ttl=20, show_spinner="Preparando exportación…")
def exportar_todo():
    return db.exportar_todas()


if st.button("🔄 Actualizar"):
    st.cache_data.clear()

items = cargar_lista()
usuarios = sorted({c.get("usuario") for c in items if c.get("usuario")})

izq, der = st.columns([1, 2.3], gap="large")

with izq:
    filtro = st.selectbox("Filtrar por pope", ["(todos)"] + usuarios)
    visibles = [c for c in items if filtro == "(todos)" or c.get("usuario") == filtro]
    st.caption(f"{len(visibles)} conversaciones")
    st.download_button("⬇️ Descargar TODO (JSON)",
                       data=json.dumps(exportar_todo(), ensure_ascii=False, indent=2),
                       file_name="conversaciones-todas.json", mime="application/json")
    st.divider()
    for c in visibles:
        fecha = (c.get("actualizado") or "")[:16].replace("T", " ")
        etiqueta = f"👤 {c.get('usuario')} · {(c.get('titulo') or 'Conversación')[:34]}"
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
            st.download_button("⬇️ Descargar ESTA conversación (JSON)",
                               data=json.dumps({"titulo": conv.get("titulo"),
                                                "mensajes": db.normalizar(conv.get("mensajes"))},
                                               ensure_ascii=False, indent=2),
                               file_name="conversacion.json", mime="application/json",
                               key="dl_" + str(cid))
            for m in db.normalizar(conv.get("mensajes")):
                with st.chat_message("user" if m["role"] == "user" else "assistant"):
                    st.markdown(m.get("content", ""))
                    for r in (m.get("mats") or []):
                        ir = r.get("ir") or ""
                        linea = f"**{r.get('tag','')}** · {r.get('autor','')} — *{r.get('titulo','')}*"
                        if ir:
                            linea += f" · [fuente]({ir})"
                        st.caption(linea)
