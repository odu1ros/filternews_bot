import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
import database as db
import platform

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- TEXTS ---

TEXT_START = (
    "👋 <b>Hi! I am the news filter bot.</b>\n\n"
    "I read news for you. I use neural networks to:\n"
    "1. Understand the meaning of the text.\n"
    "2. Filter out news duplicates to avoid sending the same news twice.\n\n"
    "<b>👇 Your tools:</b>\n\n"
    "📢 <b>Channels:</b>\n"
    "/add_channel @ссылка - Subscribe channel\n"
    "/list_channels - Get the list of subscribed channels\n\n"
    "✅ <b>Filters:</b>\n"
    "/add_keyword &lt;word&gt; - Exact match\n"
    "/add_topic &lt;topic&gt; - Filter by meaning (AI)\n"
    "/list_keywords - My words\n"
    "/list_topics - My topics\n\n"
    "⛔ <b>Blacklist:</b>\n"
    "/add_block &lt;word&gt; - Hide posts with this word\n"
    "/list_blocks - List of blocked words\n\n"
    "⚙️ <b>Other:</b>\n"
    "/clear_all - Full reset of all data\n"
    "/help - Help\n\n"
)

TEXT_HELP = (
    "<b>Bot commands:</b>\n\n"
    "<b>📢 Channels:</b>\n"
    "/add_channel @channel\n"
    "/remove_channel @channel\n"
    "/list_channels\n\n"
    "<b>✅ Filters (Enabled):</b>\n"
    "/add_keyword &lt;word&gt;\n"
    "/remove_keyword &lt;word&gt;\n"
    "/add_topic &lt;topic&gt;\n"
    "/remove_topic &lt;topic&gt;\n\n"
    "<b>⛔ Filters (Disabled):</b>\n"
    "/add_block &lt;word&gt;\n"
    "/remove_block &lt;word&gt;\n"
    "/list_blocks\n\n"
    "<b>🗑 Reset settings:</b>\n"
    "/clear_all"
)

# --- HANDLERS ---

@dp.message(Command("start"))
async def start(m: types.Message):
    await db.add_user(m.from_user.id)
    await m.answer(TEXT_START, parse_mode="HTML")

@dp.message(Command("help"))
async def help_cmd(m: types.Message):
    await m.answer(TEXT_HELP, parse_mode="HTML")

# --- ADDING ---

@dp.message(Command("add_channel"))
async def add_ch(m: types.Message):
    args = m.text.split()
    if len(args) < 2: return await m.answer("⚠️ Write the channel username. \
                                            Example: /add_channel @mash")
    ch = args[1].lower().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').replace('@', '')
    if not ch: return await m.answer("⚠️ Write the channel username. \
                                     \nExample: /add_channel @mash")
    sid = await db.add_source(ch)
    await db.subscribe_user(m.from_user.id, sid)
    await m.answer(f"✅ Channel added: @{ch}")

@dp.message(Command("add_keyword"))
async def add_kw(m: types.Message):
    kw = m.text.replace("/add_keyword", "").strip().lower()
    if not kw: return await m.answer("⚠️ Write the word.\
                                     \nExample: /add_keyword kitten")
    await db.add_filter(m.from_user.id, 'keyword', kw)
    await m.answer(f"✅ Filter added: {kw}")

@dp.message(Command("add_topic"))
async def add_top(m: types.Message):
    topic = m.text.replace("/add_topic", "").strip()
    if not topic: return await m.answer("⚠️ Write the topic.\
                                        \nExample: /add_topic politics")
    await db.add_filter(m.from_user.id, 'topic', topic)
    await m.answer(f"✅ Topic added: {topic}")

@dp.message(Command("add_block"))
async def add_blk(m: types.Message):
    block = m.text.replace("/add_block", "").strip().lower()
    if not block: return await m.answer("⚠️ Write the word to ban.\
                                        \nExample: /add_block spoiler")
    await db.add_filter(m.from_user.id, 'block', block)
    await m.answer(f"⛔ Word '{block}' added to the blacklist.")

# --- REMOVING ---

@dp.message(Command("remove_channel"))
async def rm_ch(m: types.Message):
    args = m.text.split()
    if len(args) < 2: return await m.answer("⚠️ Write the channel username.\
                                            Example: /remove_channel @mash")
    ch = args[1].replace('@', '').lower()
    if await db.remove_subscription(m.from_user.id, ch):
        await m.answer(f"🗑 Unsubscribed from @{ch}")
    else:
        await m.answer("❌ Channel not found.")

@dp.message(Command("remove_keyword"))
async def rm_kw(m: types.Message):
    kw = m.text.replace("/remove_keyword", "").strip().lower()
    if not kw: return await m.answer("⚠️ Write the word.\
                                     \nExample: /remove_keyword kitten")
    await db.remove_filter(m.from_user.id, 'keyword', kw)
    await m.answer(f"🗑 Removed word: {kw}")

@dp.message(Command("remove_topic"))
async def rm_top(m: types.Message):
    topic = m.text.replace("/remove_topic", "").strip()
    if not topic: return await m.answer("⚠️ Write the topic.\
                                        \nExample: /remove_topic politics")
    await db.remove_filter(m.from_user.id, 'topic', topic)
    await m.answer(f"🗑 Removed topic: {topic}")

@dp.message(Command("remove_block"))
async def rm_blk(m: types.Message):
    blk = m.text.replace("/remove_block", "").strip().lower()
    if not blk: return await m.answer("⚠️ Write the word to unban.\
                                      \nExample: /remove_block spoiler")
    await db.remove_filter(m.from_user.id, 'block', blk)
    await m.answer(f"🗑 Unblocked word: {blk}")

@dp.message(Command("clear_all"))
async def clear_all(m: types.Message):
    await db.clear_all_data(m.from_user.id)
    await m.answer("🔄 Full reset completed.")

# --- UI ---
# main builder
def build_kb(items, prefix, is_link=False):
    builder = []
    for item in items:
        row = []

        # --- LEFT BUTTON (text or link) ---
        if is_link:
            # if channel, make it a link
            clean_name = item.replace("@", "").strip()
            left_btn = InlineKeyboardButton(
                text=f"{item}", 
                url=f"https://t.me/{clean_name}"
            )
        else:
            # if not, just text
            left_btn = InlineKeyboardButton(
                text=f"{item}", 
                callback_data="ignore"
            )

        # --- RIGHT BUTTON (delete) ---
        callback_val = item[:20]

        del_btn = InlineKeyboardButton(
            text="❌", 
            callback_data=f"del:{prefix}:{callback_val}"
        )
        
        row.append(left_btn)
        row.append(del_btn)
        
        builder.append(row)
        
    return InlineKeyboardMarkup(inline_keyboard=builder)

# specific lists
@dp.message(Command("list_channels"))
async def list_ch_ui(m: types.Message):
    ch = await db.get_user_subscriptions_names(m.from_user.id)
    if not ch: return await m.answer("⚠️ No channels.")
    await m.answer(
        "📋 <b>Your channels:</b>\n<i>Click on the name to go to the channel, or on the cross to delete.</i>", 
        reply_markup=build_kb(ch, "ch", is_link=True), 
        parse_mode="HTML"
    )

@dp.message(Command("list_keywords"))
async def list_kw_ui(m: types.Message):
    filters = await db.get_user_filters(m.from_user.id)
    kws = [val for f_type, val in filters if f_type == 'keyword']
    if not kws: return await m.answer("⚠️ No keywords.")
    await m.answer("📋 <b>Keywords:</b>\n<i>Click on the cross to delete.</i>", reply_markup=build_kb(kws, "kw"), parse_mode="HTML")

@dp.message(Command("list_topics"))
async def list_top_ui(m: types.Message):
    filters = await db.get_user_filters(m.from_user.id)
    topics = [val for f_type, val in filters if f_type == 'topic']
    if not topics: return await m.answer("⚠️ No topics.")    
    await m.answer("📋 <b>Topics:</b>\n<i>Click on the cross to delete.</i>", reply_markup=build_kb(topics, "top"), parse_mode="HTML")

@dp.message(Command("list_blocks"))
async def list_blk_ui(m: types.Message):
    filters = await db.get_user_filters(m.from_user.id)
    blks = [val for f_type, val in filters if f_type == 'block']
    if not blks: return await m.answer("⚠️ No blocked words.")
    await m.answer("📋 <b>Blocked words:</b>\n<i>Click on the cross to delete.</i>", reply_markup=build_kb(blks, "blk"), parse_mode="HTML")

# --- CALLBACKS ---
@dp.callback_query(F.data == "ignore")
async def ignore_callback(cb: CallbackQuery):
    # removes loading state (when unclickable buttons pressed)
    await cb.answer()

@dp.callback_query(F.data.startswith("del:"))
async def process_del(cb: CallbackQuery):
    """
    Delete item (channel or filter) based on callback data
    """
    _, code, callback_val = cb.data.split(":", 2)
    uid = cb.from_user.id
    
    item_to_delete = None
    
    # channels
    if code == "ch":
        current_list = await db.get_user_subscriptions_names(uid)
        
        # match by starting substring
        # callback_val is first 20 chars of string
        # required to avoid issues with long names when building buttons
        for item in current_list:
            if item[:20] == callback_val:
                item_to_delete = item
                break
        
        # delete if found
        if item_to_delete:
            await db.remove_subscription(uid, item_to_delete)
            new_list = await db.get_user_subscriptions_names(uid)
            if new_list:
                await cb.message.edit_reply_markup(reply_markup=build_kb(new_list, "ch", is_link=True))
            else:
                await cb.message.edit_text("⚠️ No channels.")
            await cb.answer(f"Deleted {item_to_delete}")
        else:
            await cb.answer("⚠️ Not found.")
    
    # filters
    else:
        f_map = {'kw': 'keyword', 'top': 'topic', 'blk': 'block'}
        f_type = f_map.get(code)
        
        if f_type:
            filters = await db.get_user_filters(uid)

            target_items = [v for t, v in filters if t == f_type]
            
            # match by starting substring
            # callback_val is first 20 chars of string
            # required to avoid issues with long names when building buttons
            for item in target_items:
                if item[:20] == callback_val:
                    item_to_delete = item
                    break
            
            if item_to_delete:
                await db.remove_filter(uid, f_type, item_to_delete)
                
                new_filters = await db.get_user_filters(uid)
                items = [v for t, v in new_filters if t == f_type]
                
                if items:
                    await cb.message.edit_reply_markup(reply_markup=build_kb(items, code))
                else:
                    await cb.message.edit_text("⚠️ The list is empty.")
                await cb.answer("Deleted!")
            else:
                await cb.answer("⚠️ Not found.")

# --- NOTIFICATION WORKER ---

async def notification_worker():
    print("Notification worker started")
    while True:
        notifications = await db.get_and_clear_notifications()
        
        for note in notifications:
            user_id, text, source, reason, link = note[1], note[2], note[3], note[4], note[5]
            
            try:
                await bot.send_message(
                    user_id, 
                    f"🔔 <b>New news for you!</b>\
                        \n<u>{reason}</u>\
                        \nSource: @{source}\
                        \n\n{text[:300]}\n\n\
                        🔗 <a href=\"{link}\"><b>Read original</b></a>", 
                    parse_mode="HTML"
                )
                
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error sending: {e}")
        
        await asyncio.sleep(2)

async def main():
    await db.init_db()
    asyncio.create_task(notification_worker())
    
    print("Running BOT.PY")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())