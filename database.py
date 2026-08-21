import sqlite3
import pandas as pd
from datetime import datetime

# ─── CONFIGURACIÓN ───────────────────────────────────────
DB_PATH = "compliance_motor.db"

# ─── INICIALIZAR BASE DE DATOS ────────────────────────────
def inicializar_db():
    """Crea las tablas si no existen"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabla alertas listas negras
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_listas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            cliente_id TEXT,
            cliente_nombre TEXT,
            rut TEXT,
            match_encontrado TEXT,
            score REAL,
            fuente TEXT,
            tipo TEXT,
            estado TEXT DEFAULT 'PENDIENTE',
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla alertas smurfing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_smurfing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_deteccion TEXT,
            cliente_id TEXT,
            cliente_nombre TEXT,
            num_transacciones INTEGER,
            monto_total TEXT,
            umbral_reporte TEXT,
            ventana_dias INTEGER,
            tipo_alerta TEXT,
            riesgo TEXT,
            estado TEXT DEFAULT 'PENDIENTE',
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla historial de ejecuciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_ejecuciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_ejecucion TEXT,
            clientes_procesados INTEGER,
            alertas_listas INTEGER,
            alertas_smurfing INTEGER,
            estado TEXT,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")

# ─── GUARDAR ALERTAS ─────────────────────────────────────
def guardar_alertas_listas(alertas):
    """Guarda alertas de listas negras en SQLite"""
    if not alertas:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for a in alertas:
        cursor.execute("""
            INSERT INTO alertas_listas 
            (fecha, cliente_id, cliente_nombre, rut, match_encontrado, score, fuente, tipo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(a.get("ID Cliente", "")),
            a.get("Nombre Cliente", ""),
            a.get("RUT", ""),
            a.get("Match Encontrado", ""),
            a.get("Score %", 0),
            a.get("Fuente", ""),
            a.get("Tipo", "")
        ))
    conn.commit()
    conn.close()
    print(f"✅ {len(alertas)} alerta(s) de listas guardadas en BD")

def guardar_alertas_smurfing(alertas):
    """Guarda alertas de smurfing en SQLite"""
    if not alertas:
        return
    conn = sqlite3.connect(DB_PATH)
    df = pd.DataFrame(alertas)
    df.columns = [c.lower().replace(" ", "_").replace("°", "").replace("ó", "o").replace("é", "e") for c in df.columns]
    df.to_sql("alertas_smurfing", conn, if_exists="append", index=False)
    conn.close()
    print(f"✅ {len(alertas)} alerta(s) de smurfing guardadas en BD")

def guardar_ejecucion(clientes, alertas_listas, alertas_smurf, estado):
    """Registra cada ejecución del motor"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO historial_ejecuciones
        (fecha_ejecucion, clientes_procesados, alertas_listas, alertas_smurfing, estado)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%d/%m/%Y %H:%M"), clientes, alertas_listas, alertas_smurf, estado))
    conn.commit()
    conn.close()

# ─── CONSULTAR ALERTAS ────────────────────────────────────
def obtener_alertas_listas(fecha_desde=None, fecha_hasta=None):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM alertas_listas WHERE 1=1"
    params = []
    if fecha_desde:
        query += " AND fecha_creacion >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        query += " AND fecha_creacion <= ?"
        params.append(fecha_hasta + " 23:59:59")
    query += " ORDER BY fecha_creacion DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def obtener_alertas_smurfing(fecha_desde=None, fecha_hasta=None):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM alertas_smurfing WHERE 1=1"
    params = []
    if fecha_desde:
        query += " AND fecha_creacion >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        query += " AND fecha_creacion <= ?"
        params.append(fecha_hasta + " 23:59:59")
    query += " ORDER BY fecha_creacion DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def obtener_historial():
    """Obtiene el historial de ejecuciones"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM historial_ejecuciones ORDER BY fecha_creacion DESC",
        conn
    )
    conn.close()
    return df

def obtener_resumen():
    """Resumen general para el dashboard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    resumen = {
        "total_alertas_listas": cursor.execute("SELECT COUNT(*) FROM alertas_listas").fetchone()[0],
        "total_alertas_smurfing": cursor.execute("SELECT COUNT(*) FROM alertas_smurfing").fetchone()[0],
        "total_ejecuciones": cursor.execute("SELECT COUNT(*) FROM historial_ejecuciones").fetchone()[0],
        "ultima_ejecucion": cursor.execute("SELECT fecha_ejecucion FROM historial_ejecuciones ORDER BY id DESC LIMIT 1").fetchone(),
        "alertas_pendientes": cursor.execute("SELECT COUNT(*) FROM alertas_listas WHERE estado='PENDIENTE'").fetchone()[0],
    }
    conn.close()
    if resumen["ultima_ejecucion"]:
        resumen["ultima_ejecucion"] = resumen["ultima_ejecucion"][0]
    return resumen

# ─── INICIALIZAR ─────────────────────────────────────────
if __name__ == "__main__":
    inicializar_db()
    print("\nTablas creadas:")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for tabla in cursor.fetchall():
        print(f"  ✅ {tabla[0]}")
    conn.close()