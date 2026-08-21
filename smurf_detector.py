import pandas as pd
from datetime import datetime, timedelta

# ─── CONFIGURACIÓN SMURFING ───────────────────────────────
UMBRAL_REPORTE = 10000      # Monto sobre el cual se debe reportar (USD/UF)
VENTANA_DIAS = 7            # Días a analizar hacia atrás
MIN_TRANSACCIONES = 3       # Mínimo de TX fraccionadas para alertar
PORCENTAJE_UMBRAL = 0.85    # TX sospechosas si suman más del 85% del umbral

# ─── DETECTOR PRINCIPAL ───────────────────────────────────
def detectar_smurfing(df_transacciones):
    """
    Detecta patrones de smurfing en un DataFrame de transacciones.
    
    Columnas esperadas:
    - cliente_id
    - cliente_nombre
    - fecha (formato: YYYY-MM-DD)
    - monto
    - tipo (deposito, transferencia, etc)
    """
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
        tx_bajo_umbral = grupo[grupo["monto"] < UMBRAL_REPORTE]
        
        if len(tx_bajo_umbral) >= MIN_TRANSACCIONES:
            total = tx_bajo_umbral["monto"].sum()
            
            # Si la suma supera el porcentaje del umbral → smurf
            if total >= UMBRAL_REPORTE * PORCENTAJE_UMBRAL:
                alertas.append({
                    "Fecha detección": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "ID Cliente": cliente_id,
                    "Nombre Cliente": grupo["cliente_nombre"].iloc[0],
                    "N° Transacciones": len(tx_bajo_umbral),
                    "Monto Total": f"${total:,.0f}",
                    "Umbral reporte": f"${UMBRAL_REPORTE:,}",
                    "Ventana días": VENTANA_DIAS,
                    "Tipo alerta": "SMURFING / FRACCIONAMIENTO",
                    "Riesgo": "ALTO" if total > UMBRAL_REPORTE else "MEDIO"
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