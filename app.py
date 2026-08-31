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
from fuentes_sanciones import cargar_lista_onu, cargar_lista_uk, cargar_lista_eu, buscar_interpol_red_notices, consultar_riesgo_pais_fatf, FATF_ULTIMA_ACTUALIZACION
from noticias_adversas import analizar_riesgo_reputacional
from verificacion_rut import verificar_rut, consultar_proveedor_mercadopublico, consultar_dolar_hoy
from pep_infoprobidad import descargar_pep_infoprobidad, buscar_pep_local, fecha_ultima_actualizacion_pep
from pep_internacional_wikidata import buscar_pep_internacional
from res_simplificado import descargar_res_simplificado, buscar_empresa_res, fecha_ultima_actualizacion_res
import res_simplificado

# ─── CONFIGURACIÓN ───────────────────────────────────────
st.set_page_config(page_title="Motor Compliance", page_icon="🛡️", layout="wide")

# ─── ESTILO GLOBAL — tipografía y tamaños consistentes con los ─
# módulos HTML del hub (Aptos Display + escala de letra mayor).
# Aptos no está en Google Fonts: si el equipo tiene Windows 11/Office
# 365 recientes, ya la tiene instalada localmente y se usa tal cual;
# si no, cae automáticamente a la fuente sans-serif por defecto del
# navegador sin romper nada.
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'Aptos Display', 'Aptos', -apple-system, sans-serif !important;
    }
    /* Texto general y widgets */
    .stMarkdown, .stText, p, span, div, label {
        font-size: 1.05rem !important;
    }
    /* Títulos */
    h1 { font-size: 2.4rem !important; }
    h2 { font-size: 1.9rem !important; }
    h3 { font-size: 1.5rem !important; }
    /* Métricas (st.metric) — número grande */
    [data-testid="stMetricValue"] { font-size: 2rem !important; }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; }
    /* Pestañas */
    button[data-baseweb="tab"] p { font-size: 1.05rem !important; }
    /* Botones */
    .stButton button { font-size: 1.05rem !important; }
    /* Menú lateral */
    section[data-testid="stSidebar"] * { font-size: 1.05rem !important; }
</style>
""", unsafe_allow_html=True)


UMBRAL_REPORTE = 10000
VENTANA_DIAS = 7
MIN_TRANSACCIONES = 3
PORCENTAJE_UMBRAL = 0.85

inicializar_db()

# ─── MENÚ LATERAL — HUB DE MÓDULOS ────────────────────────
# Cada entrada es un archivo HTML autocontenido (artifact) guardado en
# modulos_html/. Se agregan nuevas entradas simplemente copiando el
# archivo a esa carpeta y sumando una línea al diccionario MODULOS.
import os as _os

MODULOS_HTML = {
    "Calibración de Alertas PLAFT": "calibracion_alertas_plaft.html",
    "Motor de Sensibilidad PLAFT": "motor_sensibilidad_plaft310826.html",
    "Dashboard PLAFT en Fabric": "acceso_bi_cumplimiento.html",
}

st.sidebar.title("🛡️ Hub Compliance")
opciones_menu = ["🏠 Motor Principal"] + [f"📄 {nombre}" for nombre in MODULOS_HTML]
seleccion = st.sidebar.radio("Módulos", opciones_menu, label_visibility="collapsed")

if seleccion != "🏠 Motor Principal":
    nombre_modulo = seleccion.replace("📄 ", "")
    archivo_modulo = MODULOS_HTML[nombre_modulo]
    ruta_modulo = _os.path.join(_os.path.dirname(__file__), "modulos_html", archivo_modulo)
    with open(ruta_modulo, "r", encoding="utf-8") as f:
        html_contenido = f.read()
    st.components.v1.html(html_contenido, height=1200, scrolling=True)
    st.stop()

st.title("🛡️ Motor de Compliance - Monitoreo Integral")

with st.expander("ℹ️ Marco normativo cubierto — matriz completa (Ley 19.913, Ley 20.393, Circular UAF, NCG 571)"):
    st.markdown("""
    #### Cobertura por obligación legal específica

    | Obligación legal | Norma | Cómo lo cubre el hub |
    |---|---|---|
    | Identificación y verificación de clientes ("conozca a su cliente") | Art. 3° Ley N°19.913 | 🪪 KYC — validación de RUT (algoritmo local) |
    | Screening contra listas de sanciones internacionales | Art. 3°/4° Ley N°19.913, Circular UAF N°57/62 | 🔍 OFAC, ONU, UK, Unión Europea |
    | Screening de Personas Expuestas Políticamente (PEP) | Circular UAF N°57/62, Cap. 1-16 RAN (CMF) | 🔍 PEP Chile (InfoProbidad) — caché local |
    | Debida diligencia reforzada por país de riesgo | Circular UAF N°57, estándar GAFI | 🌍 Consulta FATF/GAFI (lista negra/gris) |
    | Debida diligencia reforzada — noticias adversas | Circular UAF N°57 | 📰 GDELT, Google News (global + medios CL) |
    | Detección de fraccionamiento de operaciones (smurfing) | Delito base **lavado de activos** — Ley N°20.393, art. 5° Ley 19.913 (umbral USD 10.000) | 💸 Smurfing — umbral legal calculado en vivo |
    | Verificación de vínculos con el Estado / conflictos de interés | Buenas prácticas KYC corporativo | 🏛️ ChileCompra (proveedor del Estado) |
    | Verificación de vigencia de empresas (régimen simplificado) | Debida diligencia de personas jurídicas | 🏢 Registro de Empresas y Sociedades |
    | Notificaciones de personas buscadas internacionalmente | Debida diligencia reforzada | 🚨 INTERPOL Red Notices |
    | Procesos sancionatorios del regulador (CMF) | Cap. 3 NCG N°571 (Compendio Bolsas e Intermediarios) | ⚖️ Accesos directos a procesos activos CMF |
    | Estado de insolvencia/quiebra de clientes | Debida diligencia de riesgo financiero | ⚖️ Boletín Concursal (acceso manual) |
    | Causas judiciales de clientes | Debida diligencia reforzada | ⚖️ Poder Judicial (acceso manual — CAPTCHA impide automatizar) |

    #### Delitos base de la Ley N°20.393 relevantes para una corredora
    Lavado de activos, cohecho/soborno (nacional y transnacional), financiamiento del
    terrorismo, receptación, corrupción entre particulares, negociación incompatible,
    administración desleal, apropiación indebida — el screening de listas + PEP + noticias
    adversas + smurfing de este hub apunta principalmente a **prevenir y detectar señales**
    de estos delitos en la relación con clientes, no a los delitos cometidos por la propia
    organización (para eso se requiere un Modelo de Prevención de Delitos formal, con
    Encargado de Prevención designado — fuera del alcance de este hub).

    #### Ley N°21.595 — Ley de Delitos Económicos
    Modifica extensamente la Ley N°20.393 (nueva redacción de los arts. 1° a 13°) e
    incorpora el **art. 11 bis** sobre supervisión de la persona jurídica (posibilidad
    de un supervisor externo). Amplía el catálogo de delitos económicos y endurece
    las sanciones. Relevante en especial para la fila de "entrega de información
    falsa al regulador" — hoy también tipificada específicamente por la
    **Ley N°21.770** (presentación de información falsa y certificación/informe
    fraudulento ante la autoridad). *Recomendación: el equipo de Compliance debería
    revisar si el Modelo de Prevención de Delitos y su matriz de riesgos ya
    reflejan esta reclasificación.*

    #### Lo que este hub NO reemplaza
    - El **Modelo de Prevención de Delitos** exigido por la Ley N°20.393 (documento
      formal, con Encargado de Prevención designado por el Directorio).
    - La **presentación del Reporte de Operación Sospechosa (ROS)** a la UAF — las
      alertas de este hub son insumo para que el Oficial de Cumplimiento decida si
      corresponde, no un reporte automático.
    - El **juicio profesional** del Oficial de Cumplimiento — todas las alertas
      requieren revisión humana antes de cualquier decisión.
    - Los requisitos **prudenciales** de la NCG N°571 (capital mínimo, activos
      ponderados por riesgo, liquidez, gobierno corporativo) — son de naturaleza
      financiera/contable, no de screening de datos.

    *Este panel es una guía de referencia, no asesoría legal. Ante dudas sobre el
    alcance exacto de una obligación, consulta a tu equipo legal o directamente la
    normativa vigente en [cmfchile.cl](https://www.cmfchile.cl) y [uaf.cl](https://www.uaf.cl).*
    """)



resumen = obtener_resumen()
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Alertas Listas", resumen["total_alertas_listas"])
col2.metric("Alertas Smurfing", resumen["total_alertas_smurfing"])
col3.metric("Ejecuciones", resumen["total_ejecuciones"])
col4.metric("Pendientes", resumen["alertas_pendientes"])
col5.metric("Última ejecución", resumen["ultima_ejecucion"] or "Nunca")

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Listas Negras / PEP",
    "💸 Smurfing / Fraccionamiento",
    "📊 Historial y Análisis",
    "📰 Noticias Adversas",
    "🪪 KYC / Verificación RUT"
])

# ════════════════════════════════════════════════════════
# TAB 1 — LISTAS NEGRAS
# ════════════════════════════════════════════════════════
with tab1:
    st.subheader("📂 Cargar lista de clientes")
    archivo = st.file_uploader("Sube el CSV de clientes", type=["csv"], key="clientes")

    with st.expander("🏛️ Base PEP Chile (InfoProbidad) — gestión de caché local"):
        st.caption(
            "Fuente oficial (Contraloría/Consejo para la Transparencia) de "
            "autoridades chilenas — Ministros, Subsecretarios, Senadores, "
            "Diputados, Alcaldes, Concejales. El dataset es grande, así que "
            "se descarga a una copia local en vez de consultarse en vivo en "
            "cada búsqueda. Actualízala periódicamente (la fuente se "
            "actualiza los martes y viernes)."
        )
        ultima_act_pep = fecha_ultima_actualizacion_pep()
        if ultima_act_pep:
            st.caption(f"📅 Última actualización local: {ultima_act_pep}")
        else:
            st.warning("⚠️ Aún no se ha descargado la base PEP local — actualízala antes de usarla.")

        if st.button("🔄 Actualizar base PEP Chile"):
            estado_pep = st.empty()
            with st.spinner("Descargando InfoProbidad (puede tardar 1-2 minutos)..."):
                exito, mensaje, total = descargar_pep_infoprobidad(
                    progreso_callback=lambda m: estado_pep.text(m)
                )
            estado_pep.empty()
            if exito:
                st.success(mensaje)
            else:
                st.error(mensaje)

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
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            score_minimo = st.slider("Score mínimo (%)", 50, 100, 85)
        with col2:
            st.metric("Clientes a verificar", len(df_clientes))
        with col3:
            incluir_interpol = st.checkbox(
                "Incluir INTERPOL (notificaciones rojas)", value=False,
                help="Consulta en vivo por cliente. Es una API pública gratuita, "
                     "pero al ser 1 consulta por cliente puede demorar más con listas grandes."
            )
        with col4:
            incluir_pep_chile = st.checkbox(
                "Incluir PEP Chile (InfoProbidad, caché local)", value=bool(ultima_act_pep),
                disabled=not bool(ultima_act_pep),
                help="Usa la copia local descargada arriba. Rápido, no consulta la fuente en vivo."
            )
        with col5:
            verificar_res = st.checkbox(
                "Verificar Registro de Empresas (informativo, requiere columna RUT)",
                value=False, disabled=not bool(fecha_ultima_actualizacion_res()),
                help="No es una alerta de riesgo — solo confirma si el cliente aparece "
                     "registrado como empresa vía 'Empresa en un Día'. Se muestra aparte "
                     "de las alertas. Requiere haber actualizado la base en la pestaña KYC."
            )
        with col6:
            incluir_pep_internacional = st.checkbox(
                "Incluir PEP Internacional (Wikidata)", value=False,
                help="Consulta en vivo por cliente (2 llamadas por candidato encontrado, "
                     "puede ser lento con listas grandes). Cubre políticos internacionales "
                     "de alto perfil — no reemplaza un proveedor comercial de PEP."
            )

        if st.button("🚀 Iniciar monitoreo listas", type="primary"):
            with st.spinner("Cargando fuentes de sanciones..."):
                lista_ofac = cargar_lista_ofac()
                lista_onu = cargar_lista_onu()
                lista_uk = cargar_lista_uk()
                lista_eu = cargar_lista_eu()

            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            col_p1.metric("OFAC", f"{len(lista_ofac):,}")
            col_p2.metric("ONU", f"{len(lista_onu):,}")
            col_p3.metric("UK", f"{len(lista_uk):,}")
            col_p4.metric("Unión Europea", f"{len(lista_eu):,}")

            alertas = []
            barra = st.progress(0)
            estado = st.empty()

            for i, row in df_clientes.iterrows():
                estado.text(f"Verificando: {row['nombre']}...")
                barra.progress((i + 1) / len(df_clientes))

                for m in buscar_en_ofac(row["nombre"], lista_ofac, score_minimo):
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

                for nombre_onu in lista_onu:
                    score = fuzz.token_sort_ratio(row["nombre"].upper(), str(nombre_onu).upper())
                    if score >= score_minimo:
                        alertas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": nombre_onu,
                            "Score %": score,
                            "Fuente": "ONU Sanctions",
                            "Tipo": "SANCIÓN ONU"
                        })
                        break

                for nombre_uk in lista_uk:
                    score = fuzz.token_sort_ratio(row["nombre"].upper(), str(nombre_uk).upper())
                    if score >= score_minimo:
                        alertas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": nombre_uk,
                            "Score %": score,
                            "Fuente": "UK Sanctions",
                            "Tipo": "SANCIÓN UK"
                        })
                        break

                for nombre_eu in lista_eu:
                    score = fuzz.token_sort_ratio(row["nombre"].upper(), str(nombre_eu).upper())
                    if score >= score_minimo:
                        alertas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": nombre_eu,
                            "Score %": score,
                            "Fuente": "EU Sanctions",
                            "Tipo": "SANCIÓN UE"
                        })
                        break

                if incluir_interpol:
                    for notice in buscar_interpol_red_notices(row["nombre"]):
                        score = fuzz.token_sort_ratio(row["nombre"].upper(), notice["match"].upper())
                        if score >= score_minimo:
                            alertas.append({
                                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "ID Cliente": row["id"],
                                "Nombre Cliente": row["nombre"],
                                "RUT": row["rut"],
                                "Match Encontrado": notice["match"],
                                "Score %": score,
                                "Fuente": "INTERPOL Red Notice",
                                "Tipo": "NOTIFICACIÓN ROJA INTERPOL"
                            })

                if incluir_pep_chile:
                    for match_pep in buscar_pep_local(row["nombre"], score_minimo=max(70, score_minimo - 5)):
                        alertas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": f"{match_pep['nombre']} — {match_pep['institucion']}",
                            "Score %": match_pep["score"],
                            "Fuente": "PEP Chile (InfoProbidad)",
                            "Tipo": "PERSONA EXPUESTA POLÍTICAMENTE"
                        })

                if incluir_pep_internacional:
                    for match_pep_intl in buscar_pep_internacional(row["nombre"]):
                        cargos_txt = ", ".join(match_pep_intl["cargos"][:3])
                        alertas.append({
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "ID Cliente": row["id"],
                            "Nombre Cliente": row["nombre"],
                            "RUT": row["rut"],
                            "Match Encontrado": f"{match_pep_intl['nombre']} ({match_pep_intl['pais']}) — {cargos_txt}",
                            "Score %": "N/A",
                            "Fuente": "PEP Internacional (Wikidata)",
                            "Tipo": "PERSONA EXPUESTA POLÍTICAMENTE (INTERNACIONAL)"
                        })

            estado.empty()
            barra.empty()

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

            if verificar_res:
                if "rut" not in df_clientes.columns:
                    st.warning("⚠️ El CSV no tiene columna 'rut' — no se pudo verificar el Registro de Empresas.")
                else:
                    coincidencias_res = []
                    for _, row in df_clientes.iterrows():
                        for match in buscar_empresa_res(str(row["rut"])):
                            coincidencias_res.append({
                                "ID Cliente": row["id"],
                                "Nombre Cliente": row["nombre"],
                                "RUT": row["rut"],
                                "Razón Social (Registro)": match["razon_social"],
                                "Fecha Constitución": match["fecha_constitucion"],
                                "Año Origen": match["anio_origen"],
                            })
                    st.markdown("---")
                    st.subheader("🏢 Registro de Empresas (informativo — no es alerta de riesgo)")
                    if coincidencias_res:
                        st.info(f"ℹ️ {len(coincidencias_res)} cliente(s) encontrado(s) en el Régimen Simplificado")
                        st.dataframe(pd.DataFrame(coincidencias_res), use_container_width=True)
                    else:
                        st.caption(
                            "Ningún cliente de este CSV aparece en el Régimen Simplificado — "
                            "recuerda que esto NO indica que las empresas no existan, solo que "
                            "no se constituyeron por esa vía específica (ver limitaciones en pestaña KYC)."
                        )
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

    COLUMNAS_REQUERIDAS_TX = ["fecha", "cliente_id", "cliente_nombre", "monto"]

    # El umbral legal del Reporte de Operaciones en Efectivo (ROE) es
    # USD 10.000 o su equivalente en pesos según el dólar del día
    # (Ley N°19.913, modificada por Ley N°20.818 — antes era UF 450).
    # Se calcula el equivalente en CLP con el dólar observado de hoy
    # vía mindicador.cl (API pública, sin key, datos del Banco Central).
    dolar_info = consultar_dolar_hoy()
    if dolar_info:
        umbral_legal_clp = round(dolar_info["valor"] * 10000)
        st.caption(
            f"💵 Umbral legal ROE: USD 10.000 (Ley 19.913/20.818) ≈ "
            f"${umbral_legal_clp:,} CLP al dólar de hoy (${dolar_info['valor']:,.2f}, "
            f"{dolar_info['fecha']})"
        )
    else:
        umbral_legal_clp = 9_500_000  # fallback aproximado si falla la consulta
        st.caption("⚠️ No se pudo obtener el dólar del día — usando valor de referencia aproximado")

    col1, col2, col3 = st.columns(3)
    with col1:
        umbral = st.number_input("Umbral de reporte ($ CLP)", value=umbral_legal_clp, step=100000)
    with col2:
        ventana = st.number_input("Ventana de días", value=7, step=1)
    with col3:
        min_tx = st.number_input("Mínimo de transacciones", value=3, step=1)

    if archivo_tx:
        df_tx = pd.read_csv(archivo_tx)
        # Normaliza nombres de columna (minúsculas, sin espacios extra)
        # para tolerar variaciones como "Fecha" o " fecha " en el CSV.
        df_tx.columns = [c.strip().lower() for c in df_tx.columns]
        st.success(f"✅ {len(df_tx)} transacciones cargadas")
        st.dataframe(df_tx, use_container_width=True)

        faltantes = [c for c in COLUMNAS_REQUERIDAS_TX if c not in df_tx.columns]
        if faltantes:
            st.error(
                f"❌ El CSV no tiene la(s) columna(s) requerida(s): {', '.join(faltantes)}.\n\n"
                f"Columnas encontradas: {', '.join(df_tx.columns)}\n\n"
                f"Formato esperado: cliente_id,cliente_nombre,fecha,monto,tipo"
            )
        elif st.button("🚀 Detectar smurfing", type="primary"):
            alertas_smurf = detectar_smurfing(df_tx, umbral, ventana, min_tx, PORCENTAJE_UMBRAL)
            guardar_alertas_smurfing(alertas_smurf)
            guardar_ejecucion(0, 0, len(alertas_smurf), "OK")

            st.markdown("---")
            st.subheader("📊 Resultados")

            if alertas_smurf:
                df_smurf = pd.DataFrame(alertas_smurf)
                st.error(f"⚠️ {len(alertas_smurf)} patrón(es) detectado(s)")
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
# TAB 3 — HISTORIAL
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
        fecha_desde_str = fecha_desde.strftime("%Y-%m-%d")
        fecha_hasta_str = fecha_hasta.strftime("%Y-%m-%d")

        st.markdown("---")

        if tipo_alerta in ["Todas", "Listas Negras"]:
            st.subheader("🔴 Alertas Listas Negras / OFAC")
            df_hist = obtener_alertas_listas(fecha_desde_str, fecha_hasta_str)
            if not df_hist.empty:
                st.error(f"⚠️ {len(df_hist)} alerta(s)")
                st.dataframe(df_hist, use_container_width=True)
                csv = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Exportar", csv, "historial_listas.csv", "text/csv")
            else:
                st.success("✅ Sin alertas en este período")

        if tipo_alerta in ["Todas", "Smurfing"]:
            st.subheader("🟠 Alertas Smurfing")
            df_smurf = obtener_alertas_smurfing(fecha_desde_str, fecha_hasta_str)
            if not df_smurf.empty:
                st.error(f"⚠️ {len(df_smurf)} alerta(s)")
                st.dataframe(df_smurf, use_container_width=True)
                csv = df_smurf.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Exportar", csv, "historial_smurfing.csv", "text/csv")
            else:
                st.success("✅ Sin alertas en este período")

        st.markdown("---")
        st.subheader("📋 Historial de ejecuciones")
        df_ejec = obtener_historial()
        if not df_ejec.empty:
            st.dataframe(df_ejec, use_container_width=True)
        else:
            st.info("Sin ejecuciones registradas")

# ════════════════════════════════════════════════════════
# TAB 4 — NOTICIAS ADVERSAS
# ════════════════════════════════════════════════════════
with tab4:
    st.subheader("📰 Búsqueda de noticias adversas")
    st.caption(
        "Combina NewsAPI (si hay key configurada), GDELT Project y Google News RSS — "
        "estas dos últimas son gratuitas y no requieren API key, por lo que el módulo "
        "funciona igual sin plan pago."
    )

    col1, col2 = st.columns(2)
    with col1:
        nombre_busqueda = st.text_input("Nombre del cliente a buscar")
    with col2:
        dias_busqueda = st.number_input("Días hacia atrás", value=30, step=10)

    if st.button("🔎 Buscar noticias adversas", type="primary"):
        if nombre_busqueda:
            with st.spinner(f"Buscando noticias sobre {nombre_busqueda}..."):
                resultado = analizar_riesgo_reputacional(nombre_busqueda, dias_busqueda)

            noticias = resultado.get("noticias_adversas", [])
            if noticias:
                st.error(f"⚠️ {len(noticias)} noticia(s) adversa(s) encontrada(s)")
                for n in noticias:
                    st.markdown(f"""
**📰 {n['titulo']}**  
🗓️ {n['fecha']} | 📡 {n['fuente']} | _{n.get('tipo', 'NOTICIA ADVERSA')}_  
🔗 [Ver noticia]({n['url']})

---
""")
                csv = pd.DataFrame(noticias).to_csv(index=False).encode("utf-8")
                st.download_button("📥 Descargar noticias", csv,
                    f"noticias_{nombre_busqueda}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            else:
                st.success(f"✅ Sin noticias adversas para {nombre_busqueda}")
        else:
            st.warning("👆 Ingresa un nombre para buscar")

    st.markdown("---")
    with st.expander("⚖️ CMF — Procesos sancionatorios activos (accesos rápidos)"):
        st.caption(
            "El buscador de sanciones de la CMF no tiene API pública — es un "
            "formulario web. Estos son accesos directos a los 3 procesos "
            "sancionatorios/supervisores activos publicados por la CMF, para "
            "revisión manual del oficial de cumplimiento."
        )
        st.markdown("""
- [Proceso Sancionatorio — Larraín Vial Activos AGF](https://www.cmfchile.cl/portal/principal/623/w4-propertyvalue-48726.html)
- [Proceso Supervisor — Grupo STF (STF Capital Corredores de Bolsa)](https://www.cmfchile.cl/portal/principal/623/w4-propertyvalue-48727.html)
- [Proceso Supervisor — Sartor AGF](https://www.cmfchile.cl/portal/principal/623/w4-propertyvalue-48728.html)
- [Buscador general de sanciones CMF (formulario manual)](https://www.cmfchile.cl/institucional/sanciones/sanciones_mercados.php)
""")

# ════════════════════════════════════════════════════════
# TAB 5 — KYC / VERIFICACIÓN RUT
# ════════════════════════════════════════════════════════
with tab5:
    st.subheader("🪪 Verificación KYC — Validación de RUT")
    st.info("Verifica que los RUTs de tus clientes sean válidos y detecta discrepancias contra el SII.")

    archivo_kyc = st.file_uploader("Sube el CSV de clientes", type=["csv"], key="kyc")

    if archivo_kyc:
        df_kyc = pd.read_csv(archivo_kyc)
        st.success(f"✅ {len(df_kyc)} clientes cargados")
        st.dataframe(df_kyc, use_container_width=True)

        if st.button("🪪 Iniciar verificación KYC", type="primary"):
            alertas_kyc = []
            barra = st.progress(0)
            estado = st.empty()

            for i, row in df_kyc.iterrows():
                estado.text(f"Verificando RUT: {row['rut']} — {row['nombre']}...")
                barra.progress((i + 1) / len(df_kyc))
                resultado = verificar_rut(row["rut"])

                if resultado is None:
                    continue

                if not resultado["valido"]:
                    alertas_kyc.append({
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "ID Cliente": row["id"],
                        "Nombre Cliente": row["nombre"],
                        "RUT": row["rut"],
                        "Nombre SII": "",
                        "Tipo alerta": "RUT INVÁLIDO",
                        "Riesgo": "ALTO"
                    })
                elif resultado["nombre"] and row["nombre"].upper() not in resultado["nombre"].upper():
                    alertas_kyc.append({
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "ID Cliente": row["id"],
                        "Nombre Cliente": row["nombre"],
                        "RUT": row["rut"],
                        "Nombre SII": resultado["nombre"],
                        "Tipo alerta": "DISCREPANCIA NOMBRE/RUT",
                        "Riesgo": "MEDIO"
                    })

            estado.empty()
            barra.empty()

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total verificados", len(df_kyc))
            col2.metric("✅ Sin alertas", len(df_kyc) - len(alertas_kyc))
            col3.metric("⚠️ Con alertas", len(alertas_kyc))

            if alertas_kyc:
                df_alertas_kyc = pd.DataFrame(alertas_kyc)
                st.error(f"⚠️ {len(alertas_kyc)} alerta(s) KYC")
                st.dataframe(df_alertas_kyc, use_container_width=True)
                csv = df_alertas_kyc.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Descargar alertas KYC", csv,
                    f"alertas_kyc_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
            else:
                st.success("✅ Todos los RUTs válidos y sin discrepancias")
    else:
        st.info("👆 Sube un CSV de clientes para verificar sus RUTs")
        st.code("id,nombre,rut\n001,Juan Pérez,12345678-9\n002,María González,98765432-1")

    st.markdown("---")
    st.subheader("🌍 Consulta de riesgo país (FATF/GAFI)")
    st.caption(
        f"Lista negra y gris del FATF, embebida en el código (el FATF no ofrece API). "
        f"Última actualización aplicada: {FATF_ULTIMA_ACTUALIZACION}. "
        f"Revisar manualmente tras cada plenario del FATF (feb/jun/oct)."
    )
    pais_consulta = st.text_input("País de residencia o constitución del cliente", key="pais_fatf")
    if pais_consulta:
        resultado_fatf = consultar_riesgo_pais_fatf(pais_consulta)
        if resultado_fatf["riesgo"] == "ALTO":
            st.error(f"🔴 {resultado_fatf['pais']} — {resultado_fatf['categoria']} (Riesgo ALTO)")
        elif resultado_fatf["riesgo"] == "MEDIO":
            st.warning(f"🟡 {resultado_fatf['pais']} — {resultado_fatf['categoria']} (Riesgo MEDIO)")
        else:
            st.success(f"🟢 {pais_consulta} — No listado por FATF (Riesgo BAJO)")

    st.markdown("---")
    st.subheader("🏛️ Consulta proveedor del Estado (ChileCompra)")
    st.caption(
        "Verifica si un RUT está registrado como proveedor del Estado en "
        "Mercado Público (API oficial de ChileCompra). Usando el ticket de "
        "prueba público por ahora — para producción real, solicita tu "
        "propio ticket gratis vía ClaveÚnica y agrégalo como "
        "MERCADOPUBLICO_TICKET en tu .env."
    )
    rut_consulta_mp = st.text_input("RUT de la empresa a consultar (ej: 76.354.771-K)", key="rut_mp")
    if rut_consulta_mp:
        resultado_mp = consultar_proveedor_mercadopublico(rut_consulta_mp)
        if resultado_mp is None:
            st.error("❌ Error consultando Mercado Público — revisa tu conexión o el ticket configurado")
        elif resultado_mp["registrado"]:
            st.success(f"✅ Registrado como proveedor del Estado: {resultado_mp['nombre_empresa']} (código {resultado_mp['codigo_empresa']})")
        else:
            st.info(f"ℹ️ {rut_consulta_mp} no aparece registrado como proveedor del Estado")

    st.markdown("---")
    with st.expander("⚖️ Boletín Concursal — acceso rápido (consulta manual)"):
        st.caption(
            "El Boletín Concursal (Superintendencia de Insolvencia y "
            "Reemprendimiento) publica quiebras, liquidaciones y "
            "reorganizaciones de personas y empresas (Ley N°20.720). "
            "Su endpoint de descarga requiere token CSRF y sesión de "
            "navegador, por lo que no se automatizó — se deja como "
            "acceso rápido para consulta manual del oficial de "
            "cumplimiento."
        )
        st.markdown("""
- [Buscar publicaciones — Boletín Concursal](https://www.boletinconcursal.cl/boletin/procedimientos)
- [Verificación de documentos](https://www.boletinconcursal.cl/boletin/verificacion)
""")

    st.markdown("---")
    with st.expander("⚖️ Poder Judicial y Diario Oficial — accesos rápidos (consulta manual)"):
        st.caption(
            "El buscador de causas del Poder Judicial usa CAPTCHA (protección "
            "anti-scraping deliberada), y el Diario Oficial no tiene API "
            "pública documentada — ambos se dejan como acceso rápido para "
            "consulta manual del oficial de cumplimiento, en vez de "
            "automatizarse."
        )
        st.markdown("""
- [Consulta de Causas — Poder Judicial](https://www2.pjud.cl/consulta-de-causas2)
- [Oficina Judicial Virtual](https://oficinajudicialvirtual.pjud.cl/home/index.php)
- [Diario Oficial — Edición Electrónica](https://www.diariooficial.interior.gob.cl/edicionelectronica/index.php)
""")

    st.markdown("---")
    with st.expander("🏢 Registro de Empresas y Sociedades — Régimen Simplificado (caché local)"):
        st.error(
            "⚠️ **Cobertura limitada — leer antes de usar:**\n\n"
            "- Solo incluye empresas constituidas por **\"Empresa en un Día\"** "
            "(régimen simplificado/online, Ley N°20.659).\n"
            "- **NO incluye** empresas constituidas de forma tradicional "
            "(escritura pública ante notario) — la mayoría de las empresas "
            "grandes o antiguas caen en esta categoría y **no aparecerán aquí**.\n"
            f"- Los datos cubren como máximo los **últimos {res_simplificado.ANOS_RECIENTES_A_DESCARGAR} años** "
            "disponibles en la fuente (se recalcula automáticamente cada vez "
            "que actualizas — no necesitas ajustar años a mano).\n\n"
            "**Un resultado 'no encontrado' NO significa que la empresa no "
            "exista o no esté vigente** — solo que no se constituyó por "
            "esta vía específica. Fuente: datos.gob.cl (Ministerio de Hacienda)."
        )
        ultima_act_res = fecha_ultima_actualizacion_res()
        if ultima_act_res:
            st.caption(f"📅 Última actualización local: {ultima_act_res}")
        else:
            st.warning("⚠️ Aún no se ha descargado esta base local.")

        if st.button(f"🔄 Actualizar Registro de Empresas (últimos {res_simplificado.ANOS_RECIENTES_A_DESCARGAR} años disponibles)"):
            estado_res = st.empty()
            with st.spinner("Descargando datos.gob.cl..."):
                exito_res, mensaje_res, total_res = descargar_res_simplificado(
                    progreso_callback=lambda m: estado_res.text(m)
                )
            estado_res.empty()
            if exito_res:
                st.success(mensaje_res)
            else:
                st.error(mensaje_res)

        rut_consulta_res = st.text_input("RUT de la empresa a consultar", key="rut_res")
        if rut_consulta_res:
            resultados_res = buscar_empresa_res(rut_consulta_res)
            if resultados_res:
                for r in resultados_res:
                    st.success(f"✅ Encontrada en Régimen Simplificado: {r['razon_social']} — constituida {r['fecha_constitucion']} ({r['anio_origen']})")
            else:
                st.info(
                    f"ℹ️ {rut_consulta_res} no aparece en el Registro Simplificado. "
                    "Esto NO confirma que la empresa no exista — puede estar "
                    "constituida de forma tradicional (no cubierta por esta fuente) "
                    "o fuera del rango de años descargado."
                )