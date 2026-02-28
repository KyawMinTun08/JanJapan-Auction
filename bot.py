import os
import re
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('BOT_TOKEN', '')
SHEET_WEBHOOK = os.environ.get('SHEET_WEBHOOK', '')

# ── Auction Checklist Database ─────────────────────────
CARS = [
    {"chassis": "MNH15-0039667", "model": "ALPHARD", "color": "WHITE", "year": 2005},
    {"chassis": "CD48R-30111", "model": "BIG THUMB", "color": "GREEN", "year": 2005},
    {"chassis": "FE82EEV500266", "model": "CANTER", "color": "WHITE", "year": 2002},
    {"chassis": "FE84DV-550674", "model": "CANTER", "color": "BLUE", "year": 2008},
    {"chassis": "FB70BB-512392", "model": "CANTER GUTS", "color": "WHITE", "year": 2005},
    {"chassis": "MK35A-10405", "model": "CONDOR", "color": "PEARL WHITE", "year": 2006},
    {"chassis": "JNCLSC0A1GU006386", "model": "CONDOR", "color": "WHITE", "year": 2016},
    {"chassis": "GRS210-6004548", "model": "CROWN", "color": "PEARL WHITE", "year": 2013},
    {"chassis": "GRS200-0001831", "model": "CROWN", "color": "WHITE", "year": 2008},
    {"chassis": "GRS200-0020080", "model": "CROWN", "color": "WHITE", "year": 2008},
    {"chassis": "GRS202-0002603", "model": "CROWN", "color": "WHITE", "year": 2008},
    {"chassis": "XZC610-0001005", "model": "DUTRO", "color": "WHITE", "year": 2011},
    {"chassis": "GE6-1539486", "model": "FIT", "color": "PEARL WHITE", "year": 2011},
    {"chassis": "GP5-3032237", "model": "FIT HYBRID", "color": "PEARL WHITE", "year": 2014},
    {"chassis": "GP1-1131390", "model": "FIT HYBRID", "color": "WHITE", "year": 2012},
    {"chassis": "GP1-1049821", "model": "FIT HYBRID", "color": "PEARL WHITE", "year": 2011},
    {"chassis": "GP7-1000970", "model": "FIT SHUTTLE HYBRID", "color": "PEARL WHITE", "year": 2015},
    {"chassis": "GP2-3106770", "model": "FIT SHUTTLE HYBRID", "color": "SILVER", "year": 2013},
    {"chassis": "FK61FM765129", "model": "FUSO FIGHTER", "color": "WHITE", "year": 2003},
    {"chassis": "KDH201-0140123", "model": "HIACE VAN", "color": "WHITE", "year": 2014},
    {"chassis": "S211P-0217418", "model": "HIJET TRUCK", "color": "WHITE", "year": 2013},
    {"chassis": "S210P-2037788", "model": "HIJET TRUCK", "color": "WHITE", "year": 2005},
    {"chassis": "S510P-0173458", "model": "HIJET TRUCK", "color": "WHITE", "year": 2017},
    {"chassis": "UZJ100-0151432", "model": "LAND CRUISER", "color": "SILVER", "year": 2004},
    {"chassis": "USF40-5006069", "model": "LEXUS LS", "color": "WHITE", "year": 2006},
    {"chassis": "WVWZZZ16ZDM638030", "model": "NEW BEETLE", "color": "BLACK", "year": 2013},
    {"chassis": "ZRR75-0068964", "model": "NOAH", "color": "PEARL WHITE", "year": 2010},
    {"chassis": "V98W-0300140", "model": "PAJERO", "color": "PEARL WHITE", "year": 2010},
    {"chassis": "S211U-0000227", "model": "PIXIS TRUCK", "color": "WHITE", "year": 2011},
    {"chassis": "FC7JKY-14910", "model": "RANGER", "color": "BLUE", "year": 2011},
    {"chassis": "NCP165-0001505", "model": "SUCCEED VAN", "color": "PEARL WHITE", "year": 2014},
    {"chassis": "NCP59-0012188", "model": "SUCCEED WAGON", "color": "SILVER", "year": 2005},
    {"chassis": "FV50JJX-530670", "model": "SUPER GREAT", "color": "BLACK", "year": 2004},
    {"chassis": "CG5ZA-30374", "model": "UD", "color": "PEARL WHITE", "year": 2014},
    {"chassis": "CD5ZA-30191", "model": "UD", "color": "SILVER", "year": 2014},
    {"chassis": "CG4ZA-01338", "model": "UD", "color": "LIGHT BLUE", "year": 2006},
    {"chassis": "ZGE22-0005423", "model": "WISH", "color": "BLACK", "year": 2011},
    {"chassis": "ZGE20-0010786", "model": "WISH", "color": "PEARL WHITE", "year": 2009},
    {"chassis": "ZGE25-0015283", "model": "WISH", "color": "WHITE", "year": 2011},
    {"chassis": "NT32-504837", "model": "X-TRAIL", "color": "BLACK", "year": 2014},
    {"chassis": "NT32-531693", "model": "X-TRAIL", "color": "BLACK", "year": 2015},
    {"chassis": "NT31-316873", "model": "X-TRAIL", "color": "PEARL WHITE", "year": 2013},
    {"chassis": "NT32-508661", "model": "X-TRAIL", "color": "PEARL WHITE", "year": 2015},
]

# In-memory price history (replace with Google Sheets later)
PRICE_HISTORY = []

# Pending photo waiting for price
pending_photo = {}  # user_id -> {chassis, model, color, year, file_id}

# ── Helper Functions ──────────────────────────────────
def find_by_chassis(chassis_input):
    chassis_input = chassis_input.upper().strip()
    for car in CARS:
        if car["chassis"].upper() == chassis_input:
            return car
    return None

def find_by_model(model_input):
    model_input = model_input.upper().strip()
    return [c for c in CARS if model_input in c["model"].upper()]

def extract_chassis_from_text(text):
    """Extract chassis-like patterns from OCR text"""
    patterns = [
        r'[A-Z]{2,4}\d{2,3}-\d{6,7}',
        r'[A-Z]{3}\d{2}[A-Z]-\d{7}',
        r'[A-Z]{2}\d{1}[A-Z]{2}-\d{7}',
        r'[A-Z0-9]{5,20}-\d{4,7}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text.upper())
        if matches:
            return matches[0]
    return None

def get_price_history(chassis):
    return [p for p in PRICE_HISTORY if p["chassis"] == chassis]

def format_car_info(car, price=None, history=None):
    txt = (
        f"🚗 *{car['model']}* ({car['year']})\n"
        f"🔑 Chassis: `{car['chassis']}`\n"
        f"🎨 Color: {car['color']}\n"
    )
    if price:
        txt += f"💰 ဈေး: *฿{price:,}*\n"
    if history:
        txt += f"\n📈 *ဈေးမှတ်တမ်း ({len(history)} ကြိမ်):*\n"
        for h in history[-5:]:
            txt += f"  • {h['date']} → ฿{h['price']:,}\n"
    txt += f"\n🌐 [Web မှာကြည့်](https://kyawmintun08.github.io/JanJapan-Auction/)"
    return txt

def save_price(chassis, model, color, year, price, user_name):
    now = datetime.now().strftime("%d/%m/%Y")
    entry = {
        "chassis": chassis, "model": model, "color": color,
        "year": year, "price": price, "date": now,
        "location": "Maesot FZ", "added_by": user_name
    }
    PRICE_HISTORY.append(entry)
    # Send to Google Sheets webhook if configured
    if SHEET_WEBHOOK:
        try:
            requests.post(SHEET_WEBHOOK, json=entry, timeout=5)
        except:
            pass
    return entry

# ── Command Handlers ──────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚗 *JAN JAPAN Auction Bot*\n"
        "Maesot Freezone — ဈေးနှုန်း Tracker\n\n"
        "*Commands:*\n"
        "📸 ကားပုံ တင် → Chassis auto ဖတ်\n"
        "🔍 `/find NT32-504837` → Chassis ရှာ\n"
        "🔎 `/model xtrail` → Model ရှာ\n"
        "💰 `/price NT32-504837 150000` → ဈေးထည့်\n"
        "📋 `/history NT32-504837` → ဈေးမှတ်တမ်း\n"
        "📊 `/list` → ကားအားလုံး\n"
        "🌐 `/web` → Web Link\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def find_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Chassis ထည့်ပါ\nဥပမာ: `/find NT32-504837`", parse_mode='Markdown')
        return
    chassis = ' '.join(context.args)
    car = find_by_chassis(chassis)
    if car:
        history = get_price_history(car['chassis'])
        latest_price = history[-1]['price'] if history else None
        txt = format_car_info(car, latest_price, history if history else None)
        keyboard = [[InlineKeyboardButton("💰 ဈေးထည့်", callback_data=f"addprice_{car['chassis']}")]]
        await update.message.reply_text(txt, parse_mode='Markdown',
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(f"❌ `{chassis}` မတွေ့ပါ\n\nChecklist မှာ မပါဘူး — ဈေးထည့်လိုရင် `/price {chassis} [ဈေး]`", parse_mode='Markdown')

async def find_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Model ထည့်ပါ\nဥပမာ: `/model xtrail`", parse_mode='Markdown')
        return
    query = ' '.join(context.args)
    results = find_by_model(query)
    if not results:
        await update.message.reply_text(f"❌ *{query}* မတွေ့ပါ", parse_mode='Markdown')
        return
    txt = f"🔎 *{query.upper()}* ရလဒ် ({len(results)} စီး):\n\n"
    for car in results:
        history = get_price_history(car['chassis'])
        price_str = f"฿{history[-1]['price']:,}" if history else "ဈေးမရသေး"
        txt += f"• `{car['chassis']}` — {car['color']} {car['year']} — *{price_str}*\n"
    txt += f"\n🌐 [Web မှာကြည့်](https://kyawmintun08.github.io/JanJapan-Auction/)"
    await update.message.reply_text(txt, parse_mode='Markdown')

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format မှားနေတယ်\nဥပမာ: `/price NT32-504837 150000`", parse_mode='Markdown')
        return
    chassis = context.args[0].upper()
    try:
        price = int(context.args[1].replace(',', ''))
    except:
        await update.message.reply_text("❌ ဈေး ဂဏန်းသာ ထည့်ပါ", parse_mode='Markdown')
        return
    car = find_by_chassis(chassis)
    if not car:
        car = {"chassis": chassis, "model": "UNKNOWN", "color": "-", "year": 0}
    user_name = update.effective_user.first_name or "Unknown"
    entry = save_price(car['chassis'], car['model'], car['color'], car['year'], price, user_name)
    txt = (
        f"✅ *ဈေးထည့်ပြီးပါပြီ!*\n\n"
        f"🚗 {car['model']} — `{chassis}`\n"
        f"💰 ฿{price:,}\n"
        f"📅 {entry['date']}\n"
        f"👤 {user_name}\n\n"
        f"🌐 [Web မှာကြည့်](https://kyawmintun08.github.io/JanJapan-Auction/)"
    )
    await update.message.reply_text(txt, parse_mode='Markdown')

async def price_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Chassis ထည့်ပါ\nဥပမာ: `/history NT32-504837`", parse_mode='Markdown')
        return
    chassis = ' '.join(context.args).upper()
    history = get_price_history(chassis)
    car = find_by_chassis(chassis)
    if not history:
        await update.message.reply_text(f"❌ `{chassis}` ဈေးမှတ်တမ်း မရှိသေးပါ", parse_mode='Markdown')
        return
    model_name = car['model'] if car else chassis
    txt = f"📈 *{model_name}* ဈေးမှတ်တမ်း\n`{chassis}`\n\n"
    prev = None
    for h in history:
        if prev:
            diff = h['price'] - prev
            arrow = "📈" if diff > 0 else "📉" if diff < 0 else "➡"
            diff_str = f" ({arrow} {diff:+,})"
        else:
            diff_str = ""
        txt += f"• {h['date']} → *฿{h['price']:,}*{diff_str}\n"
        prev = h['price']
    if len(history) >= 2:
        change = history[-1]['price'] - history[0]['price']
        pct = (change / history[0]['price']) * 100
        txt += f"\n📊 စုစုပေါင်းပြောင်းလဲမှု: *{change:+,}* ({pct:+.1f}%)"
    await update.message.reply_text(txt, parse_mode='Markdown')

async def list_cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    priced = set(p['chassis'] for p in PRICE_HISTORY)
    txt = f"🚗 *ကားစာရင်း ({len(CARS)} စီး)*\n\n"
    for car in CARS[:20]:
        status = "💰" if car['chassis'] in priced else "⏳"
        txt += f"{status} `{car['chassis']}` — {car['model']} {car['year']}\n"
    if len(CARS) > 20:
        txt += f"\n... နှင့် {len(CARS)-20} စီး ထပ်ရှိသေးတယ်"
    txt += f"\n\n🌐 [အားလုံးကြည့်ရန်](https://kyawmintun08.github.io/JanJapan-Auction/)"
    await update.message.reply_text(txt, parse_mode='Markdown')

async def web_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "🌐 *JAN JAPAN Auction Web App*\n\n"
        "https://kyawmintun08.github.io/JanJapan-Auction/\n\n"
        "• ကားရှာနိုင် 🔍\n"
        "• ဈေးကြည့်နိုင် 📈\n"
        "• Chart ကြည့်နိုင် 📊\n"
        "• မည်သူမဆို ကြည့်နိုင် ✅"
    )
    await update.message.reply_text(txt, parse_mode='Markdown')

# ── Photo Handler ─────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    await update.message.reply_text("🔍 ပုံကို စစ်နေတယ်... Chassis ရှာနေတယ်")

    # Try to find chassis from caption first
    chassis = extract_chassis_from_text(caption)

    # Try to match with known cars
    car = find_by_chassis(chassis) if chassis else None

    # Check if price is in caption
    price_match = re.search(r'\d{4,6}', caption)
    price = int(price_match.group()) if price_match else None

    if car and price:
        # Auto save both
        user_name = update.effective_user.first_name or "Unknown"
        save_price(car['chassis'], car['model'], car['color'], car['year'], price, user_name)
        txt = (
            f"✅ *Auto ထည့်ပြီးပါပြီ!*\n\n"
            f"🚗 {car['model']} ({car['year']})\n"
            f"🔑 `{car['chassis']}`\n"
            f"💰 ฿{price:,}\n\n"
            f"🌐 [Web မှာကြည့်](https://kyawmintun08.github.io/JanJapan-Auction/)"
        )
        await update.message.reply_text(txt, parse_mode='Markdown')
    elif car:
        # Found chassis, need price
        pending_photo[user_id] = {
            "chassis": car['chassis'], "model": car['model'],
            "color": car['color'], "year": car['year'], "file_id": photo.file_id
        }
        txt = (
            f"🚗 ကားတွေ့ပြီ!\n\n"
            f"*{car['model']}* ({car['year']})\n"
            f"`{car['chassis']}`\n\n"
            f"💰 ဈေး ရိုက်ထည့်ပါ (ဂဏန်းသာ):\nဥပမာ: `150000`"
        )
        await update.message.reply_text(txt, parse_mode='Markdown')
    elif chassis:
        # Chassis found but not in list
        pending_photo[user_id] = {
            "chassis": chassis, "model": "UNKNOWN", "color": "-",
            "year": 0, "file_id": photo.file_id
        }
        txt = (
            f"⚠️ Chassis တွေ့ပြီ: `{chassis}`\n"
            f"Checklist မှာ မပါဘူး — ဈေး ရိုက်ထည့်ပါ:\nဥပမာ: `150000`"
        )
        await update.message.reply_text(txt, parse_mode='Markdown')
    else:
        # No chassis found
        txt = (
            "⚠️ Chassis ဖတ်မရပါ\n\n"
            "ကိုယ်တိုင် ထည့်ပါ:\n"
            "`/price [chassis] [ဈေး]`\n\n"
            "ဥပမာ: `/price NT32-504837 150000`"
        )
        await update.message.reply_text(txt, parse_mode='Markdown')

# ── Text Handler (for price after photo) ──────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Check if waiting for price
    if user_id in pending_photo:
        price_match = re.match(r'^[\d,]+$', text.replace(' ', ''))
        if price_match:
            try:
                price = int(text.replace(',', '').replace(' ', ''))
                data = pending_photo.pop(user_id)
                user_name = update.effective_user.first_name or "Unknown"
                save_price(data['chassis'], data['model'], data['color'], data['year'], price, user_name)
                txt = (
                    f"✅ *ဈေးထည့်ပြီးပါပြီ!*\n\n"
                    f"🚗 {data['model']} — `{data['chassis']}`\n"
                    f"💰 ฿{price:,}\n\n"
                    f"🌐 [Web မှာကြည့်](https://kyawmintun08.github.io/JanJapan-Auction/)"
                )
                await update.message.reply_text(txt, parse_mode='Markdown')
                return
            except:
                pass

    # Auto chassis detection in text
    chassis = extract_chassis_from_text(text)
    if chassis:
        car = find_by_chassis(chassis)
        if car:
            history = get_price_history(car['chassis'])
            latest_price = history[-1]['price'] if history else None
            txt = format_car_info(car, latest_price, history if history else None)
            keyboard = [[InlineKeyboardButton("💰 ဈေးထည့်", callback_data=f"addprice_{car['chassis']}")]]
            await update.message.reply_text(txt, parse_mode='Markdown',
                                            reply_markup=InlineKeyboardMarkup(keyboard))

# ── Callback Handler ───────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("addprice_"):
        chassis = query.data.replace("addprice_", "")
        user_id = query.from_user.id
        car = find_by_chassis(chassis)
        if car:
            pending_photo[user_id] = {
                "chassis": car['chassis'], "model": car['model'],
                "color": car['color'], "year": car['year'], "file_id": None
            }
        await query.message.reply_text(
            f"💰 `{chassis}` ဈေး ရိုက်ထည့်ပါ:\nဥပမာ: `150000`", parse_mode='Markdown')

# ── Main ───────────────────────────────────────────────
# ── Main ────────────────────────────────────────────────
# အပေါ်က handlers တွေ add လုပ်ပြီးသားဆိုရင် ဒီနေရာမှာ ထည့်ရုံပဲ

async def main():
    logger.info("Bot starting...")

    app = Application.builder().token(TOKEN).build()

    # မင်း handlers တွေ အားလုံး ပြန်ထည့်ပါ (အရင်က ထည့်ထားတဲ့ အတိုင်း)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find_car))
    app.add_handler(CommandHandler("model", find_model))
    app.add_handler(CommandHandler("price", add_price))
    # ဓာတ်ပုံ handler ရှိရင် ထည့်ပါ
    # app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(CallbackQueryHandler(button_callback))
    # အခြား handlers တွေ လိုရင် ထည့်ပါ

    # Polling စတင်ပါ
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,          # pending updates ရှင်းဖို့
        allowed_updates=Update.ALL_TYPES    # လိုအပ်ရင် ပြင်ပါ
    )

    logger.info("Bot is polling now!")
    # bot မရပ်အောင် ထားပါ (infinite loop)
    await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
