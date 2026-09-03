import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Carga las variables de entorno (token, URL de la API, y datos del webhook)
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = os.getenv("API_URL")
PUBLIC_URL = os.getenv("PUBLIC_URL")  # el dominio publico que te da Railway, ej: https://xxxx.up.railway.app
PORT = int(os.getenv("PORT", "8080"))  # Railway inyecta este valor solo


def obtener_datos(endpoint: str):
    """Hace un GET a la API y devuelve la lista de datos, o None si falla."""
    try:
        respuesta = requests.get(f"{API_URL}{endpoint}", timeout=10)
        if respuesta.status_code == 200:
            return respuesta.json()
        else:
            return None
    except requests.exceptions.RequestException:
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🌱 *AgroIA Asistente*\n\n"
        "Comandos disponibles:\n"
        "/zonas - Ver zonas geográficas\n"
        "/lotes - Ver lotes de tierra\n"
        "/sensores - Ver sensores registrados\n"
        "/muestras - Ver últimas muestras de suelo\n"
        "/alertas - Ver alertas activas"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def zonas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_datos("/zonas_geograficas/list")
    if datos is None:
        await update.message.reply_text("⚠️ No se pudo consultar la API en este momento.")
        return
    if not datos:
        await update.message.reply_text("No hay zonas registradas todavía.")
        return
    lineas = [f"• {z['Zona_Nombre']} — {z.get('Zona_Descripcion', 'sin descripción')}" for z in datos]
    await update.message.reply_text("📍 *Zonas geográficas:*\n" + "\n".join(lineas), parse_mode="Markdown")


async def lotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_datos("/lotes/list")
    if datos is None:
        await update.message.reply_text("⚠️ No se pudo consultar la API en este momento.")
        return
    if not datos:
        await update.message.reply_text("No hay lotes registrados todavía.")
        return
    lineas = [f"• {l['Lote_Nombre']} — {l.get('Lote_Area', '?')} m²" for l in datos]
    await update.message.reply_text("🌾 *Lotes de tierra:*\n" + "\n".join(lineas), parse_mode="Markdown")


async def sensores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_datos("/sensores/list")
    if datos is None:
        await update.message.reply_text("⚠️ No se pudo consultar la API en este momento.")
        return
    if not datos:
        await update.message.reply_text("No hay sensores registrados todavía.")
        return
    lineas = [f"• {s['Sensor_Nombre']} ({s.get('Sensor_Estado', '?')})" for s in datos]
    await update.message.reply_text("📡 *Sensores:*\n" + "\n".join(lineas), parse_mode="Markdown")


async def muestras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_datos("/muestras/list")
    if datos is None:
        await update.message.reply_text("⚠️ No se pudo consultar la API en este momento.")
        return
    if not datos:
        await update.message.reply_text("No hay muestras registradas todavía.")
        return
    ultimas = datos[-5:]
    lineas = [f"• Valor: {m['Muestra_Valor']} — {m.get('Muestra_FechaHora', '?')}" for m in ultimas]
    await update.message.reply_text("🧪 *Últimas muestras:*\n" + "\n".join(lineas), parse_mode="Markdown")


async def alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_datos("/alertas/list")
    if datos is None:
        await update.message.reply_text(
            "⚠️ La API respondió con error al consultar alertas.\n"
            "(Este endpoint está fallando con error 500 - avisar al encargado del backend)"
        )
        return
    if not datos:
        await update.message.reply_text("No hay alertas activas.")
        return
    lineas = [f"• [{a['Alerta_Nivel']}] {a['Alerta_Tipo']}: {a['Alerta_Mensaje']}" for a in datos]
    await update.message.reply_text("🚨 *Alertas:*\n" + "\n".join(lineas), parse_mode="Markdown")


def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: No se encontró TELEGRAM_TOKEN en las variables de entorno")
        return
    if not API_URL:
        print("ERROR: No se encontró API_URL en las variables de entorno")
        return
    if not PUBLIC_URL:
        print("ERROR: No se encontró PUBLIC_URL en las variables de entorno")
        print("Genera un dominio publico en Railway (Settings > Networking > Generate Domain)")
        print("y pega esa URL completa (con https://) en la variable PUBLIC_URL")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("zonas", zonas))
    app.add_handler(CommandHandler("lotes", lotes))
    app.add_handler(CommandHandler("sensores", sensores))
    app.add_handler(CommandHandler("muestras", muestras))
    app.add_handler(CommandHandler("alertas", alertas))

    # url_path usa el propio token como "carpeta secreta" para que nadie mas
    # le mande updates falsos a tu webhook sin saber el token.
    webhook_path = TELEGRAM_TOKEN
    webhook_url = f"{PUBLIC_URL.rstrip('/')}/{webhook_path}"

    print(f"Bot AgroIA iniciando en modo webhook.")
    print(f"Escuchando en el puerto {PORT}")
    print(f"Webhook registrado en: {webhook_url}")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()
