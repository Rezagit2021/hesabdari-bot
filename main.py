import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime
import requests

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

        # محاسبه هزینه‌های شخصی شرکا
        partner_personal_expenses = 0
        for t in self.data['partner_transactions']:
            if t['type'] == 'personal_expense':
                partner_personal_expenses += t['amount']

        total_costs_with_partner = total_costs + partner_personal_expenses

        # محاسبه سهم هر شریک (۵۰ - ۵۰)
        partner_share = (total_profit - total_costs_with_partner) / 2

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

        return reza_balance, milad_balance, total_costs_with_partner

    def get_statistics(self):
        balance = self.calculate_balance()
        inv_count, inv_value = self.calculate_inventory()
        total_profit = self.calculate_total_profit()
        sales_debt, purchase_debt = self.calculate_remaining_debts()
        total_costs = sum(c['amount'] for c in self.data['costs'])

        # محاسبه هزینه‌های شخصی شرکا
        partner_expenses = 0
        for t in self.data['partner_transactions']:
            if t['type'] == 'personal_expense':
                partner_expenses += t['amount']

        total_costs_with_partner = total_costs + partner_expenses

        # محاسبه مانده شرکا
        reza_balance, milad_balance, _ = self.calculate_partner_balances()

        # تعیین وضعیت بدهکار/بستانکار
        reza_status = "✅ بستانکار" if reza_balance >= 0 else "❌ بدهکار"
        milad_status = "✅ بستانکار" if milad_balance >= 0 else "❌ بدهکار"

        # طراحی داشبورد ساده و خوانا
        stats = "╔════════════════════════════════════╗\n"
        stats += "║        📊 **داشبورد مالی**         ║\n"
        stats += "╚════════════════════════════════════╝\n\n"

        stats += "💰 **موجودی حساب:**\n"
        stats += f"└─ {format_price(balance)} تومان\n\n"

        stats += "📦 **وضعیت انبار:**\n"
        stats += f"├─ تعداد: {inv_count} عدد\n"
        stats += f"└─ ارزش: {format_price(inv_value)} تومان\n\n"

        stats += "📈 **عملکرد:**\n"
        stats += f"├─ سود کل: {format_price(total_profit)} تومان\n"
        stats += f"├─ سود خالص: {format_price(total_profit - total_costs_with_partner)} تومان\n"
        stats += f"├─ هزینه‌های جاری: {format_price(total_costs)} تومان\n"
        stats += f"└─ هزینه‌های شخصی شرکا: {format_price(partner_expenses)} تومان\n\n"

        stats += "⚠️ **بدهی‌ها:**\n"
        stats += f"├─ بدهی فروش: {format_price(sales_debt)} تومان\n"
        stats += f"└─ بدهی خرید: {format_price(purchase_debt)} تومان\n\n"

        stats += "👥 **وضعیت شرکا:**\n"
        stats += f"├─ رضا: {format_price(abs(reza_balance))} تومان ({reza_status})\n"
        stats += f"└─ میلاد: {format_price(abs(milad_balance))} تومان ({milad_status})\n\n"

        stats += "📊 **آمار کلی:**\n"
        stats += f"├─ تعداد خریدها: {len(self.data['purchases'])}\n"
        stats += f"├─ تعداد فروش‌ها: {len(self.data['sales'])}\n"
        stats += f"├─ تعداد هزینه‌ها: {len(self.data['costs'])}\n"
        stats += f"└─ تعداد تراکنش‌ها: {len(self.data['transactions'])}"

        return stats


# نمونه از کلاس حسابداری
bot_accounting = AccountingBot()


# ==================== توابع هندلر ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی با ترتیب درست"""
    keyboard = [
        [InlineKeyboardButton("🛒 ثبت خرید", callback_data='buy_menu'),
         InlineKeyboardButton("💰 ثبت فروش", callback_data='sell_menu')],
        [InlineKeyboardButton("📋 لیست خریدها", callback_data='list_buys_menu'),
         InlineKeyboardButton("📋 لیست فروش‌ها", callback_data='list_sales_menu')],
        [InlineKeyboardButton("💸 هزینه‌های جاری", callback_data='costs_menu'),
         InlineKeyboardButton("📜 تراکنش‌ها", callback_data='transactions')],
        [InlineKeyboardButton("💳 مدیریت بدهی", callback_data='debt_menu'),
         InlineKeyboardButton("👥 تراکنش شرکا", callback_data='partner_menu')],
        [InlineKeyboardButton("💾 پشتیبان و بازیابی", callback_data='backup_menu'),
         InlineKeyboardButton("⚙️ تنظیمات", callback_data='settings_menu')],
        [InlineKeyboardButton("📊 داشبورد", callback_data='dashboard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = "🎯 **به ربات حسابداری خرید و فروش گوشی خوش آمدید**\n\n"
    welcome_text += "از منوی زیر انتخاب کنید:"

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')


async def set_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم منوی دائمی ربات"""
    commands = [
        BotCommand("start", "🏠 منوی اصلی"),
        BotCommand("dashboard", "📊 داشبورد"),
        BotCommand("buy", "🛒 ثبت خرید"),
        BotCommand("sell", "💰 ثبت فروش"),
        BotCommand("list_buys", "📋 لیست خریدها"),
        BotCommand("list_sales", "📋 لیست فروش‌ها"),
        BotCommand("costs", "💸 هزینه‌ها"),
        BotCommand("list_costs", "📋 لیست هزینه‌ها"),
        BotCommand("transactions", "📜 تراکنش‌ها"),
        BotCommand("debts", "💳 بدهی‌ها"),
        BotCommand("partners", "👥 شرکا"),
        BotCommand("backup", "💾 پشتیبان"),
        BotCommand("settings", "⚙️ تنظیمات"),
        BotCommand("cancel", "❌ لغو"),
        BotCommand("help", "❓ راهنما")
    ]

    await context.bot.set_my_commands(commands)
    await update.message.reply_text("✅ منوی ربات با موفقیت تنظیم شد!")


# ==================== توابع لیست خرید و فروش ====================

async def list_buys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست خریدها"""
    if not bot_accounting.data['purchases']:
        await update.message.reply_text(
            "❌ هیچ خریدی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "📋 **لیست خریدها:**\n\n"
    for i, p in enumerate(bot_accounting.data['purchases'][-20:], 1):
        status = "✅ فروخته شده" if p.get('sold') else "🟢 در انبار"
        text += f"{i}. **{p['model']}**\n"
        text += f"   📅 تاریخ: {p['date']}\n"
        text += f"   💰 قیمت: {format_price(p['total_cost'])} تومان\n"
        text += f"   📌 وضعیت: {status}\n"
        if p.get('purchase_debt', 0) > 0:
            remaining = p.get('remaining_debt', p['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                p['id'])
            text += f"   ⚠️ بدهی: {format_price(max(0, remaining))} تومان\n"
        text += "\n"

    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
        ]])
    )


async def list_sales_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست فروش‌ها"""
    if not bot_accounting.data['sales']:
        await update.message.reply_text(
            "❌ هیچ فروشی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "📋 **لیست فروش‌ها:**\n\n"
    for i, s in enumerate(bot_accounting.data['sales'][-20:], 1):
        profit_emoji = "📈" if s.get('profit', 0) >= 0 else "📉"
        text += f"{i}. **{s['model']}**\n"
        text += f"   📅 تاریخ: {s['date']}\n"
        text += f"   💰 خرید: {format_price(s['purchase_price'])} تومان\n"
        text += f"   💰 فروش: {format_price(s['sell_price'])} تومان\n"
        text += f"   {profit_emoji} سود: {format_price(s.get('profit', 0))} تومان\n"
        if s.get('debt', 0) > 0:
            remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(s['id'])
            text += f"   ⚠️ بدهی: {format_price(max(0, remaining))} تومان\n"
        if s.get('customer_name'):
            text += f"   👤 مشتری: {s['customer_name']}\n"
        text += "\n"

    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
        ]])
    )


# ==================== هندلر دکمه‌ها ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌ها"""
    query = update.callback_query
    await query.answer()

    # ========== منوی اصلی ==========
    if query.data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("🛒 ثبت خرید", callback_data='buy_menu'),
             InlineKeyboardButton("💰 ثبت فروش", callback_data='sell_menu')],
            [InlineKeyboardButton("📋 لیست خریدها", callback_data='list_buys_menu'),
             InlineKeyboardButton("📋 لیست فروش‌ها", callback_data='list_sales_menu')],
            [InlineKeyboardButton("💸 هزینه‌های جاری", callback_data='costs_menu'),
             InlineKeyboardButton("📜 تراکنش‌ها", callback_data='transactions')],
            [InlineKeyboardButton("💳 مدیریت بدهی", callback_data='debt_menu'),
             InlineKeyboardButton("👥 تراکنش شرکا", callback_data='partner_menu')],
            [InlineKeyboardButton("💾 پشتیبان و بازیابی", callback_data='backup_menu'),
             InlineKeyboardButton("⚙️ تنظیمات", callback_data='settings_menu')],
            [InlineKeyboardButton("📊 داشبورد", callback_data='dashboard')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 **منوی اصلی**\n\nلطفاً یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # ========== داشبورد ==========
    elif query.data == 'dashboard':
        stats = bot_accounting.get_statistics()
        keyboard = [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            stats,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # ========== ثبت خرید ==========
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

    # ========== ثبت فروش ==========
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
                f"لطفاً قیمت فروش رو وارد کن:",
                parse_mode='Markdown'
            )

    # ========== لیست خریدها ==========
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

        for i, p in enumerate(bot_accounting.data['purchases'][-10:], 1):
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

        if purchase.get('purchase_debt', 0) > 0 and max(0, remaining_debt - total_paid) > 0:
            keyboard.append([InlineKeyboardButton("💳 پرداخت بدهی", callback_data=f"pay_purchase_{purchase_id}")])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data='list_buys_menu')])
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    # ========== لیست فروش‌ها ==========
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

        for i, s in enumerate(bot_accounting.data['sales'][-10:], 1):
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
             InlineKeyboardButton("❌ حذف", callback_data=f"delete_sale_{sale_id}")]
        ]

        if sale.get('debt', 0) > 0 and max(0, remaining_debt - total_paid) > 0:
            keyboard.append([InlineKeyboardButton("💳 دریافت بدهی", callback_data=f"pay_sale_{sale_id}")])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data='list_sales_menu')])
        keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    # ========== منوی هزینه‌های جاری ==========
    elif query.data == 'costs_menu':
        keyboard = [
            [InlineKeyboardButton("➕ ثبت هزینه جدید", callback_data='new_cost')],
            [InlineKeyboardButton("📋 لیست هزینه‌ها", callback_data='list_costs')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💸 **مدیریت هزینه‌های جاری**\n\n"
            "لطفاً انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'new_cost':
        context.user_data['action'] = 'new_cost'
        context.user_data['step'] = 'waiting_cost_title'
        await query.edit_message_text(
            "📝 **ثبت هزینه جدید**\n\n"
            "لطفاً عنوان هزینه رو وارد کن:\n"
            "(مثال: اجاره مغازه، قبض برق)\n\n"
            "💡 برای انصراف /cancel رو بزن",
            parse_mode='Markdown'
        )

    elif query.data == 'list_costs':
        if not bot_accounting.data['costs']:
            await query.edit_message_text(
                "❌ هیچ هزینه‌ای ثبت نشده است.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data='costs_menu')
                ]])
            )
            return

        text = "📋 **لیست هزینه‌های جاری:**\n\n"
        for i, c in enumerate(bot_accounting.data['costs'][-20:], 1):
            text += f"{i}. **{c['title']}**\n"
            text += f"   📅 تاریخ: {c['date']}\n"
            text += f"   💰 مبلغ: {format_price(c['amount'])} تومان\n"
            if c.get('description'):
                text += f"   📌 {c['description']}\n"
            text += "\n"

        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data='costs_menu')
            ]])
        )

    # ========== منوی شرکا ==========
    elif query.data == 'partner_menu':
        keyboard = [
            [InlineKeyboardButton("👤 تراکنش رضا", callback_data='partner_reza')],
            [InlineKeyboardButton("👤 تراکنش میلاد", callback_data='partner_milad')],
            [InlineKeyboardButton("📜 لیست تراکنش‌ها", callback_data='list_partner')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👥 **مدیریت تراکنش شرکا**\n\n"
            "• هزینه شخصی شرکا به هزینه‌های جاری اضافه میشه\n\n"
            "لطفاً انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'partner_reza':
        context.user_data['partner'] = 'reza'
        context.user_data['action'] = 'partner_transaction'
        await query.edit_message_text(
            "👤 **تراکنش رضا**\n\n"
            "لطفاً نوع عملیات رو انتخاب کن:\n\n"
            "1️⃣ برداشت نقدی\n"
            "2️⃣ واریز نقدی\n"
            "3️⃣ هزینه شخصی\n"
            "4️⃣ استفاده از دارایی\n\n"
            "شماره گزینه رو وارد کن:",
            parse_mode='Markdown'
        )

    elif query.data == 'partner_milad':
        context.user_data['partner'] = 'milad'
        context.user_data['action'] = 'partner_transaction'
        await query.edit_message_text(
            "👤 **تراکنش میلاد**\n\n"
            "لطفاً نوع عملیات رو انتخاب کن:\n\n"
            "1️⃣ برداشت نقدی\n"
            "2️⃣ واریز نقدی\n"
            "3️⃣ هزینه شخصی\n"
            "4️⃣ استفاده از دارایی\n\n"
            "شماره گزینه رو وارد کن:",
            parse_mode='Markdown'
        )

    # ========== منوی پشتیبان و بازیابی ==========
    elif query.data == 'backup_menu':
        keyboard = [
            [InlineKeyboardButton("💾 پشتیبان کامل", callback_data='full_backup')],
            [InlineKeyboardButton("🔄 بازیابی کامل", callback_data='full_restore')],
            [InlineKeyboardButton("📦 پشتیبان انبار و بدهی", callback_data='inventory_backup')],
            [InlineKeyboardButton("📂 بازیابی انبار و بدهی", callback_data='inventory_restore')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💾 **مدیریت پشتیبان‌گیری و بازیابی**\n\n"
            "لطفاً انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # ========== منوی تنظیمات ==========
    elif query.data == 'settings_menu':
        keyboard = [
            [InlineKeyboardButton("💰 سرمایه اولیه", callback_data='set_initial_capital')],
            [InlineKeyboardButton("📝 راهنما", callback_data='help')],
            [InlineKeyboardButton("🧹 پاک کردن همه داده‌ها", callback_data='clear_all')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ **تنظیمات**\n\n"
            "لطفاً انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # ========== سرمایه اولیه ==========
    elif query.data == 'set_initial_capital':
        context.user_data['action'] = 'set_capital'
        await query.edit_message_text(
            "💰 **ثبت سرمایه اولیه**\n\n"
            "لطفاً مبلغ سرمایه اولیه رو به تومان وارد کن:\n"
            "(مثال: 10000000)\n\n"
            "💡 برای انصراف /cancel رو بزن",
            parse_mode='Markdown'
        )

    # ========== راهنما ==========
    elif query.data == 'help':
        help_text = """
❓ **راهنمای استفاده از ربات**

📌 **دستورات اصلی:**
/start - 🏠 منوی اصلی
/dashboard - 📊 داشبورد مالی

🛒 **مدیریت خرید و فروش:**
/buy - ثبت خرید جدید
/sell - ثبت فروش جدید
/list_buys - لیست خریدها
/list_sales - لیست فروش‌ها

💸 **هزینه‌ها:**
/costs - ثبت هزینه جدید
/list_costs - لیست هزینه‌ها

👥 **مدیریت شرکا:**
/partners - تراکنش شرکا

💳 **بدهی‌ها:**
/debts - مدیریت بدهی‌ها

💾 **پشتیبان و بازیابی:**
/backup - منوی پشتیبان

⚙️ **تنظیمات:**
/settings - منوی تنظیمات
/capital - سرمایه اولیه
/cancel - لغو عملیات
/help - راهنما

📝 **نکات مهم:**
• برای وارد کردن مبلغ، عدد بدون کاما وارد کن
• برای رد کردن هر مرحله از - استفاده کن
• همه اطلاعات در فایل ذخیره میشه
• با /cancel می‌تونی هر عملیاتی رو لغو کنی
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')

    # ========== پاک کردن همه ==========
    elif query.data == 'clear_all':
        keyboard = [
            [InlineKeyboardButton("✅ بله، پاک کن", callback_data='confirm_clear')],
            [InlineKeyboardButton("❌ خیر، برگشت", callback_data='settings_menu')]
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

    # ========== تراکنش‌ها ==========
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

        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )

    # ========== مدیریت بدهی ==========
    elif query.data == 'debt_menu':
        sales_debt, purchase_debt = bot_accounting.calculate_remaining_debts()
        text = "📊 **وضعیت بدهی‌ها:**\n\n"
        text += f"⚠️ بدهی فروش: {format_price(sales_debt)} تومان\n"
        text += f"⚠️ بدهی خرید: {format_price(purchase_debt)} تومان\n\n"

        keyboard = [
            [InlineKeyboardButton("💳 دریافت بدهی فروش", callback_data='pay_sale_debt')],
            [InlineKeyboardButton("💳 پرداخت بدهی خرید", callback_data='pay_purchase_debt')],
            [InlineKeyboardButton("🔙 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text + "لطفاً انتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # ========== پشتیبان کامل ==========
    elif query.data == 'full_backup':
        await query.edit_message_text(
            "💾 **در حال تهیه پشتیبان کامل...**",
            parse_mode='Markdown'
        )

        filename = f"full_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(bot_accounting.data, f, ensure_ascii=False, indent=2)

        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=filename,
                caption="📦 **پشتیبان کامل از تمام داده‌ها**\n"
                        f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}"
            )

        os.remove(filename)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ پشتیبان کامل با موفقیت ایجاد و ارسال شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت به منوی پشتیبان", callback_data='backup_menu')
            ]])
        )

    # ========== بازیابی کامل ==========
    elif query.data == 'full_restore':
        context.user_data['action'] = 'full_restore'
        await query.edit_message_text(
            "🔄 **بازیابی کامل داده‌ها**\n\n"
            "لطفاً فایل پشتیبان JSON رو ارسال کن.\n\n"
            "⚠️ **توجه:** این عمل تمام داده‌های فعلی رو با داده‌های فایل جایگزین می‌کند.",
            parse_mode='Markdown'
        )

    # ========== پشتیبان انبار و بدهی ==========
    elif query.data == 'inventory_backup':
        await query.edit_message_text(
            "📦 **در حال تهیه پشتیبان انبار و بدهی‌ها...**",
            parse_mode='Markdown'
        )

        inventory_items = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]

        backup_data = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'inventory_debt_backup',
            'inventory': inventory_items,
            'sales_debt': [],
            'purchase_debt': []
        }

        # بدهی‌های فروش
        for s in bot_accounting.data['sales']:
            if s.get('debt', 0) > 0:
                remaining = s.get('remaining_debt', s['debt']) - bot_accounting.get_total_sale_payments(s['id'])
                if remaining > 0:
                    backup_data['sales_debt'].append({
                        'model': s['model'],
                        'customer': s.get('customer_name', ''),
                        'debt': remaining
                    })

        # بدهی‌های خرید
        for p in bot_accounting.data['purchases']:
            if p.get('purchase_debt', 0) > 0:
                remaining = p.get('remaining_debt', p['purchase_debt']) - bot_accounting.get_total_purchase_payments(
                    p['id'])
                if remaining > 0:
                    backup_data['purchase_debt'].append({
                        'model': p['model'],
                        'debt': remaining
                    })

        filename = f"inventory_debt_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=filename,
                caption="📦 **پشتیبان انبار و بدهی‌ها**"
            )

        os.remove(filename)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ پشتیبان انبار و بدهی‌ها با موفقیت ایجاد و ارسال شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت به منوی پشتیبان", callback_data='backup_menu')
            ]])
        )

    # ========== بازیابی انبار و بدهی ==========
    elif query.data == 'inventory_restore':
        context.user_data['action'] = 'inventory_restore'
        await query.edit_message_text(
            "📂 **بازیابی انبار و بدهی‌ها**\n\n"
            "لطفاً فایل پشتیبان JSON رو ارسال کن.\n\n"
            "⚠️ **توجه:** اقلام جدید به انبار اضافه می‌شوند.",
            parse_mode='Markdown'
        )


# ==================== هندلر پیام‌های متنی ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیام‌های متنی"""
    text = update.message.text
    user_data = context.user_data

    # ========== بازیابی کامل ==========
    if user_data.get('action') == 'full_restore':
        if update.message.document:
            file = await update.message.document.get_file()
            filename = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            await file.download_to_drive(filename)

            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    restore_data = json.load(f)

                required_keys = ['purchases', 'sales', 'costs', 'transactions', 'partner_transactions']
                if all(key in restore_data for key in required_keys):
                    bot_accounting.data = restore_data
                    bot_accounting.save_data()
                    await update.message.reply_text(
                        "✅ **بازیابی کامل با موفقیت انجام شد!**\n\n"
                        f"📊 خریدها: {len(restore_data['purchases'])}\n"
                        f"💰 فروش‌ها: {len(restore_data['sales'])}\n"
                        f"💸 هزینه‌ها: {len(restore_data['costs'])}",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 بازگشت به منوی پشتیبان", callback_data='backup_menu')
                        ]])
                    )
                else:
                    await update.message.reply_text("❌ فرمت فایل پشتیبان معتبر نیست.")

                os.remove(filename)

            except Exception as e:
                await update.message.reply_text(f"❌ خطا در بازیابی: {str(e)}")
                if os.path.exists(filename):
                    os.remove(filename)

            user_data.clear()
            return

    # ========== بازیابی انبار و بدهی ==========
    if user_data.get('action') == 'inventory_restore':
        if update.message.document:
            file = await update.message.document.get_file()
            filename = f"restore_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            await file.download_to_drive(filename)

            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    restore_data = json.load(f)

                if restore_data.get('type') == 'inventory_debt_backup':
                    count = 0
                    for item in restore_data.get('inventory', []):
                        new_item = item.copy()
                        new_item['id'] = int(datetime.now().timestamp() * 1000) + count
                        new_item['sold'] = False
                        bot_accounting.data['purchases'].append(new_item)
                        count += 1

                    await update.message.reply_text(
                        f"✅ **بازیابی انبار و بدهی‌ها انجام شد**\n\n"
                        f"📱 اقلام اضافه شده: {count}\n"
                        f"⚠️ بدهی‌ها در لیست‌ها قابل مشاهده هستند",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 بازگشت به منوی پشتیبان", callback_data='backup_menu')
                        ]])
                    )
                    bot_accounting.save_data()
                else:
                    await update.message.reply_text("❌ فرمت فایل پشتیبان معتبر نیست.")

                os.remove(filename)

            except Exception as e:
                await update.message.reply_text(f"❌ خطا در بازیابی: {str(e)}")
                if os.path.exists(filename):
                    os.remove(filename)

            user_data.clear()
            return

    # ========== سرمایه اولیه ==========
    if user_data.get('action') == 'set_capital':
        try:
            amount = int(text.replace(',', ''))
            bot_accounting.data['initial_capital'] = amount

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
                f"✅ سرمایه اولیه با مبلغ {format_price(amount)} تومان ثبت شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ بازگشت به تنظیمات", callback_data='settings_menu')
                ]])
            )
            user_data.clear()
        except:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
        return

    # ========== خرید جدید ==========
    elif user_data.get('action') == 'new_buy':
        step = user_data.get('step')

        if step == 'waiting_buy_model':
            if text == '-':
                user_data.clear()
                await update.message.reply_text("❌ عملیات لغو شد.")
                return
            user_data['buy_model'] = text
            user_data['step'] = 'waiting_buy_price'
            await update.message.reply_text("💰 قیمت خرید رو وارد کن:")

        elif step == 'waiting_buy_price':
            try:
                user_data['buy_price'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_delivery'
                await update.message.reply_text("🚚 هزینه پیک رو وارد کن (0 اگه نداره):")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_buy_delivery':
            try:
                user_data['buy_delivery'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_extra'
                await update.message.reply_text("💰 هزینه جانبی رو وارد کن (0 اگه نداره):")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_buy_extra':
            try:
                user_data['buy_extra'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_debt'
                await update.message.reply_text("⚠️ بدهی به فروشنده رو وارد کن (0 اگه نقدی):")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_buy_debt':
            try:
                user_data['buy_debt'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_buy_notes'
                await update.message.reply_text("📝 توضیحات (یا - برای رد کردن):")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_buy_notes':
            notes = text if text != '-' else ''
            total_cost = user_data['buy_price'] + user_data['buy_delivery'] + user_data['buy_extra']
            cash_paid = total_cost - user_data['buy_debt']

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

    # ========== فروش جدید ==========
    elif user_data.get('action') == 'new_sell':
        step = user_data.get('step')

        if step == 'waiting_sell_price':
            try:
                user_data['sell_price'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_sell_debt'
                await update.message.reply_text("⚠️ مبلغ بدهی مشتری رو وارد کن (0 اگه نقدی):")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_sell_debt':
            try:
                debt = int(text.replace(',', ''))
                purchase_id = user_data.get('sell_purchase_id')
                purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

                if not purchase:
                    await update.message.reply_text("❌ خطا: خرید پیدا نشد!")
                    user_data.clear()
                    return

                if debt > user_data['sell_price']:
                    await update.message.reply_text("❌ بدهی نمی‌تونه بیشتر از قیمت فروش باشه!")
                    return

                user_data['sell_debt'] = debt
                user_data['step'] = 'waiting_sell_customer'
                await update.message.reply_text("👤 نام مشتری رو وارد کن (یا - برای رد کردن):")

            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_sell_customer':
            user_data['sell_customer'] = text if text != '-' else ''
            user_data['step'] = 'waiting_sell_phone'
            await update.message.reply_text("📞 تلفن مشتری رو وارد کن (یا - برای رد کردن):")

        elif step == 'waiting_sell_phone':
            user_data['sell_phone'] = text if text != '-' else ''
            user_data['step'] = 'waiting_sell_notes'
            await update.message.reply_text("📝 توضیحات فروش رو وارد کن (یا - برای رد کردن):")

        elif step == 'waiting_sell_notes':
            notes = text if text != '-' else ''
            purchase_id = user_data.get('sell_purchase_id')
            purchase = next((p for p in bot_accounting.data['purchases'] if p['id'] == purchase_id), None)

            if not purchase:
                await update.message.reply_text("❌ خطا: خرید پیدا نشد!")
                user_data.clear()
                return

            profit = user_data['sell_price'] - purchase['total_cost']
            cash_received = user_data['sell_price'] - user_data['sell_debt']

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
            purchase['sold'] = True

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

    # ========== هزینه جدید ==========
    elif user_data.get('action') == 'new_cost':
        step = user_data.get('step')

        if step == 'waiting_cost_title':
            if text == '-':
                user_data.clear()
                await update.message.reply_text("❌ عملیات لغو شد.")
                return
            user_data['cost_title'] = text
            user_data['step'] = 'waiting_cost_amount'
            await update.message.reply_text("💰 مبلغ هزینه رو وارد کن:")

        elif step == 'waiting_cost_amount':
            try:
                user_data['cost_amount'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_cost_desc'
                await update.message.reply_text("📝 توضیحات (یا - برای رد کردن):")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_cost_desc':
            desc = text if text != '-' else ''

            cost = {
                'id': int(datetime.now().timestamp() * 1000),
                'date': datetime.now().strftime('%Y/%m/%d'),
                'title': user_data['cost_title'],
                'amount': user_data['cost_amount'],
                'description': desc
            }

            bot_accounting.data['costs'].append(cost)

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
                    InlineKeyboardButton("💸 بازگشت به منوی هزینه", callback_data='costs_menu')
                ]])
            )
            user_data.clear()

    # ========== تراکنش شریک ==========
    elif user_data.get('action') == 'partner_transaction':
        step = user_data.get('step')

        if not step:
            try:
                option = int(text)
                type_map = {1: 'cash_withdraw', 2: 'cash_deposit', 3: 'personal_expense', 4: 'company_asset_use'}
                if option in type_map:
                    user_data['partner_type'] = type_map[option]
                    user_data['step'] = 'waiting_partner_amount'
                    await update.message.reply_text("💰 لطفاً مبلغ رو وارد کن:")
                else:
                    await update.message.reply_text("❌ گزینه نامعتبر. لطفاً 1 تا 4 رو انتخاب کن.")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_partner_amount':
            try:
                user_data['partner_amount'] = int(text.replace(',', ''))
                user_data['step'] = 'waiting_partner_desc'
                await update.message.reply_text("📝 لطفاً شرح تراکنش رو وارد کن:")
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif step == 'waiting_partner_desc':
            partner = user_data.get('partner', 'reza')
            trans_type = user_data.get('partner_type')
            amount = user_data.get('partner_amount')
            desc = text

            transaction = {
                'id': int(datetime.now().timestamp() * 1000),
                'partner': partner,
                'type': trans_type,
                'amount': amount,
                'date': datetime.now().strftime('%Y/%m/%d'),
                'description': desc
            }

            bot_accounting.data['partner_transactions'].append(transaction)

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
            elif trans_type == 'personal_expense':
                cost = {
                    'id': int(datetime.now().timestamp() * 1000) + 2,
                    'date': datetime.now().strftime('%Y/%m/%d'),
                    'title': f"هزینه شخصی {partner}",
                    'amount': amount,
                    'description': desc
                }
                bot_accounting.data['costs'].append(cost)

                cost_trans = {
                    'id': int(datetime.now().timestamp() * 1000) + 3,
                    'date': datetime.now().strftime('%Y/%m/%d'),
                    'type': 'هزینه',
                    'model': f"هزینه شخصی {partner}",
                    'amount': -amount,
                    'debt': 0,
                    'profit': 0,
                    'description': desc
                }
                bot_accounting.data['transactions'].insert(0, cost_trans)

            bot_accounting.save_data()

            partner_name = "رضا" if partner == 'reza' else "میلاد"
            await update.message.reply_text(
                f"✅ تراکنش {partner_name} با موفقیت ثبت شد.\n"
                f"💰 مبلغ: {format_price(amount)} تومان\n"
                f"📝 شرح: {desc}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👥 بازگشت به منوی شرکا", callback_data='partner_menu')
                ]])
            )
            user_data.clear()

    # ========== پیام ناشناخته ==========
    else:
        await update.message.reply_text(
            "لطفاً از منوی اصلی استفاده کنید.\n"
            "برای دیدن منو /start رو بزنید."
        )


# ==================== توابع کمکی دستورات ====================

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
        stats,
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


async def list_costs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست هزینه‌ها"""
    if not bot_accounting.data['costs']:
        await update.message.reply_text(
            "❌ هیچ هزینه‌ای ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )
        return

    text = "📋 **لیست هزینه‌های جاری:**\n\n"
    for i, c in enumerate(bot_accounting.data['costs'][-20:], 1):
        text += f"{i}. {c['title']} - {format_price(c['amount'])} تومان\n"
        text += f"   📅 {c['date']}\n"
        if c.get('description'):
            text += f"   📌 {c['description']}\n"
        text += "\n"

    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
        ]])
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
        [InlineKeyboardButton("📜 لیست تراکنش‌ها", callback_data='list_partner')],
        [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👥 **مدیریت تراکنش شرکا**\n\n"
        "• هزینه شخصی شرکا به هزینه‌های جاری اضافه میشه\n\n"
        "انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def debts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی بدهی‌ها"""
    sales_debt, purchase_debt = bot_accounting.calculate_remaining_debts()
    text = "📊 **وضعیت بدهی‌ها:**\n\n"
    text += f"⚠️ بدهی فروش: {format_price(sales_debt)} تومان\n"
    text += f"⚠️ بدهی خرید: {format_price(purchase_debt)} تومان\n\n"

    keyboard = [
        [InlineKeyboardButton("💳 دریافت بدهی فروش", callback_data='pay_sale_debt')],
        [InlineKeyboardButton("💳 پرداخت بدهی خرید", callback_data='pay_purchase_debt')],
        [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text + "لطفاً انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی پشتیبان"""
    keyboard = [
        [InlineKeyboardButton("💾 پشتیبان کامل", callback_data='full_backup')],
        [InlineKeyboardButton("🔄 بازیابی کامل", callback_data='full_restore')],
        [InlineKeyboardButton("📦 پشتیبان انبار و بدهی", callback_data='inventory_backup')],
        [InlineKeyboardButton("📂 بازیابی انبار و بدهی", callback_data='inventory_restore')],
        [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💾 **مدیریت پشتیبان‌گیری و بازیابی**\n\n"
        "لطفاً انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی تنظیمات"""
    keyboard = [
        [InlineKeyboardButton("💰 سرمایه اولیه", callback_data='set_initial_capital')],
        [InlineKeyboardButton("📝 راهنما", callback_data='help')],
        [InlineKeyboardButton("🧹 پاک کردن همه داده‌ها", callback_data='clear_all')],
        [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ **تنظیمات**\n\nلطفاً انتخاب کنید:",
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

📌 **دستورات اصلی:**
/start - 🏠 منوی اصلی
/dashboard - 📊 داشبورد مالی

🛒 **مدیریت خرید و فروش:**
/buy - ثبت خرید جدید
/sell - ثبت فروش جدید
/list_buys - لیست خریدها
/list_sales - لیست فروش‌ها

💸 **هزینه‌ها:**
/costs - ثبت هزینه جدید
/list_costs - لیست هزینه‌ها

👥 **مدیریت شرکا:**
/partners - تراکنش شرکا

💳 **بدهی‌ها:**
/debts - مدیریت بدهی‌ها

💾 **پشتیبان و بازیابی:**
/backup - منوی پشتیبان

⚙️ **تنظیمات:**
/settings - منوی تنظیمات
/capital - سرمایه اولیه
/cancel - لغو عملیات
/help - راهنما

📝 **نکات مهم:**
• برای وارد کردن مبلغ، عدد بدون کاما وارد کن
• برای رد کردن هر مرحله از - استفاده کن
• همه اطلاعات در فایل ذخیره میشه
• با /cancel می‌تونی هر عملیاتی رو لغو کنی
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


# ==================== تابع اصلی اجرا ====================

def main():
    """تابع اصلی راه‌اندازی ربات"""
    try:
        print("🤖 ربات حسابداری در حال راه‌اندازی...")

        # پاک کردن webhook قبل از شروع
        try:
            requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
            print("✅ Webhook پاک شد")
        except:
            pass

        # ساخت اپلیکیشن با تنظیمات ساده
        app = Application.builder().token(TOKEN).build()

        # هندلرهای دستورات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setmenu", set_menu))
        app.add_handler(CommandHandler("dashboard", dashboard_command))
        app.add_handler(CommandHandler("buy", buy_command))
        app.add_handler(CommandHandler("sell", sell_command))
        app.add_handler(CommandHandler("list_buys", list_buys_command))
        app.add_handler(CommandHandler("list_sales", list_sales_command))
        app.add_handler(CommandHandler("costs", costs_command))
        app.add_handler(CommandHandler("list_costs", list_costs_command))
        app.add_handler(CommandHandler("transactions", transactions_command))
        app.add_handler(CommandHandler("partners", partners_command))
        app.add_handler(CommandHandler("debts", debts_command))
        app.add_handler(CommandHandler("backup", backup_command))
        app.add_handler(CommandHandler("settings", settings_command))
        app.add_handler(CommandHandler("capital", capital_command))
        app.add_handler(CommandHandler("cancel", cancel_command))
        app.add_handler(CommandHandler("help", help_command))

        # هندلر دکمه‌ها
        app.add_handler(CallbackQueryHandler(button_handler))

        # هندلر پیام‌های متنی
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_message))

        print("✅ ربات با موفقیت آماده شد! در حال شروع Polling...")
        print("📝 برای فعال کردن منوی دائمی، /setmenu رو بفرست")

        # اجرای ربات
        app.run_polling(allowed_updates=['message', 'callback_query'])

    except Exception as e:
        print(f"❌ خطا در راه‌اندازی: {e}")


if __name__ == '__main__':
    print("🚀 شروع اجرای ربات حسابداری...")
    print(f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
    print("=" * 50)
    main()