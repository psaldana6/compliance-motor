import streamlit as st
import pandas as pd
import requests
from rapidfuzz import fuzz
from datetime import datetime, timedelta
from database import (
    inicializar_db, guardar_alertas_listas, guardar_alertas_smurfing,
    guardar_ejecucion, obtener_alertas_listas, obtener_alertas_smurfing,
    obtener_historial, obtener_resumen
)

# ─── CONFIGURACIÓN ───────────────────────────────────────
st.set_page_config(
    page_title="Motor Compliance",
    page_icon="🛡️",
    layout="wide"
)

UMBRAL_REPORTE = 10000
VENTANA_DIAS = 7
MIN_TRANSACCIONES = 3
PORCENTAJE_UMBRAL = 0.85

# Inicializar BD al arrancar
inicializar_db()

st.title("🛡️ Motor de Compliance - Monitoreo Integral")

# ─── MÉTRICAS RESUMEN ────────────────────────────────────
resumen = obtener_resumen()
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Alertas Listas", resumen["total_alertas_listas"])
col2.metric("Alertas Smurfing", resumen["total_alertas_smurfing"])
col3.metric("Ejecuciones", resumen["total_ejecuciones"])
col4.metric("Pendientes", resumen["alertas_pendientes"])
col5.metric("Última ejecución", resumen["ultima_ejecucion"] or "Nunca")

st.markdown("---")

# ─── TABS ────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🔍 Listas Negras / PEP",
    "💸 Smurfing / Fraccionamiento",
    "📊 Historial y Análisis"
])

# ════════════════════════════════════════════════════════
# TAB 1 — LISTAS NEGRAS
# ════════════════════════════════════════════════════════
with tab1:
    st.subheader("📂 Cargar lista de clientes")
    archivo = st.file_uploader("Sube el CSV de clientes", type=["csv"], key="clientes")

    @st.cache_data(ttl=3600)
    def cargar_lista_ofac():
        url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
        try:
            df = pd.read_csv(url, header=None, encoding="latin-1")
            return df[1].dropna().str.strip().tolist()
        except Exception as e:
            st.error(f"Error cargando OFAC: {e}")
            return []

    def buscar_en_ofac(nombre, lista_ofac, score_minimo):
        alertas = []
        for nombre_ofac in lista_ofac:
            score = fuzz.token_sort_ratio(nombre.upper(), str(nombre_ofac).upper())
            if score >= score_minimo:
                alertas.append({"match": nombre_ofac, "score": score, "fuente": "OFAC SDN List"})
        return sorted(alertas, key=lambda x: x["score"], reverse=True)[:3] if alertas else []

    if archivo:
        df_clientes = pd.read_csv(archivo)
        st.success(f"✅ {len(df_clientes)} clientes cargados")
        st.dataframe(df_clientes, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            score_minimo = st.slider("Score mínimo (%)", 50, 100, 85)
        with col2:
            st.metric("Clientes a verificar", len(df_clientes))

        if st.button("🚀 Iniciar monitoreo listas", type="primary"):
            with st.spinner("Cargando lista OFAC..."):
                lista_ofac = cargar_lista_ofac()

            if lista_ofac:
                st.info(f"✅ OFAC cargada: {len(lista_ofac):,} entradas")
                alertas = []
                barra = st.progress(0)
                estado = st.empty()

                for i, row in df_clientes.iterrows():
                    estado.text(f"Verificando: {row['nombre']}...")
                    barra.progress((i + 1) / len(df_clientes))
                    matches = buscar_en_ofac(row["nombre"], lista_ofac, score_minimo)
                    for m in matches:
                        alertas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": m["match"],
                            "Score %": m["score"],
                            "Fuente": m["fuente"],
                            "Tipo": "SANCIÓN OFAC"
                        })

                estado.empty()
                barra.empty()

                # Guardar en BD
                guardar_alertas_listas(alertas)
                guardar_ejecucion(len(df_clientes), len(alertas), 0, "OK")

                if alertas:
                    df_alertas = pd.DataFrame(alertas)
                    st.error(f"⚠️ {len(alertas)} alerta(s) encontrada(s)")
                    st.dataframe(df_alertas, use_container_width=True)
                    csv = df_alertas.to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Descargar alertas", csv,
                        f"alertas_listas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
                else:
                    st.success("✅ Sin alertas — todos los clientes están limpios")
    else:
        st.info("👆 Sube un archivo CSV para comenzar")
        st.code("id,nombre,rut\n001,Juan Pérez,12345678-9\n002,María González,98765432-1")

# ════════════════════════════════════════════════════════
# TAB 2 — SMURFING
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader("📂 Cargar transacciones")
    archivo_tx = st.file_uploader("Sube el CSV de transacciones", type=["csv"], key="transacciones")

    def detectar_smurfing(df_tx, umbral, ventana, min_tx, porcentaje):
        alertas = []
        fecha_limite = datetime.now() - timedelta(days=ventana)
        df_tx["fecha"] = pd.to_datetime(df_tx["fecha"])
        df_reciente = df_tx[df_tx["fecha"] >= fecha_limite].copy()
        for cliente_id, grupo in df_reciente.groupby("cliente_id"):
            tx_bajo = grupo[grupo["monto"] < umbral]
            if len(tx_bajo) >= min_tx:
                total = tx_bajo["monto"].sum()
                if total >= umbral * porcentaje:
                    alertas.append({
                        "Fecha detección": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "ID Cliente": cliente_id,
                        "Nombre Cliente": grupo["cliente_nombre"].iloc[0],
                        "N Transacciones": len(tx_bajo),
                        "Monto Total": f"${total:,.0f}",
                        "Umbral reporte": f"${umbral:,}",
                        "Ventana dias": ventana,
                        "Tipo alerta": "SMURFING / FRACCIONAMIENTO",
                        "Riesgo": "ALTO" if total > umbral else "MEDIO"
                    })
        return alertas

    col1, col2, col3 = st.columns(3)
    with col1:
        umbral = st.number_input("Umbral de reporte ($)", value=10000, step=1000)
    with col2:
        ventana = st.number_input("Ventana de días", value=7, step=1)
    with col3:
        min_tx = st.number_input("Mínimo de transacciones", value=3, step=1)

    if archivo_tx:
        df_tx = pd.read_csv(archivo_tx)
        st.success(f"✅ {len(df_tx)} transacciones cargadas")
        st.dataframe(df_tx, use_container_width=True)

        if st.button("🚀 Detectar smurfing", type="primary"):
            alertas_smurf = detectar_smurfing(df_tx, umbral, ventana, min_tx, PORCENTAJE_UMBRAL)

            # Guardar en BD
            guardar_alertas_smurfing(alertas_smurf)
            guardar_ejecucion(0, 0, len(alertas_smurf), "OK")

            st.markdown("---")
            st.subheader("📊 Resultados")

            if alertas_smurf:
                df_smurf = pd.DataFrame(alertas_smurf)
                st.error(f"⚠️ {len(alertas_smurf)} patrón(es) de smurfing detectado(s)")
                st.dataframe(df_smurf, use_container_width=True)
                csv = df_smurf.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Descargar alertas smurfing", csv,
                    f"alertas_smurf_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
            else:
                st.success("✅ Sin patrones de smurfing detectados")
    else:
        st.info("👆 Sube un CSV de transacciones para analizar")
        st.code("cliente_id,cliente_nombre,fecha,monto,tipo\n001,Juan Pérez,2026-08-20,9500,deposito")

# ════════════════════════════════════════════════════════
# TAB 3 — HISTORIAL Y ANÁLISIS
# ════════════════════════════════════════════════════════
with tab3:
    st.subheader("📊 Historial acumulativo de alertas")

    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Desde", value=datetime.now() - timedelta(days=30))
    with col2:
        fecha_hasta = st.date_input("Hasta", value=datetime.now())

    tipo_alerta = st.selectbox("Tipo de alerta", ["Todas", "Listas Negras", "Smurfing"])

    if st.button("🔎 Consultar historial", type="primary"):
        fecha_desde_str = fecha_desde.strftime("%d/%m/%Y")
        fecha_hasta_str = fecha_hasta.strftime("%d/%m/%Y")

        st.markdown("---")

        if tipo_alerta in ["Todas", "Listas Negras"]:
            st.subheader("🔴 Alertas Listas Negras / OFAC")
            df_hist_listas = obtener_alertas_listas(fecha_desde_str, fecha_hasta_str)
            if not df_hist_listas.empty:
                st.error(f"⚠️ {len(df_hist_listas)} alerta(s) en el período")
                st.dataframe(df_hist_listas, use_container_width=True)
                csv = df_hist_listas.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Exportar listas", csv, "historial_listas.csv", "text/csv")
            else:
                st.success("✅ Sin alertas de listas en este período")

        if tipo_alerta in ["Todas", "Smurfing"]:
            st.subheader("🟠 Alertas Smurfing")
            df_hist_smurf = obtener_alertas_smurfing(fecha_desde_str, fecha_hasta_str)
            if not df_hist_smurf.empty:
                st.error(f"⚠️ {len(df_hist_smurf)} alerta(s) en el período")
                st.dataframe(df_hist_smurf, use_container_width=True)
                csv = df_hist_smurf.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Exportar smurfing", csv, "historial_smurfing.csv", "text/csv")
            else:
                st.success("✅ Sin alertas de smurfing en este período")

        st.markdown("---")
        st.subheader("📋 Historial de ejecuciones del motor")
        df_ejec = obtener_historial()
        if not df_ejec.empty:
            st.dataframe(df_ejec, use_container_width=True)
        else:
            st.info("Sin ejecuciones registradas aún")