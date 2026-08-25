"""
Módulo RES — Registro de Empresas y Sociedades (Régimen Simplificado,
Ley N°20.659, "Empresa en un Día"). Fuente: datos.gob.cl (Ministerio
de Hacienda), portal CKAN oficial.

LIMITACIÓN IMPORTANTE: este dataset SOLO cubre empresas constituidas
por la vía simplificada/online desde 2013. NO cubre empresas
constituidas de forma tradicional (escritura pública ante notario),
que siguen siendo una parte importante de las empresas en Chile,
especialmente las más antiguas. Un "no encontrado" aquí NO significa
que la empresa no exista o no esté vigente — solo que no se constituyó
por este régimen específico. Se usa como dato complementario, no como
verificación general de vigencia legal.

Igual que con PEP Chile: se descarga a una caché local en vez de
consultarse en vivo, y se actualiza manualmente.
"""

import requests
import sqlite3
import csv
import io
from datetime import datetime

DB_PATH = "compliance_motor.db"
CKAN_PACKAGE_ID = "363edd60-4919-4ff1-b85f-f8e14d61285a"
CKAN_API_URL = f"https://datos.gob.cl/api/3/action/package_show?id={CKAN_PACKAGE_ID}"

# Cuántos años recientes descargar (para no traer 13 años de historial
# completo, que sería mucho más lento sin agregar valor proporcional
# para debida diligencia de clientes activos).
ANOS_RECIENTES_A_DESCARGAR = 5


def _detectar_columna(headers, candidatos):
    """Busca una columna cuyo nombre (en minúsculas) contenga alguno de los candidatos."""
    headers_lower = [h.lower() for h in headers]
    for candidato in candidatos:
        for i, h in enumerate(headers_lower):
            if candidato in h:
                return headers[i]
    return None


def descargar_res_simplificado(progreso_callback=None):
    """
    Descarga los últimos años del Registro de Empresas y Sociedades
    (régimen simplificado) y los guarda en una tabla local SQLite.
    Devuelve (exito: bool, mensaje: str, total_registros: int).
    """
    def reportar(msg):
        print(msg)
        if progreso_callback:
            progreso_callback(msg)

    reportar("Consultando lista de años disponibles (datos.gob.cl)...")
    try:
        response = requests.get(CKAN_API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return False, f"Error consultando el catálogo CKAN: {e}", 0

    if not data.get("success"):
        return False, "La API de datos.gob.cl respondió sin éxito.", 0

    recursos = data.get("result", {}).get("resources", [])
    # Filtra solo recursos CSV con año en el nombre, y toma los más recientes.
    recursos_csv = [r for r in recursos if r.get("format", "").upper() == "CSV" and r.get("url")]
    recursos_csv.sort(key=lambda r: r.get("name", ""), reverse=True)
    recursos_a_usar = recursos_csv[:ANOS_RECIENTES_A_DESCARGAR]

    if not recursos_a_usar:
        return False, "No se encontraron recursos CSV en el dataset.", 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM empresas_res")

    total_filas = 0
    for recurso in recursos_a_usar:
        nombre_recurso = recurso.get("name", "")
        url_csv = recurso.get("url")
        reportar(f"Descargando: {nombre_recurso}...")
        try:
            resp = requests.get(url_csv, timeout=60)
            resp.raise_for_status()
            # Intenta detectar el encoding correcto (estos CSV suelen venir en latin-1)
            try:
                texto = resp.content.decode("utf-8")
            except UnicodeDecodeError:
                texto = resp.content.decode("latin-1")

            lector = csv.reader(io.StringIO(texto), delimiter=";")
            headers = next(lector, None)
            if not headers:
                continue

            col_rut = _detectar_columna(headers, ["rut"])
            col_nombre = _detectar_columna(headers, ["razon", "nombre", "empresa"])
            col_fecha = _detectar_columna(headers, ["fecha"])

            if not col_rut:
                reportar(f"⚠️  No se encontró columna RUT en {nombre_recurso} — se omite.")
                continue

            idx_rut = headers.index(col_rut)
            idx_nombre = headers.index(col_nombre) if col_nombre else None
            idx_fecha = headers.index(col_fecha) if col_fecha else None

            filas = []
            for fila in lector:
                if len(fila) <= idx_rut:
                    continue
                rut = fila[idx_rut].strip()
                nombre = fila[idx_nombre].strip() if idx_nombre is not None and len(fila) > idx_nombre else ""
                fecha = fila[idx_fecha].strip() if idx_fecha is not None and len(fila) > idx_fecha else ""
                if rut:
                    filas.append((rut, nombre, fecha, nombre_recurso,
                                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            cursor.executemany("""
                INSERT INTO empresas_res (rut, razon_social, fecha_constitucion, anio_origen, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?)
            """, filas)
            total_filas += len(filas)
            reportar(f"  ✅ {len(filas)} registro(s) de {nombre_recurso}")
        except Exception as e:
            reportar(f"⚠️  Error descargando {nombre_recurso}: {e}")
            continue

    conn.commit()
    conn.close()

    if total_filas == 0:
        return False, "No se pudo guardar ningún registro (revisa los mensajes de arriba).", 0

    mensaje = f"✅ {total_filas} registro(s) guardados (últimos {len(recursos_a_usar)} años disponibles)."
    reportar(mensaje)
    return True, mensaje, total_filas


def fecha_ultima_actualizacion_res():
    """Devuelve la fecha de la última descarga guardada localmente, o None."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        resultado = cursor.execute(
            "SELECT MAX(fecha_actualizacion) FROM empresas_res"
        ).fetchone()
        conn.close()
        return resultado[0] if resultado else None
    except Exception:
        return None


def _normalizar_rut(rut):
    """Quita puntos/guión/espacios para comparar RUTs de forma consistente."""
    return rut.replace(".", "").replace("-", "").replace(" ", "").upper()


def buscar_empresa_res(rut):
    """
    Busca un RUT en la copia local del Registro de Empresas y
    Sociedades (régimen simplificado). Consulta rápida, contra la
    caché local, no la fuente en vivo.
    Devuelve lista de matches: [{rut, razon_social, fecha_constitucion, anio_origen}, ...]
    """
    rut_normalizado = _normalizar_rut(rut)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT rut, razon_social, fecha_constitucion, anio_origen FROM empresas_res")
    registros = cursor.fetchall()
    conn.close()

    resultados = []
    for rut_bd, razon_social, fecha_constitucion, anio_origen in registros:
        if _normalizar_rut(rut_bd) == rut_normalizado:
            resultados.append({
                "rut": rut_bd, "razon_social": razon_social,
                "fecha_constitucion": fecha_constitucion, "anio_origen": anio_origen
            })
    return resultados
