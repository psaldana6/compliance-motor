import pandas as pd
from datetime import datetime, timedelta

# ─── CONFIGURACIÓN SMURFING ───────────────────────────────
# NOTA: el umbral legal real es USD 10.000 (Ley 19.913/20.818), no
# CLP 10.000 — usa calcular_umbral_clp() para el valor correcto en
# pesos con el dólar del día, en vez de este valor fijo desactualizado.
UMBRAL_REPORTE = 10000       # ⚠️ ver nota arriba — mantenido solo como fallback
VENTANA_DIAS = 7            # Días a analizar hacia atrás
MIN_TRANSACCIONES = 3       # Mínimo de TX fraccionadas para alertar
PORCENTAJE_UMBRAL = 0.85    # TX sospechosas si suman más del 85% del umbral


def calcular_umbral_clp():
    """
    Calcula el umbral legal real (USD 10.000 → CLP) usando el dólar
    del día vía mindicador.cl. Si falla, usa un valor de referencia
    aproximado en vez del UMBRAL_REPORTE viejo (que estaba en CLP
    10.000, ~640 veces menor al umbral legal real).
    """
    try:
        from verificacion_rut import consultar_dolar_hoy
        info = consultar_dolar_hoy()
        if info:
            return round(info["valor"] * 10000)
    except Exception:
        pass
    return 9_500_000  # fallback de referencia


# ─── DETECTOR PRINCIPAL ───────────────────────────────────
def detectar_smurfing(df_transacciones, umbral=None):
    """
    Detecta patrones de smurfing en un DataFrame de transacciones.
    umbral: si no se especifica, se calcula automáticamente en CLP
    equivalente a USD 10.000 (umbral legal real).

    Columnas esperadas:
    - cliente_id
    - cliente_nombre
    - fecha (formato: YYYY-MM-DD)
    - monto
    - tipo (deposito, transferencia, etc)
    """
    if umbral is None:
        umbral = calcular_umbral_clp()

    alertas = []
    fecha_limite = datetime.now() - timedelta(days=VENTANA_DIAS)
    
    # Filtrar por ventana de tiempo
    df_transacciones["fecha"] = pd.to_datetime(df_transacciones["fecha"])
    df_reciente = df_transacciones[
        df_transacciones["fecha"] >= fecha_limite
    ].copy()
    
    # Agrupar por cliente
    for cliente_id, grupo in df_reciente.groupby("cliente_id"):
        # Filtrar TX bajo el umbral (las sospechosas de ser fraccionadas)
        tx_bajo_umbral = grupo[grupo["monto"] < umbral]
        
        if len(tx_bajo_umbral) >= MIN_TRANSACCIONES:
            total = tx_bajo_umbral["monto"].sum()
            
            # Si la suma supera el porcentaje del umbral → smurf
            if total >= umbral * PORCENTAJE_UMBRAL:
                alertas.append({
                    "Fecha detección": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "ID Cliente": cliente_id,
                    "Nombre Cliente": grupo["cliente_nombre"].iloc[0],
                    "N° Transacciones": len(tx_bajo_umbral),
                    "Monto Total": f"${total:,.0f}",
                    "Umbral reporte": f"${umbral:,}",
                    "Ventana días": VENTANA_DIAS,
                    "Tipo alerta": "SMURFING / FRACCIONAMIENTO",
                    "Riesgo": "ALTO" if total > umbral else "MEDIO"
                })
    
    return alertas

# ─── DATOS DE PRUEBA ──────────────────────────────────────
def generar_datos_prueba():
    """Genera transacciones de prueba con patrón de smurfing"""
    hoy = datetime.now()
    
    datos = [
        # Cliente 1 — patrón de smurfing claro
        {"cliente_id": "001", "cliente_nombre": "Juan Pérez García",
         "fecha": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
         "monto": 9500, "tipo": "deposito"},
        {"cliente_id": "001", "cliente_nombre": "Juan Pérez García",
         "fecha": (hoy - timedelta(days=2)).strftime("%Y-%m-%d"),
         "monto": 9800, "tipo": "deposito"},
        {"cliente_id": "001", "cliente_nombre": "Juan Pérez García",
         "fecha": (hoy - timedelta(days=3)).strftime("%Y-%m-%d"),
         "monto": 9200, "tipo": "transferencia"},
        {"cliente_id": "001", "cliente_nombre": "Juan Pérez García",
         "fecha": (hoy - timedelta(days=4)).strftime("%Y-%m-%d"),
         "monto": 9700, "tipo": "deposito"},

        # Cliente 2 — transacciones normales
        {"cliente_id": "002", "cliente_nombre": "María González",
         "fecha": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
         "monto": 500, "tipo": "deposito"},
        {"cliente_id": "002", "cliente_nombre": "María González",
         "fecha": (hoy - timedelta(days=3)).strftime("%Y-%m-%d"),
         "monto": 300, "tipo": "transferencia"},

        # Cliente 3 — patrón sospechoso moderado
        {"cliente_id": "003", "cliente_nombre": "Pedro Saldaña",
         "fecha": (hoy - timedelta(days=2)).strftime("%Y-%m-%d"),
         "monto": 8900, "tipo": "deposito"},
        {"cliente_id": "003", "cliente_nombre": "Pedro Saldaña",
         "fecha": (hoy - timedelta(days=4)).strftime("%Y-%m-%d"),
         "monto": 8500, "tipo": "deposito"},
        {"cliente_id": "003", "cliente_nombre": "Pedro Saldaña",
         "fecha": (hoy - timedelta(days=5)).strftime("%Y-%m-%d"),
         "monto": 8700, "tipo": "transferencia"},
    ]
    return pd.DataFrame(datos)

# ─── EJECUTAR ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("DETECTOR DE SMURFING / FRACCIONAMIENTO")
    print("="*55)
    
    df = generar_datos_prueba()
    print(f"\nAnalizando {len(df)} transacciones de {df['cliente_id'].nunique()} clientes...")
    print(f"Ventana de análisis: últimos {VENTANA_DIAS} días")
    print(f"Umbral de reporte: ${UMBRAL_REPORTE:,}\n")
    
    alertas = detectar_smurfing(df)
    
    if alertas:
        print(f"⚠️  {len(alertas)} ALERTA(S) DE SMURFING DETECTADA(S):\n")
        for a in alertas:
            print(f"  Cliente: {a['Nombre Cliente']}")
            print(f"  TX: {a['N° Transacciones']} operaciones")
            print(f"  Total acumulado: {a['Monto Total']}")
            print(f"  Riesgo: {a['Riesgo']}")
            print(f"  Tipo: {a['Tipo alerta']}")
            print()
    else:
        print("✅ Sin patrones de smurfing detectados")