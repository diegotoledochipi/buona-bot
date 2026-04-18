# 🤖 Buona Bot — Bot de Telegram para gastos

## Variables de entorno (Railway)

| Variable | Valor |
|----------|-------|
| `TELEGRAM_TOKEN` | El token que te dio BotFather |
| `SUPABASE_URL` | `https://hwiglzkkeambfekvapzr.supabase.co` |
| `SUPABASE_KEY` | La anon key de Supabase |
| `ANTHROPIC_KEY` | Tu API key de Anthropic |
| `ADMIN_CHAT_ID` | Tu chat_id de Telegram (mandá /start al bot para verlo) |

## Deploy en Railway

1. Subí esta carpeta a un repo de GitHub
2. En Railway: New Project → Deploy from GitHub
3. Seleccioná el repo
4. Agregá las variables de entorno
5. Deploy!

## Uso

- `carnes 45000` → registra gasto
- `verdura 3200 mercado` → con proveedor
- `adelanto juan 15000` → adelanto a empleado
- [foto de ticket] → OCR automático
- `/gastos` → resumen hoy
- `/semana` → resumen semana
- `/mes` → resumen mes
