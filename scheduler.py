from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pandas as pd
import requests
from rapidfuzz import fuzz
from smurf_detector import detectar_smurfing
from alertas_email import enviar_alerta_email

# ─── CONFIGURACIÓN ───────────────────────────────────────
HORA_EJECUCION = 8       # Hora del día que corre el motor (8 AM)
MINUTO_EJECUCION = 0
ARCHIVO_CLIENTES = "clientes.csv"
ARCHIVO_TRANSACCIONES = "transacciones.csv"
SCORE_MINIMO = 85

# ─── FUNCIONES ───────────────────────────────────────────
def cargar_ofac():
    url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
    try:
        df = pd.read_csv(url, header=None, encoding="latin-1")
        return df[1].dropna().str.strip().tolist()
    except Exception as e:
        print(f"Error cargando OFAC: {e}")
        return []

def buscar_en_ofac(nombre, lista_ofac):
    alertas = []
    for nombre_ofac in lista_ofac:
        score = fuzz.token_sort_ratio(nombre.upper(), str(nombre_ofac).upper())
        if score >= SCORE_MINIMO:
            alertas.append({
                "match": nombre_ofac,
                "score": score,
                "fuente": "OFAC SDN List"
            })
    return sorted(alertas, key=lambda x: x["score"], reverse=True)[:3] if alertas else []

def ejecutar_monitoreo():
    """Función principal que corre todo el motor"""
    print(f"\n{'='*55}")
    print(f"MOTOR COMPLIANCE — Ejecución automática")
    print(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*55}\n")

    alertas_listas = []
    alertas_smurf = []

    # ── 1. CHEQUEO LISTAS NEGRAS ──────────────────────────
    try:
        df_clientes = pd.read_csv(ARCHIVO_CLIENTES)
        print(f"✅ {len(df_clientes)} clientes cargados")

        print("Cargando lista OFAC...")
        lista_ofac = cargar_ofac()
        print(f"✅ OFAC: {len(lista_ofac):,} entradas")

        for _, row in df_clientes.iterrows():
            matches = buscar_en_ofac(row["nombre"], lista_ofac)
            for m in matches:
                alertas_listas.append({
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "ID Cliente": row["id"],
                    "Nombre Cliente": row["nombre"],
                    "RUT": row["rut"],
                    "Match Encontrado": m["match"],
                    "Score %": m["score"],
                    "Fuente": m["fuente"],
                    "Tipo": "SANCIÓN OFAC"
                })

        if alertas_listas:
            print(f"⚠️  {len(alertas_listas)} alerta(s) de listas negras")
            enviar_alerta_email(alertas_listas, "LISTA NEGRA / OFAC")
        else:
            print("✅ Sin alertas de listas negras")

    except FileNotFoundError:
        print(f"⚠️  Archivo {ARCHIVO_CLIENTES} no encontrado")

    # ── 2. CHEQUEO SMURFING ───────────────────────────────
    try:
        df_tx = pd.read_csv(ARCHIVO_TRANSACCIONES)
        print(f"\n✅ {len(df_tx)} transacciones cargadas")

        alertas_smurf = detectar_smurfing(df_tx)

        if alertas_smurf:
            print(f"⚠️  {len(alertas_smurf)} patrón(es) de smurfing")
            enviar_alerta_email(alertas_smurf, "SMURFING / FRACCIONAMIENTO")
        else:
            print("✅ Sin patrones de smurfing")

    except FileNotFoundError:
        print(f"⚠️  Archivo {ARCHIVO_TRANSACCIONES} no encontrado")

    print(f"\n{'='*55}")
    print(f"Monitoreo completado — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"Próxima ejecución: mañana a las {HORA_EJECUCION:02d}:{MINUTO_EJECUCION:02d}")
    print(f"{'='*55}\n")

# ─── SCHEDULER ───────────────────────────────────────────
if __name__ == "__main__":
    scheduler = BlockingScheduler()

    # Ejecutar inmediatamente al arrancar
    ejecutar_monitoreo()

    # Programar ejecución diaria
    scheduler.add_job(
        ejecutar_monitoreo,
        CronTrigger(hour=HORA_EJECUCION, minute=MINUTO_EJECUCION),
        id="monitoreo_diario",
        name="Motor Compliance Diario"
    )

    print(f"⏰ Scheduler activo — corriendo todos los días a las {HORA_EJECUCION:02d}:{MINUTO_EJECUCION:02d}")
    print("Presiona Ctrl+C para detener\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nScheduler detenido")