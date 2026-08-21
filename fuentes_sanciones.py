import requests
import pandas as pd
from rapidfuzz import fuzz
from datetime import datetime
import xml.etree.ElementTree as ET

# ─── CONFIGURACIÓN ───────────────────────────────────────
SCORE_MINIMO = 85

# ─── 1. UNIÓN EUROPEA ────────────────────────────────────
def cargar_lista_eu():
    """Descarga lista de sanciones de la UE"""
    url = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNy0wMS0wMQ"
    try:
        df = pd.read_csv(url, sep=";", encoding="utf-8", on_bad_lines="skip")
        nombres = df.iloc[:, 0].dropna().str.strip().tolist()
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
    """Descarga lista de sanciones del Reino Unido"""
    url = "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/consolidated-list-of-financial-sanctions-targets.csv"
    try:
        df = pd.read_csv(url, encoding="latin-1", on_bad_lines="skip")
        nombres = df.iloc[:, 5].dropna().str.strip().tolist()
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