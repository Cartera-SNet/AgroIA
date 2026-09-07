"""
Bot de Telegram - AgroIA
Versión con comprensión de lenguaje natural (sin comandos "/").

El flujo es:
1. El usuario escribe cualquier pregunta en texto libre.
2. El bot trae los datos reales actuales desde la API (Render).
3. El bot le pasa esos datos + la pregunta a un modelo de lenguaje (Groq).
4. El modelo responde SOLO usando esos datos reales, en español natural.
5. El bot reenvía esa respuesta al usuario en Telegram.
"""

import os
import logging
import requests
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

# ---------------------------------------------------------------------------
# Configuración (variables de entorno - ya existen TELEGRAM_TOKEN, API_URL,
# PUBLIC_URL, PORT en Railway; solo hay que agregar GROQ_API_KEY)
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
API_URL = os.environ["API_URL"]
PUBLIC_URL = os.environ["PUBLIC_URL"]
PORT = int(os.environ.get("PORT", 8080))
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROQ_MODEL = "llama-3.3-70b-versatile"  # rápido y gratis en Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

groq_client = Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------------------------
# Paso 1: traer datos reales desde la API (Render)
# ---------------------------------------------------------------------------
def obtener_contexto_bd() -> str:
    """
    Llama a los endpoints públicos de la API y arma un texto plano
    con los datos actuales, para dárselo al LLM como contexto.
    """
    partes = []

    try:
        sensores = requests.get(f"{API_URL}/sensores/list", timeout=15).json()
        partes.append("SENSORES:\n" + _formatear(sensores))
    except Exception as e:
        logger.warning(f"No se pudo traer /sensores/list: {e}")
        partes.append("SENSORES: (no disponible en este momento)")

    try:
        parametros = requests.get(f"{API_URL}/parametros/list", timeout=15).json()
        partes.append("PARAMETROS MEDIDOS (tipos de medición):\n" + _formatear(parametros))
    except Exception as e:
        logger.warning(f"No se pudo traer /parametros/list: {e}")
        partes.append("PARAMETROS MEDIDOS: (no disponible en este momento)")

    try:
        muestras = requests.get(f"{API_URL}/muestras/list", timeout=15).json()
        # Ordenar por fecha descendente y quedarnos solo con las más recientes,
        # para no saturar el contexto del modelo si hay muchos registros.
        muestras_ordenadas = sorted(
            muestras,
            key=lambda m: m.get("Muestra_FechaHora") or "",
            reverse=True,
        )[:30]
        partes.append("MUESTRAS DE SUELO (más recientes primero):\n" + _formatear(muestras_ordenadas))
    except Exception as e:
        logger.warning(f"No se pudo traer /muestras/list: {e}")
        partes.append("MUESTRAS DE SUELO: (no disponible en este momento)")

    return "\n\n".join(partes)


def _formatear(datos) -> str:
    """Convierte una lista de dicts en texto plano legible, línea por línea."""
    if not datos:
        return "(sin registros)"
    lineas = []
    for item in datos:
        lineas.append(", ".join(f"{k}: {v}" for k, v in item.items()))
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Paso 2: preguntarle al LLM (Groq), usando SOLO los datos reales como contexto
# ---------------------------------------------------------------------------
def preguntar_llm(pregunta_usuario: str, contexto_bd: str) -> str:
    system_prompt = (
        "Eres el asistente de AgroIA, un sistema de monitoreo de fertilidad de suelo. "
        "Debes responder SIEMPRE en español, de forma breve y natural, como si hablaras "
        "con un agricultor. "
        "IMPORTANTE: solo puedes usar los datos que se te dan a continuación. "
        "Si la pregunta no se puede responder con esos datos, dilo claramente "
        "en vez de inventar un valor. Nunca inventes números ni nombres."
        "\n\n--- DATOS ACTUALES DE LA BASE DE DATOS ---\n"
        f"{contexto_bd}"
    )

    respuesta = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pregunta_usuario},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return respuesta.choices[0].message.content


# ---------------------------------------------------------------------------
# Handlers de Telegram
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy el asistente de AgroIA 🌱\n"
        "Pregúntame lo que quieras sobre los sensores, las muestras de suelo "
        "o los parámetros medidos, en tus propias palabras. "
        "Por ejemplo: '¿cuál es el último valor registrado?' o "
        "'¿cuál es el promedio de temperatura?'"
    )


async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    await update.message.chat.send_action("typing")

    contexto = obtener_contexto_bd()
    try:
        respuesta = preguntar_llm(pregunta, contexto)
    except Exception as e:
        logger.error(f"Error consultando Groq: {e}")
        respuesta = (
            "Tuve un problema consultando la información en este momento. "
            "Intenta de nuevo en unos segundos."
        )

    await update.message.reply_text(respuesta)


# ---------------------------------------------------------------------------
# Arranque del bot (webhook, igual que la versión anterior en Railway)
# ---------------------------------------------------------------------------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # Cualquier mensaje de texto que NO sea un comando se interpreta como
    # una pregunta en lenguaje natural.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    public_url = PUBLIC_URL.rstrip("/")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{public_url}/{TELEGRAM_TOKEN}",
    )


if __name__ == "__main__":
    main()