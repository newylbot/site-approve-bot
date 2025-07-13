import os
import json
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)
from supabase import create_client, Client

# ─── Load ENV ───
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
ADMIN_IDS = [int(os.getenv("ADMIN_CHAT_ID"))]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
SEEN_USER_IDS = set()
admin_page_context = {}
PAGE_SIZE = 5

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ─── Format for /show ───
def format_user_block(user, login_data, include_keyboard=True):
    uid = user["id"]
    name = user.get("name", "(no name)")
    approved = user.get("is_approved", False)
    created = login_data[0]["created_at"] if login_data else "(unknown)"
    email = login_data[0]["email"] if login_data else "(no email)"
    profile_json = json.dumps(user, indent=2)

    keyboard = None
    if include_keyboard:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(
            text=f"Set to {'❌ False' if approved else '✅ True'}",
            callback_data=f"toggle:{uid}:{approved}"
        )]])

    msg = (
        f"<blockquote>🧑 Name: {name}</blockquote>\n"
        f"📧 Email: {email}\n"
        f"🆔 UUID: <code>{uid}</code>\n\n"
        f"📂 user_logins → Created: {created}\n"
        f"📂 users_profile → Approved: {'✅' if approved else '❌'}\n\n"
        f"📝 Full Profile:\n<pre>{profile_json}</pre>"
    )
    return msg, keyboard

# ─── Format for /showall ───
def format_compact_user(user):
    uid = user["id"]
    name = user.get("name", "(no name)")
    approved = user.get("is_approved", False)
    return (
        f"🧑 <b>{name}</b>\n"
        f"✅ Approved: {'✅' if approved else '❌'}\n"
        f"📎 <code>/show {uid}</code>\n"
        "───────────────"
    )

# ─── /start ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "👋 Welcome to Lumino Bot!\n\n"
        "Available commands:\n"
        "/showall – Show all users\n"
        "/show <uuid/email/name> – Search users"
    )

# ─── /show ───
async def show_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("🚫 Access denied.")
        return
    if not context.args:
        await update.effective_message.reply_text("❗Usage: /show <uuid/email/name>")
        return
    query = context.args[0].strip()
    try:
        result = supabase.table("users_profile") \
            .select("*") \
            .or_(f"id.eq.{query},name.ilike.%{query}%,email.ilike.%{query}%") \
            .execute()
        users = result.data
        if not users:
            await update.effective_message.reply_text("❌ No matching user found.")
            return
        for user in users:
            uid = user["id"]
            login_data = supabase.table("user_logins").select("*").eq("id", uid).execute().data
            msg, keyboard = format_user_block(user, login_data)
            await update.effective_message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Error searching user:\n{e}")

# ─── /showall ───
async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text("🚫 Access denied.")
        return
    admin_page_context[user_id] = {
        "page": 0,
        "chat_id": update.effective_chat.id
    }
    await send_user_page(context, user_id)

# ─── Pagination ───
async def handle_page_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("🚫 Not authorized.")
        return
    _, page = query.data.split(":")
    page = int(page)
    admin_page_context[user_id]["page"] = page
    await send_user_page(context, user_id)

# ─── Shared Page Renderer ───
async def send_user_page(context, user_id):
    try:
        chat_id = admin_page_context[user_id]["chat_id"]
        page = admin_page_context[user_id]["page"]
        result = supabase.table("users_profile").select("*").execute()
        users = result.data or []
        total = len(users)
        if total == 0:
            await context.bot.send_message(chat_id=chat_id, text="📭 No users found.")
            return
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_users = users[start:end]
        msg = "\n\n".join([format_compact_user(user) for user in page_users])
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⏮ Prev", callback_data=f"page:{page - 1}"))
        if end < total:
            nav_buttons.append(InlineKeyboardButton("⏭ Next", callback_data=f"page:{page + 1}"))
        if nav_buttons:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📄 Page {page + 1}/{(total - 1) // PAGE_SIZE + 1}",
                reply_markup=InlineKeyboardMarkup([nav_buttons])
            )
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Error loading users:\n{e}")

# ─── Toggle Approval ───
async def toggle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("🚫 Not authorized.")
        return
    try:
        _, uid, current = query.data.split(":")
        new_val = not (current == "True")
        supabase.table("users_profile").update({"is_approved": new_val}).eq("id", uid).execute()
        await asyncio.sleep(0.3)
        supabase.table("approval_logs").insert({
            "admin_id": str(query.from_user.id),
            "admin_name": query.from_user.full_name,
            "target_user_id": uid,
            "new_status": new_val,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).execute()
        user = supabase.table("users_profile").select("*").eq("id", uid).execute().data[0]
        login_data = supabase.table("user_logins").select("*").eq("id", uid).execute().data
        msg, keyboard = format_user_block(user, login_data)
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        await query.edit_message_text(f"⚠️ Failed:\n{e}")

# ─── Login Watcher ───
async def check_new_logins(app):
    while True:
        try:
            result = supabase.table("user_logins").select("*").execute()
            users = result.data or []
            for user in users:
                uid = user["id"]
                if uid in SEEN_USER_IDS:
                    continue
                SEEN_USER_IDS.add(uid)
                profile = supabase.table("users_profile").select("*").eq("id", uid).execute().data
                p = profile[0] if profile else {}
                approved = p.get("is_approved", False)
                name = p.get("name", "(no name)")
                msg = (
                    "🆕 New User Logged In\n\n"
                    f"🧑 Name: {name}\n"
                    f"📧 Email: {user.get('email')}\n"
                    f"🆔 UUID: <code>{uid}</code>\n\n"
                    f"📂 user_logins → Created: {user.get('created_at')}\n"
                    f"📂 users_profile → Approved: {'✅' if approved else '❌'}\n\n"
                    f"🔎 Use <code>/show {uid}</code> to review."
                )
                await app.bot.send_message(chat_id=LOG_CHANNEL_ID, text=msg, parse_mode="HTML")
        except Exception as e:
            print("Login check error:", e)
        await asyncio.sleep(15)

# ─── Start Bot ───
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("show", show_user))
    app.add_handler(CommandHandler("showall", show_all))
    app.add_handler(CallbackQueryHandler(toggle_approval, pattern="^toggle:"))
    app.add_handler(CallbackQueryHandler(handle_page_nav, pattern="^page:"))
    asyncio.get_event_loop().create_task(check_new_logins(app))
    print("🚀 Bot is running...", flush=True)
    app.run_polling()
