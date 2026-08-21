import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# ─── CARGAR VARIABLES DE ENTORNO ─────────────────────────
load_dotenv()

EMAIL_ORIGEN = os.getenv("EMAIL_ORIGEN")
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO")
APP_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

def enviar_alerta_email(alertas, tipo="LISTA NEGRA"):
    if not alertas:
        print("Sin alertas que enviar")
        return False

    if not EMAIL_ORIGEN or not APP_PASSWORD:
        print("⚠️  Credenciales de email no configuradas en .env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 ALERTA COMPLIANCE — {tipo} — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    msg["From"] = EMAIL_ORIGEN
    msg["To"] = EMAIL_DESTINO

    filas_html = ""
    for a in alertas:
        filas_html += "<tr>"
        for valor in a.values():
            filas_html += f"<td style='padding:8px;border:1px solid #ddd'>{valor}</td>"
        filas_html += "</tr>"

    encabezados_html = ""
    for col in alertas[0].keys():
        encabezados_html += f"<th style='padding:8px;background:#c0392b;color:white;border:1px solid #ddd'>{col}</th>"

    html = f"""
    <html><body>
    <div style="font-family:Arial,sans-serif;max-width:900px;margin:auto">
        <div style="background:#c0392b;color:white;padding:20px;border-radius:8px 8px 0 0">
            <h2 style="margin:0">🚨 Alerta de Compliance</h2>
            <p style="margin:5px 0">Tipo: <strong>{tipo}</strong></p>
            <p style="margin:5px 0">Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            <p style="margin:5px 0">Total alertas: <strong>{len(alertas)}</strong></p>
        </div>
        <div style="padding:20px;background:#f9f9f9;border:1px solid #ddd">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead><tr>{encabezados_html}</tr></thead>
                <tbody>{filas_html}</tbody>
            </table>
        </div>
        <div style="padding:15px;background:#ecf0f1;border-radius:0 0 8px 8px;font-size:12px;color:#666">
            Este es un mensaje automático del Motor de Compliance.
            Por favor no responda este correo.
        </div>
    </div>
    </body></html>
    """

    msg.attach(MIMEText(html, "html"))

    df = pd.DataFrame(alertas)
    csv_path = f"alertas_temp_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df.to_csv(csv_path, index=False)

    with open(csv_path, "rb") as f:
        adjunto = MIMEBase("application", "octet-stream")
        adjunto.set_payload(f.read())
        encoders.encode_base64(adjunto)
        adjunto.add_header("Content-Disposition", f"attachment; filename={csv_path}")
        msg.attach(adjunto)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ORIGEN, APP_PASSWORD)
            server.sendmail(EMAIL_ORIGEN, EMAIL_DESTINO, msg.as_string())
        print(f"✅ Email enviado a {EMAIL_DESTINO}")
        os.remove(csv_path)
        return True
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False

if __name__ == "__main__":
    alertas_prueba = [
        {
            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "ID Cliente": "004",
            "Nombre Cliente": "Kim Jong Un",
            "RUT": "22222222-2",
            "Match Encontrado": "KIM, Jong Un",
            "Score %": 95.65,
            "Fuente": "OFAC SDN List",
            "Tipo": "SANCIÓN OFAC"
        }
    ]
    enviar_alerta_email(alertas_prueba, "LISTA NEGRA")