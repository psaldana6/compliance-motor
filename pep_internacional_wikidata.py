"""
Módulo PEP Internacional — Wikidata.

Wikidata es una base de conocimiento de dominio público (licencia CC0),
mantenida por la Fundación Wikimedia — sin restricciones de uso
comercial (a diferencia de OpenSanctions, que requiere licencia
paga para uso comercial). Se usa aquí como fuente complementaria de
PEP INTERNACIONAL (fuera de Chile), ya que PEP Chile (InfoProbidad)
solo cubre autoridades chilenas.

LIMITACIÓN IMPORTANTE: Wikidata cubre bien a políticos de alto perfil
(jefes de estado, ministros, parlamentarios reconocidos internacional-
mente), pero NO es tan exhaustivo como un proveedor comercial de PEP
en niveles regionales/menores, o en familiares y allegados cercanos
de PEP (que sí exige cubrir la Circular UAF N°57/62). Es un
complemento a las fuentes ya existentes, no un reemplazo completo
de un proveedor comercial de screening PEP.
"""

import requests

WBSEARCH_URL = "https://www.wikidata.org/w/api.php"
SPARQL_URL = "https://query.wikidata.org/sparql"

# QIDs de Wikidata para "ocupación = político" y cargos políticos
# comunes — usados para filtrar si una persona encontrada por nombre
# es efectivamente un PEP (no solo un homónimo).
QID_POLITICO = "Q82955"           # occupation: politician
PROPIEDADES_CARGO_POLITICO = ["P39"]  # position held


def _buscar_candidatos_wikidata(nombre, idioma="es", limite=5):
    """Busca entidades de Wikidata que coincidan con el nombre dado."""
    params = {
        "action": "wbsearchentities",
        "search": nombre,
        "language": idioma,
        "format": "json",
        "limit": limite,
        "type": "item",
    }
    try:
        response = requests.get(WBSEARCH_URL, params=params, timeout=15,
                                 headers={"User-Agent": "MotorComplianceChile/1.0"})
        data = response.json()
        return data.get("search", [])
    except Exception as e:
        print(f"⚠️  Error buscando en Wikidata: {e}")
        return []


def _es_politico(qid):
    """
    Verifica si una entidad de Wikidata tiene ocupación 'político'
    o algún cargo político registrado (P39 no vacío), vía SPARQL.
    Devuelve (es_politico: bool, cargos: list[str]).
    """
    query = f"""
    SELECT ?cargoLabel ?paisLabel WHERE {{
      OPTIONAL {{
        wd:{qid} wdt:P39 ?cargo .
        OPTIONAL {{ wd:{qid} wdt:P27 ?pais . }}
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "es,en". }}
    }}
    LIMIT 10
    """
    try:
        response = requests.get(
            SPARQL_URL, params={"query": query, "format": "json"},
            timeout=15, headers={"User-Agent": "MotorComplianceChile/1.0",
                                  "Accept": "application/sparql-results+json"}
        )
        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])
        cargos = []
        pais = ""
        for b in bindings:
            if "cargoLabel" in b:
                cargos.append(b["cargoLabel"]["value"])
            if "paisLabel" in b and not pais:
                pais = b["paisLabel"]["value"]
        cargos = [c for c in cargos if c]
        return (len(cargos) > 0, cargos, pais)
    except Exception as e:
        print(f"⚠️  Error consultando cargo en Wikidata: {e}")
        return (False, [], "")


def buscar_pep_internacional(nombre):
    """
    Busca un nombre en Wikidata y determina si corresponde a una
    persona con cargos políticos registrados (PEP internacional).
    Es una consulta en vivo (no caché local) — 2 llamadas por
    candidato encontrado, así que puede tardar unos segundos por
    nombre. Devuelve lista de matches:
    [{nombre, descripcion, cargos, pais, qid, url}, ...]
    """
    candidatos = _buscar_candidatos_wikidata(nombre)
    resultados = []

    for c in candidatos:
        qid = c.get("id", "")
        label = c.get("label", "")
        descripcion = c.get("description", "")

        # Filtro rápido por descripción antes de gastar una consulta
        # SPARQL — muchas descripciones de políticos ya lo indican.
        descripcion_sugiere_politico = any(
            palabra in descripcion.lower() for palabra in
            ["político", "politician", "president", "presidente",
             "minister", "ministro", "senator", "senador", "diputado",
             "deputy", "primer ministro", "prime minister", "alcalde",
             "mayor", "governor", "gobernador"]
        )

        if not descripcion_sugiere_politico:
            continue  # evita gastar consultas SPARQL en homónimos obvios (ej. actores, deportistas)

        es_pol, cargos, pais = _es_politico(qid)
        if es_pol:
            resultados.append({
                "nombre": label,
                "descripcion": descripcion,
                "cargos": cargos,
                "pais": pais,
                "qid": qid,
                "url": f"https://www.wikidata.org/wiki/{qid}"
            })

    return resultados
