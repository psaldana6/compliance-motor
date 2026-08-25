import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

# ─── CONFIGURACIÓN ───────────────────────────────────────
load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
CMF_API_KEY = os.getenv("CMF_API_KEY")

# Términos de riesgo compartidos (ES/EN) — alineados a delitos base
# de la Ley 20.393 (lavado de activos, cohecho/soborno, financiamiento
# del terrorismo, receptación, corrupción entre particulares, etc.)
TERMINOS_RIESGO = [
    "fraude", "lavado de activos", "lavado de dinero", "corrupción",
    "cohecho", "soborno", "sanción", "investigado", "estafa",
    "financiamiento del terrorismo", "evasión tributaria",
    "fraud", "money laundering", "corruption", "bribery", "sanction",
    "investigated", "detenido", "imputado", "formalizado", "arrested", "indicted"
]

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
    query = f'"{nombre}" AND ({" OR ".join(TERMINOS_RIESGO[:5])})'

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

# ─── GDELT — MONITOREO GLOBAL DE PRENSA (GRATIS, SIN KEY) ─
def buscar_noticias_gdelt(nombre, dias=30):
    """
    Busca noticias adversas usando el GDELT Project DOC 2.0 API.
    Cubre miles de medios a nivel mundial (incluye prensa chilena/LatAm),
    es gratuito, público y no requiere API key — buen respaldo/backup de
    NewsAPI (cuyo plan gratuito no permite uso comercial/producción).
    Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
    """
    dias = max(1, min(dias, 90))  # GDELT limita el rango de búsqueda
    # GDELT rechaza queries booleanas muy largas (responde HTML, no JSON).
    # Usamos solo el nombre entre comillas — más resultados, y filtramos
    # por términos de riesgo del lado del cliente, igual que hace el
    # análisis final al combinar todas las fuentes.
    query = f'"{nombre}"'

    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": 30,
        "format": "json",
        "timespan": f"{dias}d",
        "sort": "DateDesc",
    }

    try:
        response = requests.get(url, params=params, timeout=30,
                                 headers={"User-Agent": "Mozilla/5.0"})
        texto = response.text.strip()
        if not texto or not texto.startswith("{"):
            # GDELT devuelve HTML/vacío cuando la query es rechazada o
            # no hay resultados — no es un error crítico, solo no hay datos.
            return []
        data = response.json()
        articulos = data.get("articles", [])
        resultados = []
        for art in articulos:
            titulo = art.get("title", "")
            # Filtro de riesgo del lado del cliente (case-insensitive)
            if not any(t.lower() in titulo.lower() for t in TERMINOS_RIESGO):
                continue
            seendate = art.get("seendate", "")  # formato YYYYMMDDTHHMMSSZ
            fecha = f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}" if len(seendate) >= 8 else ""
            resultados.append({
                "fecha": fecha,
                "titulo": titulo,
                "fuente": art.get("domain", ""),
                "url": art.get("url", ""),
                "tipo": "NOTICIA ADVERSA (GDELT)"
            })
        return resultados
    except Exception as e:
        print(f"⚠️  Error consultando GDELT: {e}")
        return []

# ─── GOOGLE NEWS RSS — NOTICIAS EN ESPAÑOL (GRATIS, SIN KEY) ─
def buscar_google_news_rss(nombre, dias=30):
    """
    Busca noticias adversas en Google News RSS, localizado para Chile
    (hl=es-419&gl=CL). Gratuito, sin API key, buena cobertura de
    prensa local (útil para PLA/FT y debida diligencia reforzada
    según Circular UAF N°49 / N°57 para el mercado de valores).
    """
    import xml.etree.ElementTree as ET

    terminos = " OR ".join(TERMINOS_RIESGO[:8])
    consulta = f'"{nombre}" ({terminos})'
    url = f"https://news.google.com/rss/search?q={quote(consulta)}&hl=es-419&gl=CL&ceid=CL:es"

    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(response.content)
        fecha_limite = datetime.now(timezone.utc) - timedelta(days=dias)

        resultados = []
        for item in root.findall(".//item")[:15]:
            pub_date_raw = item.findtext("pubDate", "")
            try:
                fecha_dt = parsedate_to_datetime(pub_date_raw)
                if fecha_dt.tzinfo is None:
                    fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
            except Exception:
                fecha_dt = None

            if fecha_dt and fecha_dt < fecha_limite:
                continue

            fuente_el = item.find("source")
            resultados.append({
                "fecha": fecha_dt.strftime("%Y-%m-%d") if fecha_dt else "",
                "titulo": item.findtext("title", ""),
                "fuente": fuente_el.text if fuente_el is not None else "Google News",
                "url": item.findtext("link", ""),
                "tipo": "NOTICIA ADVERSA (Google News)"
            })
        return resultados
    except Exception as e:
        print(f"⚠️  Error consultando Google News RSS: {e}")
        return []

# Medios chilenos de investigación/finanzas priorizados por el equipo
# de compliance para debida diligencia reforzada (Circular UAF N°57).
MEDIOS_CHILENOS_PRIORITARIOS = [
    "emol.com", "latercera.com", "biobiochile.cl", "cnnchile.com",
    "df.cl", "pulso.cl", "elmostrador.cl", "ciperchile.cl",
    "theclinic.cl", "cooperativa.cl", "chvnoticias.cl",
    "fastcheck.cl", "interferencia.cl",
]

# ─── GOOGLE NEWS RSS DIRIGIDO — MEDIOS CHILENOS PRIORITARIOS ─
def buscar_google_news_medios_chile(nombre, dias=30):
    """
    Igual que buscar_google_news_rss, pero restringido a un listado
    curado de medios chilenos de investigación y finanzas (Circular
    UAF N°57 recomienda debida diligencia reforzada apoyada en fuentes
    de prensa local especializada, no solo cobertura internacional).
    Se ejecuta como fuente ADICIONAL, no reemplaza la búsqueda global.
    """
    import xml.etree.ElementTree as ET

    filtro_sitios = " OR ".join(f"site:{m}" for m in MEDIOS_CHILENOS_PRIORITARIOS)
    consulta = f'"{nombre}" ({filtro_sitios})'
    url = f"https://news.google.com/rss/search?q={quote(consulta)}&hl=es-419&gl=CL&ceid=CL:es"

    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(response.content)
        fecha_limite = datetime.now(timezone.utc) - timedelta(days=dias)

        resultados = []
        for item in root.findall(".//item")[:15]:
            pub_date_raw = item.findtext("pubDate", "")
            try:
                fecha_dt = parsedate_to_datetime(pub_date_raw)
                if fecha_dt.tzinfo is None:
                    fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
            except Exception:
                fecha_dt = None

            if fecha_dt and fecha_dt < fecha_limite:
                continue

            fuente_el = item.find("source")
            resultados.append({
                "fecha": fecha_dt.strftime("%Y-%m-%d") if fecha_dt else "",
                "titulo": item.findtext("title", ""),
                "fuente": fuente_el.text if fuente_el is not None else "Google News",
                "url": item.findtext("link", ""),
                "tipo": "NOTICIA ADVERSA (Medios CL priorizados)"
            })
        return resultados
    except Exception as e:
        print(f"⚠️  Error consultando Google News (medios CL): {e}")
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

    # Noticias adversas — se combinan varias fuentes gratuitas/públicas.
    # NewsAPI solo corre si hay key configurada; GDELT y Google News
    # RSS siempre corren porque no requieren key, así el motor funciona
    # sin depender de un plan pago.
    noticias = []
    noticias += buscar_noticias_adversas(nombre, dias)
    noticias += buscar_noticias_gdelt(nombre, dias)
    noticias += buscar_google_news_rss(nombre, dias)
    noticias += buscar_google_news_medios_chile(nombre, dias)

    # Deduplicar por URL (o por título si no hay URL)
    vistos = set()
    noticias_unicas = []
    for n in noticias:
        clave = n.get("url") or n.get("titulo")
        if clave and clave not in vistos:
            vistos.add(clave)
            noticias_unicas.append(n)
    noticias = noticias_unicas

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