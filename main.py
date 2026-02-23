import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime
import threading
import time

# تنظیمات logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات خودت رو اینجا قرار بده
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
        """محاسبه بدهکار و بستانکاری شرکا"""
        total_profit = self.calculate_total_profit()
        total_costs = sum(c['amount'] for c in self.data['costs'])

        # محاسبه سهم هر شریک (۵۰ - ۵۰)
        partner_share = (total_profit - total_costs) / 2

        # محاسبه تراکنش‌های رضا
        reza_transactions = 0
        for t in self.data['partner_transactions']:
            if t['partner'] == 'reza':
                if t['type'] == 'cash_withdraw':
                    reza_transactions -= t['amount']
                elif t['type'] == 'cash_deposit':
                    reza_transactions += t['amount']
                elif t['type'] == 'personal_expense':
                    reza_transactions += t['amount']
                elif t['type'] == 'company_asset_use':
                    reza_transactions -= t['amount']

        # محاسبه تراکنش‌های میلاد
        milad_transactions = 0
        for t in self.data['partner_transactions']:
            if t['partner'] == 'milad':
                if t['type'] == 'cash_withdraw':
                    milad_transactions -= t['amount']
                elif t['type'] == 'cash_deposit':
                    milad_transactions += t['amount']
                elif t['type'] == 'personal_expense':
                    milad_transactions += t['amount']
                elif t['type'] == 'company_asset_use':
                    milad_transactions -= t['amount']

        # مانده نهایی هر شریک
        reza_balance = partner_share + reza_transactions
        milad_balance = partner_share + milad_transactions

        return reza_balance, milad_balance

    def get_statistics(self):
        balance = self.calculate_balance()
        inv_count, inv_value = self.calculate_inventory()
        total_profit = self.calculate_total_profit()
        sales_debt, purchase_debt = self.calculate_remaining_debts()
        total_costs = sum(c['amount'] for c in self.data['costs'])

        # محاسبه مانده شرکا
        reza_balance, milad_balance = self.calculate_partner_balances()

        # تعیین وضعیت بدهکار/بستانکار
        reza_status = "✅ بستانکار" if reza_balance >= 0 else "❌ بدهکار"
        milad_status = "✅ بستانکار" if milad_balance >= 0 else "❌ بدهکار"

        stats = f"💰 **موجودی حساب:** {format_price(balance)} تومان\n"
        stats += f"📦 **موجودی انبار:** {inv_count} عدد\n"
        stats += f"💎 **ارزش انبار:** {format_price(inv_value)} تومان\n"
        stats += f"📊 **مجموع سودها:** {format_price(total_profit)} تومان\n"
        stats += f"⚠️ **بدهی فروش:** {format_price(sales_debt)} تومان\n"
        stats += f"⚠️ **بدهی خرید:** {format_price(purchase_debt)} تومان\n"
        stats += f"💸 **هزینه‌های جاری:** {format_price(total_costs)} تومان\n\n"

        stats += f"👤 **رضا:** {format_price(abs(reza_balance))} تومان ({reza_status})\n"
        stats += f"👤 **میلاد:** {format_price(abs(milad_balance))} تومان ({milad_status})\n\n"

        stats += f"📝 **تعداد خریدها:** {len(self.data['purchases'])}\n"
        stats += f"📝 **تعداد فروش‌ها:** {len(self.data['sales'])}"

        return stats


# نمونه از کلاس حسابداری
bot_accounting = AccountingBot()


# ==================== توابع هندلر ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی"""
    keyboard = [
        [InlineKeyboardButton("📊 داشبورد", callback_data='dashboard')],
        [InlineKeyboardButton("🛒 ثبت خرید", callback_data='buy_menu'),
         InlineKeyboardButton("💰 ثبت فروش", callback_data='sell_menu')],
        [InlineKeyboardButton("💸 هزینه‌های جاری", callback_data='costs_menu'),
         InlineKeyboardButton("📋 لیست خریدها", callback_data='list_buys_menu')],
        [InlineKeyboardButton("📋 لیست فروش‌ها", callback_data='list_sales_menu'),
         InlineKeyboardButton("📜 تراکنش‌ها", callback_data='transactions')],
        [InlineKeyboardButton("👥 تراکنش شرکا", callback_data='partner_menu'),
         InlineKeyboardButton("💰 وضعیت شرکا", callback_data='partner_balance_menu')],
        [InlineKeyboardButton("💳 مدیریت بدهی", callback_data='debt_menu'),
         InlineKeyboardButton("💰 سرمایه اولیه", callback_data='set_initial_capital')],
        [InlineKeyboardButton("💾 پشتیبان انبار", callback_data='backup_menu'),
         InlineKeyboardButton("🔄 بازیابی انبار", callback_data='restore_menu')],
        [InlineKeyboardButton("❓ راهنما", callback_data='help'),
         InlineKeyboardButton("🧹 پاک کردن همه", callback_data='clear_all')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = "🎯 **به ربات حسابداری خرید و فروش گوشی خوش آمدید**\n\n"
    welcome_text += "از منوی زیر انتخاب کنید یا از دستورات منوی پایین استفاده کنید:"

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌ها"""
    query = update.callback_query
    await query.answer()

    if query.data == 'dashboard':
        stats = bot_accounting.get_statistics()
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📊 **داشبورد حسابداری**\n\n{stats}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("📊 داشبورد", callback_data='dashboard')],
            [InlineKeyboardButton("🛒 ثبت خرید", callback_data='buy_menu'),
             InlineKeyboardButton("💰 ثبت فروش", callback_data='sell_menu')],
            [InlineKeyboardButton("💸 هزینه‌های جاری", callback_data='costs_menu'),
             InlineKeyboardButton("📋 لیست خریدها", callback_data='list_buys_menu')],
            [InlineKeyboardButton("📋 لیست فروش‌ها", callback_data='list_sales_menu'),
             InlineKeyboardButton("📜 تراکنش‌ها", callback_data='transactions')],
            [InlineKeyboardButton("👥 تراکنش شرکا", callback_data='partner_menu'),
             InlineKeyboardButton("💰 وضعیت شرکا", callback_data='partner_balance_menu')],
            [InlineKeyboardButton("💳 مدیریت بدهی", callback_data='debt_menu'),
             InlineKeyboardButton("💰 سرمایه اولیه", callback_data='set_initial_capital')],
            [InlineKeyboardButton("💾 پشتیبان انبار", callback_data='backup_menu'),
             InlineKeyboardButton("🔄 بازیابی انبار", callback_data='restore_menu')],
            [InlineKeyboardButton("❓ راهنما", callback_data='help'),
             InlineKeyboardButton("🧹 پاک کردن همه", callback_data='clear_all')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 **منوی اصلی**\n\nلطفاً یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'buy_menu':
        context.user_data['action'] = 'new_buy'
        context.user_data['step'] = 'waiting_buy_model'
        await query.edit_message_text(
            "📱 **ثبت خرید جدید**\n\n"
            "لطفاً مدل گوشی رو وارد کن:\n"
            "(مثال: آیفون 13)\n\n"
            "💡 برای انصراف در هر مرحله /cancel رو بزن",
            parse_mode='Markdown'
        )

    elif query.data == 'sell_menu':
        available = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]
        if not available:
            await query.edit_message_text(
                "❌ هیچ گوشی برای فروش موجود نیست!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        text = "💰 **ثبت فروش جدید**\n\nلطفاً مدل گوشی رو انتخاب کن:\n\n"
        keyboard = []
        for i, p in enumerate(available[-10:], 1):
            keyboard.append([InlineKeyboardButton(
                f"{i}. {p['model']} - {format_price(p['total_cost'])} تومان",
                callback_data=f"sell_select_{p['id']}"
            )])
        keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    # اینجا بقیه هندلرهای دکمه‌ها ادامه داره...
    # برای خلاصه‌سازی، بقیه هندلرها رو حذف کردم ولی توی فایل اصلی باید باشن


# ==================== توابع کمکی ====================

async def set_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم منوی دائمی ربات"""
    commands = [
        BotCommand("start", "🏠 منوی اصلی"),
        BotCommand("dashboard", "📊 داشبورد"),
        BotCommand("buy", "🛒 ثبت خرید"),
        BotCommand("sell", "💰 ثبت فروش"),
        BotCommand("costs", "💸 هزینه‌ها"),
        BotCommand("list_buys", "📋 لیست خریدها"),
        BotCommand("list_sales", "📋 لیست فروش‌ها"),
        BotCommand("transactions", "📜 تراکنش‌ها"),
        BotCommand("partners", "👥 شرکا"),
        BotCommand("partner_balance", "💰 وضعیت شرکا"),
        BotCommand("debts", "💳 بدهی‌ها"),
        BotCommand("backup", "💾 پشتیبان"),
        BotCommand("restore", "🔄 بازیابی"),
        BotCommand("capital", "💰 سرمایه اولیه"),
        BotCommand("cancel", "❌ لغو"),
        BotCommand("help", "❓ راهنما")
    ]

    await context.bot.set_my_commands(commands)
    await update.message.reply_text("✅ منوی ربات با موفقیت تنظیم شد!")


async def capital_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت سرمایه اولیه"""
    context.user_data['action'] = 'set_capital'
    await update.message.reply_text(
        "💰 **ثبت سرمایه اولیه**\n\n"
        "لطفاً مبلغ سرمایه اولیه رو به تومان وارد کن:\n"
        "(مثال: 10000000)",
        parse_mode='Markdown'
    )


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش داشبورد"""
    stats = bot_accounting.get_statistics()
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📊 **داشبورد حسابداری**\n\n{stats}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت خرید جدید"""
    context.user_data['action'] = 'new_buy'
    context.user_data['step'] = 'waiting_buy_model'
    await update.message.reply_text(
        "📱 **ثبت خرید جدید**\n\n"
        "لطفاً مدل گوشی رو وارد کن:\n"
        "(مثال: آیفون 13)\n\n"
        "💡 برای انصراف در هر مرحله /cancel رو بزن",
        parse_mode='Markdown'
    )


async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت فروش جدید"""
    available = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]
    if not available:
        await update.message.reply_text(
            "❌ هیچ گوشی برای فروش موجود نیست!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "💰 **ثبت فروش جدید**\n\nلطفاً مدل گوشی رو انتخاب کن:\n\n"
    keyboard = []
    for i, p in enumerate(available[-10:], 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {p['model']} - {format_price(p['total_cost'])} تومان",
            callback_data=f"sell_select_{p['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def costs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت هزینه جدید"""
    context.user_data['action'] = 'new_cost'
    context.user_data['step'] = 'waiting_cost_title'
    await update.message.reply_text(
        "📝 **ثبت هزینه جدید**\n\n"
        "لطفاً عنوان هزینه رو وارد کن:\n"
        "(مثال: اجاره مغازه، قبض برق)\n\n"
        "💡 برای انصراف در هر مرحله /cancel رو بزن",
        parse_mode='Markdown'
    )


async def list_buys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست خریدها"""
    if not bot_accounting.data['purchases']:
        await update.message.reply_text(
            "❌ هیچ خریدی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "📋 **لیست خریدها:**\n\n"
    keyboard = []

    for i, p in enumerate(bot_accounting.data['purchases'][-20:], 1):
        status = "✅ فروخته شده" if p.get('sold') else "🟢 در انبار"
        btn_text = f"{i}. {p['model']} - {format_price(p['total_cost'])} تومان ({status})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_purchase_{p['id']}")])

    keyboard.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def list_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست فروش‌ها"""
    if not bot_accounting.data['sales']:
        await update.message.reply_text(
            "❌ هیچ فروشی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "📋 **لیست فروش‌ها:**\n\n"
    keyboard = []

    for i, s in enumerate(bot_accounting.data['sales'][-20:], 1):
        profit_emoji = "📈" if s.get('profit', 0) >= 0 else "📉"
        btn_text = f"{i}. {s['model']} - {format_price(s['sell_price'])} تومان {profit_emoji}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_sale_{s['id']}")])

    keyboard.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش تراکنش‌ها"""
    if not bot_accounting.data['transactions']:
        await update.message.reply_text(
            "❌ هیچ تراکنشی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "📜 **آخرین تراکنش‌ها:**\n\n"
    for i, t in enumerate(bot_accounting.data['transactions'][-15:], 1):
        amount = t['amount']
        amount_emoji = "💰" if amount > 0 else "💸"
        text += f"{i}. {amount_emoji} {t['type']} - {t['date']}\n"
        text += f"   {t['model']}\n"
        text += f"   مبلغ: {format_price(abs(amount))} تومان\n"
        if t.get('profit'):
            text += f"   سود: {format_price(t['profit'])} تومان\n"
        text += f"   📝 {t['description'][:50]}\n\n"

    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
        ]])
    )


async def partners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی شرکا"""
    keyboard = [
        [InlineKeyboardButton("👤 تراکنش رضا", callback_data='partner_reza')],
        [InlineKeyboardButton("👤 تراکنش میلاد", callback_data='partner_milad')],
        [InlineKeyboardButton("💰 وضعیت بدهکار/بستانکار", callback_data='partner_balance_menu')],
        [InlineKeyboardButton("📜 لیست تراکنش‌ها", callback_data='list_partner')],
        [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👥 **مدیریت تراکنش شرکا**\n\nانتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def partner_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش وضعیت شرکا"""
    reza_balance, milad_balance = bot_accounting.calculate_partner_balances()

    text = "👥 **وضعیت بدهکار و بستانکاری شرکا:**\n\n"
    text += f"**رضا:** {format_price(abs(reza_balance))} تومان ({'✅ بستانکار' if reza_balance >= 0 else '❌ بدهکار'})\n"
    text += f"**میلاد:** {format_price(abs(milad_balance))} تومان ({'✅ بستانکار' if milad_balance >= 0 else '❌ بدهکار'})\n\n"
    text += "📌 **راهنما:**\n"
    text += "• ✅ **بستانکار:** شرکت به شریک بدهکار است\n"
    text += "• ❌ **بدهکار:** شریک به شرکت بدهکار است"

    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def debts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی بدهی‌ها"""
    keyboard = [
        [InlineKeyboardButton("💳 پرداخت بدهی فروش", callback_data='pay_sale_debt')],
        [InlineKeyboardButton("💳 پرداخت بدهی خرید", callback_data='pay_purchase_debt')],
        [InlineKeyboardButton("📊 وضعیت بدهی‌ها", callback_data='debt_status')],
        [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💳 **مدیریت بدهی‌ها**\n\nانتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پشتیبان‌گیری از انبار"""
    inventory = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]

    if inventory:
        await update.message.reply_text(
            f"💾 **پشتیبان‌گیری انبار**\n\n"
            f"تعداد اقلام موجود در انبار: {len(inventory)}\n\n"
            f"در حال آماده‌سازی فایل..."
        )

        backup_data = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'inventory_backup',
            'items': inventory
        }

        filename = f"inventory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=filename,
                caption=f"📦 پشتیبان انبار - {len(inventory)} قلم"
            )

        os.remove(filename)

        await update.message.reply_text(
            "✅ فایل پشتیبان با موفقیت ارسال شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
    else:
        await update.message.reply_text(
            "❌ انبار خالی است! هیچ قلمی برای پشتیبان‌گیری وجود ندارد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )


async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازیابی انبار از فایل"""
    context.user_data['action'] = 'restore_inventory'
    await update.message.reply_text(
        "🔄 **بازیابی انبار**\n\n"
        "لطفاً فایل پشتیبان JSON رو ارسال کن.\n\n"
        "⚠️ توجه: اقلام موجود در فایل به انبار اضافه می‌شوند.",
        parse_mode='Markdown'
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو عملیات جاری"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ عملیات لغو شد.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
        ]])
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش راهنما"""
    help_text = """
❓ **راهنمای استفاده از ربات**

📌 **دستورات موجود:**
/start - منوی اصلی
/dashboard - داشبورد مالی
/buy - ثبت خرید جدید
/sell - ثبت فروش جدید
/costs - ثبت هزینه جاری
/list_buys - لیست خریدها
/list_sales - لیست فروش‌ها
/transactions - تراکنش‌ها
/partners - منوی شرکا
/partner_balance - وضعیت شرکا
/debts - مدیریت بدهی‌ها
/backup - پشتیبان‌گیری از انبار
/restore - بازیابی انبار
/capital - ثبت سرمایه اولیه
/cancel - لغو عملیات جاری
/help - راهنما

📝 **نکات مهم:**
• برای وارد کردن مبلغ، عدد بدون کاما وارد کن
• برای رد کردن هر مرحله از - استفاده کن
• همه اطلاعات در فایل ذخیره میشه
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


# ==================== هندلر پیام‌های متنی ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیام‌های متنی"""
    text = update.message.text
    user_data = context.user_data

    # اینجا منطق پردازش پیام‌ها بر اساس user_data['action'] و user_data['step']
    # برای خلاصه‌سازی، این بخش رو حذف کردم
    await update.message.reply_text("پیام دریافت شد. برای شروع از منوی اصلی استفاده کنید.")


# ==================== تابع اصلی اجرا ====================

def run_bot():
    """اجرای واقعی ربات - این تابع در thread جداگانه اجرا میشه"""
    try:
        print("🤖 ربات حسابداری در حال راه‌اندازی...")

        # ساخت اپلیکیشن
        app = Application.builder().token(TOKEN).build()

        # هندلرهای دستورات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setmenu", set_menu))
        app.add_handler(CommandHandler("dashboard", dashboard_command))
        app.add_handler(CommandHandler("buy", buy_command))
        app.add_handler(CommandHandler("sell", sell_command))
        app.add_handler(CommandHandler("costs", costs_command))
        app.add_handler(CommandHandler("list_buys", list_buys_command))
        app.add_handler(CommandHandler("list_sales", list_sales_command))
        app.add_handler(CommandHandler("transactions", transactions_command))
        app.add_handler(CommandHandler("partners", partners_command))
        app.add_handler(CommandHandler("partner_balance", partner_balance_command))
        app.add_handler(CommandHandler("debts", debts_command))
        app.add_handler(CommandHandler("backup", backup_command))
        app.add_handler(CommandHandler("restore", restore_command))
        app.add_handler(CommandHandler("capital", capital_command))
        app.add_handler(CommandHandler("cancel", cancel_command))
        app.add_handler(CommandHandler("help", help_command))

        # هندلر دکمه‌ها
        app.add_handler(CallbackQueryHandler(button_handler))

        # هندلر پیام‌های متنی
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_message))

        print("✅ ربات با موفقیت شروع به کار کرد!")
        print("📝 برای فعال کردن منوی دائمی، /setmenu رو بفرست")

        # اجرا - بدون allowed_updates اضافی
        app.run_polling()

    except Exception as e:
        print(f"❌ خطا در اجرای ربات: {e}")
        print("🔄 تلاش مجدد بعد از ۵ ثانیه...")
        time.sleep(5)
        run_bot()


def main():
    """تابع اصلی - فقط thread رو شروع می‌کنه"""
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    print("✅ ربات در thread جداگانه شروع به کار کرد")

    # نگه داشتن thread اصلی
    while True:
        time.sleep(60)


if __name__ == '__main__':
    main()