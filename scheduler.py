import os
import pandas as pd
import requests
from rapidfuzz import fuzz
from datetime import datetime
from dotenv import load_dotenv

from smurf_detector import detectar_smurfing, calcular_umbral_clp
from alertas_email import enviar_alerta_email
from fuentes_sanciones import cargar_lista_onu, cargar_lista_uk, cargar_lista_eu
from pep_infoprobidad import buscar_pep_local, fecha_ultima_actualizacion_pep
from verificacion_rut import verificar_rut
from database import (
    inicializar_db, guardar_alertas_listas, guardar_alertas_smurfing,
    guardar_ejecucion
)

load_dotenv()

# ─── CONFIGURACIÓN ───────────────────────────────────────
HORA_EJECUCION = int(os.getenv("SCHEDULER_HORA", 8))       # Hora del día que corre el motor
MINUTO_EJECUCION = int(os.getenv("SCHEDULER_MINUTO", 0))
# Nombres de archivo configurables — por defecto apuntan a los CSV de
# muestra del proyecto. En producción, cambia estas rutas en tu .env:
# CLIENTES_CSV=ruta/a/tus/clientes.csv
ARCHIVO_CLIENTES = os.getenv("CLIENTES_CSV", "clientes_prueba.csv")
ARCHIVO_TRANSACCIONES = os.getenv("TRANSACCIONES_CSV", "transacciones_prueba.csv")
SCORE_MINIMO = int(os.getenv("SCORE_MINIMO", 85))
INCLUIR_INTERPOL = os.getenv("SCHEDULER_INCLUIR_INTERPOL", "false").lower() == "true"


# ─── FUENTES DE LISTAS ────────────────────────────────────
def cargar_ofac():
    url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
    try:
        df = pd.read_csv(url, header=None, encoding="latin-1")
        return df[1].dropna().str.strip().tolist()
    except Exception as e:
        print(f"⚠️  Error cargando OFAC: {e}")
        return []


def buscar_en_lista(nombre, lista, fuente):
    """Fuzzy match genérico contra cualquier lista de nombres."""
    alertas = []
    for nombre_lista in lista:
        score = fuzz.token_sort_ratio(nombre.upper(), str(nombre_lista).upper())
        if score >= SCORE_MINIMO:
            alertas.append({"match": nombre_lista, "score": score, "fuente": fuente})
    return sorted(alertas, key=lambda x: x["score"], reverse=True)[:3] if alertas else []


# ─── MOTOR PRINCIPAL ──────────────────────────────────────
def ejecutar_monitoreo():
    """Función principal que corre todo el motor — todas las fuentes."""
    print(f"\n{'='*55}")
    print(f"MOTOR COMPLIANCE — Ejecución automática")
    print(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*55}\n")

    inicializar_db()
    alertas_listas = []
    alertas_smurf = []
    alertas_kyc = []
    df_clientes = None

    # ── 1. CHEQUEO LISTAS NEGRAS + PEP ────────────────────
    try:
        df_clientes = pd.read_csv(ARCHIVO_CLIENTES)
        print(f"✅ {len(df_clientes)} clientes cargados desde {ARCHIVO_CLIENTES}")

        print("Cargando listas de sanciones (OFAC, ONU, UK, EU)...")
        lista_ofac = cargar_ofac()
        lista_onu = cargar_lista_onu()
        lista_uk = cargar_lista_uk()
        lista_eu = cargar_lista_eu()
        print(f"✅ OFAC: {len(lista_ofac):,} | ONU: {len(lista_onu):,} | "
              f"UK: {len(lista_uk):,} | EU: {len(lista_eu):,}")

        pep_disponible = bool(fecha_ultima_actualizacion_pep())
        if pep_disponible:
            print("✅ PEP Chile (InfoProbidad): usando caché local")
        else:
            print("⚠️  PEP Chile: sin caché local descargada — se omite este chequeo "
                  "(actualízala desde la app Streamlit, pestaña Listas Negras/PEP)")

        for _, row in df_clientes.iterrows():
            fuentes_check = [
                (lista_ofac, "OFAC SDN List", "SANCIÓN OFAC"),
                (lista_onu, "ONU Sanctions", "SANCIÓN ONU"),
                (lista_uk, "UK Sanctions", "SANCIÓN UK"),
                (lista_eu, "EU Sanctions", "SANCIÓN UE"),
            ]
            for lista, fuente, tipo in fuentes_check:
                for m in buscar_en_lista(row["nombre"], lista, fuente):
                    alertas_listas.append({
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "ID Cliente": row["id"],
                        "Nombre Cliente": row["nombre"],
                        "RUT": row["rut"],
                        "Match Encontrado": m["match"],
                        "Score %": m["score"],
                        "Fuente": m["fuente"],
                        "Tipo": tipo
                    })

            if pep_disponible:
                for match_pep in buscar_pep_local(row["nombre"], max(70, SCORE_MINIMO - 5)):
                    alertas_listas.append({
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "ID Cliente": row["id"],
                        "Nombre Cliente": row["nombre"],
                        "RUT": row["rut"],
                        "Match Encontrado": f"{match_pep['nombre']} — {match_pep['institucion']}",
                        "Score %": match_pep["score"],
                        "Fuente": "PEP Chile (InfoProbidad)",
                        "Tipo": "PERSONA EXPUESTA POLÍTICAMENTE"
                    })

            if INCLUIR_INTERPOL:
                from fuentes_sanciones import buscar_interpol_red_notices
                for notice in buscar_interpol_red_notices(row["nombre"]):
                    score = fuzz.token_sort_ratio(row["nombre"].upper(), notice["match"].upper())
                    if score >= SCORE_MINIMO:
                        alertas_listas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": notice["match"],
                            "Score %": score,
                            "Fuente": "INTERPOL Red Notice",
                            "Tipo": "NOTIFICACIÓN ROJA INTERPOL"
                        })

            # KYC — validación de RUT (local, sin dependencia externa)
            resultado_rut = verificar_rut(str(row["rut"]))
            if resultado_rut and not resultado_rut["valido"]:
                alertas_kyc.append({
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "ID Cliente": row["id"],
                    "Nombre Cliente": row["nombre"],
                    "RUT": row["rut"],
                    "Tipo alerta": "RUT INVÁLIDO",
                    "Detalle": resultado_rut["mensaje"],
                    "Riesgo": "ALTO"
                })

        guardar_alertas_listas(alertas_listas)

        if alertas_listas:
            print(f"⚠️  {len(alertas_listas)} alerta(s) de listas negras/PEP")
            enviar_alerta_email(alertas_listas, "LISTA NEGRA / PEP")
        else:
            print("✅ Sin alertas de listas negras/PEP")

        if alertas_kyc:
            print(f"⚠️  {len(alertas_kyc)} alerta(s) KYC (RUT inválido)")
            enviar_alerta_email(alertas_kyc, "KYC / RUT INVÁLIDO")

    except FileNotFoundError:
        print(f"⚠️  Archivo {ARCHIVO_CLIENTES} no encontrado — configura CLIENTES_CSV en tu .env")

    # ── 2. CHEQUEO SMURFING (umbral legal correcto) ───────
    try:
        df_tx = pd.read_csv(ARCHIVO_TRANSACCIONES)
        print(f"\n✅ {len(df_tx)} transacciones cargadas desde {ARCHIVO_TRANSACCIONES}")

        umbral_hoy = calcular_umbral_clp()
        print(f"💵 Umbral legal ROE hoy: ${umbral_hoy:,} CLP (≈USD 10.000)")

        alertas_smurf = detectar_smurfing(df_tx, umbral=umbral_hoy)
        guardar_alertas_smurfing(alertas_smurf)

        if alertas_smurf:
            print(f"⚠️  {len(alertas_smurf)} patrón(es) de smurfing")
            enviar_alerta_email(alertas_smurf, "SMURFING / FRACCIONAMIENTO")
        else:
            print("✅ Sin patrones de smurfing")

    except FileNotFoundError:
        print(f"⚠️  Archivo {ARCHIVO_TRANSACCIONES} no encontrado — configura TRANSACCIONES_CSV en tu .env")

    guardar_ejecucion(
        len(df_clientes) if df_clientes is not None else 0,
        len(alertas_listas), len(alertas_smurf), "OK"
    )

    print(f"\n{'='*55}")
    print(f"Monitoreo completado — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"Próxima ejecución: mañana a las {HORA_EJECUCION:02d}:{MINUTO_EJECUCION:02d}")
    print(f"{'='*55}\n")


# ─── SCHEDULER ───────────────────────────────────────────
if __name__ == "__main__":
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

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
