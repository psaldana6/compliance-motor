import sqlite3
import json

conn = sqlite3.connect("compliance_motor.db")
cursor = conn.cursor()

cursor.execute("SELECT raw_json FROM pep_chile WHERE raw_json LIKE '%Boric%' LIMIT 1")
row = cursor.fetchone()

if row:
    data = json.loads(row[0])
    print("=== CLAVES DISPONIBLES EN EL REGISTRO ===")
    for clave, valor in data.items():
        if isinstance(valor, dict) and "value" in valor:
            print(f"  {clave}: '{valor['value']}'")
        else:
            print(f"  {clave}: {valor}")
else:
    print("No se encontro ningun registro con Boric en raw_json")

conn.close()
