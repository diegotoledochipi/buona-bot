"""
Buona Bot - Bot de Telegram para registro de gastos
Conectado a Supabase (B-Gestión)
"""
import os
import json
import base64
import logging
import re
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from supabase import create_client, Client
import anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
SUPABASE_URL    = os.environ.get("SUPABASE_URL", "https://hwiglzkkeambfekvapzr.supabase.co")
SUPABASE_KEY    = os.environ.get("SUPABASE_KEY")
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_KEY")
ADMIN_CHAT_ID   = os.environ.get("ADMIN_CHAT_ID")  # Tu chat_id de Telegram

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ── CATEGORÍAS ────────────────────────────────────────────────────────────
CATEGORIAS = {
    # Variables
    "Supermercado":  ["super", "supermercado", "dia", "carrefour", "coto", "vea", "mayorista", "disco", "jumbo"],
    "Verdulería":    ["verdura", "fruta", "verdu", "verduleria", "fruteria", "limon", "tomate", "papa", "cebolla", "lechuga"],
    "Carnicería":    ["carne", "carnes", "pollo", "cerdo", "vaca", "cordero", "bife", "asado", "costilla", "carniceria", "frigorifico", "frigo"],
    "Congelados":    ["congelado", "freezer", "congelados"],
    "Fiambre":       ["fiambre", "jamon", "queso", "salchicha", "panceta", "embutido", "mortadela", "salame", "lomito"],
    "Limpieza":      ["limpieza", "detergente", "lavandina", "trapo", "escoba", "jabón", "jabon", "papel", "servilleta", "rollo"],
    "Casa":          ["casa", "hogar", "ferreteria", "herramienta", "ferretería"],
    "Insumos":       ["aceite", "harina", "sal", "azucar", "azúcar", "especias", "envase", "packaging", "descartable", "film", "aluminio", "bolsa"],
    "Bebidas":       ["gaseosa", "cerveza", "vino", "agua", "jugo", "bebida", "botella", "lata", "sodas", "espirituosa"],
    "Mantenimiento": ["plomero", "electricista", "pintor", "reparacion", "reparación", "arreglo", "mantenimiento", "gasfiter", "albañil"],
    "Marketing":     ["meta", "facebook", "instagram", "publicidad", "imprenta", "diseño", "folleteria", "banner", "marketing"],
    "Digital":       ["netlify", "supabase", "railway", "hosting", "dominio", "app", "subscripcion", "suscripcion"],
    # Fijos
    "Alquiler":      ["alquiler", "arriendo", "alq"],
    "Impuestos":     ["impuesto", "afip", "iibb", "ingresos brutos", "iva", "municipal", "tasa", "agip", "arba"],
    "Sueldos":       ["sueldo", "salario", "pago empleado", "empleado"],
    "Adelantos":     ["adelanto", "anticipo"],
    "Mensuales":     ["internet", "luz", "gas", "agua", "telefono", "teléfono", "seguro", "abono", "cuota"],
}

CATEGORIAS_FIJAS = {"Alquiler", "Impuestos", "Sueldos", "Adelantos", "Mensuales"}

def detectar_categoria(texto: str) -> str:
    """Detecta la categoría del gasto según palabras clave."""
    texto_lower = texto.lower()
    for categoria, palabras in CATEGORIAS.items():
        for palabra in palabras:
            if palabra in texto_lower:
                return categoria
    return "Otros"

def es_fijo(categoria: str) -> bool:
    return categoria in CATEGORIAS_FIJAS

def hoy() -> str:
    return date.today().isoformat()

def mes_actual() -> str:
    return date.today().replace(day=1).isoformat()

def fmt_pesos(n: float) -> str:
    return f"${int(n):,}".replace(",", ".")

# ── PARSEO DE TEXTO CON IA ────────────────────────────────────────────────
async def parsear_gasto_texto(texto: str) -> dict | None:
    """Usa Claude para entender el gasto del mensaje."""
    try:
        resp = ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Analizá este mensaje de registro de gasto de un restaurante argentino y extraé la información.
Respondé SOLO con JSON válido, sin texto extra:
{{"descripcion": "nombre del gasto", "monto": 12500, "proveedor": "nombre si se menciona o null"}}

Si no podés identificar un monto numérico claro, devolvé null.
El monto siempre en números sin símbolos.

Mensaje: "{texto}"

Ejemplos:
"carnes 45000 frigo" → {{"descripcion": "Carnes", "monto": 45000, "proveedor": "Frigo"}}
"luz 18500" → {{"descripcion": "Luz", "monto": 18500, "proveedor": null}}
"verdura mercado 3200" → {{"descripcion": "Verdura", "monto": 3200, "proveedor": "Mercado"}}"""
            }]
        )
        texto_resp = resp.content[0].text.strip()
        return json.loads(texto_resp)
    except Exception as e:
        logger.error(f"Error parseando gasto: {e}")
        return None

# ── PARSEO DE IMAGEN CON IA ───────────────────────────────────────────────
async def parsear_ticket_imagen(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict | None:
    """Usa Claude para leer un ticket/factura."""
    try:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        resp = ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                    {"type": "text", "text": """Analizá este ticket o factura de compra y extraé la información.
Respondé SOLO con JSON válido, sin texto extra:
{"proveedor": "nombre del negocio", "total": 15000, "items": [{"descripcion": "producto", "monto": 5000}]}

Si no podés leer el total claramente, usá la suma de los items.
Si no hay items detallados, dejá items como lista vacía.
Todos los montos en números enteros sin símbolos."""}
                ]
            }]
        )
        texto_resp = resp.content[0].text.strip()
        return json.loads(texto_resp)
    except Exception as e:
        logger.error(f"Error parseando imagen: {e}")
        return None

# ── GUARDAR EN SUPABASE ───────────────────────────────────────────────────
async def guardar_gasto(descripcion: str, monto: float, categoria: str, proveedor: str = None) -> bool:
    """Guarda el gasto en gastos_manuales."""
    try:
        sb.table("gastos_manuales").insert({
            "descripcion": descripcion,
            "monto": monto,
            "categoria": categoria,
            "fecha": hoy()
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error guardando gasto: {e}")
        return False

async def guardar_adelanto(empleado_nombre: str, monto: float) -> bool:
    """Busca el empleado y registra el adelanto."""
    try:
        # Buscar empleado por nombre aproximado
        result = sb.table("empleados").select("id, nombre").execute()
        empleados = result.data or []
        nombre_lower = empleado_nombre.lower()
        empleado = next(
            (e for e in empleados if nombre_lower in e["nombre"].lower()),
            None
        )
        if not empleado:
            return False
        sb.table("adelantos").insert({
            "empleado_id": empleado["id"],
            "monto": monto,
            "fecha": hoy(),
            "observacion": "Cargado via bot Telegram"
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error guardando adelanto: {e}")
        return False

async def resumen_gastos(periodo: str = "hoy") -> str:
    """Genera un resumen de gastos del período."""
    try:
        if periodo == "hoy":
            desde = hoy()
            titulo = "📊 Gastos de hoy"
        elif periodo == "semana":
            from datetime import timedelta
            lunes = date.today() - timedelta(days=date.today().weekday())
            desde = lunes.isoformat()
            titulo = "📊 Gastos de esta semana"
        else:  # mes
            desde = mes_actual()
            titulo = "📊 Gastos del mes"

        result = sb.table("gastos_manuales").select("*").gte("fecha", desde).execute()
        gastos = result.data or []

        if not gastos:
            return f"{titulo}\n\nSin gastos registrados aún."

        total = sum(g["monto"] for g in gastos)
        por_categoria = {}
        for g in gastos:
            cat = g.get("categoria", "Otros")
            por_categoria[cat] = por_categoria.get(cat, 0) + g["monto"]

        lineas = [f"{titulo}\n"]
        for cat, monto in sorted(por_categoria.items(), key=lambda x: x[1], reverse=True):
            lineas.append(f"• {cat}: {fmt_pesos(monto)}")
        lineas.append(f"\n💰 *Total: {fmt_pesos(total)}*")
        lineas.append(f"📝 {len(gastos)} registros")

        return "\n".join(lineas)
    except Exception as e:
        logger.error(f"Error resumen: {e}")
        return "Error generando resumen."

# ── HANDLERS ──────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida."""
    chat_id = update.effective_chat.id
    msg = f"""🍔 *Buona Gestión Bot*

¡Hola! Soy tu asistente de gastos.

*Cómo usarme:*
• Mandame un gasto: `carnes 45000 frigo`
• Mandame una foto de un ticket
• `/gastos` — resumen de hoy
• `/semana` — resumen de la semana
• `/mes` — resumen del mes
• `/categorias` — ver todas las categorías
• `/ayuda` — ayuda completa

Tu chat ID es: `{chat_id}`"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_categorias(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra las categorías disponibles."""
    lineas = ["📋 *Categorías disponibles:*\n"]
    lineas.append("*Variables:*")
    for cat in ["Supermercado","Verdulería","Carnicería","Congelados","Fiambre",
                "Limpieza","Casa","Insumos","Bebidas","Mantenimiento","Marketing","Digital","Otros"]:
        lineas.append(f"  • {cat}")
    lineas.append("\n*Fijos:*")
    for cat in ["Alquiler","Impuestos","Sueldos","Adelantos","Mensuales"]:
        lineas.append(f"  • {cat}")
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

async def cmd_gastos_hoy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    resumen = await resumen_gastos("hoy")
    await update.message.reply_text(resumen, parse_mode="Markdown")

async def cmd_gastos_semana(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    resumen = await resumen_gastos("semana")
    await update.message.reply_text(resumen, parse_mode="Markdown")

async def cmd_gastos_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    resumen = await resumen_gastos("mes")
    await update.message.reply_text(resumen, parse_mode="Markdown")

async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = """🤖 *Ayuda — Buona Bot*

*Registrar un gasto (texto):*
`carnes 45000`
`verdura mercado 3200`
`luz 18500`
`adelanto juan 15000`
`alquiler 280000`

*Registrar un gasto (imagen):*
Mandame una foto del ticket o factura y lo proceso automático.

*Consultas:*
/gastos — resumen de hoy
/semana — resumen de esta semana
/mes — resumen del mes
/categorias — todas las categorías

*Corrección:*
Si una categoría quedó mal, respondé al mensaje con:
`corregir [categoría correcta]`"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_texto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Procesa mensajes de texto — registra gastos."""
    texto = update.message.text.strip()

    # Ignorar comandos
    if texto.startswith("/"):
        return

    # Verificar que es el admin
    chat_id = str(update.effective_chat.id)
    if ADMIN_CHAT_ID and chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⚠️ No tenés permiso para usar este bot.")
        return

    # Mensaje de procesando
    msg_proceso = await update.message.reply_text("⏳ Procesando...")

    # Detectar si es adelanto manual directo
    adelanto_match = re.search(r'adelanto\s+(\w+)\s+(\d+)', texto.lower())
    if adelanto_match:
        nombre = adelanto_match.group(1).capitalize()
        monto = float(adelanto_match.group(2))
        ok = await guardar_adelanto(nombre, monto)
        if ok:
            await msg_proceso.edit_text(
                f"✅ *Adelanto registrado*\n👤 {nombre}\n💰 {fmt_pesos(monto)}",
                parse_mode="Markdown"
            )
        else:
            await msg_proceso.edit_text(
                f"⚠️ No encontré al empleado *{nombre}* en el sistema.\n"
                f"Verificá el nombre en B-Gestión.",
                parse_mode="Markdown"
            )
        return

    # Parsear gasto con IA
    datos = await parsear_gasto_texto(texto)

    if not datos or not datos.get("monto"):
        await msg_proceso.edit_text(
            "❓ No pude identificar el monto.\n\n"
            "Usá el formato: `descripción monto`\n"
            "Ejemplo: `carnes 45000`",
            parse_mode="Markdown"
        )
        return

    descripcion = datos.get("descripcion", texto.title())
    monto = float(datos["monto"])
    proveedor = datos.get("proveedor")
    categoria = detectar_categoria(texto)
    tipo = "Fijo" if es_fijo(categoria) else "Variable"

    ok = await guardar_gasto(descripcion, monto, categoria, proveedor)

    if ok:
        resp = (
            f"✅ *Gasto registrado*\n"
            f"📝 {descripcion}\n"
            f"💰 {fmt_pesos(monto)}\n"
            f"🏷️ {categoria} ({tipo})\n"
            f"📅 {hoy()}"
        )
        if proveedor:
            resp += f"\n🏪 {proveedor}"
        await msg_proceso.edit_text(resp, parse_mode="Markdown")
    else:
        await msg_proceso.edit_text("❌ Error al guardar. Intentá de nuevo.")

async def handle_foto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Procesa fotos de tickets/facturas."""
    chat_id = str(update.effective_chat.id)
    if ADMIN_CHAT_ID and chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⚠️ No tenés permiso para usar este bot.")
        return

    msg_proceso = await update.message.reply_text("📷 Leyendo el ticket con IA...")

    try:
        # Obtener la foto de mayor resolución
        foto = update.message.photo[-1]
        file = await ctx.bot.get_file(foto.file_id)
        image_bytes = await file.download_as_bytearray()

        datos = await parsear_ticket_imagen(bytes(image_bytes))

        if not datos or not datos.get("total"):
            await msg_proceso.edit_text(
                "⚠️ No pude leer el total del ticket.\n"
                "Intentá mandar el gasto como texto: `descripción monto`"
            )
            return

        proveedor = datos.get("proveedor", "Sin nombre")
        total = float(datos["total"])
        items = datos.get("items", [])
        categoria = detectar_categoria(proveedor)

        # Guardar el gasto total
        ok = await guardar_gasto(
            f"Ticket: {proveedor}",
            total,
            categoria
        )

        if ok:
            resp = (
                f"✅ *Ticket registrado*\n"
                f"🏪 {proveedor}\n"
                f"💰 Total: {fmt_pesos(total)}\n"
                f"🏷️ {categoria}\n"
                f"📅 {hoy()}"
            )
            if items:
                resp += f"\n\n📋 *Detalle ({len(items)} items):*"
                for item in items[:5]:  # Máximo 5 items en el mensaje
                    resp += f"\n• {item['descripcion']}: {fmt_pesos(item['monto'])}"
                if len(items) > 5:
                    resp += f"\n_...y {len(items)-5} más_"
            await msg_proceso.edit_text(resp, parse_mode="Markdown")
        else:
            await msg_proceso.edit_text("❌ Error al guardar el ticket.")

    except Exception as e:
        logger.error(f"Error procesando foto: {e}")
        await msg_proceso.edit_text("❌ Error procesando la imagen. Intentá de nuevo.")

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN no configurado")
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_KEY no configurado")
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_KEY no configurado")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("categorias", cmd_categorias))
    app.add_handler(CommandHandler("gastos", cmd_gastos_hoy))
    app.add_handler(CommandHandler("semana", cmd_gastos_semana))
    app.add_handler(CommandHandler("mes", cmd_gastos_mes))

    # Mensajes
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))
    app.add_handler(MessageHandler(filters.PHOTO, handle_foto))

    logger.info("🤖 Buona Bot iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
