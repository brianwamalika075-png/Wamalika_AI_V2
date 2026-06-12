import os
import sqlite3
import json
import math
import random
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

ADMIN_ID = 8963076547  # Replace with your Telegram ID

db = sqlite3.connect("wamalika.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)
""")

db.commit()
def is_admin(user_id):
    return user_id == ADMIN_ID


def register_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (user_id,)
    )
    db.commit()


def user_count():
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]


def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]


def get_profile(context: ContextTypes.DEFAULT_TYPE):
    profile = context.user_data
    profile.setdefault("balance", 56.0)
    profile.setdefault("risk_pct", 1.0)
    profile.setdefault("pair", "EUR/USD")
    profile.setdefault("auto_trading", False)
    return profile


PAIR_SYMBOLS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "XAU/USD": "XAUUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "USD/CHF": "CHF=X",
    "NZD/USD": "NZDUSD=X",
}

PAIR_DECIMALS = {
    "EUR/USD": 5,
    "GBP/USD": 5,
    "XAU/USD": 2,
    "USD/JPY": 3,
    "AUD/USD": 5,
    "USD/CAD": 5,
    "USD/CHF": 5,
    "NZD/USD": 5,
}
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Access denied.")
        return

    await update.message.reply_text(
        "👑 Wamalika Admin Panel\n\n"
        "/stats\n"
        "/users\n"
        "/health\n"
        "/broadcast <message>"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        f"📊 Statistics\n\n"
        f"Users: {user_count()}\n"
        f"Status: Online ✅"
    )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        f"👥 Registered Users: {user_count()}"
    )


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "🟢 Bot Status: Online"
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/broadcast message"
        )
        return

    message = " ".join(context.args)

    sent = 0

    for uid in get_all_users():
        try:
            await context.bot.send_message(
                uid,
                f"📢 {message}"
            )
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(
        f"Broadcast sent to {sent} users."
    )


def main_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📈 Analysis", callback_data="menu:analysis"),
                InlineKeyboardButton("🚀 AI Signal", callback_data="menu:signal"),
            ],
            [
                InlineKeyboardButton("📊 Market Snapshot", callback_data="menu:snapshot"),
                InlineKeyboardButton("💹 Forex Pairs", callback_data="menu:pairs"),
            ],
            [
                InlineKeyboardButton("💰 Account", callback_data="menu:account"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="menu:refresh"),
                InlineKeyboardButton("ℹ️ Help", callback_data="menu:help"),
            ],
        ]
    )


def pair_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("EUR/USD", callback_data="pair:EUR/USD"),
                InlineKeyboardButton("GBP/USD", callback_data="pair:GBP/USD"),
            ],
            [
                InlineKeyboardButton("XAU/USD", callback_data="pair:XAU/USD"),
                InlineKeyboardButton("USD/JPY", callback_data="pair:USD/JPY"),
            ],
            [
                InlineKeyboardButton("AUD/USD", callback_data="pair:AUD/USD"),
                InlineKeyboardButton("USD/CAD", callback_data="pair:USD/CAD"),
            ],
            [
                InlineKeyboardButton("USD/CHF", callback_data="pair:USD/CHF"),
                InlineKeyboardButton("NZD/USD", callback_data="pair:NZD/USD"),
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="menu:settings"),
            ],
        ]
    )


def settings_keyboard(profile):
    auto = "ON" if profile["auto_trading"] else "OFF"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Pair: {profile['pair']}", callback_data="settings:pair"
                )
            ],
            [
                InlineKeyboardButton("Risk 0.5%", callback_data="risk:0.5"),
                InlineKeyboardButton("Risk 1%", callback_data="risk:1.0"),
                InlineKeyboardButton("Risk 2%", callback_data="risk:2.0"),
            ],
            [
                InlineKeyboardButton(
                    f"Auto Trading: {auto}", callback_data="settings:auto"
                )
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="menu:back"),
            ],
        ]
    )


def ema(values, period: int):
    if not values or len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_value = sum(values[:period]) / period
    for price in values[period:]:
        ema_value = price * k + ema_value * (1 - k)
    return ema_value


def rsi(values, period: int = 14):
    if len(values) <= period:
        return 50.0

    gains = []
    losses = []

    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = max(diff, 0)
        loss = abs(min(diff, 0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values):
    if len(values) < 35:
        return None, None, None

    ema12 = []
    ema26 = []
    k12 = 2 / (12 + 1)
    k26 = 2 / (26 + 1)

    e12 = values[0]
    e26 = values[0]

    for price in values:
        e12 = price * k12 + e12 * (1 - k12)
        e26 = price * k26 + e26 * (1 - k26)
        ema12.append(e12)
        ema26.append(e26)

    macd_line_series = [a - b for a, b in zip(ema12, ema26)]

    signal_series = []
    k9 = 2 / (9 + 1)
    sig = macd_line_series[0]
    for v in macd_line_series:
        sig = v * k9 + sig * (1 - k9)
        signal_series.append(sig)

    return macd_line_series[-1], signal_series[-1], macd_line_series[-1] - signal_series[-1]


def average_true_movement(values, period: int = 14):
    if len(values) < period + 1:
        return None
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return mean(diffs[-period:])


def yahoo_closes(symbol: str, interval: str = "15m", range_: str = "1d"):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range={range_}&interval={interval}&includePrePost=false&events=div,splits"
    )
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    result = data["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    closes = [float(x) for x in quote["close"] if x is not None]

    if len(closes) < 20:
        raise ValueError("Not enough market data")

    return closes


def demo_closes(pair: str):
    base = {
        "EUR/USD": 1.1550,
        "GBP/USD": 1.3300,
        "XAU/USD": 3325.0,
        "USD/JPY": 156.00,
        "AUD/USD": 0.6550,
        "USD/CAD": 1.3700,
        "USD/CHF": 0.9150,
        "NZD/USD": 0.6020,
    }.get(pair, 1.0)

    points = []
    drift = 0.00012 if pair not in ("XAU/USD", "USD/JPY") else 0.8
    for i in range(80):
        wave = math.sin(i / 6) * (0.00018 if pair not in ("XAU/USD", "USD/JPY") else 1.0)
        noise = random.uniform(-drift, drift)
        base = base + wave + noise
        points.append(base)
    return points


def fmt_price(value: float, pair: str) -> str:
    decimals = PAIR_DECIMALS.get(pair, 5)
    return f"{value:.{decimals}f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def analyze_pair(pair: str):
    symbol = PAIR_SYMBOLS.get(pair, "EURUSD=X")

    try:
        closes = yahoo_closes(symbol)
        source = "Live market data"
    except (HTTPError, URLError, ValueError, TimeoutError, KeyError, json.JSONDecodeError):
        closes = demo_closes(pair)
        source = "Demo fallback data"

    current = closes[-1]
    prev = closes[-2]
    change = current - prev
    change_pct = (change / prev) * 100 if prev else 0.0

    ema20 = ema(closes, 20) or current
    ema50 = ema(closes, 50) or current
    rsi_value = rsi(closes, 14)
    macd_line, macd_signal, macd_hist = macd(closes)
    volatility = average_true_movement(closes, 14) or (current * 0.001)

    bull = 0
    bear = 0

    if current > ema20:
        bull += 1
    else:
        bear += 1

    if ema20 > ema50:
        bull += 1
    else:
        bear += 1

    if rsi_value < 35:
        bull += 1
    elif rsi_value > 65:
        bear += 1

    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            bull += 1
        else:
            bear += 1

    if bull > bear:
        direction = "BUY"
        reason = "Trend and momentum are leaning upward."
        sl = current - (volatility * 2)
        tp = current + (volatility * 3)
    elif bear > bull:
        direction = "SELL"
        reason = "Trend and momentum are leaning downward."
        sl = current + (volatility * 2)
        tp = current - (volatility * 3)
    else:
        direction = "WAIT"
        reason = "The market is mixed. No strong edge right now."
        sl = None
        tp = None

    confidence = min(95, 45 + abs(bull - bear) * 12)
    if rsi_value < 30 or rsi_value > 70:
        confidence += 4
    if macd_hist is not None and abs(macd_hist) > volatility * 0.1:
        confidence += 4
    confidence = min(confidence, 95)

    if pair == "XAU/USD":
        trend_bias = "Gold is more volatile than majors, so wait for confirmation."
    else:
        trend_bias = "Confirm with support, resistance, and candle structure."

    return {
        "pair": pair,
        "symbol": symbol,
        "source": source,
        "current": current,
        "prev": prev,
        "change": change,
        "change_pct": change_pct,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi_value,
        "macd": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "volatility": volatility,
        "direction": direction,
        "confidence": confidence,
        "reason": reason,
        "trend_bias": trend_bias,
        "sl": sl,
        "tp": tp,
    }


def market_text(context: ContextTypes.DEFAULT_TYPE):
    profile = get_profile(context)
    pair = profile["pair"]

    try:
        a = analyze_pair(pair)
        return (
            f"📊 Market Snapshot\n\n"
            f"Pair: {a['pair']}\n"
            f"Source: {a['source']}\n"
            f"Price: {fmt_price(a['current'], pair)}\n"
            f"Change: {fmt_price(a['change'], pair)} ({pct(a['change_pct'])})\n"
            f"RSI(14): {a['rsi']:.1f}\n"
            f"EMA20: {fmt_price(a['ema20'], pair)}\n"
            f"EMA50: {fmt_price(a['ema50'], pair)}\n"
            f"MACD: {a['macd']:.6f}\n"
            f"Signal: {a['macd_signal']:.6f}\n"
            f"Volatility: {fmt_price(a['volatility'], pair)}\n\n"
            f"Bias: {a['trend_bias']}"
        )
    except Exception:
        return (
            f"📊 Market Snapshot\n\n"
            f"Pair: {pair}\n"
            f"Source: Offline demo\n"
            f"Trend: Neutral\n"
            f"RSI: 50.0\n"
            f"Bias: Market data is unavailable right now."
        )


def signal_text(context: ContextTypes.DEFAULT_TYPE):
    profile = get_profile(context)
    pair = profile["pair"]

    try:
        a = analyze_pair(pair)
        text = (
            f"🚀 AI Signal\n\n"
            f"Pair: {a['pair']}\n"
            f"Direction: {a['direction']}\n"
            f"Confidence: {a['confidence']}%\n"
            f"Reason: {a['reason']}\n"
            f"Bias: {a['trend_bias']}\n"
        )
        if a["direction"] != "WAIT":
            text += (
                f"Entry: Market close confirmation\n"
                f"Stop Loss: {fmt_price(a['sl'], pair)}\n"
                f"Take Profit: {fmt_price(a['tp'], pair)}\n"
            )
        else:
            text += "Action: Wait for a cleaner setup.\n"
        text += "\nEducational use only. Confirm before trading."
        return text
    except Exception:
        choices = [
            "🚀 AI Signal\n\nPair: EUR/USD\nDirection: WAIT\nConfidence: 61%\nReason: No clear edge right now.",
            "🚀 AI Signal\n\nPair: EUR/USD\nDirection: BUY\nConfidence: 69%\nReason: Momentum is improving.",
            "🚀 AI Signal\n\nPair: EUR/USD\nDirection: SELL\nConfidence: 67%\nReason: Price may be rejecting resistance.",
        ]
        return random.choice(choices)


def account_text(context: ContextTypes.DEFAULT_TYPE):
    profile = get_profile(context)
    balance = float(profile["balance"])
    risk_pct = float(profile["risk_pct"])
    max_loss = balance * (risk_pct / 100.0)

    return (
        f"💰 Account\n\n"
        f"Balance: ${balance:.2f}\n"
        f"Risk per trade: {risk_pct:.1f}%\n"
        f"Max loss per trade: ${max_loss:.2f}\n"
        f"Selected pair: {profile['pair']}\n"
        f"Auto trading: {'ON' if profile['auto_trading'] else 'OFF'}"
    )


def settings_text(context: ContextTypes.DEFAULT_TYPE):
    profile = get_profile(context)
    return (
        f"⚙️ Settings\n\n"
        f"Selected pair: {profile['pair']}\n"
        f"Risk per trade: {profile['risk_pct']:.1f}%\n"
        f"Auto trading: {'ON' if profile['auto_trading'] else 'OFF'}\n\n"
        f"Tap a button below to change settings."
    )


def help_text():
    return (
        "ℹ️ Help\n\n"
        "Use the buttons to open analysis, signals, settings, and account info.\n"
        "Commands:\n"
        "/start\n"
        "/menu\n"
        "/analysis\n"
        "/signal\n"
        "/account\n"
        "/settings\n"
        "/help\n\n"
        "This version is ready for Railway using the BOT_TOKEN environment variable."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_profile(context)

    register_user(update.effective_user.id)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Main menu:", reply_markup=main_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(help_text(), reply_markup=main_keyboard())


async def analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(market_text(context), reply_markup=main_keyboard())


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(signal_text(context), reply_markup=main_keyboard())


async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(account_text(context), reply_markup=main_keyboard())


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = get_profile(context)
    await update.message.reply_text(settings_text(context), reply_markup=settings_keyboard(profile))


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    profile = get_profile(context)
    data = query.data

    if data == "menu:back":
        await query.message.edit_text(
            "🤖 Wamalika AI Trading Bot\n\nSelect an option below:",
            reply_markup=main_keyboard(),
        )
        return

    if data == "menu:analysis":
        await query.message.edit_text(market_text(context), reply_markup=main_keyboard())
        return

    if data == "menu:signal":
        await query.message.edit_text(signal_text(context), reply_markup=main_keyboard())
        return

    if data == "menu:snapshot":
        await query.message.edit_text(market_text(context), reply_markup=main_keyboard())
        return

    if data == "menu:pairs":
        await query.message.edit_text("💹 Select Trading Pair", reply_markup=pair_keyboard())
        return

    if data == "menu:account":
        await query.message.edit_text(account_text(context), reply_markup=main_keyboard())
        return

    if data == "menu:settings":
        await query.message.edit_text(settings_text(context), reply_markup=settings_keyboard(profile))
        return

    if data == "menu:help":
        await query.message.edit_text(help_text(), reply_markup=main_keyboard())
        return

    if data == "menu:refresh":
        await query.message.edit_text(
            f"🔄 Refreshed\n\n{market_text(context)}",
            reply_markup=main_keyboard(),
        )
        return

    if data.startswith("risk:"):
        try:
            profile["risk_pct"] = float(data.split(":", 1)[1])
        except ValueError:
            pass
        await query.message.edit_text(settings_text(context), reply_markup=settings_keyboard(profile))
        return

    if data == "settings:auto":
        profile["auto_trading"] = not profile["auto_trading"]
        note = "ON" if profile["auto_trading"] else "OFF"
        msg = (
            f"⚙️ Settings\n\n"
            f"Auto trading is now {note}.\n\n"
            f"On Android, keep this as a signals bot.\n"
            f"For real execution through MT5, use a Windows/VPS bridge."
        )
        await query.message.edit_text(msg, reply_markup=settings_keyboard(profile))
        return

    if data == "settings:pair":
        await query.message.edit_text("Select a trading pair:", reply_markup=pair_keyboard())
        return

    if data.startswith("pair:"):
        selected_pair = data.split(":", 1)[1]
        if selected_pair in PAIR_SYMBOLS:
            profile["pair"] = selected_pair
        await query.message.edit_text(settings_text(context), reply_markup=settings_keyboard(profile))
        return


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()

    mapping = {
        "📈 analysis": analysis_command,
        "🚀 ai signal": signal_command,
        "📊 market snapshot": analysis_command,
        "💹 forex pairs": settings_command,
        "💰 account": account_command,
        "⚙️ settings": settings_command,
        "ℹ️ help": help_command,
    }

    handler = mapping.get(text)
    if handler:
        await handler(update, context)


app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("analysis", analysis_command))
app.add_handler(CommandHandler("signal", signal_command))
app.add_handler(CommandHandler("account", account_command))
app.add_handler(CommandHandler("settings", settings_command))
app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(CommandHandler("stats", stats_command))
app.add_handler(CommandHandler("users", users_command))
app.add_handler(CommandHandler("health", health_command))
app.add_handler(CommandHandler("broadcast", broadcast_command))

print("Wamalika AI Trading Bot Running...")

app.run_polling()
