import streamlit as st
import pandas as pd
import requests
from rapidfuzz import fuzz
from datetime import datetime

# ─── CONFIGURACIÓN ───────────────────────────────────────
st.set_page_config(
    page_title="Motor Compliance",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Motor de Compliance - Monitoreo de Clientes")
st.markdown("---")

# ─── FUNCIÓN OFAC ────────────────────────────────────────
@st.cache_data(ttl=3600)
def cargar_lista_ofac():
    """Descarga la lista OFAC SDN desde el Tesoro de EEUU"""
    url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
    try:
        df = pd.read_csv(url, header=None, encoding="latin-1")
        nombres = df[1].dropna().str.strip().tolist()
        return nombres
    except Exception as e:
        st.error(f"Error cargando OFAC: {e}")
        return []

def buscar_en_ofac(nombre, lista_ofac, score_minimo):
    """Busca nombre contra lista OFAC con fuzzy matching"""
    alertas = []
    for nombre_ofac in lista_ofac:
        score = fuzz.token_sort_ratio(nombre.upper(), str(nombre_ofac).upper())
        if score >= score_minimo:
            alertas.append({
                "match": nombre_ofac,
                "score": score,
                "fuente": "OFAC SDN List"
            })
    if alertas:
        return sorted(alertas, key=lambda x: x["score"], reverse=True)[:3]
    return []

# ─── CARGA DE ARCHIVO ────────────────────────────────────
st.subheader("📂 Cargar lista de clientes")
archivo = st.file_uploader(
    "Sube el archivo CSV de clientes",
    type=["csv"],
    help="Columnas requeridas: id, nombre, rut"
)

if archivo:
    df_clientes = pd.read_csv(archivo)
    st.success(f"✅ {len(df_clientes)} clientes cargados")
    st.dataframe(df_clientes, use_container_width=True)

    st.markdown("---")
    st.subheader("🔍 Ejecutar monitoreo")

    col1, col2 = st.columns(2)
    with col1:
        score_minimo = st.slider(
            "Score mínimo de alerta (%)",
            min_value=50, max_value=100, value=85
        )
    with col2:
        st.metric("Clientes a verificar", len(df_clientes))

    if st.button("🚀 Iniciar monitoreo", type="primary"):
        with st.spinner("Cargando lista OFAC desde el Tesoro de EEUU..."):
            lista_ofac = cargar_lista_ofac()

        if not lista_ofac:
            st.error("No se pudo cargar la lista OFAC. Verifica tu conexión.")
        else:
            st.info(f"✅ Lista OFAC cargada: {len(lista_ofac):,} entradas")
            alertas = []
            barra = st.progress(0)
            estado = st.empty()

            for i, row in df_clientes.iterrows():
                estado.text(f"Verificando: {row['nombre']}...")
                barra.progress((i + 1) / len(df_clientes))

                matches_ofac = buscar_en_ofac(
                    row["nombre"], lista_ofac, score_minimo
                )

                for match in matches_ofac:
                    alertas.append({
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "ID Cliente": row["id"],
                        "Nombre Cliente": row["nombre"],
                        "RUT": row["rut"],
                        "Match Encontrado": match["match"],
                        "Score %": match["score"],
                        "Fuente": match["fuente"],
                        "Tipo": "SANCIÓN OFAC"
                    })

            estado.empty()
            barra.empty()

            st.markdown("---")
            st.subheader("📊 Resultados del monitoreo")

            if alertas:
                df_alertas = pd.DataFrame(alertas)
                st.error(f"⚠️ {len(alertas)} alerta(s) encontrada(s)")
                st.dataframe(df_alertas, use_container_width=True)

                csv = df_alertas.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Descargar alertas CSV",
                    csv,
                    f"alertas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv"
                )
            else:
                st.success("✅ Sin alertas — todos los clientes están limpios")

else:
    st.info("👆 Sube un archivo CSV para comenzar el monitoreo")
    st.markdown("### Formato esperado:")
    st.code("id,nombre,rut\n001,Juan Pérez,12345678-9\n002,María González,98765432-1")