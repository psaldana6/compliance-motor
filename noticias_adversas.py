import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# ─── CONFIGURACIÓN ───────────────────────────────────────
load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
CMF_API_KEY = os.getenv("CMF_API_KEY")

# ─── NEWSAPI — NOTICIAS ADVERSAS ─────────────────────────
def buscar_noticias_adversas(nombre, dias=30):
    """
    Busca noticias negativas sobre un cliente en medios mundiales.
    Palabras clave de riesgo: fraude, lavado, corrupción, sanción, etc.
    """
    if not NEWSAPI_KEY:
        print("⚠️  NEWSAPI_KEY no configurada en .env")
        return []

    fecha_desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

    # Términos de riesgo en español e inglés
    terminos_riesgo = [
        "fraude", "lavado", "corrupción", "sanción", "investigado",
        "fraud", "money laundering", "corruption", "sanction", "investigated",
        "detenido", "imputado", "formalizado", "arrested", "indicted"
    ]

    query = f'"{nombre}" AND ({" OR ".join(terminos_riesgo[:5])})'

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": fecha_desde,
        "language": "es",
        "sortBy": "relevancy",
        "pageSize": 5,
        "apiKey": NEWSAPI_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            print(f"⚠️  Error NewsAPI: {data.get('message', 'Error desconocido')}")
            return []

        articulos = data.get("articles", [])
        resultados = []

        for art in articulos:
            resultados.append({
                "fecha": art.get("publishedAt", "")[:10],
                "titulo": art.get("title", ""),
                "fuente": art.get("source", {}).get("name", ""),
                "url": art.get("url", ""),
                "tipo": "NOTICIA ADVERSA"
            })

        return resultados

    except Exception as e:
        print(f"❌ Error consultando NewsAPI: {e}")
        return []

# ─── CMF CHILE — ENTIDADES REGULADAS ─────────────────────
def buscar_en_cmf(nombre):
    """
    Busca si el cliente está vinculado a entidades reguladas por la CMF.
    Útil para detectar personas relacionadas con instituciones financieras.
    """
    if not CMF_API_KEY:
        print("⚠️  CMF_API_KEY no configurada en .env")
        return []

    url = f"https://api.cmfchile.cl/api-sbifv3/recursos_api/empresas?apikey={CMF_API_KEY}&formato=json"

    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        empresas = data.get("Empresas", [])

        resultados = []
        nombre_upper = nombre.upper()

        for empresa in empresas:
            nombre_empresa = empresa.get("Nombre", "").upper()
            if nombre_upper in nombre_empresa or nombre_empresa in nombre_upper:
                resultados.append({
                    "entidad": empresa.get("Nombre", ""),
                    "rut": empresa.get("RUT", ""),
                    "tipo": empresa.get("Tipo", ""),
                    "fuente": "CMF Chile"
                })

        return resultados

    except Exception as e:
        print(f"❌ Error consultando CMF: {e}")
        return []

# ─── ANÁLISIS COMPLETO DE RIESGO REPUTACIONAL ────────────
def analizar_riesgo_reputacional(nombre, dias=30):
    """
    Análisis completo: noticias adversas + CMF
    """
    print(f"\nAnalizando riesgo reputacional: {nombre}")
    print("-" * 45)

    resultado = {
        "cliente": nombre,
        "fecha_analisis": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "noticias_adversas": [],
        "vinculo_cmf": [],
        "nivel_riesgo": "BAJO"
    }

    # Noticias adversas
    noticias = buscar_noticias_adversas(nombre, dias)
    if noticias:
        resultado["noticias_adversas"] = noticias
        resultado["nivel_riesgo"] = "ALTO"
        print(f"⚠️  {len(noticias)} noticia(s) adversa(s) encontrada(s)")
        for n in noticias:
            print(f"   📰 {n['fecha']} | {n['fuente']} | {n['titulo'][:60]}...")
    else:
        print("✅ Sin noticias adversas")

    # CMF
    cmf = buscar_en_cmf(nombre)
    if cmf:
        resultado["vinculo_cmf"] = cmf
        print(f"ℹ️  {len(cmf)} vínculo(s) con entidades CMF")
        for c in cmf:
            print(f"   🏦 {c['entidad']} ({c['tipo']})")
    else:
        print("✅ Sin vínculos CMF directos")

    return resultado

# ─── PRUEBA ───────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("MOTOR DE NOTICIAS ADVERSAS Y CMF")
    print("="*55)

    clientes_prueba = ["Kim Jong Un", "Juan Pérez García", "Elon Musk"]

    for cliente in clientes_prueba:
        analizar_riesgo_reputacional(cliente)

    print("\n" + "="*55)
    print("Análisis completado")
    print("="*55)