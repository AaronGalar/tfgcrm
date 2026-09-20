"""
TFG CRM
Gestor personal para organizar el Trabajo de Fin de Grado (o Máster):
tareas por fase, reuniones con el tutor/a, bibliografía y diario de escritura.
Soporta varios TFGs a la vez (por ejemplo, si llevas más de un proyecto).

Ejecutar con:
    streamlit run app.py
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st

import database as db

st.set_page_config(page_title="TFG CRM", page_icon="🎓", layout="wide")
db.init_db()

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def dias_restantes(fecha_entrega_str):
    fecha_entrega = parse_date(fecha_entrega_str)
    if not fecha_entrega:
        return None
    return (fecha_entrega - date.today()).days


st.title("🎓 TFG CRM")
st.caption("Organiza tu Trabajo de Fin de Grado en un solo sitio: tareas, reuniones, bibliografía y avance de escritura.")

# ---------------------------------------------------------------------------
# Selector de proyecto (barra lateral)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📁 Tus TFGs")
    proyectos = db.get_proyectos()

    if proyectos:
        opciones = {p["id"]: p["titulo"] for p in proyectos}
        ultimo_id = db.get_config("proyecto_activo_id")
        ids_disponibles = list(opciones.keys())
        try:
            index_defecto = ids_disponibles.index(int(ultimo_id)) if ultimo_id else 0
        except (ValueError, TypeError):
            index_defecto = 0

        proyecto_id = st.selectbox(
            "Proyecto activo",
            options=ids_disponibles,
            format_func=lambda i: opciones[i],
            index=index_defecto,
        )
        if str(proyecto_id) != ultimo_id:
            db.set_config("proyecto_activo_id", str(proyecto_id))

        proyecto = db.get_proyecto(proyecto_id)

        st.divider()
        st.subheader("⚙️ Editar este TFG")
        nuevo_titulo = st.text_input("Título", value=proyecto["titulo"])
        nueva_fecha = st.date_input(
            "Fecha límite de entrega",
            value=parse_date(proyecto["fecha_entrega"]) or date.today(),
        )
        nuevo_objetivo = st.number_input(
            "Objetivo de palabras (total)",
            min_value=0, step=500, value=int(proyecto["objetivo_palabras"]),
        )
        if st.button("💾 Guardar cambios", use_container_width=True):
            db.update_proyecto(proyecto_id, nuevo_titulo.strip() or proyecto["titulo"],
                                nueva_fecha.isoformat(), int(nuevo_objetivo))
            st.success("Guardado")
            st.rerun()

        with st.expander("🗑️ Borrar este TFG"):
            st.warning("Esto borra el proyecto y TODAS sus tareas, reuniones, bibliografía y diario. No se puede deshacer.")
            confirmar = st.checkbox(f"Sí, quiero borrar «{proyecto['titulo']}»")
            if st.button("Borrar definitivamente", disabled=not confirmar, use_container_width=True):
                db.delete_proyecto(proyecto_id)
                db.set_config("proyecto_activo_id", "")
                st.success("Proyecto borrado")
                st.rerun()
    else:
        proyecto_id = None
        st.info("Todavía no tienes ningún TFG creado. Crea el primero abajo 👇")

    st.divider()
    st.subheader("➕ Nuevo TFG")
    with st.form("form_nuevo_proyecto", clear_on_submit=True):
        titulo_nuevo = st.text_input("Título del nuevo TFG")
        fecha_nueva = st.date_input("Fecha límite de entrega", value=date.today(), key="fecha_nuevo_proyecto")
        objetivo_nuevo = st.number_input("Objetivo de palabras", min_value=0, step=500, value=12000, key="obj_nuevo_proyecto")
        crear = st.form_submit_button("Crear TFG")
        if crear and titulo_nuevo.strip():
            nuevo_id = db.add_proyecto(titulo_nuevo.strip(), fecha_nueva.isoformat(), int(objetivo_nuevo))
            db.set_config("proyecto_activo_id", str(nuevo_id))
            st.success("TFG creado")
            st.rerun()

# ---------------------------------------------------------------------------
# Si no hay ningún proyecto todavía, no seguimos
# ---------------------------------------------------------------------------

if not proyectos:
    st.stop()

tab_dash, tab_tareas, tab_reuniones, tab_biblio, tab_diario = st.tabs(
    ["📊 Dashboard", "✅ Tareas", "🗓️ Reuniones", "📚 Bibliografía", "✍️ Diario de escritura"]
)

# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

with tab_dash:
    tareas = db.get_tareas(proyecto_id)
    diario = db.get_diario(proyecto_id)

    total_tareas = len(tareas)
    hechas = len([t for t in tareas if t["estado"] == "Hecho"])
    progreso_tareas = (hechas / total_tareas * 100) if total_tareas else 0

    total_palabras = sum(d["palabras"] for d in diario)
    objetivo = int(proyecto["objetivo_palabras"] or 0)
    progreso_palabras = (total_palabras / objetivo * 100) if objetivo else 0

    dias = dias_restantes(proyecto["fecha_entrega"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⏳ Días restantes", dias if dias is not None else "—")
    col2.metric("✅ Tareas completadas", f"{hechas}/{total_tareas}", f"{progreso_tareas:.0f}%")
    col3.metric("✍️ Palabras escritas", f"{total_palabras:,}", f"{progreso_palabras:.0f}% del objetivo")
    proximas = [r for r in db.get_reuniones(proyecto_id) if r["proxima_fecha"]]
    col4.metric("🗓️ Próxima reunión", proximas[0]["proxima_fecha"] if proximas else "Sin fijar")

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Progreso por fase")
        if tareas:
            df = pd.DataFrame(tareas)
            resumen = (
                df.groupby("fase")["estado"]
                .apply(lambda s: (s == "Hecho").sum() / len(s) * 100)
                .reindex(db.FASES)
                .fillna(0)
            )
            st.bar_chart(resumen)
        else:
            st.info("Añade tareas en la pestaña ✅ Tareas para ver tu progreso por fase.")

    with c2:
        st.subheader("Palabras escritas a lo largo del tiempo")
        if diario:
            df_d = pd.DataFrame(diario)
            df_d["fecha"] = pd.to_datetime(df_d["fecha"])
            df_d = df_d.sort_values("fecha")
            df_d["acumulado"] = df_d["palabras"].cumsum()
            st.line_chart(df_d.set_index("fecha")["acumulado"])
        else:
            st.info("Registra tus sesiones de escritura en ✍️ Diario para ver tu evolución.")

# ---------------------------------------------------------------------------
# TAREAS (kanban)
# ---------------------------------------------------------------------------

with tab_tareas:
    with st.expander("➕ Añadir tarea nueva", expanded=False):
        with st.form("form_tarea", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            fase = c1.selectbox("Fase del TFG", db.FASES)
            prioridad = c2.selectbox("Prioridad", db.PRIORIDADES, index=1)
            fecha_limite = c3.date_input("Fecha límite (opcional)", value=None)
            titulo = st.text_input("Título de la tarea")
            notas = st.text_area("Notas (opcional)")
            enviado = st.form_submit_button("Añadir tarea")
            if enviado and titulo.strip():
                db.add_tarea(
                    proyecto_id, fase, titulo.strip(), "Por hacer", prioridad,
                    fecha_limite.isoformat() if fecha_limite else None, notas,
                )
                st.success("Tarea añadida")
                st.rerun()

    st.divider()
    tareas = db.get_tareas(proyecto_id)
    fase_filtro = st.selectbox("Filtrar por fase", ["Todas"] + db.FASES)
    if fase_filtro != "Todas":
        tareas = [t for t in tareas if t["fase"] == fase_filtro]

    cols = st.columns(3)
    for estado, col in zip(db.ESTADOS, cols):
        with col:
            st.markdown(f"### {estado}")
            for t in [x for x in tareas if x["estado"] == estado]:
                icono = {"Alta": "🔴", "Media": "🟡", "Baja": "🟢"}[t["prioridad"]]
                with st.container(border=True):
                    st.markdown(f"**{icono} {t['titulo']}**")
                    st.caption(f"{t['fase']} · vence: {t['fecha_limite'] or 'sin fecha'}")
                    if t["notas"]:
                        st.caption(t["notas"])
                    nuevo_estado = st.selectbox(
                        "Estado", db.ESTADOS, index=db.ESTADOS.index(estado),
                        key=f"estado_{t['id']}", label_visibility="collapsed",
                    )
                    if nuevo_estado != estado:
                        db.update_tarea_estado(t["id"], nuevo_estado)
                        st.rerun()
                    if st.button("🗑️ Eliminar", key=f"del_{t['id']}"):
                        db.delete_tarea(t["id"])
                        st.rerun()

# ---------------------------------------------------------------------------
# REUNIONES
# ---------------------------------------------------------------------------

with tab_reuniones:
    with st.expander("➕ Registrar reunión", expanded=False):
        with st.form("form_reunion", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            fecha_r = c1.date_input("Fecha de la reunión", value=date.today())
            tipo_r = c2.selectbox("Tipo", db.TIPOS_REUNION)
            proxima = c3.date_input("Próxima reunión (opcional)", value=None)
            resumen = st.text_area("Resumen de lo hablado")
            acuerdos = st.text_area("Acuerdos / tareas que salieron de la reunión")
            enviado_r = st.form_submit_button("Guardar reunión")
            if enviado_r:
                db.add_reunion(
                    proyecto_id, fecha_r.isoformat(), tipo_r, resumen, acuerdos,
                    proxima.isoformat() if proxima else None,
                )
                st.success("Reunión guardada")
                st.rerun()

    st.divider()
    for r in db.get_reuniones(proyecto_id):
        with st.container(border=True):
            st.markdown(f"**{r['fecha']} · {r['tipo']}**")
            if r["resumen"]:
                st.write(r["resumen"])
            if r["acuerdos"]:
                st.markdown(f"📌 **Acuerdos:** {r['acuerdos']}")
            if r["proxima_fecha"]:
                st.caption(f"Próxima reunión: {r['proxima_fecha']}")
            if st.button("🗑️ Eliminar", key=f"del_reunion_{r['id']}"):
                db.delete_reunion(r["id"])
                st.rerun()

# ---------------------------------------------------------------------------
# BIBLIOGRAFÍA
# ---------------------------------------------------------------------------

with tab_biblio:
    with st.expander("➕ Añadir referencia", expanded=False):
        with st.form("form_biblio", clear_on_submit=True):
            c1, c2 = st.columns(2)
            tipo_b = c1.selectbox("Tipo de fuente", db.TIPOS_FUENTE)
            anio = c2.text_input("Año")
            autores = st.text_input("Autor/es (Apellido, N.)")
            titulo_b = st.text_input("Título")
            fuente = st.text_input("Editorial / revista / URL")
            notas_b = st.text_area("Notas (opcional)")
            enviado_b = st.form_submit_button("Añadir referencia")
            if enviado_b and autores.strip() and titulo_b.strip():
                db.add_bibliografia(proyecto_id, tipo_b, autores.strip(), titulo_b.strip(), anio, fuente, notas_b)
                st.success("Referencia añadida")
                st.rerun()

    st.divider()
    refs = db.get_bibliografia(proyecto_id)
    if refs:
        for r in refs:
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                with c1:
                    cita = f"{r['autores']} ({r['anio']}). *{r['titulo']}*."
                    if r["fuente"]:
                        cita += f" {r['fuente']}."
                    st.markdown(cita)
                    st.caption(f"{r['tipo']}" + (f" · {r['notas']}" if r["notas"] else ""))
                with c2:
                    citado = st.checkbox("Citado", value=bool(r["citado"]), key=f"citado_{r['id']}")
                    if citado != bool(r["citado"]):
                        db.toggle_citado(r["id"], citado)
                        st.rerun()
                    if st.button("🗑️", key=f"del_biblio_{r['id']}"):
                        db.delete_bibliografia(r["id"])
                        st.rerun()

        texto_export = "\n".join(
            f"{r['autores']} ({r['anio']}). {r['titulo']}." + (f" {r['fuente']}." if r["fuente"] else "")
            for r in refs
        )
        st.download_button(
            "⬇️ Exportar bibliografía (.txt)", texto_export,
            file_name="bibliografia_tfg.txt", mime="text/plain",
        )
    else:
        st.info("Todavía no has añadido ninguna referencia.")

# ---------------------------------------------------------------------------
# DIARIO DE ESCRITURA
# ---------------------------------------------------------------------------

with tab_diario:
    with st.expander("➕ Registrar sesión de escritura", expanded=True):
        with st.form("form_diario", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            fecha_d = c1.date_input("Fecha", value=date.today())
            apartado_d = c2.selectbox("Apartado", db.FASES)
            palabras_d = c3.number_input("Palabras escritas hoy", min_value=0, step=50)
            notas_d = st.text_area("¿Qué has avanzado / qué te ha costado?")
            enviado_d = st.form_submit_button("Registrar")
            if enviado_d:
                db.add_diario(proyecto_id, fecha_d.isoformat(), apartado_d, int(palabras_d), notas_d)
                st.success("Sesión registrada")
                st.rerun()

    st.divider()
    entradas = db.get_diario(proyecto_id)
    if entradas:
        df = pd.DataFrame(entradas)[["fecha", "apartado", "palabras", "notas"]]
        st.dataframe(df.sort_values("fecha", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Registra tu primera sesión de escritura para empezar a ver tu evolución.")
