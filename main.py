import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime
import requests

# تنظیمات logging
logging.basicConfig(
    format='%(asame)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات
TOKEN = '8678842471:AAGg09zAWG7xC2vdzVE4-0iTDaW73QUwuwc'


# فرمت‌کننده قیمت
def format_price(price):
    try:
        return f"{int(price):,}"
    except:
        return "0"


# کلاس اصلی مدیریت داده‌ها
class AccountingBot:
    def __init__(self):
        self.data_file = 'accounting_data.json'
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except:
                self.data = self.get_default_data()
        else:
            self.data = self.get_default_data()

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_default_data(self):
        return {
            'initial_capital': 0,
            'purchases': [],
            'sales': [],
            'costs': [],
            'transactions': [],
            'debt_payments': [],
            'purchase_debt_payments': [],
            'partner_transactions': []
        }

    def get_total_purchase_payments(self, purchase_id):
        total = 0
        for payment in self.data['purchase_debt_payments']:
            if payment['purchase_id'] == purchase_id:
                total += payment['amount']
        return total

    def get_total_sale_payments(self, sale_id):
        total = 0
        for payment in self.data['debt_payments']:
            if payment['sale_id'] == sale_id:
                total += payment['amount']
        return total

    def calculate_balance(self):
        cash_in = self.data['initial_capital']
        for p in self.data['purchases']:
            cash_paid = p.get('cash_paid', p['total_cost'] - p.get('purchase_debt', 0))
            cash_in -= cash_paid
        for s in self.data['sales']:
            cash_received = s.get('cash_received', s['sell_price'] - s.get('debt', 0))
            cash_in += cash_received
        for c in self.data['costs']:
            cash_in -= c['amount']
        for t in self.data['partner_transactions']:
            if t['type'] == 'cash_withdraw':
                cash_in -= t['amount']
            elif t['type'] == 'cash_deposit':
                cash_in += t['amount']
        return cash_in

    def calculate_inventory(self):
        items = [p for p in self.data['purchases'] if not p.get('sold', False)]
        count = len(items)
        value = sum(p['total_cost'] for p in items)
        return count, value

    def calculate_total_profit(self):
        return sum(s.get('profit', 0) for s in self.data['sales'])

    def calculate_total_costs(self):
        total_costs = sum(c['amount'] for c in self.data['costs'])
        partner_expenses = 0
        for t in self.data['partner_transactions']:
            if t['type'] == 'personal_expense':
                partner_expenses += t['amount']
        return total_costs + partner_expenses

    def calculate_remaining_debts(self):
        sales_debt = 0
        for s in self.data['sales']:
            remaining = s.get('remaining_debt', s.get('debt', 0))
            paid = self.get_total_sale_payments(s['id'])
            sales_debt += remaining - paid if remaining > paid else 0
        purchase_debt = 0
        for p in self.data['purchases']:
            if p.get('purchase_debt', 0) > 0:
                remaining = p.get('remaining_debt', p['purchase_debt'])
                paid = self.get_total_purchase_payments(p['id'])
                purchase_debt += remaining - paid if remaining > paid else 0
        return sales_debt, purchase_debt

    def calculate_partner_balances(self):
        total_profit = self.calculate_total_profit()
        total_costs = self.calculate_total_costs()
        partner_share = (total_profit - total_costs) / 2

        reza_transactions = 0
        milad_transactions = 0
        for t in self.data['partner_transactions']:
            multiplier = 1
            if t['type'] in ['cash_withdraw', 'company_asset_use']:
                multiplier = -1
            amount = t['amount'] * multiplier
            if t['partner'] == 'reza':
                reza_transactions += amount
            else:
                milad_transactions += amount

        reza_balance = partner_share + reza_transactions
        milad_balance = partner_share + milad_transactions
        return reza_balance, milad_balance

    def calculate_consistency(self):
        balance = self.calculate_balance()
        inv_count, inv_value = self.calculate_inventory()
        sales_debt, purchase_debt = self.calculate_remaining_debts()
        assets = balance + inv_value + sales_debt
        liabilities = purchase_debt + self.data['initial_capital']
        reza_balance, milad_balance = self.calculate_partner_balances()
        total_partner = reza_balance + milad_balance
        total_liabilities = liabilities + total_partner
        discrepancy = abs(assets - total_liabilities)
        return assets, total_liabilities, discrepancy

    def get_statistics(self):
        balance = self.calculate_balance()
        inv_count, inv_value = self.calculate_inventory()
        total_profit = self.calculate_total_profit()
        sales_debt, purchase_debt = self.calculate_remaining_debts()
        total_costs = self.calculate_total_costs()
        reza_balance, milad_balance = self.calculate_partner_balances()
        assets, liabilities, discrepancy = self.calculate_consistency()

        reza_status = "✅" if reza_balance >= 0 else "❌"
        milad_status = "✅" if milad_balance >= 0 else "❌"
        consistency_status = "✓" if discrepancy < 1000 else "⚠️"

        stats = "╔════════════════════════╗\n"
        stats += "║     📊 **داشبورد**     ║\n"
        stats += "╚════════════════════════╝\n\n"

        stats += f"💰 موجودی: {format_price(balance)} تومان\n"
        stats += f"📦 انبار: {inv_count} عدد ({format_price(inv_value)} ت)\n"
        stats += f"📈 سود کل: {format_price(total_profit)} تومان\n"
        stats += f"💸 هزینه‌ها: {format_price(total_costs)} تومان\n\n"

        stats += "⚠️ **بدهی‌ها:**\n"
        stats += f"└─ فروش: {format_price(sales_debt)} ت\n"
        stats += f"└─ خرید: {format_price(purchase_debt)} ت\n\n"

        stats += "👥 **شرکا:**\n"
        stats += f"└─ رضا: {format_price(abs(reza_balance))} ت {reza_status}\n"
        stats += f"└─ میلاد: {format_price(abs(milad_balance))} ت {milad_status}\n\n"

        stats += f"📊 تطابق حساب:\n"
        stats += f"└─ جمع کل: {format_price(assets)} ت\n"
        stats += f"└─ مغایرت: {format_price(discrepancy)} ت {consistency_status}"

        return stats


bot_accounting = AccountingBot()


# ==================== منوی اصلی ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 ثبت فروش", callback_data='sell_menu'),
         InlineKeyboardButton("🛒 ثبت خرید", callback_data='buy_menu')],
        [InlineKeyboardButton("📋 لیست فروش‌ها", callback_data='list_sales_menu'),
         InlineKeyboardButton("📋 لیست خریدها", callback_data='list_buys_menu')],
        [InlineKeyboardButton("💸 هزینه‌های جاری", callback_data='costs_menu'),
         InlineKeyboardButton("📜 تراکنش‌ها", callback_data='transactions')],
        [InlineKeyboardButton("👥 تراکنش شرکا", callback_data='partner_menu'),
         InlineKeyboardButton("💳 مدیریت بدهی", callback_data='debt_menu')],
        [InlineKeyboardButton("💾 پشتیبان و بازیابی", callback_data='backup_menu'),
         InlineKeyboardButton("⚙️ تنظیمات", callback_data='settings_menu')],
        [InlineKeyboardButton("📊 داشبورد", callback_data='dashboard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎯 **به ربات حسابداری خوش آمدید**\n\nاز منوی زیر انتخاب کنید:",
        reply_markup=reply_markup, parse_mode='Markdown'
    )


async def set_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = [
        BotCommand("start", "🏠 منوی اصلی"),
        BotCommand("dashboard", "📊 داشبورد"),
        BotCommand("sell", "💰 ثبت فروش"),
        BotCommand("buy", "🛒 ثبت خرید"),
        BotCommand("list_sales", "📋 لیست فروش‌ها"),
        BotCommand("list_buys", "📋 لیست خریدها"),
        BotCommand("costs", "💸 هزینه‌ها"),
        BotCommand("list_costs", "📋 لیست هزینه‌ها"),
        BotCommand("transactions", "📜 تراکنش‌ها"),
        BotCommand("partners", "👥 شرکا"),
        BotCommand("debts", "💳 بدهی‌ها"),
        BotCommand("backup", "💾 پشتیبان"),
        BotCommand("settings", "⚙️ تنظیمات"),
        BotCommand("cancel", "❌ لغو"),
        BotCommand("help", "❓ راهنما")
    ]
    await context.bot.set_my_commands(commands)
    await update.message.reply_text("✅ منوی ربات تنظیم شد!")


# ==================== توابع لیست ====================

async def list_buys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_accounting.data['purchases']:
        await update.message.reply_text("❌ هیچ خریدی ثبت نشده.")
        return
    text = "📋 **لیست خریدها:**\n\n"
    for i, p in enumerate(bot_accounting.data['purchases'][-20:], 1):
        status = "✅" if p.get('sold') else "🟢"
        text += f"{i}. **{p['model']}** {status}\n"
        text += f"   📅 {p['date']} | 💰 {format_price(p['total_cost'])} ت\n"
        if p.get('purchase_debt', 0) > 0:
            remaining = p.get('remaining_debt', p['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                p['id'])
            text += f"   ⚠️ بدهی: {format_price(max(0, remaining))} ت\n"
        text += "\n"
    await update.message.reply_text(text, parse_mode='Markdown')


async def list_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_accounting.data['sales']:
        await update.message.reply_text("❌ هیچ فروشی ثبت نشده.")
        return
    text = "📋 **لیست فروش‌ها:**\n\n"
    for i, s in enumerate(bot_accounting.data['sales'][-20:], 1):
        profit_emoji = "📈" if s.get('profit', 0) >= 0 else "📉"
        text += f"{i}. **{s['model']}** {profit_emoji}\n"
        text += f"   📅 {s['date']} | 💰 فروش: {format_price(s['sell_price'])} ت\n"
        text += f"   سود: {format_price(s.get('profit', 0))} ت\n"
        if s.get('debt', 0) > 0:
            remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(s['id'])
            text += f"   ⚠️ بدهی: {format_price(max(0, remaining))} ت\n"
        if s.get('customer_name'):
            text += f"   👤 {s['customer_name']}\n"
        text += "\n"
    await update.message.reply_text(text, parse_mode='Markdown')


async def list_costs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_accounting.data['costs']:
        await update.message.reply_text("❌ هیچ هزینه‌ای ثبت نشده.")
        return
    text = "📋 **لیست هزینه‌ها:**\n\n"
    for i, c in enumerate(bot_accounting.data['costs'][-20:], 1):
        text += f"{i}. **{c['title']}**\n"
        text += f"   📅 {c['date']} | 💰 {format_price(c['amount'])} ت\n"
        if c.get('description'):
            text += f"   📌 {c['description']}\n"
        text += "\n"
    await update.message.reply_text(text, parse_mode='Markdown')


# ==================== هندلر دکمه‌ها ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("💰 ثبت فروش", callback_data='sell_menu'),
             InlineKeyboardButton("🛒 ثبت خرید", callback_data='buy_menu')],
            [InlineKeyboardButton("📋 لیست فروش‌ها", callback_data='list_sales_menu'),
             InlineKeyboardButton("📋 لیست خریدها", callback_data='list_buys_menu')],
            [InlineKeyboardButton("💸 هزینه‌های جاری", callback_data='costs_menu'),
             InlineKeyboardButton("📜 تراکنش‌ها", callback_data='transactions')],
            [InlineKeyboardButton("👥 تراکنش شرکا", callback_data='partner_menu'),
             InlineKeyboardButton("💳 مدیریت بدهی", callback_data='debt_menu')],
            [InlineKeyboardButton("💾 پشتیبان و بازیابی", callback_data='backup_menu'),
             InlineKeyboardButton("⚙️ تنظیمات", callback_data='settings_menu')],
            [InlineKeyboardButton("📊 داشبورد", callback_data='dashboard')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎯 **منوی اصلی**", reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'dashboard':
        stats = bot_accounting.get_statistics()
        keyboard = [[InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(stats, reply_markup=reply_markup, parse_mode='Markdown')

    # ========== فروش ==========
    elif query.data == 'sell_menu':
        available = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]
        if not available:
            await query.edit_message_text("❌ گوشی موجود نیست!", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]]))
            return
        text = "💰 **ثبت فروش**\n\nانتخاب کنید:\n"
        keyboard = []
        for i, p in enumerate(available[-10:], 1):
            keyboard.append([InlineKeyboardButton(f"{i}. {p['model']} - {format_price(p['total_cost'])} ت",
                                                  callback_data=f"sell_select_{p['id']}")])
        keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data.startswith('sell_select_'):
        pid = int(query.data.replace('sell_select_', ''))
        context.user_data['sell_purchase_id'] = pid
        context.user_data['action'] = 'new_sell'
        context.user_data['step'] = 'waiting_sell_price'
        p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
        await query.edit_message_text(
            f"📱 {p['model']}\n💰 خرید: {format_price(p['total_cost'])} ت\n\nقیمت فروش را وارد کن:")

    # ========== خرید ==========
    elif query.data == 'buy_menu':
        context.user_data['action'] = 'new_buy'
        context.user_data['step'] = 'waiting_buy_model'
        await query.edit_message_text("📱 مدل گوشی را وارد کن:")

    # ========== لیست خریدها ==========
    elif query.data == 'list_buys_menu':
        if not bot_accounting.data['purchases']:
            await query.edit_message_text("❌ خریدی نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]]))
            return
        text = "📋 **لیست خریدها**\n\n"
        keyboard = []
        for i, p in enumerate(bot_accounting.data['purchases'][-10:], 1):
            status = "✅" if p.get('sold') else "🟢"
            keyboard.append([InlineKeyboardButton(f"{i}. {p['model']} - {format_price(p['total_cost'])} ت {status}",
                                                  callback_data=f"view_purchase_{p['id']}")])
        keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data.startswith('view_purchase_'):
        pid = int(query.data.replace('view_purchase_', ''))
        p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
        remaining = p.get('remaining_debt', p.get('purchase_debt', 0)) - bot_accounting.get_total_purchase_payments(pid)
        text = f"📱 **{p['model']}**\n📅 {p['date']}\n💰 {format_price(p['total_cost'])} ت\n"
        if p.get('purchase_debt', 0) > 0:
            text += f"⚠️ بدهی: {format_price(p['purchase_debt'])} ت\n💸 پرداخت شده: {format_price(bot_accounting.get_total_purchase_payments(pid))} ت\n"
        text += f"📌 {'✅ فروخته شده' if p.get('sold') else '🟢 در انبار'}"
        keyboard = []
        if not p.get('sold'):
            keyboard.append([InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_purchase_{pid}"),
                             InlineKeyboardButton("❌ حذف", callback_data=f"delete_purchase_{pid}")])
        else:
            keyboard.append([InlineKeyboardButton("❌ حذف", callback_data=f"delete_purchase_{pid}")])
        if p.get('purchase_debt', 0) > 0 and remaining > 0:
            keyboard.append([InlineKeyboardButton("💳 پرداخت بدهی", callback_data=f"pay_purchase_{pid}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='list_buys_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ========== لیست فروش‌ها ==========
    elif query.data == 'list_sales_menu':
        if not bot_accounting.data['sales']:
            await query.edit_message_text("❌ فروشی نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]]))
            return
        text = "📋 **لیست فروش‌ها**\n\n"
        keyboard = []
        for i, s in enumerate(bot_accounting.data['sales'][-10:], 1):
            emoji = "📈" if s.get('profit', 0) >= 0 else "📉"
            keyboard.append([InlineKeyboardButton(f"{i}. {s['model']} - {format_price(s['sell_price'])} ت {emoji}",
                                                  callback_data=f"view_sale_{s['id']}")])
        keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data.startswith('view_sale_'):
        sid = int(query.data.replace('view_sale_', ''))
        s = next((s for s in bot_accounting.data['sales'] if s['id'] == sid))
        remaining = s.get('remaining_debt', s.get('debt', 0)) - bot_accounting.get_total_sale_payments(sid)
        text = f"💰 **{s['model']}**\n📅 {s['date']}\n💰 خرید: {format_price(s.get('purchase_price', 0))} ت\n💰 فروش: {format_price(s['sell_price'])} ت\n📊 سود: {format_price(s.get('profit', 0))} ت\n"
        if s.get('debt', 0) > 0:
            text += f"⚠️ بدهی: {format_price(s['debt'])} ت\n💸 دریافت شده: {format_price(bot_accounting.get_total_sale_payments(sid))} ت\n"
        if s.get('customer_name'):
            text += f"👤 {s['customer_name']}\n"
        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_sale_{sid}"),
             InlineKeyboardButton("❌ حذف", callback_data=f"delete_sale_{sid}")]
        ]
        if s.get('debt', 0) > 0 and remaining > 0:
            keyboard.append([InlineKeyboardButton("💳 دریافت بدهی", callback_data=f"pay_sale_{sid}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='list_sales_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ========== هزینه‌ها ==========
    elif query.data == 'costs_menu':
        keyboard = [
            [InlineKeyboardButton("➕ ثبت هزینه", callback_data='new_cost')],
            [InlineKeyboardButton("📋 لیست هزینه‌ها", callback_data='list_costs')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        await query.edit_message_text("💸 **هزینه‌ها**", reply_markup=InlineKeyboardMarkup(keyboard),
                                      parse_mode='Markdown')

    elif query.data == 'new_cost':
        context.user_data['action'] = 'new_cost'
        context.user_data['step'] = 'waiting_cost_title'
        await query.edit_message_text("📝 عنوان هزینه را وارد کن:")

    elif query.data == 'list_costs':
        if not bot_accounting.data['costs']:
            await query.edit_message_text("❌ هزینه‌ای نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='costs_menu')]]))
            return
        text = "📋 **لیست هزینه‌ها**\n\n"
        keyboard = []
        for i, c in enumerate(bot_accounting.data['costs'][-10:], 1):
            keyboard.append([InlineKeyboardButton(f"{i}. {c['title']} - {format_price(c['amount'])} ت",
                                                  callback_data=f"view_cost_{c['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='costs_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data.startswith('view_cost_'):
        cid = int(query.data.replace('view_cost_', ''))
        c = next((c for c in bot_accounting.data['costs'] if c['id'] == cid))
        text = f"💸 **{c['title']}**\n📅 {c['date']}\n💰 {format_price(c['amount'])} ت\n"
        if c.get('description'):
            text += f"📌 {c['description']}\n"
        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_cost_{cid}"),
             InlineKeyboardButton("❌ حذف", callback_data=f"delete_cost_{cid}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='list_costs')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ========== شرکا ==========
    elif query.data == 'partner_menu':
        keyboard = [
            [InlineKeyboardButton("👤 تراکنش رضا", callback_data='partner_reza')],
            [InlineKeyboardButton("👤 تراکنش میلاد", callback_data='partner_milad')],
            [InlineKeyboardButton("📜 لیست تراکنش‌ها", callback_data='list_partner')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        await query.edit_message_text("👥 **شرکا**\n\nهزینه شخصی به هزینه‌ها اضافه می‌شود",
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data == 'partner_reza':
        context.user_data['partner'] = 'reza'
        context.user_data['action'] = 'partner_transaction'
        await query.edit_message_text(
            "👤 **رضا**\n\n1️⃣ برداشت نقدی\n2️⃣ واریز نقدی\n3️⃣ هزینه شخصی\n4️⃣ استفاده دارایی\n\nشماره را وارد کن:")

    elif query.data == 'partner_milad':
        context.user_data['partner'] = 'milad'
        context.user_data['action'] = 'partner_transaction'
        await query.edit_message_text(
            "👤 **میلاد**\n\n1️⃣ برداشت نقدی\n2️⃣ واریز نقدی\n3️⃣ هزینه شخصی\n4️⃣ استفاده دارایی\n\nشماره را وارد کن:")

    elif query.data == 'list_partner':
        if not bot_accounting.data['partner_transactions']:
            await query.edit_message_text("❌ تراکنشی نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='partner_menu')]]))
            return
        text = "👥 **تراکنش‌ها**\n\n"
        for i, t in enumerate(bot_accounting.data['partner_transactions'][-20:], 1):
            partner = "رضا" if t['partner'] == 'reza' else "میلاد"
            type_text = {'cash_withdraw': 'برداشت', 'cash_deposit': 'واریز', 'personal_expense': 'هزینه شخصی',
                         'company_asset_use': 'استفاده دارایی', 'other': 'سایر'}.get(t['type'], t['type'])
            text += f"{i}. {partner} - {type_text}\n   📅 {t['date']} | 💰 {format_price(t['amount'])} ت\n   📝 {t['description'][:30]}\n\n"
        await query.edit_message_text(text, parse_mode='Markdown')

    # ========== بدهی ==========
    elif query.data == 'debt_menu':
        sales, purchase = bot_accounting.calculate_remaining_debts()
        text = f"💳 **بدهی‌ها**\n\n⚠️ فروش: {format_price(sales)} ت\n⚠️ خرید: {format_price(purchase)} ت\n\n"
        keyboard = [
            [InlineKeyboardButton("💳 دریافت بدهی فروش", callback_data='pay_sale_debt')],
            [InlineKeyboardButton("💳 پرداخت بدهی خرید", callback_data='pay_purchase_debt')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data == 'pay_sale_debt':
        sales = []
        for s in bot_accounting.data['sales']:
            if s.get('debt', 0) > 0:
                remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(s['id'])
                if remaining > 0:
                    sales.append((s, remaining))
        if not sales:
            await query.edit_message_text("✅ بدهی معوقی نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='debt_menu')]]))
            return
        text = "💳 **دریافت بدهی**\n\n"
        keyboard = []
        for i, (s, r) in enumerate(sales[-10:], 1):
            keyboard.append([InlineKeyboardButton(f"{i}. {s['model']} - {format_price(r)} ت",
                                                  callback_data=f"pay_sale_{s['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='debt_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data == 'pay_purchase_debt':
        purchases = []
        for p in bot_accounting.data['purchases']:
            if p.get('purchase_debt', 0) > 0:
                remaining = p.get('remaining_debt', p['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                    p['id'])
                if remaining > 0:
                    purchases.append((p, remaining))
        if not purchases:
            await query.edit_message_text("✅ بدهی معوقی نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='debt_menu')]]))
            return
        text = "💳 **پرداخت بدهی**\n\n"
        keyboard = []
        for i, (p, r) in enumerate(purchases[-10:], 1):
            keyboard.append([InlineKeyboardButton(f"{i}. {p['model']} - {format_price(r)} ت",
                                                  callback_data=f"pay_purchase_{p['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data='debt_menu')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ========== پشتیبان ==========
    elif query.data == 'backup_menu':
        keyboard = [
            [InlineKeyboardButton("💾 پشتیبان کامل", callback_data='full_backup')],
            [InlineKeyboardButton("🔄 بازیابی کامل", callback_data='full_restore')],
            [InlineKeyboardButton("📦 پشتیبان انبار", callback_data='inventory_backup')],
            [InlineKeyboardButton("📂 بازیابی انبار", callback_data='inventory_restore')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        await query.edit_message_text("💾 **مدیریت پشتیبان**", reply_markup=InlineKeyboardMarkup(keyboard),
                                      parse_mode='Markdown')

    elif query.data == 'full_backup':
        await query.edit_message_text("💾 در حال تهیه پشتیبان...")
        fn = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(bot_accounting.data, f, ensure_ascii=False, indent=2)
        with open(fn, 'rb') as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=fn,
                                            caption="📦 پشتیبان کامل")
        os.remove(fn)

    elif query.data == 'full_restore':
        context.user_data['action'] = 'full_restore'
        await query.edit_message_text("🔄 فایل پشتیبان را ارسال کن:")

    elif query.data == 'inventory_backup':
        await query.edit_message_text("📦 در حال تهیه پشتیبان...")
        items = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]
        data = {'date': str(datetime.now()), 'type': 'inventory', 'items': items}
        fn = f"inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(fn, 'rb') as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=fn,
                                            caption="📦 پشتیبان انبار")
        os.remove(fn)

    elif query.data == 'inventory_restore':
        context.user_data['action'] = 'inventory_restore'
        await query.edit_message_text("📂 فایل پشتیبان را ارسال کن:")

    # ========== تنظیمات ==========
    elif query.data == 'settings_menu':
        keyboard = [
            [InlineKeyboardButton("💰 سرمایه اولیه", callback_data='set_initial_capital')],
            [InlineKeyboardButton("📝 راهنما", callback_data='help')],
            [InlineKeyboardButton("🧹 پاک کردن همه", callback_data='clear_all')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        await query.edit_message_text("⚙️ **تنظیمات**", reply_markup=InlineKeyboardMarkup(keyboard),
                                      parse_mode='Markdown')

    elif query.data == 'set_initial_capital':
        context.user_data['action'] = 'set_capital'
        await query.edit_message_text("💰 مبلغ سرمایه اولیه را وارد کن:")

    elif query.data == 'help':
        help_text = """
❓ **راهنما**

🛒 **ثبت خرید:** مدل، قیمت، هزینه‌ها، بدهی
💰 **ثبت فروش:** انتخاب از لیست، قیمت، بدهی، مشتری
📋 **لیست‌ها:** مشاهده و مدیریت
💸 **هزینه‌ها:** ثبت و مدیریت هزینه‌ها
👥 **شرکا:** تراکنش رضا و میلاد
💳 **بدهی‌ها:** دریافت و پرداخت
💾 **پشتیبان:** کامل و انبار
⚙️ **تنظیمات:** سرمایه، پاک کردن

📝 برای انصراف /cancel بزن
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')

    elif query.data == 'clear_all':
        keyboard = [
            [InlineKeyboardButton("✅ بله", callback_data='confirm_clear')],
            [InlineKeyboardButton("❌ خیر", callback_data='settings_menu')]
        ]
        await query.edit_message_text("⚠️ همه داده‌ها پاک شوند؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'confirm_clear':
        bot_accounting.data = bot_accounting.get_default_data()
        bot_accounting.save_data()
        await query.edit_message_text("✅ پاک شد.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 منو", callback_data='main_menu')]]))

    # ========== تراکنش‌ها ==========
    elif query.data == 'transactions':
        if not bot_accounting.data['transactions']:
            await query.edit_message_text("❌ تراکنشی نیست.", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]]))
            return
        text = "📜 **تراکنش‌ها**\n\n"
        for i, t in enumerate(bot_accounting.data['transactions'][-15:], 1):
            emoji = "💰" if t['amount'] > 0 else "💸"
            text += f"{i}. {emoji} {t['type']} - {t['date']}\n   {t['model']} | {format_price(abs(t['amount']))} ت\n"
        await query.edit_message_text(text, parse_mode='Markdown')

    # ========== ویرایش/حذف خرید ==========
    elif query.data.startswith('edit_purchase_'):
        pid = int(query.data.replace('edit_purchase_', ''))
        p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
        if p.get('sold'):
            await query.edit_message_text("❌ قابل ویرایش نیست")
            return
        context.user_data['edit_purchase_id'] = pid
        context.user_data['action'] = 'edit_purchase'
        context.user_data['step'] = 'waiting_buy_model'
        context.user_data.update({
            'buy_model': p['model'], 'buy_price': p['buy_price'],
            'buy_delivery': p.get('delivery_cost', 0), 'buy_extra': p.get('extra_cost', 0),
            'buy_debt': p.get('purchase_debt', 0), 'original_notes': p.get('notes', '')
        })
        await query.edit_message_text(f"✏️ مدل جدید ({p['model']}) را وارد کن:")

    elif query.data.startswith('delete_purchase_'):
        pid = int(query.data.replace('delete_purchase_', ''))
        context.user_data['delete_purchase_id'] = pid
        keyboard = [
            [InlineKeyboardButton("✅ بله", callback_data='confirm_delete_purchase')],
            [InlineKeyboardButton("❌ خیر", callback_data='list_buys_menu')]
        ]
        await query.edit_message_text("⚠️ حذف شود؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'confirm_delete_purchase':
        pid = context.user_data.get('delete_purchase_id')
        if pid:
            bot_accounting.data['purchases'] = [p for p in bot_accounting.data['purchases'] if p['id'] != pid]
            bot_accounting.data['transactions'] = [t for t in bot_accounting.data['transactions']
                                                   if not (t.get('type') == 'خرید' and t.get('purchase_id') == pid)]
            bot_accounting.data['purchase_debt_payments'] = [p for p in bot_accounting.data['purchase_debt_payments']
                                                             if p['purchase_id'] != pid]
            bot_accounting.save_data()
        context.user_data.pop('delete_purchase_id', None)
        await query.edit_message_text("✅ حذف شد.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 لیست", callback_data='list_buys_menu')]]))

    # ========== ویرایش/حذف فروش ==========
    elif query.data.startswith('edit_sale_'):
        sid = int(query.data.replace('edit_sale_', ''))
        s = next((s for s in bot_accounting.data['sales'] if s['id'] == sid))
        context.user_data['edit_sale_id'] = sid
        context.user_data['action'] = 'edit_sale'
        context.user_data['step'] = 'waiting_sell_price'
        context.user_data.update({
            'sell_price': s['sell_price'], 'sell_debt': s.get('debt', 0),
            'sell_customer': s.get('customer_name', ''), 'sell_phone': s.get('customer_phone', ''),
            'original_notes': s.get('notes', '')
        })
        await query.edit_message_text(f"✏️ قیمت جدید ({format_price(s['sell_price'])} ت) را وارد کن:")

    elif query.data.startswith('delete_sale_'):
        sid = int(query.data.replace('delete_sale_', ''))
        context.user_data['delete_sale_id'] = sid
        keyboard = [
            [InlineKeyboardButton("✅ بله", callback_data='confirm_delete_sale')],
            [InlineKeyboardButton("❌ خیر", callback_data='list_sales_menu')]
        ]
        await query.edit_message_text("⚠️ حذف شود؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'confirm_delete_sale':
        sid = context.user_data.get('delete_sale_id')
        if sid:
            s = next((s for s in bot_accounting.data['sales'] if s['id'] == sid), None)
            if s:
                p = next((p for p in bot_accounting.data['purchases'] if p['id'] == s['purchase_id']), None)
                if p:
                    p['sold'] = False
                bot_accounting.data['sales'] = [x for x in bot_accounting.data['sales'] if x['id'] != sid]
                bot_accounting.data['transactions'] = [t for t in bot_accounting.data['transactions']
                                                       if not (t.get('type') == 'فروش' and t.get('sale_id') == sid)]
                bot_accounting.data['debt_payments'] = [d for d in bot_accounting.data['debt_payments']
                                                        if d['sale_id'] != sid]
                bot_accounting.save_data()
        context.user_data.pop('delete_sale_id', None)
        await query.edit_message_text("✅ حذف شد.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 لیست", callback_data='list_sales_menu')]]))

    # ========== ویرایش/حذف هزینه ==========
    elif query.data.startswith('edit_cost_'):
        cid = int(query.data.replace('edit_cost_', ''))
        c = next((c for c in bot_accounting.data['costs'] if c['id'] == cid))
        context.user_data['edit_cost_id'] = cid
        context.user_data['action'] = 'edit_cost'
        context.user_data['step'] = 'waiting_cost_title'
        context.user_data.update({
            'cost_title': c['title'], 'cost_amount': c['amount'],
            'cost_description': c.get('description', '')
        })
        await query.edit_message_text(f"✏️ عنوان جدید ({c['title']}) را وارد کن:")

    elif query.data.startswith('delete_cost_'):
        cid = int(query.data.replace('delete_cost_', ''))
        context.user_data['delete_cost_id'] = cid
        keyboard = [
            [InlineKeyboardButton("✅ بله", callback_data='confirm_delete_cost')],
            [InlineKeyboardButton("❌ خیر", callback_data='list_costs')]
        ]
        await query.edit_message_text("⚠️ حذف شود؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'confirm_delete_cost':
        cid = context.user_data.get('delete_cost_id')
        if cid:
            c = next((c for c in bot_accounting.data['costs'] if c['id'] == cid), None)
            if c:
                bot_accounting.data['costs'] = [x for x in bot_accounting.data['costs'] if x['id'] != cid]
                bot_accounting.data['transactions'] = [t for t in bot_accounting.data['transactions']
                                                       if
                                                       not (t.get('type') == 'هزینه' and t.get('model') == c['title'])]
                bot_accounting.save_data()
        context.user_data.pop('delete_cost_id', None)
        await query.edit_message_text("✅ حذف شد.", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 لیست", callback_data='list_costs')]]))


# ==================== هندلر پیام‌ها ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_data = context.user_data
    action = user_data.get('action')

    if not action:
        await update.message.reply_text("لطفاً از منو استفاده کنید.")
        return

    # سرمایه اولیه
    if action == 'set_capital':
        try:
            amount = int(text.replace(',', ''))
            bot_accounting.data['initial_capital'] = amount
            bot_accounting.data['transactions'].insert(0, {
                'id': int(datetime.now().timestamp() * 1000), 'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'سرمایه اولیه', 'model': '-', 'amount': amount, 'debt': 0, 'profit': 0,
                'description': 'سرمایه اولیه'
            })
            bot_accounting.save_data()
            await update.message.reply_text(f"✅ سرمایه {format_price(amount)} ت ثبت شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("⚙️ تنظیمات", callback_data='settings_menu')]]))
            user_data.clear()
        except:
            await update.message.reply_text("❌ عدد معتبر وارد کن.")
        return

    # خرید جدید
    if action == 'new_buy':
        step = user_data.get('step')
        if step == 'waiting_buy_model':
            if text == '-':
                user_data.clear();
                await update.message.reply_text("❌ لغو شد.");
                return
            user_data['buy_model'] = text
            user_data['step'] = 'waiting_buy_price'
            await update.message.reply_text("💰 قیمت خرید را وارد کن:")
        elif step == 'waiting_buy_price':
            try:
                user_data['buy_price'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_delivery'
                await update.message.reply_text("🚚 هزینه پیک (0):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_buy_delivery':
            try:
                user_data['buy_delivery'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_extra'
                await update.message.reply_text("💰 هزینه جانبی (0):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_buy_extra':
            try:
                user_data['buy_extra'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_debt'
                await update.message.reply_text("⚠️ بدهی به فروشنده (0):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_buy_debt':
            try:
                user_data['buy_debt'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_notes'
                await update.message.reply_text("📝 توضیحات (یا -):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_buy_notes':
            notes = text if text != '-' else ''
            total = user_data['buy_price'] + user_data['buy_delivery'] + user_data['buy_extra']
            cash = total - user_data['buy_debt']
            p = {
                'id': int(datetime.now().timestamp() * 1000), 'date': datetime.now().strftime('%Y/%m/%d'),
                'model': user_data['buy_model'], 'buy_price': user_data['buy_price'],
                'delivery_cost': user_data['buy_delivery'], 'extra_cost': user_data['buy_extra'],
                'total_cost': total, 'purchase_debt': user_data['buy_debt'],
                'remaining_debt': user_data['buy_debt'], 'cash_paid': cash, 'notes': notes, 'sold': False
            }
            bot_accounting.data['purchases'].append(p)
            bot_accounting.data['transactions'].insert(0, {
                'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'خرید', 'model': user_data['buy_model'], 'amount': -cash,
                'debt': user_data['buy_debt'], 'profit': 0, 'description': f"خرید {user_data['buy_model']}"
            })
            bot_accounting.save_data()
            await update.message.reply_text(f"✅ خرید ثبت شد.\n💰 {format_price(total)} ت",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("🏠 منو", callback_data='main_menu')]]))
            user_data.clear()
        return

    # فروش جدید
    if action == 'new_sell':
        step = user_data.get('step')
        if step == 'waiting_sell_price':
            try:
                user_data['sell_price'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_sell_debt'
                await update.message.reply_text("⚠️ بدهی مشتری (0):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_sell_debt':
            try:
                debt = int(text.replace(',', ''))
                pid = user_data.get('sell_purchase_id')
                p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
                if debt > user_data['sell_price']:
                    await update.message.reply_text("❌ بدهی بیشتر از فروش!")
                    return
                user_data['sell_debt'] = debt
                user_data['step'] = 'waiting_sell_customer'
                await update.message.reply_text("👤 نام مشتری (یا -):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_sell_customer':
            user_data['sell_customer'] = text if text != '-' else ''
            user_data['step'] = 'waiting_sell_phone'
            await update.message.reply_text("📞 تلفن (یا -):")
        elif step == 'waiting_sell_phone':
            user_data['sell_phone'] = text if text != '-' else ''
            user_data['step'] = 'waiting_sell_notes'
            await update.message.reply_text("📝 توضیحات (یا -):")
        elif step == 'waiting_sell_notes':
            notes = text if text != '-' else ''
            pid = user_data.get('sell_purchase_id')
            p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
            profit = user_data['sell_price'] - p['total_cost']
            cash = user_data['sell_price'] - user_data['sell_debt']
            s = {
                'id': int(datetime.now().timestamp() * 1000), 'date': datetime.now().strftime('%Y/%m/%d'),
                'purchase_id': pid, 'model': p['model'], 'purchase_price': p['total_cost'],
                'sell_price': user_data['sell_price'], 'debt': user_data['sell_debt'],
                'remaining_debt': user_data['sell_debt'], 'profit': profit, 'cash_received': cash,
                'customer_name': user_data['sell_customer'], 'customer_phone': user_data['sell_phone'],
                'notes': notes
            }
            bot_accounting.data['sales'].append(s)
            p['sold'] = True
            bot_accounting.data['transactions'].insert(0, {
                'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'فروش', 'model': p['model'], 'amount': cash,
                'debt': user_data['sell_debt'], 'profit': profit,
                'description': f"فروش به {user_data['sell_customer'] or 'مشتری'}"
            })
            bot_accounting.save_data()
            emoji = "📈" if profit >= 0 else "📉"
            await update.message.reply_text(f"✅ فروش ثبت شد.\n{emoji} سود: {format_price(profit)} ت",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("🏠 منو", callback_data='main_menu')]]))
            user_data.clear()
        return

    # هزینه جدید
    if action == 'new_cost':
        step = user_data.get('step')
        if step == 'waiting_cost_title':
            if text == '-':
                user_data.clear();
                await update.message.reply_text("❌ لغو شد.");
                return
            user_data['cost_title'] = text
            user_data['step'] = 'waiting_cost_amount'
            await update.message.reply_text("💰 مبلغ را وارد کن:")
        elif step == 'waiting_cost_amount':
            try:
                user_data['cost_amount'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_cost_desc'
                await update.message.reply_text("📝 توضیحات (یا -):")
            except:
                await update.message.reply_text("❌ عدد معتبر وارد کن.")
        elif step == 'waiting_cost_desc':
            desc = text if text != '-' else ''
            c = {
                'id': int(datetime.now().timestamp() * 1000), 'date': datetime.now().strftime('%Y/%m/%d'),
                'title': user_data['cost_title'], 'amount': user_data['cost_amount'], 'description': desc
            }
            bot_accounting.data['costs'].append(c)
            bot_accounting.data['transactions'].insert(0, {
                'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'هزینه', 'model': user_data['cost_title'], 'amount': -user_data['cost_amount'],
                'debt': 0, 'profit': 0, 'description': desc or user_data['cost_title']
            })
            bot_accounting.save_data()
            await update.message.reply_text(f"✅ هزینه ثبت شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("💸 هزینه‌ها", callback_data='costs_menu')]]))
            user_data.clear()
        return

    # ویرایش خرید
    if action == 'edit_purchase':
        step = user_data.get('step')
        if step == 'waiting_buy_model':
            if text != '-': user_data['buy_model'] = text
            user_data['step'] = 'waiting_buy_price'
            await update.message.reply_text("💰 قیمت جدید (یا -):")
        elif step == 'waiting_buy_price':
            if text != '-':
                try:
                    user_data['buy_price'] = int(text.replace(',', ''))
                except:
                    await update.message.reply_text("❌ عدد معتبر."); return
            user_data['step'] = 'waiting_buy_delivery'
            await update.message.reply_text("🚚 پیک جدید (یا -):")
        elif step == 'waiting_buy_delivery':
            if text != '-':
                try:
                    user_data['buy_delivery'] = int(text.replace(',', ''))
                except:
                    await update.message.reply_text("❌ عدد معتبر."); return
            user_data['step'] = 'waiting_buy_extra'
            await update.message.reply_text("💰 جانبی جدید (یا -):")
        elif step == 'waiting_buy_extra':
            if text != '-':
                try:
                    user_data['buy_extra'] = int(text.replace(',', ''))
                except:
                    await update.message.reply_text("❌ عدد معتبر."); return
            user_data['step'] = 'waiting_buy_debt'
            await update.message.reply_text("⚠️ بدهی جدید (یا -):")
        elif step == 'waiting_buy_debt':
            if text != '-':
                try:
                    user_data['buy_debt'] = int(text.replace(',', ''))
                except:
                    await update.message.reply_text("❌ عدد معتبر."); return
            user_data['step'] = 'waiting_buy_notes'
            await update.message.reply_text("📝 توضیحات جدید (یا -):")
        elif step == 'waiting_buy_notes':
            pid = user_data['edit_purchase_id']
            p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
            total = user_data['buy_price'] + user_data['buy_delivery'] + user_data['buy_extra']
            cash = total - user_data['buy_debt']
            p.update({
                'model': user_data['buy_model'], 'buy_price': user_data['buy_price'],
                'delivery_cost': user_data['buy_delivery'], 'extra_cost': user_data['buy_extra'],
                'total_cost': total, 'purchase_debt': user_data['buy_debt'],
                'remaining_debt': user_data['buy_debt'], 'cash_paid': cash,
                'notes': text if text != '-' else user_data.get('original_notes', '')
            })
            bot_accounting.save_data()
            await update.message.reply_text("✅ ویرایش شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("📋 لیست", callback_data='list_buys_menu')]]))
            user_data.clear()
        return

    # ویرایش فروش
    if action == 'edit_sale':
        step = user_data.get('step')
        if step == 'waiting_sell_price':
            if text != '-':
                try:
                    user_data['sell_price'] = int(text.replace(',', ''))
                except:
                    await update.message.reply_text("❌ عدد معتبر."); return
            user_data['step'] = 'waiting_sell_debt'
            await update.message.reply_text("⚠️ بدهی جدید (یا -):")
        elif step == 'waiting_sell_debt':
            if text != '-':
                try:
                    user_data['sell_debt'] = int(text.replace(',', ''))
                except:
                    await update.message.reply_text("❌ عدد معتبر."); return
            user_data['step'] = 'waiting_sell_customer'
            await update.message.reply_text("👤 نام مشتری جدید (یا -):")
        elif step == 'waiting_sell_customer':
            if text != '-': user_data['sell_customer'] = text
            user_data['step'] = 'waiting_sell_phone'
            await update.message.reply_text("📞 تلفن جدید (یا -):")
        elif step == 'waiting_sell_phone':
            if text != '-': user_data['sell_phone'] = text
            user_data['step'] = 'waiting_sell_notes'
            await update.message.reply_text("📝 توضیحات جدید (یا -):")
        elif step == 'waiting_sell_notes':
            sid = user_data['edit_sale_id']
            s = next((s for s in bot_accounting.data['sales'] if s['id'] == sid))
            p = next((p for p in bot_accounting.data['purchases'] if p['id'] == s['purchase_id']))
            profit = user_data['sell_price'] - p['total_cost']
            cash = user_data['sell_price'] - user_data['sell_debt']
            s.update({
                'sell_price': user_data['sell_price'], 'debt': user_data['sell_debt'],
                'remaining_debt': user_data['sell_debt'], 'profit': profit, 'cash_received': cash,
                'customer_name': user_data['sell_customer'], 'customer_phone': user_data['sell_phone'],
                'notes': text if text != '-' else user_data.get('original_notes', '')
            })
            bot_accounting.save_data()
            await update.message.reply_text("✅ ویرایش شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("📋 لیست", callback_data='list_sales_menu')]]))
            user_data.clear()
        return

    # پرداخت بدهی
    if action == 'pay_sale_debt':
        step = user_data.get('step')
        if step == 'waiting_payment_amount':
            try:
                amt = int(text.replace(',', ''))
                sid = user_data['payment_sale_id']
                s = next((s for s in bot_accounting.data['sales'] if s['id'] == sid))
                remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(sid)
                if amt > remaining:
                    await update.message.reply_text(f"❌ حداکثر {format_price(remaining)} ت")
                    return
                user_data['payment_amount'] = amt
                user_data['step'] = 'waiting_payment_notes'
                await update.message.reply_text("📝 توضیحات (یا -):")
            except:
                await update.message.reply_text("❌ عدد معتبر.")
        elif step == 'waiting_payment_notes':
            notes = text if text != '-' else ''
            sid = user_data['payment_sale_id']
            s = next((s for s in bot_accounting.data['sales'] if s['id'] == sid))
            bot_accounting.data['debt_payments'].append({
                'id': int(datetime.now().timestamp() * 1000), 'sale_id': sid,
                'date': datetime.now().strftime('%Y/%m/%d'), 'amount': user_data['payment_amount'],
                'notes': notes, 'model': s['model'], 'customer_name': s.get('customer_name', '')
            })
            if 'remaining_debt' not in s: s['remaining_debt'] = s['debt']
            s['remaining_debt'] -= user_data['payment_amount']
            bot_accounting.data['transactions'].insert(0, {
                'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'دریافت بدهی', 'model': s['model'], 'amount': user_data['payment_amount'],
                'debt': 0, 'profit': 0, 'description': f"دریافت از {s.get('customer_name', 'مشتری')}"
            })
            bot_accounting.save_data()
            await update.message.reply_text("✅ دریافت شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("💳 بدهی", callback_data='debt_menu')]]))
            user_data.clear()
        return

    if action == 'pay_purchase_debt':
        step = user_data.get('step')
        if step == 'waiting_purchase_payment_amount':
            try:
                amt = int(text.replace(',', ''))
                pid = user_data['payment_purchase_id']
                p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
                remaining = p.get('remaining_debt',
                                  p.get('purchase_debt', 0)) - bot_accounting.get_total_purchase_payments(pid)
                if amt > remaining:
                    await update.message.reply_text(f"❌ حداکثر {format_price(remaining)} ت")
                    return
                user_data['purchase_payment_amount'] = amt
                user_data['step'] = 'waiting_purchase_payment_notes'
                await update.message.reply_text("📝 توضیحات (یا -):")
            except:
                await update.message.reply_text("❌ عدد معتبر.")
        elif step == 'waiting_purchase_payment_notes':
            notes = text if text != '-' else ''
            pid = user_data['payment_purchase_id']
            p = next((p for p in bot_accounting.data['purchases'] if p['id'] == pid))
            bot_accounting.data['purchase_debt_payments'].append({
                'id': int(datetime.now().timestamp() * 1000), 'purchase_id': pid,
                'date': datetime.now().strftime('%Y/%m/%d'), 'amount': user_data['purchase_payment_amount'],
                'notes': notes, 'model': p['model']
            })
            if 'remaining_debt' not in p: p['remaining_debt'] = p.get('purchase_debt', 0)
            p['remaining_debt'] -= user_data['purchase_payment_amount']
            bot_accounting.data['transactions'].insert(0, {
                'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'پرداخت بدهی خرید', 'model': p['model'], 'amount': -user_data['purchase_payment_amount'],
                'debt': 0, 'profit': 0, 'description': f"پرداخت بدهی {p['model']}"
            })
            bot_accounting.save_data()
            await update.message.reply_text("✅ پرداخت شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("💳 بدهی", callback_data='debt_menu')]]))
            user_data.clear()
        return

    # تراکنش شریک
    if action == 'partner_transaction':
        step = user_data.get('step')
        if not step:
            try:
                opt = int(text)
                types = {1: 'cash_withdraw', 2: 'cash_deposit', 3: 'personal_expense', 4: 'company_asset_use'}
                if opt in types:
                    user_data['partner_type'] = types[opt]
                    user_data['step'] = 'waiting_partner_amount'
                    await update.message.reply_text("💰 مبلغ را وارد کن:")
                else:
                    await update.message.reply_text("❌ 1-4 را انتخاب کن.")
            except:
                await update.message.reply_text("❌ عدد وارد کن.")
        elif step == 'waiting_partner_amount':
            try:
                user_data['partner_amount'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_partner_desc'
                await update.message.reply_text("📝 شرح:")
            except:
                await update.message.reply_text("❌ عدد معتبر.")
        elif step == 'waiting_partner_desc':
            partner = user_data['partner']
            ttype = user_data['partner_type']
            amt = user_data['partner_amount']
            desc = text
            trans = {
                'id': int(datetime.now().timestamp() * 1000), 'partner': partner,
                'type': ttype, 'amount': amt, 'date': datetime.now().strftime('%Y/%m/%d'), 'description': desc
            }
            bot_accounting.data['partner_transactions'].append(trans)
            if ttype == 'cash_withdraw':
                bot_accounting.data['transactions'].insert(0, {
                    'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                    'type': 'برداشت شریک', 'model': 'رضا' if partner == 'reza' else 'میلاد',
                    'amount': -amt, 'debt': 0, 'profit': 0, 'description': desc
                })
            elif ttype == 'cash_deposit':
                bot_accounting.data['transactions'].insert(0, {
                    'id': int(datetime.now().timestamp() * 1000) + 1, 'date': datetime.now().strftime('%Y/%m/%d'),
                    'type': 'واریز شریک', 'model': 'رضا' if partner == 'reza' else 'میلاد',
                    'amount': amt, 'debt': 0, 'profit': 0, 'description': desc
                })
            elif ttype == 'personal_expense':
                bot_accounting.data['costs'].append({
                    'id': int(datetime.now().timestamp() * 1000) + 2, 'date': datetime.now().strftime('%Y/%m/%d'),
                    'title': f"هزینه شخصی {partner}", 'amount': amt, 'description': desc
                })
                bot_accounting.data['transactions'].insert(0, {
                    'id': int(datetime.now().timestamp() * 1000) + 3, 'date': datetime.now().strftime('%Y/%m/%d'),
                    'type': 'هزینه', 'model': f"هزینه شخصی {partner}",
                    'amount': -amt, 'debt': 0, 'profit': 0, 'description': desc
                })
            bot_accounting.save_data()
            name = "رضا" if partner == 'reza' else "میلاد"
            await update.message.reply_text(f"✅ تراکنش {name} ثبت شد.",
                                            reply_markup=InlineKeyboardMarkup(
                                                [[InlineKeyboardButton("👥 شرکا", callback_data='partner_menu')]]))
            user_data.clear()
        return

    # بازیابی
    if action == 'full_restore' and update.message.document:
        file = await update.message.document.get_file()
        fn = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        await file.download_to_drive(fn)
        try:
            with open(fn, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if all(k in data for k in ['purchases', 'sales', 'costs', 'transactions', 'partner_transactions']):
                bot_accounting.data = data
                bot_accounting.save_data()
                await update.message.reply_text("✅ بازیابی شد.",
                                                reply_markup=InlineKeyboardMarkup(
                                                    [[InlineKeyboardButton("💾 پشتیبان", callback_data='backup_menu')]]))
            else:
                await update.message.reply_text("❌ فرمت نامعتبر.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
        finally:
            if os.path.exists(fn): os.remove(fn)
            user_data.clear()
        return

    if action == 'inventory_restore' and update.message.document:
        file = await update.message.document.get_file()
        fn = f"restore_inv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        await file.download_to_drive(fn)
        try:
            with open(fn, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('type') == 'inventory':
                count = 0
                for item in data.get('items', []):
                    new = item.copy()
                    new['id'] = int(datetime.now().timestamp() * 1000) + count
                    new['sold'] = False
                    bot_accounting.data['purchases'].append(new)
                    count += 1
                bot_accounting.save_data()
                await update.message.reply_text(f"✅ {count} قلم اضافه شد.",
                                                reply_markup=InlineKeyboardMarkup(
                                                    [[InlineKeyboardButton("💾 پشتیبان", callback_data='backup_menu')]]))
            else:
                await update.message.reply_text("❌ فرمت نامعتبر.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
        finally:
            if os.path.exists(fn): os.remove(fn)
            user_data.clear()
        return

    await update.message.reply_text("❌ عملیات نامعتبر.")


# ==================== توابع کمکی ====================

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ لغو شد.", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 منو", callback_data='main_menu')]]))


# ==================== تابع اصلی ====================

def main():
    try:
        print("🤖 ربات در حال راه‌اندازی...")
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        app = Application.builder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setmenu", set_menu))
        app.add_handler(CommandHandler("cancel", cancel_command))
        app.add_handler(CommandHandler("dashboard", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("sell", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("buy", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("list_sales", list_sales_command))
        app.add_handler(CommandHandler("list_buys", list_buys_command))
        app.add_handler(CommandHandler("list_costs", list_costs_command))
        app.add_handler(CommandHandler("costs", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("partners", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("debts", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("backup", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("settings", lambda u, c: button_handler(u, c) if u.message else None))
        app.add_handler(CommandHandler("help", lambda u, c: button_handler(u, c) if u.message else None))

        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_message))

        print("✅ ربات آماده است!")
        app.run_polling(allowed_updates=['message', 'callback_query'])
    except Exception as e:
        print(f"❌ خطا: {e}")


if __name__ == '__main__':
    main()