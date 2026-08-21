import requests
from rapidfuzz import fuzz
import pandas as pd
from datetime import datetime

# ─── CONFIGURACIÓN ───────────────────────────────────────
SCORE_MINIMO = 85  # % de similitud para generar alerta
ARCHIVO_CLIENTES = "clientes.csv"

# ─── FUNCIÓN PRINCIPAL DE MATCHING ───────────────────────
def buscar_en_opensanctions(nombre):
    """Busca un nombre en OpenSanctions y retorna matches"""
    url = "https://api.opensanctions.org/match/default"
    payload = {
        "queries": {
            "q1": {
                "schema": "Person",
                "properties": {"name": [nombre]}
            }
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        resultados = data.get("responses", {}).get("q1", {}).get("results", [])
        return resultados
    except Exception as e:
        print(f"Error consultando OpenSanctions: {e}")
        return []

def analizar_clientes():
    """Lee la lista de clientes y los chequea contra listas"""
    alertas = []

    # Clientes de prueba (después conectamos tu CSV real)
    clientes = [
        {"id": "001", "nombre": "Juan Pérez García", "rut": "12345678-9"},
        {"id": "002", "nombre": "Vladimir Putin",    "rut": "98765432-1"},
        {"id": "003", "nombre": "María González",    "rut": "11111111-1"},
    ]

    print(f"\n{'='*50}")
    print(f"MOTOR DE COMPLIANCE - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")
    print(f"Chequeando {len(clientes)} clientes...\n")

    for cliente in clientes:
        print(f"Verificando: {cliente['nombre']}...")
        resultados = buscar_en_opensanctions(cliente["nombre"])

        for resultado in resultados:
            score = resultado.get("score", 0)
            if score >= SCORE_MINIMO:
                alerta = {
                    "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "cliente_id": cliente["id"],
                    "cliente_nombre": cliente["nombre"],
                    "match_nombre": resultado.get("name", ""),
                    "score": score,
                    "fuente": resultado.get("datasets", [""])[0],
                    "tipo": "SANCIÓN/PEP"
                }
                alertas.append(alerta)
                print(f"  ⚠️  ALERTA: Match encontrado con score {score}%")

    if alertas:
        df = pd.DataFrame(alertas)
        df.to_csv("alertas.csv", index=False)
        print(f"\n{len(alertas)} alerta(s) guardadas en alertas.csv")
    else:
        print("\n✅ Sin alertas encontradas")

    return alertas

# ─── EJECUTAR ─────────────────────────────────────────────
if __name__ == "__main__":
    analizar_clientes()