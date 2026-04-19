import os
import re
import json
import base64
import logging
import requests
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

# ── CATEGORIAS ───────────────────────────────────────────────────────────────
# Variables: gastos_manuales SIN categoria (null) -> pestana Variables en herramienta
CATEGORIAS_VARIABLES = [
    "supermercado", "panaderia", "verduleria", "carniceria", "congelados",
    "fiambre", "limpieza", "casa", "mantenimiento", "varios", "pagos",
]
# Fijos: gastos_manuales CON categoria -> pestana Puntuales en herramienta
CATEGORIAS_FIJAS = ["alquiler", "impuestos", "sueldos", "adelantos", "mensuales"]
TODAS_CATEGORIAS = CATEGORIAS_VARIABLES + CATEGORIAS_FIJAS

# ── SUPABASE HELPERS ─────────────────────────────────────────────────────────
def sb_insert(table, data):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=SUPABASE_HEADERS,
        json=data,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

def sb_select(table, params=None):
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

def get_file_url(file_id):
    r = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=10)
    path = r.json()["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{path}"

# ── ANTHROPIC OCR ─────────────────────────────────────────────────────────────
def ocr_ticket(image_bytes, mime="image/jpeg"):
    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": (
                    "Sos un asistente de gastos para un restaurante argentino. "
                    "Analiza este ticket y extrae: monto total en pesos, proveedor si se ve, "
                    "y categoria mas probable entre: " + ", ".join(TODAS_CATEGORIAS) +
                    ". Responde SOLO en JSON sin markdown: "
                    '{"monto": 12500, "proveedor": "Carrefour", "categoria": "supermercado", "descripcion": "compra supermercado"}'
                )},
            ],
        }],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    raw = r.json()["content"][0]["text"].strip()
    raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
    return raw

# ── PARSEO DE TEXTO ───────────────────────────────────────────────────────────
def normalizar(text):
    return (text.lower()
        .replace("a","a").replace("e","e").replace("i","i").replace("o","o").replace("u","u"))

def parse_gasto(text):
    text = normalizar(text.strip())
    tokens = text.split()
    if len(tokens) < 2:
        return None

    categoria = None
    for cat in TODAS_CATEGORIAS:
        if tokens[0] == cat or (len(tokens[0]) >= 4 and cat.startswith(tokens[0][:4])):
            categoria = cat
            break
    if not categoria:
        return None

    monto = None
    desc_tokens = []
    for t in tokens[1:]:
        limpio = t.replace(".", "").replace(",", "")
        if limpio.isdigit() and monto is None:
            monto = int(limpio)
        else:
            desc_tokens.append(t)

    if monto is None:
        return None

    descripcion = " ".join(desc_tokens) if desc_tokens else categoria
    return {"categoria": categoria, "monto": monto, "descripcion": descripcion}

def parse_adelanto(text):
    m = re.match(r"adelanto\s+(\w+)\s+([\d.,]+)", text.strip(), re.IGNORECASE)
    if not m:
        return None
    return {"empleado": m.group(1).capitalize(), "monto": int(m.group(2).replace(".", "").replace(",", ""))}

# ── INSERTAR GASTO ────────────────────────────────────────────────────────────
def insertar_gasto(categoria, monto, descripcion, fuente="manual"):
    """
    Variables  -> gastos_manuales sin campo 'categoria' (null)
                  La herramienta detecta null = Variable
    Fijos      -> gastos_manuales con campo 'categoria'
                  La herramienta detecta con categoria = Puntual
    """
    hoy = date.today().isoformat()

    if categoria in CATEGORIAS_VARIABLES:
        sb_insert("gastos_manuales", {
            "descripcion": descripcion,
            "monto": monto,
            "fecha": hoy,
            "fuente": fuente,
            # sin 'categoria' -> null -> aparece como Variable
        })
        return "Variable"
    else:
        sb_insert("gastos_manuales", {
            "descripcion": descripcion,
            "monto": monto,
            "fecha": hoy,
            "categoria": categoria.capitalize(),
            "fuente": fuente,
        })
        return "Fijo"

# ── RESUMEN ───────────────────────────────────────────────────────────────────
def fmt_pesos(n):
    return f"${int(n):,}".replace(",", ".")

def resumen_gastos(filas):
    if not filas:
        return "No hay gastos registrados."
    total = sum(f["monto"] for f in filas)
    por_desc = {}
    for f in filas:
        k = f.get("descripcion") or f.get("categoria") or "varios"
        por_desc[k] = por_desc.get(k, 0) + f["monto"]
    lineas = [f"*{k.capitalize()}*: {fmt_pesos(v)}" for k, v in sorted(por_desc.items())]
    lineas.append(f"\n*TOTAL: {fmt_pesos(total)}*")
    return "\n".join(lineas)

# ── COMANDOS ──────────────────────────────────────────────────────────────────
def cmd_gastos(chat_id):
    hoy = date.today().isoformat()
    filas = sb_select("gastos_manuales", {"fecha": f"eq.{hoy}", "select": "descripcion,categoria,monto", "order": "created_at.desc"})
    send_message(chat_id, f"Gastos de hoy ({hoy})\n\n" + resumen_gastos(filas))

def cmd_semana(chat_id):
    from datetime import timedelta
    inicio = (date.today() - timedelta(days=7)).isoformat()
    filas = sb_select("gastos_manuales", {"fecha": f"gte.{inicio}", "select": "descripcion,categoria,monto"})
    send_message(chat_id, f"Gastos ultimos 7 dias\n\n" + resumen_gastos(filas))

def cmd_mes(chat_id):
    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    filas = sb_select("gastos_manuales", {"fecha": f"gte.{inicio}", "select": "descripcion,categoria,monto"})
    send_message(chat_id, f"Gastos de {hoy.strftime('%B %Y')}\n\n" + resumen_gastos(filas))

# ── HANDLE UPDATE ─────────────────────────────────────────────────────────────
def handle_update(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text    = msg.get("text", "").strip()
    photo   = msg.get("photo")

    if text.startswith("/start"):
        send_message(chat_id,
            f"Buona Bot activo!\n\nTu chat ID: {chat_id}\n\n"
            "Comandos:\n"
            "- categoria monto descripcion -> registrar gasto\n"
            "- adelanto nombre monto -> registrar adelanto\n"
            "- Foto de ticket -> OCR automatico\n"
            "- /gastos -> resumen hoy\n"
            "- /semana -> ultimos 7 dias\n"
            "- /mes -> mes actual\n\n"
            "Variables: " + ", ".join(CATEGORIAS_VARIABLES) + "\n"
            "Fijos: " + ", ".join(CATEGORIAS_FIJAS)
        )
        return

    if text.startswith("/gastos"):
        cmd_gastos(chat_id); return
    if text.startswith("/semana"):
        cmd_semana(chat_id); return
    if text.startswith("/mes"):
        cmd_mes(chat_id); return

    if photo:
        send_message(chat_id, "Procesando ticket con IA...")
        file_url  = get_file_url(photo[-1]["file_id"])
        img_bytes = requests.get(file_url, timeout=20).content
        try:
            data      = json.loads(ocr_ticket(img_bytes))
            monto     = int(data.get("monto", 0))
            categoria = data.get("categoria", "varios")
            desc      = data.get("descripcion", data.get("proveedor", categoria))
            if monto <= 0:
                send_message(chat_id, "No pude detectar el monto. Registra el gasto manualmente.")
                return
            tipo = insertar_gasto(categoria, monto, desc, fuente="ocr")
            send_message(chat_id, f"Ticket registrado ({tipo})\n{desc}\n{fmt_pesos(monto)}")
        except Exception as e:
            logger.error("OCR error: %s", e)
            send_message(chat_id, "No pude leer el ticket. Registra el gasto manualmente.")
        return

    if text.lower().startswith("adelanto"):
        data = parse_adelanto(text)
        if data:
            sb_insert("adelantos", {"empleado": data["empleado"], "monto": data["monto"]})
            send_message(chat_id, f"Adelanto registrado\n{data['empleado']}: {fmt_pesos(data['monto'])}")
        else:
            send_message(chat_id, "Formato: adelanto nombre monto\nEj: adelanto Juan 15000")
        return

    if text and not text.startswith("/"):
        data = parse_gasto(text)
        if data:
            tipo = insertar_gasto(data["categoria"], data["monto"], data["descripcion"])
            send_message(chat_id,
                f"Gasto registrado ({tipo})\n"
                f"{data['descripcion'].capitalize()} - {data['categoria'].capitalize()}\n"
                f"{fmt_pesos(data['monto'])}"
            )
        else:
            send_message(chat_id,
                "No entendi el gasto.\n\n"
                "Formato: categoria monto descripcion\n"
                "Ej: supermercado 23300 dia\n\n"
                "Categorias: " + ", ".join(TODAS_CATEGORIAS)
            )

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    logger.info("Buona Bot iniciado")
    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "edited_message"]}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=40)
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                try:
                    handle_update(upd)
                except Exception as e:
                    logger.error("Error update %s: %s", upd.get("update_id"), e)
        except Exception as e:
            logger.error("Error polling: %s", e)

if __name__ == "__main__":
    main()
