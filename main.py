import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime

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


# ==================== دستورات منوی دائمی ====================

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


async def partner_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش وضعیت بدهکار و بستانکاری شرکا"""
    reza_balance, milad_balance = bot_accounting.calculate_partner_balances()

    # محاسبه جزئیات تراکنش‌ها
    reza_details = []
    milad_details = []

    for t in bot_accounting.data['partner_transactions']:
        type_text = {
            'cash_withdraw': 'برداشت نقدی',
            'cash_deposit': 'واریز نقدی',
            'personal_expense': 'هزینه شخصی',
            'company_asset_use': 'استفاده دارایی',
            'other': 'سایر'
        }.get(t['type'], t['type'])

        if t['partner'] == 'reza':
            reza_details.append(f"   • {t['date']} - {type_text}: {format_price(t['amount'])} تومان")
        else:
            milad_details.append(f"   • {t['date']} - {type_text}: {format_price(t['amount'])} تومان")

    text = "👥 **وضعیت بدهکار و بستانکاری شرکا:**\n\n"

    text += f"**رضا:**\n"
    text += f"مانده حساب: {format_price(abs(reza_balance))} تومان\n"
    text += f"وضعیت: {'✅ بستانکار' if reza_balance >= 0 else '❌ بدهکار'}\n"
    if reza_details:
        text += "آخرین تراکنش‌ها:\n" + "\n".join(reza_details[-3:]) + "\n"
    else:
        text += "تراکنشی ثبت نشده.\n"
    text += "\n"

    text += f"**میلاد:**\n"
    text += f"مانده حساب: {format_price(abs(milad_balance))} تومان\n"
    text += f"وضعیت: {'✅ بستانکار' if milad_balance >= 0 else '❌ بدهکار'}\n"
    if milad_details:
        text += "آخرین تراکنش‌ها:\n" + "\n".join(milad_details[-3:]) + "\n"
    else:
        text += "تراکنشی ثبت نشده.\n"
    text += "\n"

    text += "📌 **راهنما:**\n"
    text += "• ✅ **بستانکار:** شرکت به شریک بدهکار است\n"
    text += "• ❌ **بدهکار:** شریک به شرکت بدهکار است"

    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


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
    """نمایش لیست خریدها با امکان ویرایش و حذف"""
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
        debt = p.get('purchase_debt', 0)
        remaining = p.get('remaining_debt', debt) - bot_accounting.get_total_purchase_payments(p['id'])

        # دکمه برای هر خرید
        btn_text = f"{i}. {p['model']} - {format_price(p['total_cost'])} تومان ({status})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_purchase_{p['id']}")])

    keyboard.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def list_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست فروش‌ها با امکان ویرایش و حذف"""
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

        # دکمه برای هر فروش
        btn_text = f"{i}. {s['model']} - {format_price(s['sell_price'])} تومان {profit_emoji}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_sale_{s['id']}")])

    keyboard.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پشتیبان‌گیری از موجودی انبار"""
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
    """بازیابی موجودی انبار از فایل پشتیبان"""
    context.user_data['action'] = 'restore_inventory'
    await update.message.reply_text(
        "🔄 **بازیابی انبار**\n\n"
        "لطفاً فایل پشتیبان JSON رو ارسال کن.\n\n"
        "⚠️ توجه: اقلام موجود در فایل به انبار اضافه می‌شوند.",
        parse_mode='Markdown'
    )


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
/list_buys - لیست خریدها (با امکان ویرایش)
/list_sales - لیست فروش‌ها (با امکان ویرایش)
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
• برای ویرایش خرید یا فروش، از لیست مربوطه انتخاب کن
• در هر مرحله با /cancel می‌تونی عملیات رو لغو کنی
• برای وارد کردن مبلغ، عدد بدون کاما وارد کن
• برای رد کردن هر مرحله از - استفاده کن
• همه اطلاعات در فایل ذخیره میشه
• قبل از هر کار VPN روشن کن

👥 **وضعیت شرکا:**
• ✅ بستانکار: شرکت به شریک بدهکار است
• ❌ بدهکار: شریک به شرکت بدهکار است

💾 **پشتیبان‌گیری:**
• فقط اقلام موجود در انبار پشتیبان گرفته می‌شود
• فایل JSON برای بازیابی بعدی ذخیره می‌شود
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


# ==================== هندلر استارت ====================

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


# ==================== هندلر دکمه‌ها ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'main_menu':
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

    elif query.data == 'dashboard':
        stats = bot_accounting.get_statistics()
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📊 **داشبورد حسابداری**\n\n{stats}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'partner_balance_menu':
        reza_balance, milad_balance = bot_accounting.calculate_partner_balances()

        text = "👥 **وضعیت بدهکار و بستانکاری شرکا:**\n\n"

        text += f"**رضا:**\n"
        text += f"مانده حساب: {format_price(abs(reza_balance))} تومان\n"
        text += f"وضعیت: {'✅ بستانکار' if reza_balance >= 0 else '❌ بدهکار'}\n\n"

        text += f"**میلاد:**\n"
        text += f"مانده حساب: {format_price(abs(milad_balance))} تومان\n"
        text += f"وضعیت: {'✅ بستانکار' if milad_balance >= 0 else '❌ بدهکار'}\n\n"

        text += "📌 **راهنما:**\n"
        text += "• ✅ **بستانکار:** شرکت به شریک بدهکار است\n"
        text += "• ❌ **بدهکار:** شریک به شرکت بدهکار است"

        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'set_initial_capital':
        context.user_data['action'] = 'set_capital'
        await query.edit_message_text(
            "💰 **ثبت سرمایه اولیه**\n\n"
            "لطفاً مبلغ سرمایه اولیه رو به تومان وارد کن:\n"
            "(مثال: 10000000)\n\n"
            "💡 برای انصراف /cancel رو بزن",
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

    elif query.data.startswith('sell_select_'):
        purchase_id = int(query.data.replace('sell_select_', ''))
        context.user_data['sell_purchase_id'] = purchase_id
        context.user_data['action'] = 'new_sell'
        context.user_data['step'] = 'waiting_sell_price'

        purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)
        if purchase:
            await query.edit_message_text(
                f"📱 **گوشی:** {purchase['model']}\n"
                f"💰 **قیمت خرید:** {format_price(purchase['total_cost'])} تومان\n\n"
                f"لطفاً قیمت فروش رو وارد کن (یا - برای انصراف):",
                parse_mode='Markdown'
            )

    elif query.data == 'costs_menu':
        context.user_data['action'] = 'new_cost'
        context.user_data['step'] = 'waiting_cost_title'
        await query.edit_message_text(
            "📝 **ثبت هزینه جدید**\n\n"
            "لطفاً عنوان هزینه رو وارد کن:\n"
            "(مثال: اجاره مغازه)\n\n"
            "💡 برای انصراف /cancel رو بزن",
            parse_mode='Markdown'
        )

    elif query.data == 'list_buys_menu':
        if not bot_accounting.data['purchases']:
            await query.edit_message_text(
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
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('view_purchase_'):
        purchase_id = int(query.data.replace('view_purchase_', ''))
        purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

        if not purchase:
            await query.edit_message_text("❌ خرید پیدا نشد!")
            return

        remaining_debt = purchase.get('remaining_debt', purchase.get('purchase_debt', 0))
        total_paid = bot_accounting.get_total_purchase_payments(purchase_id)

        text = f"📱 **جزئیات خرید**\n\n"
        text += f"🆔 شناسه: {purchase['id']}\n"
        text += f"📅 تاریخ: {purchase['date']}\n"
        text += f"📱 مدل: {purchase['model']}\n"
        text += f"💰 قیمت خرید: {format_price(purchase['buy_price'])} تومان\n"
        text += f"🚚 پیک: {format_price(purchase.get('delivery_cost', 0))} تومان\n"
        text += f"💎 جانبی: {format_price(purchase.get('extra_cost', 0))} تومان\n"
        text += f"💵 جمع کل: {format_price(purchase['total_cost'])} تومان\n"
        text += f"⚠️ بدهی: {format_price(purchase.get('purchase_debt', 0))} تومان\n"
        text += f"💸 پرداخت شده: {format_price(total_paid)} تومان\n"
        text += f"📊 باقیمانده: {format_price(max(0, remaining_debt - total_paid))} تومان\n"
        text += f"📌 وضعیت: {'✅ فروخته شده' if purchase.get('sold') else '🟢 در انبار'}\n"
        text += f"📝 توضیحات: {purchase.get('notes', '-')}\n"

        keyboard = []
        if not purchase.get('sold'):
            keyboard.append([
                InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_purchase_{purchase_id}"),
                InlineKeyboardButton("❌ حذف", callback_data=f"delete_purchase_{purchase_id}")
            ])
        else:
            keyboard.append([InlineKeyboardButton("❌ حذف", callback_data=f"delete_purchase_{purchase_id}")])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data='list_buys_menu')])
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('edit_purchase_'):
        purchase_id = int(query.data.replace('edit_purchase_', ''))
        purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

        if not purchase:
            await query.edit_message_text("❌ خرید پیدا نشد!")
            return

        if purchase.get('sold'):
            await query.edit_message_text("❌ این گوشی فروخته شده و قابل ویرایش نیست!")
            return

        # ذخیره اطلاعات برای ویرایش
        context.user_data['edit_purchase_id'] = purchase_id
        context.user_data['action'] = 'edit_purchase'
        context.user_data['step'] = 'waiting_buy_model'
        context.user_data['buy_model'] = purchase['model']
        context.user_data['buy_price'] = purchase['buy_price']
        context.user_data['buy_delivery'] = purchase.get('delivery_cost', 0)
        context.user_data['buy_extra'] = purchase.get('extra_cost', 0)
        context.user_data['buy_debt'] = purchase.get('purchase_debt', 0)
        context.user_data['original_notes'] = purchase.get('notes', '')

        await query.edit_message_text(
            f"✏️ **ویرایش خرید**\n\n"
            f"مدل فعلی: {purchase['model']}\n"
            f"لطفاً مدل جدید رو وارد کن (یا - برای保持不变):",
            parse_mode='Markdown'
        )

    elif query.data.startswith('delete_purchase_'):
        purchase_id = int(query.data.replace('delete_purchase_', ''))
        purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

        if purchase and purchase.get('sold'):
            await query.edit_message_text(
                "❌ این گوشی فروخته شده و قابل حذف نیست! ابتدا فروش را حذف کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data='list_buys_menu')
                ]])
            )
            return

        context.user_data['delete_purchase_id'] = purchase_id
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف کن", callback_data='confirm_delete_purchase')],
            [InlineKeyboardButton("❌ خیر، انصراف", callback_data='list_buys_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ **آیا از حذف این خرید مطمئن هستید؟**\nاین عمل غیرقابل بازگشت است.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'confirm_delete_purchase':
        purchase_id = context.user_data.get('delete_purchase_id')
        if purchase_id:
            # حذف خرید
            index = None
            for i, p in enumerate(bot_accounting.data['purchases']):
                if p['id'] == purchase_id:
                    index = i
                    break

            if index is not None:
                # حذف تراکنش‌های مربوطه
                bot_accounting.data['transactions'] = [
                    t for t in bot_accounting.data['transactions']
                    if not (t.get('type') == 'خرید' and t.get('purchase_id') == purchase_id)
                ]
                # حذف پرداخت‌های بدهی مربوطه
                bot_accounting.data['purchase_debt_payments'] = [
                    p for p in bot_accounting.data['purchase_debt_payments']
                    if p['purchase_id'] != purchase_id
                ]
                # حذف خرید
                bot_accounting.data['purchases'].pop(index)
                bot_accounting.save_data()

        context.user_data.pop('delete_purchase_id', None)
        await query.edit_message_text(
            "✅ خرید با موفقیت حذف شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 بازگشت به لیست", callback_data='list_buys_menu')
            ]])
        )

    elif query.data == 'list_sales_menu':
        if not bot_accounting.data['sales']:
            await query.edit_message_text(
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
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('view_sale_'):
        sale_id = int(query.data.replace('view_sale_', ''))
        sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)

        if not sale:
            await query.edit_message_text("❌ فروش پیدا نشد!")
            return

        remaining_debt = sale.get('remaining_debt', sale.get('debt', 0))
        total_paid = bot_accounting.get_total_sale_payments(sale_id)

        text = f"💰 **جزئیات فروش**\n\n"
        text += f"🆔 شناسه: {sale['id']}\n"
        text += f"📅 تاریخ: {sale['date']}\n"
        text += f"📱 مدل: {sale['model']}\n"
        text += f"💰 قیمت خرید: {format_price(sale.get('purchase_price', 0))} تومان\n"
        text += f"💰 قیمت فروش: {format_price(sale['sell_price'])} تومان\n"
        text += f"📊 سود/زیان: {format_price(sale.get('profit', 0))} تومان\n"
        text += f"⚠️ بدهی: {format_price(sale.get('debt', 0))} تومان\n"
        text += f"💸 دریافت شده: {format_price(total_paid)} تومان\n"
        text += f"📊 باقیمانده: {format_price(max(0, remaining_debt - total_paid))} تومان\n"
        text += f"👤 مشتری: {sale.get('customer_name', '-')}\n"
        text += f"📞 تلفن: {sale.get('customer_phone', '-')}\n"
        text += f"📝 توضیحات: {sale.get('notes', '-')}\n"

        keyboard = [
            [InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_sale_{sale_id}"),
             InlineKeyboardButton("❌ حذف", callback_data=f"delete_sale_{sale_id}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data='list_sales_menu')],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('edit_sale_'):
        sale_id = int(query.data.replace('edit_sale_', ''))
        sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)

        if not sale:
            await query.edit_message_text("❌ فروش پیدا نشد!")
            return

        # ذخیره اطلاعات برای ویرایش
        context.user_data['edit_sale_id'] = sale_id
        context.user_data['action'] = 'edit_sale'
        context.user_data['step'] = 'waiting_sell_price'
        context.user_data['sell_price'] = sale['sell_price']
        context.user_data['sell_debt'] = sale.get('debt', 0)
        context.user_data['sell_customer'] = sale.get('customer_name', '')
        context.user_data['sell_phone'] = sale.get('customer_phone', '')
        context.user_data['original_notes'] = sale.get('notes', '')

        await query.edit_message_text(
            f"✏️ **ویرایش فروش**\n\n"
            f"قیمت فروش فعلی: {format_price(sale['sell_price'])} تومان\n"
            f"لطفاً قیمت فروش جدید رو وارد کن (یا - برای保持不变):",
            parse_mode='Markdown'
        )

    elif query.data.startswith('delete_sale_'):
        sale_id = int(query.data.replace('delete_sale_', ''))
        context.user_data['delete_sale_id'] = sale_id
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف کن", callback_data='confirm_delete_sale')],
            [InlineKeyboardButton("❌ خیر، انصراف", callback_data='list_sales_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ **آیا از حذف این فروش مطمئن هستید؟**\nاین عمل غیرقابل بازگشت است.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'confirm_delete_sale':
        sale_id = context.user_data.get('delete_sale_id')
        if sale_id:
            sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)
            if sale:
                # برگردوندن وضعیت خرید به فروش نرفته
                purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == sale['purchase_id']), None)
                if purchase:
                    purchase['sold'] = False

                # حذف فروش
                index = None
                for i, s in enumerate(bot_accounting.data['sales']):
                    if s['id'] == sale_id:
                        index = i
                        break

                if index is not None:
                    bot_accounting.data['sales'].pop(index)

                # حذف تراکنش‌های مربوطه
                bot_accounting.data['transactions'] = [
                    t for t in bot_accounting.data['transactions']
                    if not (t.get('type') == 'فروش' and t.get('sale_id') == sale_id)
                ]
                # حذف پرداخت‌های بدهی مربوطه
                bot_accounting.data['debt_payments'] = [
                    p for p in bot_accounting.data['debt_payments']
                    if p['sale_id'] != sale_id
                ]
                bot_accounting.save_data()

        context.user_data.pop('delete_sale_id', None)
        await query.edit_message_text(
            "✅ فروش با موفقیت حذف شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 بازگشت به لیست", callback_data='list_sales_menu')
            ]])
        )

    elif query.data == 'transactions':
        if not bot_accounting.data['transactions']:
            await query.edit_message_text(
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

        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'partner_menu':
        keyboard = [
            [InlineKeyboardButton("👤 تراکنش رضا", callback_data='partner_reza')],
            [InlineKeyboardButton("👤 تراکنش میلاد", callback_data='partner_milad')],
            [InlineKeyboardButton("💰 وضعیت بدهکار/بستانکار", callback_data='partner_balance_menu')],
            [InlineKeyboardButton("📜 لیست تراکنش‌ها", callback_data='list_partner')],
            [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👥 **مدیریت تراکنش شرکا**\n\nانتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'debt_menu':
        keyboard = [
            [InlineKeyboardButton("💳 پرداخت بدهی فروش", callback_data='pay_sale_debt')],
            [InlineKeyboardButton("💳 پرداخت بدهی خرید", callback_data='pay_purchase_debt')],
            [InlineKeyboardButton("📊 وضعیت بدهی‌ها", callback_data='debt_status')],
            [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💳 **مدیریت بدهی‌ها**\n\nانتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'backup_menu':
        await backup_command(update, context)

    elif query.data == 'restore_menu':
        context.user_data['action'] = 'restore_inventory'
        await query.edit_message_text(
            "🔄 **بازیابی انبار**\n\n"
            "لطفاً فایل پشتیبان JSON رو ارسال کن.\n\n"
            "⚠️ توجه: اقلام موجود در فایل به انبار اضافه می‌شوند.",
            parse_mode='Markdown'
        )

    elif query.data == 'partner_reza' or query.data == 'partner_milad':
        partner = 'reza' if query.data == 'partner_reza' else 'milad'
        context.user_data['partner'] = partner
        context.user_data['action'] = 'partner_transaction'

        keyboard = [
            [InlineKeyboardButton("💸 برداشت نقدی", callback_data='partner_type_cash_withdraw')],
            [InlineKeyboardButton("💰 واریز نقدی", callback_data='partner_type_cash_deposit')],
            [InlineKeyboardButton("🧾 هزینه شخصی", callback_data='partner_type_personal_expense')],
            [InlineKeyboardButton("📱 استفاده دارایی", callback_data='partner_type_company_asset_use')],
            [InlineKeyboardButton("🔄 سایر", callback_data='partner_type_other')],
            [InlineKeyboardButton("🏠 بازگشت", callback_data='partner_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        partner_name = "رضا" if partner == 'reza' else "میلاد"
        await query.edit_message_text(
            f"👤 **تراکنش {partner_name}**\n\nنوع عملیات رو انتخاب کن:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data.startswith('partner_type_'):
        trans_type = query.data.replace('partner_type_', '')
        context.user_data['partner_type'] = trans_type
        await query.edit_message_text(
            "💰 لطفاً مبلغ رو به تومان وارد کن:\n(مثال: 500000)\n\n"
            "💡 برای انصراف /cancel رو بزن",
            parse_mode='Markdown'
        )
        context.user_data['step'] = 'waiting_partner_amount'

    elif query.data == 'list_partner':
        if not bot_accounting.data['partner_transactions']:
            await query.edit_message_text(
                "❌ هیچ تراکنش شرکایی ثبت نشده است.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت", callback_data='partner_menu')
                ]])
            )
            return

        text = "👥 **تراکنش‌های شرکا:**\n\n"
        for i, t in enumerate(bot_accounting.data['partner_transactions'][-20:], 1):
            partner = "رضا" if t['partner'] == 'reza' else "میلاد"
            type_text = {
                'cash_withdraw': 'برداشت نقدی',
                'cash_deposit': 'واریز نقدی',
                'personal_expense': 'هزینه شخصی',
                'company_asset_use': 'استفاده دارایی',
                'other': 'سایر'
            }.get(t['type'], t['type'])
            text += f"{i}. {partner} - {type_text}\n"
            text += f"   📅 {t['date']}\n"
            text += f"   💰 {format_price(t['amount'])} تومان\n"
            text += f"   📝 {t['description'][:50]}\n\n"

        keyboard = [[InlineKeyboardButton("🏠 بازگشت", callback_data='partner_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'pay_sale_debt':
        sales_with_debt = []
        for s in bot_accounting.data['sales']:
            if s.get('debt', 0) > 0:
                remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(s['id'])
                if remaining > 0:
                    sales_with_debt.append((s, remaining))

        if not sales_with_debt:
            await query.edit_message_text(
                "✅ هیچ بدهی فروش معوقی وجود ندارد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت", callback_data='debt_menu')
                ]])
            )
            return

        text = "💳 **پرداخت بدهی فروش**\n\nلطفاً فروش مورد نظر رو انتخاب کن:\n\n"
        keyboard = []
        for i, (s, remaining) in enumerate(sales_with_debt[-10:], 1):
            keyboard.append([InlineKeyboardButton(
                f"{i}. {s['model']} - {format_price(remaining)} تومان",
                callback_data=f"pay_sale_{s['id']}"
            )])
        keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='debt_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('pay_sale_'):
        sale_id = int(query.data.replace('pay_sale_', ''))
        context.user_data['payment_sale_id'] = sale_id
        context.user_data['action'] = 'pay_sale_debt'
        context.user_data['step'] = 'waiting_payment_amount'

        sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)
        if sale:
            remaining = sale.get('remaining_debt', sale['debt']) - bot_accounting.get_total_sale_payments(sale['id'])
            await query.edit_message_text(
                f"💰 **پرداخت بدهی فروش**\n\n"
                f"📱 {sale['model']}\n"
                f"👤 مشتری: {sale.get('customer_name', 'ناشناس')}\n"
                f"⚠️ بدهی باقیمانده: {format_price(max(0, remaining))} تومان\n\n"
                f"لطفاً مبلغ پرداختی رو وارد کن (یا - برای انصراف):",
                parse_mode='Markdown'
            )

    elif query.data == 'pay_purchase_debt':
        purchases_with_debt = []
        for p in bot_accounting.data['purchases']:
            if p.get('purchase_debt', 0) > 0:
                remaining = p.get('remaining_debt', p['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                    p['id'])
                if remaining > 0:
                    purchases_with_debt.append((p, remaining))

        if not purchases_with_debt:
            await query.edit_message_text(
                "✅ هیچ بدهی خرید معوقی وجود ندارد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت", callback_data='debt_menu')
                ]])
            )
            return

        text = "💳 **پرداخت بدهی خرید**\n\nلطفاً خرید مورد نظر رو انتخاب کن:\n\n"
        keyboard = []
        for i, (p, remaining) in enumerate(purchases_with_debt[-10:], 1):
            keyboard.append([InlineKeyboardButton(
                f"{i}. {p['model']} - {format_price(remaining)} تومان",
                callback_data=f"pay_purchase_{p['id']}"
            )])
        keyboard.append([InlineKeyboardButton("🏠 بازگشت", callback_data='debt_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('pay_purchase_'):
        purchase_id = int(query.data.replace('pay_purchase_', ''))
        context.user_data['payment_purchase_id'] = purchase_id
        context.user_data['action'] = 'pay_purchase_debt'
        context.user_data['step'] = 'waiting_purchase_payment_amount'

        purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)
        if purchase:
            remaining = purchase.get('remaining_debt',
                                     purchase['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                purchase['id'])
            await query.edit_message_text(
                f"💰 **پرداخت بدهی خرید**\n\n"
                f"📱 {purchase['model']}\n"
                f"⚠️ بدهی باقیمانده: {format_price(max(0, remaining))} تومان\n\n"
                f"لطفاً مبلغ پرداختی رو وارد کن (یا - برای انصراف):",
                parse_mode='Markdown'
            )

    elif query.data == 'debt_status':
        sales_debt, purchase_debt = bot_accounting.calculate_remaining_debts()
        text = "📊 **وضعیت بدهی‌ها:**\n\n"
        text += f"⚠️ **بدهی فروش:** {format_price(sales_debt)} تومان\n\n"
        text += "🔴 **لیست بدهی‌های فروش:**\n"

        debt_exists = False
        for s in bot_accounting.data['sales']:
            if s.get('debt', 0) > 0:
                remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(s['id'])
                if remaining > 0:
                    debt_exists = True
                    text += f"• {s['model']} - {format_price(remaining)} تومان (مشتری: {s.get('customer_name', 'ناشناس')})\n"

        if not debt_exists:
            text += "هیچ بدهی فروش معوقی وجود ندارد.\n"

        text += f"\n⚠️ **بدهی خرید:** {format_price(purchase_debt)} تومان\n\n"
        text += "🔵 **لیست بدهی‌های خرید:**\n"

        debt_exists = False
        for p in bot_accounting.data['purchases']:
            if p.get('purchase_debt', 0) > 0:
                remaining = p.get('remaining_debt', p['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                    p['id'])
                if remaining > 0:
                    debt_exists = True
                    text += f"• {p['model']} - {format_price(remaining)} تومان\n"

        if not debt_exists:
            text += "هیچ بدهی خرید معوقی وجود ندارد."

        keyboard = [[InlineKeyboardButton("🏠 بازگشت", callback_data='debt_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'help':
        help_text = """
❓ **راهنمای استفاده از ربات**

📌 **دستورات موجود:**
/start - منوی اصلی
/dashboard - داشبورد مالی
/buy - ثبت خرید جدید
/sell - ثبت فروش جدید
/costs - ثبت هزینه جاری
/list_buys - لیست خریدها (با امکان ویرایش)
/list_sales - لیست فروش‌ها (با امکان ویرایش)
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
• برای ویرایش خرید یا فروش، از لیست مربوطه انتخاب کن
• در هر مرحله با /cancel می‌تونی عملیات رو لغو کنی
• برای وارد کردن مبلغ، عدد بدون کاما وارد کن
• برای رد کردن هر مرحله از - استفاده کن
• همه اطلاعات در فایل ذخیره میشه
• قبل از هر کار VPN روشن کن
        """
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'clear_all':
        keyboard = [
            [InlineKeyboardButton("✅ بله، پاک کن", callback_data='confirm_clear')],
            [InlineKeyboardButton("❌ خیر، برگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ **هشدار!**\n\nآیا از پاک کردن همه داده‌ها مطمئنی؟ این عمل غیرقابل بازگشت هست.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'confirm_clear':
        bot_accounting.data = bot_accounting.get_default_data()
        bot_accounting.save_data()
        await query.edit_message_text(
            "✅ همه داده‌ها با موفقیت پاک شدند.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )


# ==================== هندلر دریافت پیام‌های متنی ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_data = context.user_data

    if user_data.get('action') == 'set_capital':
        try:
            amount = int(text.replace(',', ''))

            # ثبت سرمایه اولیه
            bot_accounting.data['initial_capital'] = amount

            # ثبت تراکنش
            transaction = {
                'id': int(datetime.now().timestamp() * 1000),
                'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'سرمایه اولیه',
                'model': '-',
                'amount': amount,
                'debt': 0,
                'profit': 0,
                'description': 'ثبت سرمایه اولیه'
            }
            bot_accounting.data['transactions'].insert(0, transaction)

            bot_accounting.save_data()

            await update.message.reply_text(
                f"✅ **سرمایه اولیه با موفقیت ثبت شد**\n\n"
                f"💰 مبلغ: {format_price(amount)} تومان",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )

            user_data.clear()

        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('action') == 'restore_inventory':
        # دریافت فایل پشتیبان
        if update.message.document:
            file = await update.message.document.get_file()
            filename = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            await file.download_to_drive(filename)

            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    restore_data = json.load(f)

                if restore_data.get('type') == 'inventory_backup' and 'items' in restore_data:
                    count = 0
                    for item in restore_data['items']:
                        # ایجاد آیتم جدید با id جدید
                        new_item = item.copy()
                        new_item['id'] = int(datetime.now().timestamp() * 1000) + count
                        new_item['sold'] = False
                        new_item['date'] = datetime.now().strftime('%Y/%m/%d')
                        bot_accounting.data['purchases'].append(new_item)

                        # ثبت تراکنش
                        transaction = {
                            'id': int(datetime.now().timestamp() * 1000) + count + 1000,
                            'date': datetime.now().strftime('%Y/%m/%d'),
                            'type': 'بازیابی انبار',
                            'model': new_item['model'],
                            'amount': -new_item['total_cost'],
                            'debt': new_item.get('purchase_debt', 0),
                            'profit': 0,
                            'description': f"بازیابی از فایل پشتیبان - {new_item['model']}"
                        }
                        bot_accounting.data['transactions'].insert(0, transaction)
                        count += 1

                    bot_accounting.save_data()

                    await update.message.reply_text(
                        f"✅ {count} قلم با موفقیت به انبار اضافه شد.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                        ]])
                    )
                else:
                    await update.message.reply_text("❌ فرمت فایل نامعتبر است.")

                os.remove(filename)

            except Exception as e:
                await update.message.reply_text(f"❌ خطا در بازیابی: {str(e)}")
                if os.path.exists(filename):
                    os.remove(filename)
        else:
            await update.message.reply_text(
                "❌ لطفاً یک فایل JSON ارسال کن.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )

        user_data.clear()

    elif user_data.get('step') == 'waiting_partner_amount':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            amount = int(text.replace(',', ''))
            user_data['partner_amount'] = amount
            user_data['step'] = 'waiting_partner_desc'

            await update.message.reply_text(
                "📝 لطفاً شرح عملیات رو وارد کن (یا - برای انصراف):"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_partner_desc':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        partner = user_data.get('partner', 'reza')
        trans_type = user_data.get('partner_type', 'other')
        amount = user_data.get('partner_amount', 0)
        desc = text

        # ثبت تراکنش
        transaction = {
            'id': int(datetime.now().timestamp() * 1000),
            'partner': partner,
            'type': trans_type,
            'amount': amount,
            'date': datetime.now().strftime('%Y/%m/%d'),
            'description': desc
        }

        bot_accounting.data['partner_transactions'].append(transaction)

        # ثبت در تراکنش‌های اصلی
        if trans_type == 'cash_withdraw':
            main_trans = {
                'id': int(datetime.now().timestamp() * 1000) + 1,
                'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'برداشت شریک',
                'model': 'رضا' if partner == 'reza' else 'میلاد',
                'amount': -amount,
                'debt': 0,
                'profit': 0,
                'description': desc
            }
            bot_accounting.data['transactions'].insert(0, main_trans)
        elif trans_type == 'cash_deposit':
            main_trans = {
                'id': int(datetime.now().timestamp() * 1000) + 1,
                'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'واریز شریک',
                'model': 'رضا' if partner == 'reza' else 'میلاد',
                'amount': amount,
                'debt': 0,
                'profit': 0,
                'description': desc
            }
            bot_accounting.data['transactions'].insert(0, main_trans)

        bot_accounting.save_data()

        partner_name = "رضا" if partner == 'reza' else "میلاد"
        await update.message.reply_text(
            f"✅ تراکنش {partner_name} با موفقیت ثبت شد.\n"
            f"💰 مبلغ: {format_price(amount)} تومان\n"
            f"📝 شرح: {desc}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )

        user_data.clear()

    elif user_data.get('step') == 'waiting_buy_model':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        if user_data.get('action') == 'edit_purchase':
            if text != '-':
                user_data['buy_model'] = text
        else:
            user_data['buy_model'] = text

        user_data['step'] = 'waiting_buy_price'
        await update.message.reply_text(
            "💰 قیمت خرید رو به تومان وارد کن (یا - برای انصراف):\n(مثال: 15000000)"
        )

    elif user_data.get('step') == 'waiting_buy_price':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            price = int(text.replace(',', ''))
            if user_data.get('action') == 'edit_purchase':
                if text != '-':
                    user_data['buy_price'] = price
            else:
                user_data['buy_price'] = price

            user_data['step'] = 'waiting_buy_delivery'
            await update.message.reply_text(
                "🚚 هزینه پیک رو به تومان وارد کن (یا - برای انصراف):\n(اگه نداره 0 رو وارد کن)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_buy_delivery':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            delivery = int(text.replace(',', ''))
            if user_data.get('action') == 'edit_purchase':
                if text != '-':
                    user_data['buy_delivery'] = delivery
            else:
                user_data['buy_delivery'] = delivery

            user_data['step'] = 'waiting_buy_extra'
            await update.message.reply_text(
                "💰 هزینه جانبی رو به تومان وارد کن (یا - برای انصراف):\n(اگه نداره 0 رو وارد کن)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_buy_extra':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            extra = int(text.replace(',', ''))
            if user_data.get('action') == 'edit_purchase':
                if text != '-':
                    user_data['buy_extra'] = extra
            else:
                user_data['buy_extra'] = extra

            user_data['step'] = 'waiting_buy_debt'
            await update.message.reply_text(
                "⚠️ مبلغ بدهی به فروشنده رو وارد کن (یا - برای انصراف):\n(اگه نقدی خریدی 0 رو وارد کن)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_buy_debt':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            debt = int(text.replace(',', ''))
            if user_data.get('action') == 'edit_purchase':
                if text != '-':
                    user_data['buy_debt'] = debt
            else:
                user_data['buy_debt'] = debt

            user_data['step'] = 'waiting_buy_notes'
            await update.message.reply_text(
                "📝 توضیحات خرید رو وارد کن (یا - برای انصراف):\n(یا برای رد کردن - رو بفرست)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_buy_notes':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        notes = text if text != '-' else ''

        # محاسبات
        total_cost = user_data['buy_price'] + user_data['buy_delivery'] + user_data['buy_extra']
        cash_paid = total_cost - user_data['buy_debt']

        if user_data.get('action') == 'edit_purchase':
            # ویرایش خرید
            purchase_id = user_data['edit_purchase_id']
            purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

            if purchase:
                # بروزرسانی خرید
                old_total = purchase['total_cost']
                purchase['model'] = user_data['buy_model']
                purchase['buy_price'] = user_data['buy_price']
                purchase['delivery_cost'] = user_data['buy_delivery']
                purchase['extra_cost'] = user_data['buy_extra']
                purchase['total_cost'] = total_cost
                purchase['purchase_debt'] = user_data['buy_debt']
                purchase['remaining_debt'] = user_data['buy_debt']
                purchase['cash_paid'] = cash_paid
                purchase['notes'] = notes

                # بروزرسانی تراکنش
                for t in bot_accounting.data['transactions']:
                    if t.get('type') == 'خرید' and t.get('model') == purchase['model']:
                        t['amount'] = -cash_paid
                        t['debt'] = user_data['buy_debt']
                        t['description'] = f"خرید {purchase['model']}{' - ' + notes if notes else ''}"
                        break

                bot_accounting.save_data()

                await update.message.reply_text(
                    f"✅ **خرید با موفقیت ویرایش شد**\n\n"
                    f"📱 {purchase['model']}\n"
                    f"💰 قیمت خرید: {format_price(user_data['buy_price'])} تومان\n"
                    f"🚚 پیک: {format_price(user_data['buy_delivery'])} تومان\n"
                    f"💎 جانبی: {format_price(user_data['buy_extra'])} تومان\n"
                    f"💵 جمع کل: {format_price(total_cost)} تومان\n"
                    f"⚠️ بدهی: {format_price(user_data['buy_debt'])} تومان\n"
                    f"💸 پرداخت نقدی: {format_price(cash_paid)} تومان",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📋 بازگشت به لیست", callback_data='list_buys_menu')
                    ]])
                )
        else:
            # ایجاد خرید جدید
            purchase = {
                'id': int(datetime.now().timestamp() * 1000),
                'date': datetime.now().strftime('%Y/%m/%d'),
                'model': user_data['buy_model'],
                'buy_price': user_data['buy_price'],
                'delivery_cost': user_data['buy_delivery'],
                'extra_cost': user_data['buy_extra'],
                'total_cost': total_cost,
                'purchase_debt': user_data['buy_debt'],
                'remaining_debt': user_data['buy_debt'],
                'cash_paid': cash_paid,
                'notes': notes,
                'sold': False
            }

            bot_accounting.data['purchases'].append(purchase)

            # ثبت تراکنش
            transaction = {
                'id': int(datetime.now().timestamp() * 1000) + 1,
                'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'خرید',
                'model': user_data['buy_model'],
                'amount': -cash_paid,
                'debt': user_data['buy_debt'],
                'profit': 0,
                'description': f"خرید {user_data['buy_model']}{' - ' + notes if notes else ''}"
            }
            bot_accounting.data['transactions'].insert(0, transaction)

            bot_accounting.save_data()

            await update.message.reply_text(
                f"✅ **خرید با موفقیت ثبت شد**\n\n"
                f"📱 {user_data['buy_model']}\n"
                f"💰 قیمت خرید: {format_price(user_data['buy_price'])} تومان\n"
                f"🚚 پیک: {format_price(user_data['buy_delivery'])} تومان\n"
                f"💎 جانبی: {format_price(user_data['buy_extra'])} تومان\n"
                f"💵 جمع کل: {format_price(total_cost)} تومان\n"
                f"⚠️ بدهی: {format_price(user_data['buy_debt'])} تومان\n"
                f"💸 پرداخت نقدی: {format_price(cash_paid)} تومان",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )

        user_data.clear()

    elif user_data.get('step') == 'waiting_sell_price':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            price = int(text.replace(',', ''))
            if user_data.get('action') == 'edit_sale':
                if text != '-':
                    user_data['sell_price'] = price
            else:
                user_data['sell_price'] = price

            user_data['step'] = 'waiting_sell_debt'
            await update.message.reply_text(
                "⚠️ مبلغ بدهی مشتری رو وارد کن (یا - برای انصراف):\n(اگه نقدی فروختی 0 رو وارد کن)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_sell_debt':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            debt = int(text.replace(',', ''))
            purchase_id = user_data.get('sell_purchase_id')
            purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

            if not purchase and user_data.get('action') != 'edit_sale':
                await update.message.reply_text("❌ خطا: خرید پیدا نشد!")
                user_data.clear()
                return

            if debt > user_data['sell_price']:
                await update.message.reply_text(
                    "❌ بدهی نمی‌تونه بیشتر از قیمت فروش باشه!\n"
                    "لطفاً دوباره وارد کن:"
                )
                return

            if user_data.get('action') == 'edit_sale':
                if text != '-':
                    user_data['sell_debt'] = debt
            else:
                user_data['sell_debt'] = debt

            user_data['step'] = 'waiting_sell_customer'
            await update.message.reply_text(
                "👤 نام مشتری رو وارد کن (یا - برای انصراف):\n(یا برای رد کردن - رو بفرست)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_sell_customer':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        customer = text if text != '-' else ''
        if user_data.get('action') == 'edit_sale':
            if text != '-':
                user_data['sell_customer'] = customer
        else:
            user_data['sell_customer'] = customer

        user_data['step'] = 'waiting_sell_phone'
        await update.message.reply_text(
            "📞 تلفن مشتری رو وارد کن (یا - برای انصراف):\n(یا برای رد کردن - رو بفرست)"
        )

    elif user_data.get('step') == 'waiting_sell_phone':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        phone = text if text != '-' else ''
        if user_data.get('action') == 'edit_sale':
            if text != '-':
                user_data['sell_phone'] = phone
        else:
            user_data['sell_phone'] = phone

        user_data['step'] = 'waiting_sell_notes'
        await update.message.reply_text(
            "📝 توضیحات فروش رو وارد کن (یا - برای انصراف):\n(یا برای رد کردن - رو بفرست)"
        )

    elif user_data.get('step') == 'waiting_sell_notes':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        notes = text if text != '-' else ''

        if user_data.get('action') == 'edit_sale':
            # ویرایش فروش
            sale_id = user_data['edit_sale_id']
            sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)

            if sale:
                purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == sale['purchase_id']), None)

                if purchase:
                    # محاسبات جدید
                    profit = user_data['sell_price'] - purchase['total_cost']
                    cash_received = user_data['sell_price'] - user_data['sell_debt']

                    # بروزرسانی فروش
                    sale['sell_price'] = user_data['sell_price']
                    sale['debt'] = user_data['sell_debt']
                    sale['remaining_debt'] = user_data['sell_debt']
                    sale['profit'] = profit
                    sale['cash_received'] = cash_received
                    sale['customer_name'] = user_data['sell_customer']
                    sale['customer_phone'] = user_data['sell_phone']
                    sale['notes'] = notes

                    # بروزرسانی تراکنش
                    for t in bot_accounting.data['transactions']:
                        if t.get('type') == 'فروش' and t.get('model') == purchase['model']:
                            t['amount'] = cash_received
                            t['debt'] = user_data['sell_debt']
                            t['profit'] = profit
                            t[
                                'description'] = f"فروش به {user_data['sell_customer'] or 'مشتری'} - {format_price(user_data['sell_price'])} تومان"
                            break

                    bot_accounting.save_data()

                    profit_emoji = "📈" if profit >= 0 else "📉"
                    await update.message.reply_text(
                        f"✅ **فروش با موفقیت ویرایش شد**\n\n"
                        f"📱 {purchase['model']}\n"
                        f"💰 قیمت خرید: {format_price(purchase['total_cost'])} تومان\n"
                        f"💰 قیمت فروش: {format_price(user_data['sell_price'])} تومان\n"
                        f"{profit_emoji} سود/زیان: {format_price(profit)} تومان\n"
                        f"⚠️ بدهی: {format_price(user_data['sell_debt'])} تومان\n"
                        f"💵 دریافت نقدی: {format_price(cash_received)} تومان\n"
                        f"👤 مشتری: {user_data['sell_customer'] or 'ناشناس'}",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("📋 بازگشت به لیست", callback_data='list_sales_menu')
                        ]])
                    )
        else:
            # ثبت فروش جدید
            purchase_id = user_data.get('sell_purchase_id')
            purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

            if not purchase:
                await update.message.reply_text("❌ خطا: خرید پیدا نشد!")
                user_data.clear()
                return

            # محاسبات
            profit = user_data['sell_price'] - purchase['total_cost']
            cash_received = user_data['sell_price'] - user_data['sell_debt']

            # ایجاد فروش
            sale = {
                'id': int(datetime.now().timestamp() * 1000),
                'date': datetime.now().strftime('%Y/%m/%d'),
                'purchase_id': purchase_id,
                'model': purchase['model'],
                'purchase_price': purchase['total_cost'],
                'sell_price': user_data['sell_price'],
                'debt': user_data['sell_debt'],
                'remaining_debt': user_data['sell_debt'],
                'profit': profit,
                'cash_received': cash_received,
                'customer_name': user_data['sell_customer'],
                'customer_phone': user_data['sell_phone'],
                'notes': notes
            }

            bot_accounting.data['sales'].append(sale)

            # بروزرسانی خرید
            purchase['sold'] = True

            # ثبت تراکنش
            transaction = {
                'id': int(datetime.now().timestamp() * 1000) + 1,
                'date': datetime.now().strftime('%Y/%m/%d'),
                'type': 'فروش',
                'model': purchase['model'],
                'amount': cash_received,
                'debt': user_data['sell_debt'],
                'profit': profit,
                'description': f"فروش به {user_data['sell_customer'] or 'مشتری'} - {format_price(user_data['sell_price'])} تومان"
            }
            bot_accounting.data['transactions'].insert(0, transaction)

            bot_accounting.save_data()

            profit_emoji = "📈" if profit >= 0 else "📉"
            await update.message.reply_text(
                f"✅ **فروش با موفقیت ثبت شد**\n\n"
                f"📱 {purchase['model']}\n"
                f"💰 قیمت خرید: {format_price(purchase['total_cost'])} تومان\n"
                f"💰 قیمت فروش: {format_price(user_data['sell_price'])} تومان\n"
                f"{profit_emoji} سود/زیان: {format_price(profit)} تومان\n"
                f"⚠️ بدهی: {format_price(user_data['sell_debt'])} تومان\n"
                f"💵 دریافت نقدی: {format_price(cash_received)} تومان\n"
                f"👤 مشتری: {user_data['sell_customer'] or 'ناشناس'}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )

        user_data.clear()

    elif user_data.get('step') == 'waiting_cost_title':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        user_data['cost_title'] = text
        user_data['step'] = 'waiting_cost_amount'
        await update.message.reply_text(
            "💰 مبلغ هزینه رو به تومان وارد کن (یا - برای انصراف):"
        )

    elif user_data.get('step') == 'waiting_cost_amount':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            amount = int(text.replace(',', ''))
            user_data['cost_amount'] = amount
            user_data['step'] = 'waiting_cost_desc'
            await update.message.reply_text(
                "📝 توضیحات هزینه رو وارد کن (یا - برای انصراف):\n(یا برای رد کردن - رو بفرست)"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_cost_desc':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        desc = text if text != '-' else ''

        # ثبت هزینه
        cost = {
            'id': int(datetime.now().timestamp() * 1000),
            'date': datetime.now().strftime('%Y/%m/%d'),
            'title': user_data['cost_title'],
            'amount': user_data['cost_amount'],
            'description': desc
        }

        bot_accounting.data['costs'].append(cost)

        # ثبت تراکنش
        transaction = {
            'id': int(datetime.now().timestamp() * 1000) + 1,
            'date': datetime.now().strftime('%Y/%m/%d'),
            'type': 'هزینه',
            'model': user_data['cost_title'],
            'amount': -user_data['cost_amount'],
            'debt': 0,
            'profit': 0,
            'description': desc or f"هزینه: {user_data['cost_title']}"
        }
        bot_accounting.data['transactions'].insert(0, transaction)

        bot_accounting.save_data()

        await update.message.reply_text(
            f"✅ **هزینه با موفقیت ثبت شد**\n\n"
            f"📝 {user_data['cost_title']}\n"
            f"💰 مبلغ: {format_price(user_data['cost_amount'])} تومان\n"
            f"📌 {desc or 'بدون توضیحات'}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )

        user_data.clear()

    elif user_data.get('step') == 'waiting_payment_amount':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            amount = int(text.replace(',', ''))
            sale_id = user_data.get('payment_sale_id')
            sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)

            if not sale:
                await update.message.reply_text("❌ خطا: فروش پیدا نشد!")
                user_data.clear()
                return

            remaining = sale.get('remaining_debt', sale['debt']) - bot_accounting.get_total_sale_payments(sale_id)

            if amount > remaining:
                await update.message.reply_text(
                    f"❌ مبلغ پرداختی نمی‌تونه بیشتر از {format_price(remaining)} تومان باشه!\n"
                    f"لطفاً دوباره وارد کن:"
                )
                return

            user_data['payment_amount'] = amount
            user_data['step'] = 'waiting_payment_notes'
            await update.message.reply_text(
                "📝 توضیحات پرداخت رو وارد کن (یا - برای انصراف):"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_payment_notes':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        notes = text if text != '-' else ''
        sale_id = user_data.get('payment_sale_id')
        sale = next((s for s in bot_accounting.data['sales'] if s['id'] == sale_id), None)

        if not sale:
            await update.message.reply_text("❌ خطا: فروش پیدا نشد!")
            user_data.clear()
            return

        # ثبت پرداخت
        payment = {
            'id': int(datetime.now().timestamp() * 1000),
            'sale_id': sale_id,
            'date': datetime.now().strftime('%Y/%m/%d'),
            'amount': user_data['payment_amount'],
            'notes': notes,
            'model': sale['model'],
            'customer_name': sale.get('customer_name', '')
        }

        bot_accounting.data['debt_payments'].append(payment)

        # بروزرسانی باقیمانده بدهی
        if 'remaining_debt' not in sale:
            sale['remaining_debt'] = sale['debt']
        sale['remaining_debt'] -= user_data['payment_amount']
        if sale['remaining_debt'] < 0:
            sale['remaining_debt'] = 0

        # ثبت تراکنش
        transaction = {
            'id': int(datetime.now().timestamp() * 1000) + 1,
            'date': datetime.now().strftime('%Y/%m/%d'),
            'type': 'دریافت بدهی',
            'model': sale['model'],
            'amount': user_data['payment_amount'],
            'debt': 0,
            'profit': 0,
            'description': f"دریافت بدهی از {sale.get('customer_name', 'مشتری')} - {notes}"
        }
        bot_accounting.data['transactions'].insert(0, transaction)

        bot_accounting.save_data()

        await update.message.reply_text(
            f"✅ **پرداخت بدهی با موفقیت ثبت شد**\n\n"
            f"📱 {sale['model']}\n"
            f"💰 مبلغ پرداختی: {format_price(user_data['payment_amount'])} تومان\n"
            f"⚠️ باقیمانده بدهی: {format_price(max(0, sale['remaining_debt']))} تومان",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )

        user_data.clear()

    elif user_data.get('step') == 'waiting_purchase_payment_amount':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        try:
            amount = int(text.replace(',', ''))
            purchase_id = user_data.get('payment_purchase_id')
            purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

            if not purchase:
                await update.message.reply_text("❌ خطا: خرید پیدا نشد!")
                user_data.clear()
                return

            remaining = purchase.get('remaining_debt',
                                     purchase.get('purchase_debt', 0)) - bot_accounting.get_total_purchase_payments(
                purchase_id)

            if amount > remaining:
                await update.message.reply_text(
                    f"❌ مبلغ پرداختی نمی‌تونه بیشتر از {format_price(remaining)} تومان باشه!\n"
                    f"لطفاً دوباره وارد کن:"
                )
                return

            user_data['purchase_payment_amount'] = amount
            user_data['step'] = 'waiting_purchase_payment_notes'
            await update.message.reply_text(
                "📝 توضیحات پرداخت رو وارد کن (یا - برای انصراف):"
            )
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

    elif user_data.get('step') == 'waiting_purchase_payment_notes':
        if text == '-':
            user_data.clear()
            await update.message.reply_text(
                "❌ عملیات لغو شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
            return

        notes = text if text != '-' else ''
        purchase_id = user_data.get('payment_purchase_id')
        purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

        if not purchase:
            await update.message.reply_text("❌ خطا: خرید پیدا نشد!")
            user_data.clear()
            return

        # ثبت پرداخت
        payment = {
            'id': int(datetime.now().timestamp() * 1000),
            'purchase_id': purchase_id,
            'date': datetime.now().strftime('%Y/%m/%d'),
            'amount': user_data['purchase_payment_amount'],
            'notes': notes,
            'model': purchase['model']
        }

        bot_accounting.data['purchase_debt_payments'].append(payment)

        # بروزرسانی باقیمانده بدهی
        if 'remaining_debt' not in purchase:
            purchase['remaining_debt'] = purchase.get('purchase_debt', 0)
        purchase['remaining_debt'] -= user_data['purchase_payment_amount']
        if purchase['remaining_debt'] < 0:
            purchase['remaining_debt'] = 0

        # ثبت تراکنش
        transaction = {
            'id': int(datetime.now().timestamp() * 1000) + 1,
            'date': datetime.now().strftime('%Y/%m/%d'),
            'type': 'پرداخت بدهی خرید',
            'model': purchase['model'],
            'amount': -user_data['purchase_payment_amount'],
            'debt': 0,
            'profit': 0,
            'description': f"پرداخت بدهی خرید {purchase['model']} - {notes}"
        }
        bot_accounting.data['transactions'].insert(0, transaction)

        bot_accounting.save_data()

        await update.message.reply_text(
            f"✅ **پرداخت بدهی خرید با موفقیت ثبت شد**\n\n"
            f"📱 {purchase['model']}\n"
            f"💰 مبلغ پرداختی: {format_price(user_data['purchase_payment_amount'])} تومان\n"
            f"⚠️ باقیمانده بدهی: {format_price(max(0, purchase['remaining_debt']))} تومان",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )

        user_data.clear()


# ==================== راه‌اندازی ربات ====================

def main():
    try:
        # ساخت اپلیکیشن با تنظیمات ساده
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

        # هندلر فایل‌ها (برای بازیابی)
        app.add_handler(MessageHandler(filters.Document.ALL, handle_message))

        print("🤖 ربات حسابداری در حال راه‌اندازی...")
        print("✅ برای فعال کردن منوی دائمی، دستور /setmenu رو به ربات بفرست")
        print("⚠️ اگر در ایران هستی، VPN روشن کن!")
        print("📝 ویژگی‌های جدید:")
        print("   • پشتیبان‌گیری از انبار")
        print("   • بازیابی انبار از فایل")
        print("   • ویرایش خرید از لیست")
        print("   • ویرایش فروش از لیست")
        print("   • حذف خرید و فروش")
        print("   • امکان انصراف با /cancel")

        # اجرا
        app.run_polling(allowed_updates=['message', 'callback_query'])

    except Exception as e:
        print(f"❌ خطا در راه‌اندازی: {e}")
        print("💡 راه‌حل:")
        print("1. VPN یا پروکسی خودت رو چک کن")
        print("2. توکن ربات رو چک کن")
        print("3. اینترنت رو چک کن")


if __name__ == '__main__':
    main()