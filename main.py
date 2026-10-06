import os
import time
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from requests.exceptions import ConnectionError, Timeout

TOKEN = "8911769501:AAFfvOUIQmwuzB4LeLOpWSmDlqnkrcaRIl8"

# 🛑 تم تعيين الآيدي الرقمي الصحيح الخاص بك هنا
ADMIN_ID_FIXED = 8267132327 
ADMIN_USERNAME = "hs_viv"

bot = telebot.TeleBot(TOKEN)

# --- إعداد قاعدة البيانات المحلية SQLite ---
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.00,
            deals INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals_history (
            deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            deal_details TEXT,
            status TEXT DEFAULT 'قيد المراجعة'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, username=""):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance, deals, username, is_admin FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    is_adm = 1 if (user_id == ADMIN_ID_FIXED or (username and username.lower() == ADMIN_USERNAME.lower())) else 0
    
    if not row:
        cursor.execute('INSERT INTO users (user_id, username, balance, deals, is_admin) VALUES (?, ?, 0.00, 0, ?)', (user_id, username, is_adm))
        conn.commit()
        row = (0.00, 0, username, is_adm)
    else:
        if is_adm == 1:
            cursor.execute('UPDATE users SET username = ?, is_admin = 1 WHERE user_id = ?', (username, user_id))
            conn.commit()
            
    conn.close()
    return {"balance": row[0], "deals": row[1], "is_admin": is_adm}

def update_user_balance(user_id, amount):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_deal_record(user_id, details):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO deals_history (user_id, deal_details, status) VALUES (?, ?, ?)', (user_id, details, 'قيد المراجعة'))
    deal_id = cursor.lastrowid
    cursor.execute('UPDATE users SET deals = deals + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return deal_id

def update_deal_status(deal_id, status):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE deals_history SET status = ? WHERE deal_id = ?', (status, deal_id))
    conn.commit()
    conn.close()

def get_user_deals(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT deal_id, deal_details, status FROM deals_history WHERE user_id = ? ORDER BY deal_id DESC LIMIT 5', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_admin_id():
    return ADMIN_ID_FIXED

user_states = {}
pending_recharge_approvals = {} 
last_request_time = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    username = message.from_user.username or ""
    
    get_user(user_id, username)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📥 التحميل من (تيك توك بدقة عالية، إنستغرام، يوتيوب)", callback_data="media_tools"),
        InlineKeyboardButton("🛡 خدمات الوسيط والأمان", callback_data="escrow_tools"),
        InlineKeyboardButton("👤 حسابي والأرصدة وسجل الصفقات", callback_data="user_profile"),
        InlineKeyboardButton("📜 شروط وقواعد الاستخدام", callback_data="terms_rules")
    )
    
    if user_id == ADMIN_ID_FIXED or (username and username.lower() == ADMIN_USERNAME.lower()):
        markup.add(InlineKeyboardButton("⚙️ لوحة تحكم المشرف", callback_data="admin_panel"))

    try:
        bot.reply_to(
            message,
            f"أهلاً بك يا <b>{user_name}</b> في منصة الخدمات الشاملة! 🚀\n\n"
            "أرسل أي رابط (تيك توك بدون حقوق، يوتيوب، إنستغرام) وسأقوم بتحميله فوراً:",
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Error in start: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    username = call.from_user.username or ""
    data = call.data

    user_info = get_user(user_id, username)
    is_admin = user_info["is_admin"]

    try:
        if data == "media_tools":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "💬 أرسل الرابط الآن (تيك توك، يوتيوب، إنستغرام) وسأقوم بتحميله لك بدقة عالية:")
        
        elif data == "escrow_tools":
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton("📝 طلب صفقة وساطة جديدة", callback_data="request_deal"))
            markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
            bot.edit_message_text(
                "🛡️ <b>قسم خدمات الوسيط الرقمي والأمان:</b>\n\nاضغط أدناه لتقديم طلب صفقة جديدة:",
                call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup
            )

        elif data == "request_deal":
            bot.answer_callback_query(call.id)
            user_states[user_id] = "waiting_for_deal_details"
            bot.send_message(call.message.chat.id, "📝 يرجى إرسال تفاصيل الصفقة الآن في رسالة واحدة (المبلغ، اسم الطرف الثاني، ونوع الخدمة):")

        elif data == "user_profile":
            info = get_user(user_id, username)
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("💳 طلب شحن رصيد (إرسال إيصال)", callback_data="request_recharge"),
                InlineKeyboardButton("📋 استعراض سجل صفقاتي", callback_data="view_my_deals"),
                InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
            )
            bot.edit_message_text(
                f"👤 <b>ملفك الشخصي:</b>\n\n💰 الرصيد الحالي: <b>${info['balance']:.2f}</b>\n🤝 الصفقات المنجزة: <b>{info['deals']}</b>",
                call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup
            )

        elif data == "view_my_deals":
            bot.answer_callback_query(call.id)
            deals = get_user_deals(user_id)
            if not deals:
                text = "📋 ليس لديك أي صفقات مسجلة حتى الآن."
            else:
                text = "📋 <b>آخر صفقاتك المسجلة:</b>\n\n"
                for d in deals:
                    text += f"🔹 <b>رقم الصفقة #{d[0]}</b>\n📝 التفاصيل: {d[1]}\n📌 الحالة: <code>{d[2]}</code>\n\n"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 عودة للحساب", callback_data="user_profile"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

        elif data == "request_recharge":
            bot.answer_callback_query(call.id)
            user_states[user_id] = "waiting_for_receipt"
            bot.send_message(call.message.chat.id, "💳 يرجى إرسال **صورة إيصال التحويل (سكرين شوت)** أو ملف الإيصال الآن لمراجعته من قبل الإدارة.")

        elif data == "terms_rules":
            bot.answer_callback_query(call.id)
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
            terms_text = (
                "📜 <b>شروط وقواعد الاستخدام والوساطة:</b>\n\n"
                "1️⃣ <b>الوساطة الآمنة:</b> يتم حجز المبلغ لدى المشرف حتى يتم تسليم الخدمة أو السلعة للطرفين.\n"
                "2️⃣ <b>إيصالات الشحن:</b> يجب أن يكون الإيصال واضحاً ويحمل تفاصيل عملية التحويل.\n"
                "3️⃣ <b>المسؤولية:</b> البوت أداة تنظيمية وسيطة، ومحاولات الاحتيال تعرض للحظر النهائي."
            )
            bot.edit_message_text(terms_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

        elif data.startswith("approve_recharge_"):
            if is_admin != 1:
                bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
                return
            target_user = int(data.split("_")[2])
            pending_recharge_approvals[user_id] = target_user
            user_states[user_id] = "waiting_for_custom_amount"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "💰 أرسل الآن **المبلغ المراد إضافته** لرصيد هذا المستخدم (مثال: <code>15.5</code>):", parse_mode="HTML")

        elif data.startswith("reject_recharge_"):
            if is_admin != 1:
                bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
                return
            target_user = int(data.split("_")[2])
            bot.answer_callback_query(call.id, "❌ تم رفض الإيصال.")
            try:
                bot.edit_message_caption("❌ <b>تم رفض الإيصال من قبل المشرف.</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except:
                pass
            try:
                bot.send_message(target_user, "❌ عذراً، تم رفض إيصال الشحن من قبل الإدارة.", parse_mode="HTML")
            except:
                pass

        elif data.startswith("approve_deal_"):
            if is_admin != 1:
                bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
                return
            parts = data.split("_")
            deal_id = int(parts[2])
            target_user = int(parts[3])
            
            update_deal_status(deal_id, "مقبولة / قيد التنفيذ")
            bot.answer_callback_query(call.id, "✅ تم قبول الصفقة بنجاح!")
            try:
                bot.edit_message_text(f"✅ <b>تم قبول طلب الصفقة #{deal_id} من قبل المشرف.</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except:
                pass
            try:
                bot.send_message(target_user, f"🎉 <b>تم قبول طلب صفقتك رقم #{deal_id} من قبل الإدارة!</b>", parse_mode="HTML")
            except:
                pass

        elif data.startswith("reject_deal_"):
            if is_admin != 1:
                bot.answer_callback_query(call.id, "⚠️ غير مصرح لك!", show_alert=True)
                return
            parts = data.split("_")
            deal_id = int(parts[2])
            target_user = int(parts[3])
            
            update_deal_status(deal_id, "مرفوضة")
            bot.answer_callback_query(call.id, "❌ تم رفض الصفقة.")
            try:
                bot.edit_message_text(f"❌ <b>تم رفض طلب الصفقة #{deal_id} من قبل المشرف.</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except:
                pass
            try:
                bot.send_message(target_user, f"❌ عذراً، تم رفض طلب صفقتك رقم #{deal_id} من قبل الإدارة.", parse_mode="HTML")
            except:
                pass

        elif data == "admin_panel":
            if is_admin != 1:
                bot.answer_callback_query(call.id, "⚠ عذراً، هذه اللوحة مخصصة للمشرف فقط!", show_alert=True)
                return

            bot.answer_callback_query(call.id)
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
                InlineKeyboardButton("📢 إرسال اذاعة للجميع", callback_data="admin_broadcast"),
                InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
            )
            bot.edit_message_text(
                "⚙️ <b>لوحة تحكم المشرف:</b>\n\nاختر العملية المطلوبة:",
                call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup
            )

        elif data == "admin_stats":
            if is_admin != 1:
                return
            bot.answer_callback_query(call.id)
            users = get_all_users()
            total_users = len(users)
            
            conn = sqlite3.connect('bot_database.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('SELECT SUM(balance), SUM(deals) FROM users')
            row = cursor.fetchone()
            conn.close()
            
            total_balance = row[0] if row[0] else 0.0
            total_deals = row[1] if row[1] else 0

            bot.send_message(
                call.message.chat.id,
                f"📊 <b>إحصائيات البوت الشاملة:</b>\n\n👥 المستخدمين: <b>{total_users}</b>\n🤝 إجمالي الصفقات: <b>{total_deals}</b>\n💰 إجمالي الأرصدة: <b>${total_balance:.2f}</b>",
                parse_mode="HTML"
            )

        elif data == "admin_broadcast":
            if is_admin != 1:
                return
            bot.answer_callback_query(call.id)
            user_states[user_id] = "waiting_for_broadcast"
            bot.send_message(call.message.chat.id, "📢 أرسل الرسالة الآن ليتم إذاعتها لجميع المستخدمين:")

        elif data == "main_menu":
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("📥 التحميل الشامل", callback_data="media_tools"),
                InlineKeyboardButton("🛡 خدمات الوسيط والأمان", callback_data="escrow_tools"),
                InlineKeyboardButton("👤 حسابك والأرصدة", callback_data="user_profile"),
                InlineKeyboardButton("📜 شروط وقواعد الاستخدام", callback_data="terms_rules")
            )
            if is_admin == 1:
                markup.add(InlineKeyboardButton("⚙ لوحة تحكم المشرف", callback_data="admin_panel"))
            bot.edit_message_text("القائمة الرئيسية:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        print(f"Error in callback_query: {e}")

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_messages(message):
    user_id = message.from_user.id
    user_first_name = message.from_user.first_name
    username = message.from_user.username or "لا يوجد"
    state = user_states.get(user_id)

    user_info = get_user(user_id, username)
    is_admin = user_info["is_admin"]
    admin_chat_id = get_admin_id()

    if is_admin == 1 and state == "waiting_for_custom_amount" and message.text:
        user_states.pop(user_id, None)
        try:
            amount = float(message.text.strip())
            target_user = pending_recharge_approvals.get(user_id)
            if target_user:
                update_user_balance(target_user, amount)
                bot.reply_to(message, f"✅ تمت إضافة مبلغ <b>${amount:.2f}</b> بنجاح للمستخدم (ID: <code>{target_user}</code>).", parse_mode="HTML")
                try:
                    bot.send_message(target_user, f"🎉 <b>تم قبول إيصال التحويل وشحن رصيدك بمبلغ:</b> ${amount:.2f}", parse_mode="HTML")
                except:
                    pass
                pending_recharge_approvals.pop(user_id, None)
            else:
                bot.reply_to(message, "⚠️ حدث خطأ في تحديد المستخدم.")
        except ValueError:
            bot.reply_to(message, "⚠️ يرجى إرسال رقم صحيح للمبلغ (مثال: <code>10</code>).", parse_mode="HTML")
        return

    if state == "waiting_for_deal_details" and message.text:
        user_states.pop(user_id, None)
        deal_text = message.text
        deal_id = add_deal_record(user_id, deal_text)
        
        bot.reply_to(message, f"✅ تم تسجيل طلب الصفقة برقم <b>#{deal_id}</b> وإرساله للإدارة للمتابعة.", parse_mode="HTML")
        
        admin_message = (
            f"🚨 <b>طلب صفقة وساطة جديد #{deal_id}!</b>\n\n"
            f"👤 المرسل: {user_first_name}\n"
            f"🔗 المعرف: @{username} (ID: <code>{user_id}</code>)\n\n"
            f"📝 <b>التفاصيل:</b>\n{deal_text}"
        )
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ قبول الصفقة", callback_data=f"approve_deal_{deal_id}_{user_id}"),
            InlineKeyboardButton("❌ رفض الصفقة", callback_data=f"reject_deal_{deal_id}_{user_id}")
        )
        
        if admin_chat_id:
            try:
                bot.send_message(admin_chat_id, admin_message, parse_mode="HTML", reply_markup=markup)
            except Exception as e:
                print(f"Error sending deal to admin: {e}")
        return

    if state == "waiting_for_receipt" and (message.photo or message.document):
        user_states.pop(user_id, None)
        bot.reply_to(message, "✅ تم استلام الإيصال وإرساله للإدارة للمراجعة والشحن الفوري.")
        
        caption_text = (
            f"💳 <b>طلب شحن رصيد جديد (إيصال)!</b>\n\n"
            f"👤 المرسل: {user_first_name}\n"
            f"🔗 المعرف: @{username} (ID: <code>{user_id}</code>)"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ قبول وشحن", callback_data=f"approve_recharge_{user_id}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject_recharge_{user_id}")
        )
        
        if admin_chat_id:
            try:
                if message.photo:
                    bot.send_photo(chat_id=admin_chat_id, photo=message.photo[-1].file_id, caption=caption_text, parse_mode="HTML", reply_markup=markup)
                elif message.document:
                    bot.send_document(chat_id=admin_chat_id, document=message.document.file_id, caption=caption_text, parse_mode="HTML", reply_markup=markup)
            except Exception as e:
                print(f"❌ خطأ أثناء إرسال الإيصال للمشرف: {e}")
        return

    if is_admin == 1 and state == "waiting_for_broadcast":
        user_states.pop(user_id, None)
        users = get_all_users()
        success_count = 0
        
        bot.reply_to(message, "🚀 جاري بدء الإذاعة لجميع المستخدمين...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                success_count += 1
            except:
                pass
        bot.reply_to(message, f"✅ تمت الإذاعة بنجاح إلى <b>{success_count}</b> مستخدم.", parse_mode="HTML")
        return

    if is_admin == 1 and message.text and message.text.startswith("/add"):
        try:
            parts = message.text.split()
            target_user = int(parts[1])
            amount = float(parts[2])
            update_user_balance(target_user, amount)
            bot.reply_to(message, f"✅ تمت إضافة ${amount} للمستخدم {target_user}")
            try:
                bot.send_message(target_user, f"🎉 <b>تم شحن حسابك بنجاح بمبلغ:</b> ${amount:.2f}", parse_mode="HTML")
            except:
                pass
        except Exception as e:
            bot.reply_to(message, f"خطأ في الصيغة. استخدم:\n`/add ID AMOUNT`")
        return

    if not message.text or not ("http://" in message.text or "https://" in message.text):
        if message.text and not message.text.startswith('/'):
            bot.reply_to(message, "⚠️ يرجى استخدام الأزرار في القائمة أو إرسال رابط صحيح للتحميل.")
        return

    current_time = time.time()
    if is_admin != 1:
        if user_id in last_request_time and (current_time - last_request_time[user_id]) < 4:
            bot.reply_to(message, "⚠ برجاء الانتظار بضع ثوانٍ قبل إرسال رابط تحميل آخر.")
            return
    last_request_time[user_id] = current_time

    url = message.text.strip()
    msg = bot.reply_to(message, "⏳ <b>جاري تحليل وتحميل الوسائط بدقة عالية...</b>", parse_mode="HTML")
    
    output_template = "downloaded_media"
    ydl_opts = {
        'outtmpl': f'{output_template}.%(ext)s',
        'max_filesize': 50 * 1024 * 1024,
    }

    try:
        for ext in ['mp4', 'mkv', 'webm', 'jpg', 'png', 'webp']:
            if os.path.exists(f"{output_template}.{ext}"):
                os.remove(f"{output_template}.{ext}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)

        if os.path.exists(filename):
            bot.edit_message_text("📤 <b>جاري إرسال الملف لك...</b>", message.chat.id, msg.message_id, parse_mode="HTML")
            file_extension = filename.split('.')[-1].lower()
            with open(filename, 'rb') as f:
                if file_extension in ['jpg', 'jpeg', 'png', 'webp']:
                    bot.send_photo(message.chat.id, f, caption="✅ تم التحميل بنجاح!")
                else:
                    bot.send_video(message.chat.id, f, caption="✅ تم التحميل بنجاح!")
            os.remove(filename)
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ لم يتم العثور على الملف.", message.chat.id, msg.message_id)

    except Exception as e:
            bot.edit_message_text(f"❌ حدث خطأ أثناء التحميل:\n<code>{str(e)}</code>", message.chat.id, msg.message_id, parse_mode="HTML")

print("Ultimate Super Bot with Permanent Admin ID is running...")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
    except Exception as e:
        time.sleep(3)
        continue
