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

        for i, p in enumerate(bot_accounting.data['purchases'][-10:], 1):
            status = "✅ فروخته شده" if p.get('sold') else "🟢 در انبار"
            btn_text = f"{i}. {p['model']} - {format_price(p['total_cost'])} تومان ({status})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_purchase_{p['id']}")])

        keyboard.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

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
        for i, t in enumerate(bot_accounting.data['transactions'][-10:], 1):
            amount = t['amount']
            amount_emoji = "💰" if amount > 0 else "💸"
            text += f"{i}. {amount_emoji} {t['type']} - {t['date']}\n"
            text += f"   {t['model']}\n"
            text += f"   مبلغ: {format_price(abs(amount))} تومان\n"
            if t.get('profit'):
                text += f"   سود: {format_price(t['profit'])} تومان\n"

        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
            ]])
        )

    elif query.data == 'partner_menu':
        keyboard = [
            [InlineKeyboardButton("👤 تراکنش رضا", callback_data='partner_reza')],
            [InlineKeyboardButton("👤 تراکنش میلاد", callback_data='partner_milad')],
            [InlineKeyboardButton("💰 وضعیت شرکا", callback_data='partner_balance_menu')],
            [InlineKeyboardButton("📜 لیست تراکنش‌ها", callback_data='list_partner')],
            [InlineKeyboardButton("🏠 بازگشت", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👥 **مدیریت تراکنش شرکا**\n\nانتخاب کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'partner_balance_menu':
        reza_balance, milad_balance = bot_accounting.calculate_partner_balances()

        text = "👥 **وضعیت بدهکار و بستانکاری شرکا:**\n\n"
        text += f"**رضا:** {format_price(abs(reza_balance))} تومان ({'✅ بستانکار' if reza_balance >= 0 else '❌ بدهکار'})\n"
        text += f"**میلاد:** {format_price(abs(milad_balance))} تومان ({'✅ بستانکار' if milad_balance >= 0 else '❌ بدهکار'})\n\n"
        text += "📌 **راهنما:**\n"
        text += "• ✅ **بستانکار:** شرکت به شریک بدهکار است\n"
        text += "• ❌ **بدهکار:** شریک به شرکت بدهکار است"

        await query.edit_message_text(text, parse_mode='Markdown')

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

    elif query.data == 'set_initial_capital':
        context.user_data['action'] = 'set_capital'
        await query.edit_message_text(
            "💰 **ثبت سرمایه اولیه**\n\n"
            "لطفاً مبلغ سرمایه اولیه رو به تومان وارد کن:\n"
            "(مثال: 10000000)\n\n"
            "💡 برای انصراف /cancel رو بزن",
            parse_mode='Markdown'
        )

    elif query.data == 'backup_menu':
        inventory = [p for p in bot_accounting.data['purchases'] if not p.get('sold', False)]

        if inventory:
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

            await query.edit_message_text(
                "✅ فایل پشتیبان ارسال شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )
        else:
            await query.edit_message_text(
                "❌ انبار خالی است!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                ]])
            )

    elif query.data == 'restore_menu':
        context.user_data['action'] = 'restore_inventory'
        await query.edit_message_text(
            "🔄 **بازیابی انبار**\n\n"
            "لطفاً فایل پشتیبان JSON رو ارسال کن.",
            parse_mode='Markdown'
        )

    elif query.data == 'help':
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
        await query.edit_message_text(help_text, parse_mode='Markdown')

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

    # هندلرهای اضافی برای دکمه‌های دیگه
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
        for i, t in enumerate(bot_accounting.data['partner_transactions'][-10:], 1):
            partner = "رضا" if t['partner'] == 'reza' else "میلاد"
            text += f"{i}. {partner} - {t['date']}\n"
            text += f"   مبلغ: {format_price(t['amount'])} تومان\n"
            text += f"   شرح: {t['description'][:50]}\n\n"

        await query.edit_message_text(text, parse_mode='Markdown')


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

    for i, p in enumerate(bot_accounting.data['purchases'][-10:], 1):
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

    for i, s in enumerate(bot_accounting.data['sales'][-10:], 1):
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
        [InlineKeyboardButton("💰 وضعیت شرکا", callback_data='partner_balance_menu')],
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

    # اگه پیام /start بود
    if text == '/start':
        await start(update, context)
        return

    # اگه کاربر در حال انجام عملیات هست
    if user_data and 'action' in user_data:
        action = user_data.get('action')

        if action == 'set_capital':
            try:
                amount = int(text.replace(',', ''))
                bot_accounting.data['initial_capital'] = amount
                bot_accounting.save_data()

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
                        InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                    ]])
                )
                user_data.clear()
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif action == 'partner_transaction':
            # منطق ثبت تراکنش شریک
            try:
                amount = int(text.replace(',', ''))
                user_data['amount'] = amount
                await update.message.reply_text("📝 لطفاً شرح تراکنش رو وارد کن:")
                user_data['step'] = 'waiting_description'
            except:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")

        elif action == 'new_buy':
            # منطق ثبت خرید
            step = user_data.get('step')
            if step == 'waiting_buy_model':
                user_data['model'] = text
                user_data['step'] = 'waiting_buy_price'
                await update.message.reply_text("💰 قیمت خرید رو وارد کن:")
            elif step == 'waiting_buy_price':
                try:
                    user_data['price'] = int(text.replace(',', ''))
                    user_data['step'] = 'waiting_buy_delivery'
                    await update.message.reply_text("🚚 هزینه پیک رو وارد کن (0 اگه نداره):")
                except:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
            elif step == 'waiting_buy_delivery':
                try:
                    user_data['delivery'] = int(text.replace(',', ''))
                    user_data['step'] = 'waiting_buy_extra'
                    await update.message.reply_text("💰 هزینه جانبی رو وارد کن (0 اگه نداره):")
                except:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
            elif step == 'waiting_buy_extra':
                try:
                    user_data['extra'] = int(text.replace(',', ''))
                    user_data['step'] = 'waiting_buy_debt'
                    await update.message.reply_text("⚠️ بدهی به فروشنده رو وارد کن (0 اگه نقدی):")
                except:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
            elif step == 'waiting_buy_debt':
                try:
                    user_data['debt'] = int(text.replace(',', ''))
                    user_data['step'] = 'waiting_buy_notes'
                    await update.message.reply_text("📝 توضیحات (یا - برای رد کردن):")
                except:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
            elif step == 'waiting_buy_notes':
                notes = text if text != '-' else ''
                total_cost = user_data['price'] + user_data['delivery'] + user_data['extra']
                cash_paid = total_cost - user_data['debt']

                purchase = {
                    'id': int(datetime.now().timestamp() * 1000),
                    'date': datetime.now().strftime('%Y/%m/%d'),
                    'model': user_data['model'],
                    'buy_price': user_data['price'],
                    'delivery_cost': user_data['delivery'],
                    'extra_cost': user_data['extra'],
                    'total_cost': total_cost,
                    'purchase_debt': user_data['debt'],
                    'remaining_debt': user_data['debt'],
                    'cash_paid': cash_paid,
                    'notes': notes,
                    'sold': False
                }

                bot_accounting.data['purchases'].append(purchase)
                bot_accounting.save_data()

                await update.message.reply_text(
                    f"✅ خرید با موفقیت ثبت شد:\n"
                    f"مدل: {user_data['model']}\n"
                    f"جمع کل: {format_price(total_cost)} تومان\n"
                    f"پرداخت نقدی: {format_price(cash_paid)} تومان\n"
                    f"بدهی: {format_price(user_data['debt'])} تومان",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 بازگشت به منو", callback_data='main_menu')
                    ]])
                )
                user_data.clear()

        elif action == 'new_sell':
            # منطق ثبت فروش - برای کامل شدن نیاز به توسعه داره
            await update.message.reply_text("⚠️ ثبت فروش در حال توسعه است.")

    else:
        # پیام عادی
        await update.message.reply_text(
            "لطفاً از منوی اصلی استفاده کنید.\n"
            "برای دیدن منو /start رو بزنید."
        )


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
    main() 
 

