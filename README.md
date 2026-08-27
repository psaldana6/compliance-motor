# 🛡️ Motor de Compliance — Renta 4

Hub de monitoreo de cumplimiento normativo para corredora de bolsa, construido en Python + Streamlit. Consolida screening de sanciones, PEP (nacional e internacional), noticias adversas, detección de smurfing, KYC y verificaciones institucionales — todo con fuentes públicas gratuitas, en una sola aplicación.

> Este documento existe para que cualquier persona (o cualquier instancia de Claude) entienda el proyecto en minutos, sin depender de que alguien lo explique de memoria cada vez.

---

## 1. Cómo correr la app

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Se abre en `http://localhost:8501`. Si el puerto está ocupado, Streamlit usa el siguiente disponible (8502, etc.) — revisa la URL que imprime en la terminal.

**⚠️ Antes de correr desde una carpeta nueva:** este equipo tiene una carpeta de OneDrive corporativa (`OneDrive - RENTA 4 BANCO SA\Documentos\...`) que puede confundirse con la carpeta local del repo (`Documents\compliance-motor`). Siempre verifica con `pwd` en PowerShell que estás en la carpeta correcta antes de correr comandos.

---

## 2. Estructura del proyecto

| Archivo | Qué hace |
|---|---|
| `app.py` | La aplicación Streamlit — 5 pestañas (ver sección 3) |
| `database.py` | Inicializa y gestiona SQLite (`compliance_motor.db`) — tablas de alertas, ejecuciones, caché PEP y Registro de Empresas |
| `fuentes_sanciones.py` | OFAC, ONU, UK, EU (listas de sanciones), INTERPOL Red Notices, FATF/GAFI (riesgo país) |
| `noticias_adversas.py` | NewsAPI (opcional), GDELT, Google News (global + medios chilenos priorizados) |
| `pep_infoprobidad.py` | PEP Chile — descarga y cachea localmente el registro de autoridades de InfoProbidad (Contraloría/Consejo para la Transparencia) |
| `pep_internacional_wikidata.py` | PEP Internacional — consulta en vivo a Wikidata (dominio público, sin restricción comercial) |
| `res_simplificado.py` | Registro de Empresas y Sociedades — régimen simplificado "Empresa en un Día" (últimos 5 años, caché local) |
| `verificacion_rut.py` | Validación de RUT (algoritmo local, sin API externa) + consulta proveedor del Estado (ChileCompra) + dólar del día (Banco Central vía mindicador.cl) |
| `smurf_detector.py` | Detector de smurfing/fraccionamiento — usado por `scheduler.py` |
| `scheduler.py` | Script standalone para correr el monitoreo diario automático (cron interno vía APScheduler) + envío de alertas por email |
| `alertas_email.py` | Envío de alertas por correo (SMTP) |
| `matcher.py` | Integración con OpenSanctions — **NO conectado a la app** (requiere licencia paga para uso comercial, ver sección 6) |
| `.env` | Credenciales y API keys — **nunca se sube a git** (protegido por `.gitignore`) |

---

## 3. Las 5 pestañas de la app

### 🔍 Listas Negras / PEP
Sube un CSV de clientes (`id,nombre,rut`) y verifica contra:
- OFAC, ONU, UK, EU (listas de sanciones — descarga en vivo)
- INTERPOL Red Notices (opcional, checkbox — consulta en vivo, más lento)
- PEP Chile — InfoProbidad (caché local, se actualiza con un botón)
- PEP Internacional — Wikidata (opcional, checkbox — consulta en vivo)
- Registro de Empresas (opcional, informativo — no es alerta de riesgo)

### 💸 Smurfing / Fraccionamiento
Detecta fraccionamiento de transacciones. **El umbral se calcula en vivo** en base al dólar del día (USD 10.000 según Ley 19.913/20.818 — no un monto fijo en pesos).

### 📊 Historial y Análisis
Vista de ejecuciones y alertas guardadas en la base de datos.

### 📰 Noticias Adversas
Búsqueda combinada: NewsAPI (si hay key), GDELT, Google News global, Google News dirigido a medios chilenos de investigación/finanzas (Emol, La Tercera, BioBioChile, CNN Chile, Diario Financiero, Pulso, El Mostrador, Ciper Chile, The Clinic, Cooperativa, CHV Noticias, Fast Check CL, Interferencia). También incluye accesos rápidos a procesos sancionatorios activos de la CMF.

### 🪪 KYC / Verificación RUT
Valida RUTs (algoritmo local módulo 11 — no depende de ninguna API). Además: consulta de riesgo país (FATF/GAFI), proveedor del Estado (ChileCompra), Registro de Empresas, y accesos rápidos a Boletín Concursal, Poder Judicial y Diario Oficial.

---

## 4. Configuración — `.env`

Ninguna variable es obligatoria para que la app funcione (todo tiene comportamiento por defecto o se omite con un aviso), pero estas mejoran la cobertura:

```bash
# Email de alertas (opcional — para scheduler.py)
EMAIL_ORIGEN=tu_correo@renta4.cl
EMAIL_PASSWORD=tu_app_password        # NO tu contraseña normal, una App Password
EMAIL_DESTINO=correo_destino@renta4.cl
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587

# APIs opcionales (mejoran cobertura pero no son necesarias)
NEWSAPI_KEY=...                        # newsapi.org — plan gratis no permite uso comercial/producción
CMF_API_KEY=...                        # api.cmfchile.cl (legado SBIF)
BOOSTR_API_KEY=...                     # api.boostr.cl — solo para cruce de nombre SII en KYC (opcional)
MERCADOPUBLICO_TICKET=...              # ticket real de ClaveÚnica (si no está, usa uno de prueba público y compartido)

# Configuración del scheduler (opcional, tienen defaults razonables)
SCHEDULER_HORA=8
SCHEDULER_MINUTO=0
CLIENTES_CSV=clientes_prueba.csv
TRANSACCIONES_CSV=transacciones_prueba.csv
SCORE_MINIMO=85
SCHEDULER_INCLUIR_INTERPOL=false
```

---

## 5. Flujo de actualización del proyecto

Cada vez que se modifica el código (por ejemplo, en una sesión con Claude):

1. Descargar el `.zip` con los archivos actualizados.
2. Copiar los archivos a `C:\Users\Paul\Documents\compliance-motor` con `Copy-Item` en PowerShell (nunca arrastrar en el Explorador de Windows — el atajo "Documents" del panel izquierdo puede redirigir a la carpeta de OneDrive corporativa por error).
3. `git add .` → `git commit -m "..."` → `git push`
4. Si el cambio tocó **cualquier archivo que no sea `app.py`**, hay que reiniciar Streamlit completo (`Ctrl+C` + `streamlit run app.py`) — Python cachea los módulos ya importados, así que el auto-reload de Streamlit no basta.

**Recomendación:** usa dos ventanas de PowerShell — una dedicada a correr Streamlit (donde nunca escribes otra cosa), y otra para copiar archivos / git. Así nunca hay que adivinar cuál ventana detener.

---

## 6. Limitaciones conocidas — importante leer

| Limitación | Detalle |
|---|---|
| **GDELT y mindicador.cl bloqueados** | El firewall corporativo de Renta 4 bloquea estos dominios (`TimeoutError`/`ConnectionError`). No es un bug — se necesita que IT abra esos dominios/puertos, o el hub sigue funcionando con las demás fuentes de todos modos (fallback automático a valor de referencia para el dólar). |
| **Email SMTP bloqueado** | Puerto 587 hacia `smtp.office365.com` también bloqueado por el firewall. `scheduler.py` corre el monitoreo igual, pero no logra enviar el correo. Requiere gestión con IT (abrir el puerto, o usar un relay SMTP interno de la empresa). |
| **OpenSanctions (`matcher.py`) no está conectado** | Requiere licencia paga para uso comercial — screening de compliance cuenta como uso comercial aunque no genere ingresos directos. El código existe pero no se usa en la app hasta que se decida pagar la licencia. |
| **PEP Internacional (Wikidata) no es exhaustivo** | Cubre bien a políticos de alto perfil (jefes de estado, ministros, parlamentarios reconocidos). No iguala la profundidad de un proveedor comercial en PEP regional/familiares — es un complemento, no un reemplazo completo. |
| **Registro de Empresas — cobertura parcial** | Solo cubre "Empresa en un Día" (régimen simplificado, últimos 5 años). No cubre empresas de constitución tradicional (escritura pública). Un "no encontrado" NO significa que la empresa no exista. |
| **Beneficiarios finales (beneficial ownership)** | No hay fuente pública gratuita viable en Chile ni globalmente para esto — sigue siendo una brecha frente a un proveedor comercial tipo Gesintel. |
| **Antecedentes penales de empleados** | No consultable en masa por privacidad (requiere ClaveÚnica de la propia persona) — no automatizable. |
| **Poder Judicial, Diario Oficial, CMF Sanciones, Boletín Concursal** | Sin API pública — quedan como accesos rápidos manuales, no automatizados (algunos usan CAPTCHA deliberadamente para evitar scraping). |
| **Ya no se usa Gesintel** | El hub pasó de ser un complemento a ser la capa principal de screening externo. Revisar periódicamente si conviene contratar un proveedor comercial para cerrar las brechas de esta tabla. |

---

## 7. Marco normativo cubierto

Ver el panel **"Marco normativo cubierto"** dentro de la propia app (parte superior) — incluye matriz completa cruzando Ley N°19.913, Ley N°20.393, Ley N°21.595 (Delitos Económicos), Circular UAF N°57/62, y NCG N°571 (CMF) contra cada módulo del hub.

**Este hub apoya el cumplimiento normativo pero no lo reemplaza.** No sustituye el Modelo de Prevención de Delitos formal, la presentación del ROS a la UAF, ni el juicio profesional del Oficial de Cumplimiento — todas las alertas requieren revisión humana.

---

## 8. Datos de prueba

`clientes_prueba.csv` y `transacciones_prueba.csv` — usar como plantilla de formato para tus propios CSV reales.

---

*Última actualización de este documento: 25 de agosto de 2026.*
