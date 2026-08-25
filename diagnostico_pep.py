"""
Script de diagnóstico: busca "Boric" en la base local de PEP Chile
para ver exactamente qué se guardó como nombre/cargo/raw_json.
Correr desde la carpeta del proyecto: python diagnostico_pep.py
"""
import sqlite3
import json

conn = sqlite3.connect("compliance_motor.db")
cursor = conn.cursor()

print("=== Búsqueda por columna 'nombre' ===")
cursor.execute("SELECT nombre, cargo, institucion FROM pep_chile WHERE nombre LIKE '%Boric%' LIMIT 5")
resultados = cursor.fetchall()
if resultados:
    for r in resultados:
        print(r)
else:
    print("(sin resultados en la columna 'nombre')")

print("\n=== Búsqueda por raw_json (por si el nombre quedó en otro campo) ===")
cursor.execute("SELECT nombre, cargo, raw_json FROM pep_chile WHERE raw_json LIKE '%Boric%' LIMIT 3")
resultados2 = cursor.fetchall()
if resultados2:
    for nombre, cargo, raw in resultados2:
        print(f"\nnombre extraído: '{nombre}' | cargo extraído: '{cargo}'")
        print("raw_json completo del registro:")
        print(json.dumps(json.loads(raw), indent=2, ensure_ascii=False))
else:
    print("(sin resultados — 'Boric' no aparece en ningún registro descargado)")

print("\n=== Muestra de 3 registros cualquiera (para ver la forma general) ===")
cursor.execute("SELECT nombre, cargo, institucion FROM pep_chile LIMIT 3")
for r in cursor.fetchall():
    print(r)

conn.close()
