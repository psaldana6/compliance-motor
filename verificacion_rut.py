import requests
from datetime import datetime

# ─── VERIFICACIÓN RUT CHILE via Boostr ───────────────────
def verificar_rut(rut):
    """
    Verifica si un RUT chileno es válido y obtiene información.
    Usa la API gratuita de Boostr.
    """
    # Limpiar RUT — quitar puntos y guión
    rut_limpio = rut.replace(".", "").replace("-", "").strip()
    
    url = f"https://api.boostr.cl/rut/{rut_limpio}.json"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "rut": rut,
                "valido": data.get("status") == "ok",
                "nombre": data.get("data", {}).get("nombre", ""),
                "actividades": data.get("data", {}).get("actividades", []),
                "fuente": "Boostr / SII"
            }
        else:
            return {
                "rut": rut,
                "valido": False,
                "nombre": "",
                "actividades": [],
                "fuente": "Boostr / SII"
            }
    except Exception as e:
        print(f"❌ Error verificando RUT {rut}: {e}")
        return None

def verificar_lista_clientes(clientes):
    """
    Verifica todos los RUTs de una lista de clientes.
    clientes: lista de dicts con keys 'id', 'nombre', 'rut'
    """
    print("\n" + "="*55)
    print("VERIFICACIÓN DE RUT — KYC")
    print("="*55 + "\n")

    resultados = {
        "validos": [],
        "invalidos": [],
        "alertas": []
    }

    for cliente in clientes:
        print(f"Verificando RUT: {cliente['rut']} — {cliente['nombre']}...")
        resultado = verificar_rut(cliente["rut"])

        if resultado is None:
            continue

        if resultado["valido"]:
            resultados["validos"].append(cliente)
            print(f"  ✅ RUT válido")

            # Alerta si el nombre no coincide
            if resultado["nombre"] and cliente["nombre"].upper() not in resultado["nombre"].upper():
                alerta = {
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "ID Cliente": cliente["id"],
                    "Nombre Cliente": cliente["nombre"],
                    "RUT": cliente["rut"],
                    "Nombre SII": resultado["nombre"],
                    "Tipo alerta": "DISCREPANCIA NOMBRE/RUT",
                    "Riesgo": "MEDIO"
                }
                resultados["alertas"].append(alerta)
                print(f"  ⚠️  Discrepancia: cliente dice '{cliente['nombre']}' pero SII dice '{resultado['nombre']}'")
        else:
            resultados["invalidos"].append(cliente)
            alerta = {
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "ID Cliente": cliente["id"],
                "Nombre Cliente": cliente["nombre"],
                "RUT": cliente["rut"],
                "Nombre SII": "",
                "Tipo alerta": "RUT INVÁLIDO",
                "Riesgo": "ALTO"
            }
            resultados["alertas"].append(alerta)
            print(f"  ❌ RUT inválido o no encontrado")

    print(f"\n{'='*55}")
    print(f"Resumen KYC:")
    print(f"  ✅ RUTs válidos: {len(resultados['validos'])}")
    print(f"  ❌ RUTs inválidos: {len(resultados['invalidos'])}")
    print(f"  ⚠️  Alertas: {len(resultados['alertas'])}")
    print(f"{'='*55}\n")

    return resultados

# ─── PRUEBA ───────────────────────────────────────────────
if __name__ == "__main__":
    clientes_prueba = [
        {"id": "001", "nombre": "Juan Pérez García", "rut": "12345678-9"},
        {"id": "002", "nombre": "Vladimir Putin", "rut": "98765432-1"},
        {"id": "003", "nombre": "Empresa Prueba", "rut": "76354771-K"},
    ]
    resultados = verificar_lista_clientes(clientes_prueba)