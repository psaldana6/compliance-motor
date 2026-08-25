import requests
import pandas as pd
from rapidfuzz import fuzz
from datetime import datetime
import xml.etree.ElementTree as ET

# ─── CONFIGURACIÓN ───────────────────────────────────────
SCORE_MINIMO = 85

# ─── 1. UNIÓN EUROPEA ────────────────────────────────────
def cargar_lista_eu():
    """Descarga lista de sanciones de la UE via XML"""
    url = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"
    try:
        response = requests.get(url, timeout=30)
        root = ET.fromstring(response.content)
        nombres = []
        for entity in root.iter("nameAlias"):
            nombre = entity.get("wholeName", "")
            if not nombre:
                nombre = entity.get("firstName", "") + " " + entity.get("lastName", "")
            if nombre.strip():
                nombres.append(nombre.strip())
        # También buscar entidades
        for entity in root.iter("entity"):
            nombre = entity.findtext("name", "")
            if nombre:
                nombres.append(nombre.strip())
        print(f"✅ EU Sanctions: {len(nombres):,} entradas cargadas")
        return nombres
    except Exception as e:
        print(f"⚠️  Error cargando EU Sanctions: {e}")
        return []

# ─── 2. NACIONES UNIDAS ──────────────────────────────────
def cargar_lista_onu():
    """Descarga lista de sanciones de la ONU"""
    url = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    try:
        response = requests.get(url, timeout=30)
        root = ET.fromstring(response.content)
        nombres = []
        for individual in root.iter("INDIVIDUAL"):
            first = individual.findtext("FIRST_NAME", "")
            second = individual.findtext("SECOND_NAME", "")
            third = individual.findtext("THIRD_NAME", "")
            nombre_completo = " ".join(filter(None, [first, second, third])).strip()
            if nombre_completo:
                nombres.append(nombre_completo)
        for entity in root.iter("ENTITY"):
            nombre = entity.findtext("FIRST_NAME", "")
            if nombre:
                nombres.append(nombre.strip())
        print(f"✅ ONU Sanctions: {len(nombres):,} entradas cargadas")
        return nombres
    except Exception as e:
        print(f"⚠️  Error cargando ONU Sanctions: {e}")
        return []

# ─── 3. REINO UNIDO ──────────────────────────────────────
def cargar_lista_uk():
    """Descarga UK Sanctions List — nueva lista desde enero 2026"""
    url = "https://assets.publishing.service.gov.uk/media/uk-sanctions-list.csv"
    try:
        response = requests.get(url, timeout=30)
        df = pd.read_csv(pd.io.common.BytesIO(response.content), encoding="latin-1", on_bad_lines="skip")
        # Buscar columna de nombres
        col_nombre = [c for c in df.columns if "name" in c.lower() or "nombre" in c.lower()]
        if col_nombre:
            nombres = df[col_nombre[0]].dropna().str.strip().tolist()
        else:
            nombres = df.iloc[:, 0].dropna().str.strip().tolist()
        print(f"✅ UK Sanctions: {len(nombres):,} entradas cargadas")
        return nombres
    except Exception as e:
        print(f"⚠️  Error cargando UK Sanctions: {e}")
        return []

# ─── 4. CMF CHILE ────────────────────────────────────────
def cargar_lista_cmf():
    """Consulta API de la CMF Chile"""
    url = "https://api.cmfchile.cl/api-sbifv3/recursos_api/instituciones?apikey=DEMO&formato=json"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        instituciones = [i.get("Nombre", "") for i in data.get("Instituciones", [])]
        print(f"✅ CMF Chile: {len(instituciones):,} instituciones cargadas")
        return instituciones
    except Exception as e:
        print(f"⚠️  Error cargando CMF: {e}")
        return []

# ─── 5. INTERPOL — NOTIFICACIONES ROJAS (GRATIS, SIN KEY) ─
def buscar_interpol_red_notices(nombre):
    """
    Consulta la API pública de INTERPOL (personas con notificación roja,
    es decir, buscadas internacionalmente). Gratuita, no requiere key.
    Docs: https://interpol.api.bund.dev/ (ws-public.interpol.int)
    Es una consulta en vivo por nombre, no una lista descargable completa.
    """
    partes = nombre.strip().split()
    if not partes:
        return []
    forename = partes[0]
    apellido = " ".join(partes[1:]) if len(partes) > 1 else ""

    url = "https://ws-public.interpol.int/notices/v1/red"
    params = {"forename": forename, "name": apellido, "resultPerPage": 20}

    try:
        response = requests.get(url, params=params, timeout=15,
                                 headers={"Accept": "application/json"})
        data = response.json()
        notices = data.get("_embedded", {}).get("notices", [])
        resultados = []
        for n in notices:
            resultados.append({
                "match": f"{n.get('forename', '')} {n.get('name', '')}".strip(),
                "entity_id": n.get("entity_id", ""),
                "fuente": "INTERPOL Red Notice",
                "detalle_url": n.get("_links", {}).get("self", {}).get("href", "")
            })
        return resultados
    except Exception as e:
        print(f"⚠️  Error consultando INTERPOL: {e}")
        return []

# ─── 6. FATF/GAFI — PAÍSES DE ALTO RIESGO (LISTA ESTÁTICA) ─
# El FATF/GAFI NO publica una API — solo páginas web, actualizadas
# 3 veces al año en sus plenarios. Por eso esta lista está embebida
# en el código (no es una consulta en vivo) y debe revisarse
# manualmente contra https://www.fatf-gafi.org/en/countries/black-and-grey-lists.html
# tras cada plenario (~febrero, junio, octubre).
FATF_ULTIMA_ACTUALIZACION = "19 de junio de 2026"

# Lista negra — "High-Risk Jurisdictions subject to a Call for Action"
FATF_LISTA_NEGRA = ["Corea del Norte", "Irán", "Myanmar"]

# Lista gris — "Jurisdictions under Increased Monitoring"
FATF_LISTA_GRIS = [
    "Argelia", "Angola", "Bolivia", "Bulgaria", "Camerún",
    "Costa de Marfil", "República Democrática del Congo", "Haití",
    "Kenia", "Laos", "Líbano", "Mónaco", "Namibia", "Nepal",
    "Sudán del Sur", "Siria", "Venezuela", "Vietnam",
    "Islas Vírgenes Británicas", "Yemen", "Bosnia y Herzegovina", "Irak",
    "Kuwait", "Papúa Nueva Guinea",
]

def consultar_riesgo_pais_fatf(pais):
    """
    Consulta si un país está en lista negra o gris del FATF/GAFI.
    Lista estática embebida (ver FATF_ULTIMA_ACTUALIZACION) —
    NO es una consulta en vivo, ya que el FATF no ofrece API.
    Útil para debida diligencia reforzada según nacionalidad/país
    de constitución del cliente (Circular UAF N°57).
    """
    pais_norm = pais.strip().lower()
    for p in FATF_LISTA_NEGRA:
        if p.lower() == pais_norm:
            return {"riesgo": "ALTO", "categoria": "Lista negra FATF (Call for Action)",
                    "pais": p, "actualizado": FATF_ULTIMA_ACTUALIZACION}
    for p in FATF_LISTA_GRIS:
        if p.lower() == pais_norm:
            return {"riesgo": "MEDIO", "categoria": "Lista gris FATF (Increased Monitoring)",
                    "pais": p, "actualizado": FATF_ULTIMA_ACTUALIZACION}
    return {"riesgo": "BAJO", "categoria": "No listado por FATF", "pais": pais,
            "actualizado": FATF_ULTIMA_ACTUALIZACION}

# ─── MOTOR DE BÚSQUEDA MULTI-FUENTE ──────────────────────
def buscar_todas_las_fuentes(nombre, score_minimo=SCORE_MINIMO):
    """Busca un nombre en todas las fuentes disponibles"""
    resultados = []

    fuentes = {
        "EU Sanctions": cargar_lista_eu(),
        "ONU Sanctions": cargar_lista_onu(),
        "UK Sanctions": cargar_lista_uk(),
    }

    for fuente_nombre, lista in fuentes.items():
        if not lista:
            continue
        for nombre_lista in lista:
            score = fuzz.token_sort_ratio(nombre.upper(), str(nombre_lista).upper())
            if score >= score_minimo:
                resultados.append({
                    "match": nombre_lista,
                    "score": score,
                    "fuente": fuente_nombre
                })

    return sorted(resultados, key=lambda x: x["score"], reverse=True)[:5]

# ─── PRUEBA ───────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("PRUEBA MULTI-FUENTE SANCIONES")
    print("="*55 + "\n")

    nombres_prueba = ["Vladimir Putin", "Kim Jong Un", "Juan Pérez"]

    for nombre in nombres_prueba:
        print(f"\nBuscando: {nombre}")
        resultados = buscar_todas_las_fuentes(nombre)
        if resultados:
            for r in resultados:
                print(f"  ⚠️  Match: {r['match']} | Score: {r['score']}% | Fuente: {r['fuente']}")
        else:
            print(f"  ✅ Sin matches")