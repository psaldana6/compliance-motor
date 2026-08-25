"""
Módulo PEP Chile — InfoProbidad (Contraloría General de la República /
Consejo para la Transparencia).

Fuente oficial de datos abiertos con las Declaraciones de Interés y
Patrimonio de autoridades chilenas (Ministros, Subsecretarios, Senadores,
Diputados, Alcaldes, Concejales, etc.) — en la práctica, la lista más
oficial disponible de Personas Expuestas Políticamente (PEP) en Chile,
relevante para debida diligencia reforzada (Circular UAF N°57/N°62).

IMPORTANTE — diseño de esta integración:
- El dataset es GRANDE (declaraciones históricas desde 2016) y la
  descarga puede tardar bastante (se han observado timeouts >30s).
  Por eso NO se consulta en vivo en cada screening — se descarga una
  vez (o periódicamente, ya que la fuente se actualiza solo martes y
  viernes) y se guarda en una tabla local SQLite. El screening
  posterior es rápido porque consulta la copia local.
- No se pudo verificar en línea la estructura EXACTA del JSON antes de
  programar (timeout impidió inspeccionarlo). Por eso el parser es
  DEFENSIVO: prueba varios nombres de campo candidatos en vez de
  asumir uno fijo, y guarda el registro crudo si no logra identificar
  los campos esperados, en vez de fallar en silencio o con datos
  incorrectos. Si al usarlo notas que "nombre"/"cargo" salen vacíos,
  revisa la columna raw_json de la tabla pep_chile para ajustar los
  nombres de campo reales.
"""

import requests
import sqlite3
import json
from datetime import datetime
from rapidfuzz import fuzz

DB_PATH = "compliance_motor.db"
URL_DECLARACIONES = "https://datos.cplt.cl/catalogos/infoprobidad/jsondeclaraciones"

# Candidatos de nombres de campo — el parser prueba estos en orden
# porque no se pudo confirmar el esquema exacto del JSON de antemano.
CAMPOS_NOMBRE = ["nombre", "Nombre", "nombreAutoridad", "NombreAutoridad", "name"]
CAMPOS_CARGO = ["cargo", "Cargo", "autoridad", "Autoridad", "tipoAutoridad", "TipoAutoridad"]
CAMPOS_INSTITUCION = ["institucion", "Institucion", "organismo", "Organismo", "entidad", "Entidad"]


def _extraer_campo(registro, candidatos):
    """Prueba varios nombres de campo posibles y devuelve el primero que exista."""
    for campo in candidatos:
        if campo in registro and registro[campo]:
            return str(registro[campo])
    return ""


def descargar_pep_infoprobidad(progreso_callback=None):
    """
    Descarga el catálogo de Declaraciones de InfoProbidad y lo guarda
    en la tabla local pep_chile (reemplaza el contenido anterior).
    Devuelve (exito: bool, mensaje: str, total_registros: int).

    progreso_callback: función opcional que recibe un string de estado
    (para mostrar en un st.spinner/st.status desde la app).
    """
    def reportar(msg):
        print(msg)
        if progreso_callback:
            progreso_callback(msg)

    reportar("Descargando catálogo de InfoProbidad (puede tardar 1-2 minutos)...")
    try:
        # Timeout largo a propósito — el dataset histórico es grande.
        response = requests.get(URL_DECLARACIONES, timeout=180,
                                 headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        return False, "Timeout: InfoProbidad no respondió a tiempo (dataset muy grande o servidor lento). Intenta de nuevo más tarde.", 0
    except Exception as e:
        return False, f"Error descargando InfoProbidad: {e}", 0

    # El JSON puede venir como lista directa, o envuelto en una clave
    # (ej. {"data": [...]} o {"declaraciones": [...]}) — se maneja
    # ambos casos sin asumir una estructura fija.
    if isinstance(data, list):
        registros = data
    elif isinstance(data, dict):
        registros = None
        for clave in data:
            if isinstance(data[clave], list):
                registros = data[clave]
                break
        if registros is None:
            return False, "Estructura JSON inesperada — no se encontró una lista de registros.", 0
    else:
        return False, "Respuesta inesperada de InfoProbidad (no es JSON lista/dict).", 0

    reportar(f"Descargados {len(registros)} registros. Guardando en base local...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pep_chile")

    filas = []
    for r in registros:
        if not isinstance(r, dict):
            continue
        nombre = _extraer_campo(r, CAMPOS_NOMBRE)
        cargo = _extraer_campo(r, CAMPOS_CARGO)
        institucion = _extraer_campo(r, CAMPOS_INSTITUCION)
        filas.append((
            nombre, cargo, institucion,
            json.dumps(r, ensure_ascii=False),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    cursor.executemany("""
        INSERT INTO pep_chile (nombre, cargo, institucion, raw_json, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?)
    """, filas)
    conn.commit()
    conn.close()

    sin_nombre = sum(1 for f in filas if not f[0])
    mensaje = f"✅ {len(filas)} registro(s) PEP guardados localmente."
    if sin_nombre > 0:
        mensaje += (f" ⚠️ {sin_nombre} registro(s) sin campo 'nombre' reconocido — "
                    f"revisa raw_json en la tabla pep_chile para ajustar el parser.")
    reportar(mensaje)
    return True, mensaje, len(filas)


def fecha_ultima_actualizacion_pep():
    """Devuelve la fecha de la última descarga guardada localmente, o None."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        resultado = cursor.execute(
            "SELECT MAX(fecha_actualizacion) FROM pep_chile"
        ).fetchone()
        conn.close()
        return resultado[0] if resultado else None
    except Exception:
        return None


def buscar_pep_local(nombre, score_minimo=85):
    """
    Busca un nombre contra la copia local de PEP chilenos (fuzzy match).
    Rápido porque consulta SQLite local, no la fuente en vivo.
    Devuelve lista de matches: [{nombre, cargo, institucion, score}, ...]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nombre, cargo, institucion FROM pep_chile WHERE nombre != ''")
    registros = cursor.fetchall()
    conn.close()

    resultados = []
    for nombre_pep, cargo, institucion in registros:
        score = fuzz.token_sort_ratio(nombre.upper(), nombre_pep.upper())
        if score >= score_minimo:
            resultados.append({
                "nombre": nombre_pep, "cargo": cargo,
                "institucion": institucion, "score": score
            })
    return resultados
