import os
import re
import json
import base64
import logging
import os
import re
import json
import base64
import logging
import requests
from datetime import datetime, date

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL    = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_KEY"]
ADMIN_CHAT_ID   = os.environ.get("ADMIN_CHAT_ID", "")

TELEGRAM_API    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
}

CATEGORIAS_VARIABLES = [
        "supermercado", "panaderia", "verduleria", "carniceria", "congelados",
        "fiambre", "limpieza", "casa", "mantenimiento", "varios", "pagos",
]
CATEGORIAS_FIJAS = ["alquiler", "impuestos", "sueldos", "adelantos", "mensuales"]
TODAS_CATEGORIAS = CATEGORIAS_VARIABLES + CATEGORIAS_FIJAS

def sb_insert(table, data):
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SUPABASE_HEADERS, json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    
def sb_select(table, params=None):
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SUPABASE_HEADERS, params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    
def send_message(chat_id, text):
        requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    
def get_file_url(file_id):
        r = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=10)
        path = r.json()["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{path}"
    
def ocr_ticket(image_bytes, mime="image/jpeg"):
        b64 = base64.b64encode(image_bytes).decode()
        payload = {
                    "model": "claude-sonnet-4-20250514", "max_tokens": 1000,
                    "messages": [{"role": "user", "content": [
                                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                                    {"type": "text", "text": "Sos un asistente de gastos para un restaurante argentino. Analiza este ticket y extrae monto total en pesos, proveedor y categoria mas probable entre: " + ", ".join(TODAS_CATEGORIAS) + ". Responde SOLO en JSON: {\"monto\": 12500, \"proveedor\": \"Carrefour\", \"categoria\": \"supermercado\", \"descripcion\": \"compra\"}"},
                    ]}],
        }
        r = requests.post("https://api.anthropic.com/v1/messages",
                                  headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                                  json=payload, timeout=30)
        r.raise_for_status()
        raw = r.json()["content"][0]["text"].strip()
        return re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
    
def parse_gasto(text):
        text = text.strip().lower()
        for ch in "aeiou":
                    pass  # tildes ya manejadas por lower()
                tokens = text.split()
    if len(tokens) < 2:
                return None
            categoria = None
    for cat in TODAS_CATEGORIAS:
                if tokens[0] == cat or (len(tokens[0]) >= import requests
from datetime import datetime, date

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── ENV ──────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL    = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_KEY"]
ADMIN_CHAT_ID   = os.environ.get("ADMIN_CHAT_ID", "")

TELEGRAM_API    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# ── CATEGORÍAS ───────────────────────────────────────────────────────────────
CATEGORIAS_VARIABLES = [
    "supermercado", "verduleria", "carniceria", "congelados",
    "fiambre", "limpieza", "casa", "insumos", "bebidas",
    "mantenimiento", "marketing", "digital",
]
CATEGORIAS_FIJAS = ["alquiler", "impuestos", "sueldos", "adelantos", "mensuales"]
TODAS_CATEGORIAS = CATEGORIAS_VARIABLES + CATEGORIAS_FIJAS

# ── SUPABASE HELPERS ─────────────────────────────────────────────────────────
def sb_insert(table: str, data: dict):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=SUPABASE_HEADERS,
        json=data,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

def sb_select(table: str, params: dict = None):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=SUPABASE_HEADERS,
        params=params or {},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

# ── TELEGRAM HELPERS ─────────────────────────────────────────────────────────
def send_message(chat_id, text, parse_mode="Markdown"):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        timeout=10,
    )

def get_file_url(file_id: str) -> str:
    r = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=10)
    path = r.json()["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{path}"

# ── ANTHROPIC OCR ─────────────────────────────────────────────────────────────
def ocr_ticket(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Sos un asistente de gestión de gastos para un restaurante argentino. "
                            "Analizá este ticket/foto y extraé: monto total en pesos, proveedor/comercio si se ve, "
                            "y categoría más probable entre: "
                            + ", ".join(TODAS_CATEGORIAS)
                            + ". Respondé SOLO en este formato JSON sin markdown:\n"
                            '{"monto": 12500, "proveedor": "Carrefour", "categoria": "supermercado", "descripcion": "compra supermercado"}'
                        ),
                    },
                ],
            }
        ],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    raw = r.json()["content"][0]["text"].strip()
    # limpiar posibles backticks
    raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
    return raw

# ── PARSEO DE TEXTO ───────────────────────────────────────────────────────────
def parse_gasto(text: str):
    """
    Formato esperado: 'categoria monto descripcion'
    Ej: 'carnes 45000 frigo'
    """
    text = text.strip().lower()
    tokens = text.split()
    if len(tokens) < 2:
        return None

    categoria = None
    for cat in TODAS_CATEGORIAS:
        # coincidencia parcial al inicio
        if tokens[0].startswith(cat[:4]):
            categoria = cat
            break
    if not categoria:
        return None

    # buscar monto (número con posible punto/coma)
    monto = None
    descripcion_tokens = []
    for i, t in enumerate(tokens[1:], 1):
        limpio = t.replace(".", "").replace(",", "")
        if limpio.isdigit() and monto is None:
            monto = int(limpio)
        else:
            descripcion_tokens.append(t)

    if monto is None:
        return None

    descripcion = " ".join(descripcion_tokens) if descripcion_tokens else categoria
    return {"categoria": categoria, "monto": monto, "descripcion": descripcion}

def parse_adelanto(text: str):
    """
    Formato: 'adelanto nombre monto'
    Ej: 'adelanto juan 15000'
    """
    m = re.match(r"adelanto\s+(\w+)\s+([\d.,]+)", text.strip(), re.IGNORECASE)
    if not m:
        return None
    nombre = m.group(1).capitalize()
    monto  = int(m.group(2).replace(".", "").replace(",", ""))
    return {"empleado": nombre, "monto": monto}

# ── RESÚMENES ─────────────────────────────────────────────────────────────────
def fmt_pesos(n) -> str:
    return f"${int(n):,}".replace(",", ".")

def resumen_gastos(filas: list) -> str:
    if not filas:
        return "No hay gastos registrados."
    total = sum(f["monto"] for f in filas)
    por_cat = {}
    for f in filas:
        cat = f.get("categoria", "otro")
        por_cat[cat] = por_cat.get(cat, 0) + f["monto"]
    lineas = [f"*{cat.capitalize()}*: {fmt_pesos(v)}" for cat, v in sorted(por_cat.items())]
    lineas.append(f"\n*TOTAL: {fmt_pesos(total)}*")
    return "\n".join(lineas)

# ── COMANDOS ──────────────────────────────────────────────────────────────────
def cmd_gastos(chat_id):
    hoy = date.today().isoformat()
    filas = sb_select("gastos_manuales", {
        "created_at": f"gte.{hoy}T00:00:00",
        "select": "categoria,monto,descripcion,created_at",
        "order": "created_at.desc",
    })
    send_message(chat_id, f"📊 *Gastos de hoy ({hoy})*\n\n" + resumen_gastos(filas))

def cmd_semana(chat_id):
    from datetime import timedelta
    inicio = (date.today() - timedelta(days=7)).isoformat()
    filas = sb_select("gastos_manuales", {
        "created_at": f"gte.{inicio}T00:00:00",
        "select": "categoria,monto,descripcion,created_at",
    })
    send_message(chat_id, f"📆 *Gastos últimos 7 días*\n\n" + resumen_gastos(filas))

def cmd_mes(chat_id):
    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    filas = sb_select("gastos_manuales", {
        "created_at": f"gte.{inicio}T00:00:00",
        "select": "categoria,monto,descripcion,created_at",
    })
    send_message(chat_id, f"🗓 *Gastos de {hoy.strftime('%B %Y')}*\n\n" + resumen_gastos(filas))

# ── MANEJADOR DE UPDATES ──────────────────────────────────────────────────────
def handle_update(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text    = msg.get("text", "").strip()
    photo   = msg.get("photo")

    # ── /start ────────────────────────────────────────────────────────────────
    if text.startswith("/start"):
        send_message(
            chat_id,
            f"🤖 *Buona Bot activo!*\n\nTu chat ID: `{chat_id}`\n\n"
            "Comandos:\n"
            "• `categoria monto descripcion` → registrar gasto\n"
            "• `adelanto nombre monto` → registrar adelanto\n"
            "• Foto de ticket → OCR automático\n"
            "• `/gastos` → resumen hoy\n"
            "• `/semana` → últimos 7 días\n"
            "• `/mes` → mes actual",
        )
        return

    # ── Comandos de resumen ───────────────────────────────────────────────────
    if text.startswith("/gastos"):
        cmd_gastos(chat_id)
        return
    if text.startswith("/semana"):
        cmd_semana(chat_id)
        return
    if text.startswith("/mes"):
        cmd_mes(chat_id)
        return

    # ── Foto / ticket ─────────────────────────────────────────────────────────
    if photo:
        send_message(chat_id, "📸 Procesando ticket con IA...")
        file_id  = photo[-1]["file_id"]   # mayor resolución
        file_url = get_file_url(file_id)
        img_bytes = requests.get(file_url, timeout=20).content
        try:
            raw  = ocr_ticket(img_bytes)
            data = json.loads(raw)
            monto     = int(data.get("monto", 0))
            categoria = data.get("categoria", "supermercado")
            proveedor = data.get("proveedor", "")
            desc      = data.get("descripcion", proveedor or categoria)

            if monto <= 0:
                send_message(chat_id, "⚠️ No pude detectar el monto. Registrá el gasto manualmente.")
                return

            sb_insert("gastos_manuales", {
                "categoria": categoria,
                "monto": monto,
                "descripcion": desc,
                "fuente": "ocr",
            })
            send_message(
                chat_id,
                f"✅ *Ticket registrado*\n"
                f"Categoría: {categoria.capitalize()}\n"
                f"Monto: {fmt_pesos(monto)}\n"
                f"Descripción: {desc}",
            )
        except Exception as e:
            logger.error("OCR error: %s", e)
            send_message(chat_id, "❌ No pude leer el ticket. Intentá registrar el gasto manualmente.")
        return

    # ── Adelanto ──────────────────────────────────────────────────────────────
    if text.lower().startswith("adelanto"):
        data = parse_adelanto(text)
        if data:
            sb_insert("adelantos", {
                "empleado": data["empleado"],
                "monto": data["monto"],
            })
            send_message(
                chat_id,
                f"✅ *Adelanto registrado*\n"
                f"Empleado: {data['empleado']}\n"
                f"Monto: {fmt_pesos(data['monto'])}",
            )
        else:
            send_message(chat_id, "⚠️ Formato: `adelanto nombre monto`\nEj: `adelanto Juan 15000`")
        return

    # ── Gasto de texto ────────────────────────────────────────────────────────
    if text and not text.startswith("/"):
        data = parse_gasto(text)
        if data:
            sb_insert("gastos_manuales", {
                "categoria": data["categoria"],
                "monto": data["monto"],
                "descripcion": data["descripcion"],
                "fuente": "manual",
            })
            send_message(
                chat_id,
                f"✅ *Gasto registrado*\n"
                f"Categoría: {data['categoria'].capitalize()}\n"
                f"Monto: {fmt_pesos(data['monto'])}\n"
                f"Descripción: {data['descripcion']}",
            )
        else:
            send_message(
                chat_id,
                "⚠️ No entendí el gasto.\n\n"
                "Formato: `categoria monto descripcion`\n"
                "Ej: `carnes 45000 frigo`\n\n"
                "Categorías: " + ", ".join(TODAS_CATEGORIAS),
            )

# ── LONG POLLING ──────────────────────────────────────────────────────────────
def main():
    logger.info("Buona Bot iniciado con long polling")
    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "edited_message"]}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=40)
            updates = r.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                try:
                    handle_update(upd)
                except Exception as e:
                    logger.error("Error en update %s: %s", upd.get("update_id"), e)
        except Exception as e:
            logger.error("Error en polling: %s", e)

if __name__ == "__main__":
    main()
