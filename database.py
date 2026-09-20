"""
database.py
Capa de acceso a datos del CRM de TFG.
Usa SQLite (un único fichero tfg_crm.db) para que la app funcione sin
necesidad de instalar ni configurar ningún servidor de base de datos.

Soporta varios "proyectos" (TFGs) independientes: cada tarea, reunión,
referencia bibliográfica y entrada de diario pertenece a un proyecto.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "tfg_crm.db"

FASES = [
    "Introducción",
    "Marco teórico",
    "Metodología",
    "Desarrollo / Resultados",
    "Discusión",
    "Conclusiones",
    "Bibliografía",
    "Anexos",
    "Revisión final",
]

ESTADOS = ["Por hacer", "En progreso", "Hecho"]
PRIORIDADES = ["Alta", "Media", "Baja"]
TIPOS_FUENTE = ["Libro", "Artículo", "Web", "Tesis/TFG", "Informe", "Otro"]
TIPOS_REUNION = ["Tutor/a", "Comité", "Otro"]


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS proyectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            fecha_entrega TEXT,
            objetivo_palabras INTEGER NOT NULL DEFAULT 12000,
            creado TEXT
        );

        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            fase TEXT NOT NULL,
            titulo TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Por hacer',
            prioridad TEXT NOT NULL DEFAULT 'Media',
            fecha_limite TEXT,
            notas TEXT,
            creado TEXT
        );

        CREATE TABLE IF NOT EXISTS reuniones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'Tutor/a',
            resumen TEXT,
            acuerdos TEXT,
            proxima_fecha TEXT
        );

        CREATE TABLE IF NOT EXISTS bibliografia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            autores TEXT NOT NULL,
            titulo TEXT NOT NULL,
            anio TEXT,
            fuente TEXT,
            notas TEXT,
            citado INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS diario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            apartado TEXT,
            palabras INTEGER NOT NULL DEFAULT 0,
            notas TEXT
        );

        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        );
        """
    )
    conn.commit()
    conn.close()


# ---------- Config (preferencias globales, no ligadas a un proyecto) ----------

def set_config(clave: str, valor: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO config (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
        (clave, valor),
    )
    conn.commit()
    conn.close()


def get_config(clave: str, default=None):
    conn = get_connection()
    row = conn.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return row["valor"] if row else default


# ---------- Proyectos (TFGs) ----------

def add_proyecto(titulo, fecha_entrega=None, objetivo_palabras=12000):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO proyectos (titulo, fecha_entrega, objetivo_palabras, creado) "
        "VALUES (?, ?, ?, ?)",
        (titulo, fecha_entrega, objetivo_palabras, datetime.now().isoformat()),
    )
    conn.commit()
    nuevo_id = cur.lastrowid
    conn.close()
    return nuevo_id


def get_proyectos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM proyectos ORDER BY creado").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_proyecto(proyecto_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM proyectos WHERE id=?", (proyecto_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_proyecto(proyecto_id, titulo=None, fecha_entrega=None, objetivo_palabras=None):
    conn = get_connection()
    if titulo is not None:
        conn.execute("UPDATE proyectos SET titulo=? WHERE id=?", (titulo, proyecto_id))
    if fecha_entrega is not None:
        conn.execute("UPDATE proyectos SET fecha_entrega=? WHERE id=?", (fecha_entrega, proyecto_id))
    if objetivo_palabras is not None:
        conn.execute("UPDATE proyectos SET objetivo_palabras=? WHERE id=?", (objetivo_palabras, proyecto_id))
    conn.commit()
    conn.close()


def delete_proyecto(proyecto_id):
    """Borra el proyecto y todo lo que cuelga de él (tareas, reuniones, bibliografía, diario)."""
    conn = get_connection()
    conn.execute("DELETE FROM tareas WHERE proyecto_id=?", (proyecto_id,))
    conn.execute("DELETE FROM reuniones WHERE proyecto_id=?", (proyecto_id,))
    conn.execute("DELETE FROM bibliografia WHERE proyecto_id=?", (proyecto_id,))
    conn.execute("DELETE FROM diario WHERE proyecto_id=?", (proyecto_id,))
    conn.execute("DELETE FROM proyectos WHERE id=?", (proyecto_id,))
    conn.commit()
    conn.close()


# ---------- Tareas ----------

def add_tarea(proyecto_id, fase, titulo, estado="Por hacer", prioridad="Media", fecha_limite=None, notas=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO tareas (proyecto_id, fase, titulo, estado, prioridad, fecha_limite, notas, creado) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (proyecto_id, fase, titulo, estado, prioridad, fecha_limite, notas, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_tareas(proyecto_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tareas WHERE proyecto_id=? ORDER BY fecha_limite IS NULL, fecha_limite",
        (proyecto_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_tarea_estado(tarea_id, nuevo_estado):
    conn = get_connection()
    conn.execute("UPDATE tareas SET estado=? WHERE id=?", (nuevo_estado, tarea_id))
    conn.commit()
    conn.close()


def delete_tarea(tarea_id):
    conn = get_connection()
    conn.execute("DELETE FROM tareas WHERE id=?", (tarea_id,))
    conn.commit()
    conn.close()


# ---------- Reuniones ----------

def add_reunion(proyecto_id, fecha, tipo, resumen, acuerdos, proxima_fecha=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO reuniones (proyecto_id, fecha, tipo, resumen, acuerdos, proxima_fecha) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (proyecto_id, fecha, tipo, resumen, acuerdos, proxima_fecha),
    )
    conn.commit()
    conn.close()


def get_reuniones(proyecto_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reuniones WHERE proyecto_id=? ORDER BY fecha DESC", (proyecto_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_reunion(reunion_id):
    conn = get_connection()
    conn.execute("DELETE FROM reuniones WHERE id=?", (reunion_id,))
    conn.commit()
    conn.close()


# ---------- Bibliografía ----------

def add_bibliografia(proyecto_id, tipo, autores, titulo, anio, fuente, notas="", citado=False):
    conn = get_connection()
    conn.execute(
        "INSERT INTO bibliografia (proyecto_id, tipo, autores, titulo, anio, fuente, notas, citado) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (proyecto_id, tipo, autores, titulo, anio, fuente, notas, int(citado)),
    )
    conn.commit()
    conn.close()


def get_bibliografia(proyecto_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM bibliografia WHERE proyecto_id=? ORDER BY autores", (proyecto_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_citado(ref_id, citado: bool):
    conn = get_connection()
    conn.execute("UPDATE bibliografia SET citado=? WHERE id=?", (int(citado), ref_id))
    conn.commit()
    conn.close()


def delete_bibliografia(ref_id):
    conn = get_connection()
    conn.execute("DELETE FROM bibliografia WHERE id=?", (ref_id,))
    conn.commit()
    conn.close()


# ---------- Diario de escritura ----------

def add_diario(proyecto_id, fecha, apartado, palabras, notas=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO diario (proyecto_id, fecha, apartado, palabras, notas) VALUES (?, ?, ?, ?, ?)",
        (proyecto_id, fecha, apartado, palabras, notas),
    )
    conn.commit()
    conn.close()


def get_diario(proyecto_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM diario WHERE proyecto_id=? ORDER BY fecha", (proyecto_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_diario(entry_id):
    conn = get_connection()
    conn.execute("DELETE FROM diario WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()