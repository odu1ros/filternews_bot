import asyncio
from telethon import TelegramClient, events
import config
import database as db
from filter_engine import FilterEngine

# Using the scanner session
client = TelegramClient("scanner_session", config.API_ID, config.API_HASH)
engine = FilterEngine()

def clean_text(text):
    """
    Guard against Unicode issues by cleaning the text
    """
    if not text: return ""
    try:
        return text.encode('utf-8', 'ignore').decode('utf-8')
    except:
        return ""

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    """
    Handle incoming messages from subscribed channels, 
    apply filters and deduplication,
    and queue notifications for users.
    """
    # check if message is from a channel (not private chat)
    if not event.is_channel:
        return

    # try to get username
    chat = await event.get_chat()
    if not chat.username:
        return
        
    chat_username = chat.username.lower()
    text = event.text or event.message.message
    text = clean_text(text)
    
    if not text: return

    # check if the source has subs
    subscribers = await db.get_users_for_source(chat_username)
    if not subscribers: return

    # debug with scores
    print(f">>> [SCANNER] Message at @{chat_username}")
    print(f"Message: {text[:50]}...")

    for user_id in subscribers:
        # check filters
        filters = await db.get_user_filters(user_id)
        matched, reason = await engine.process_message(text, filters)
        
        if matched:
            # --- DUP CHECK ---
            print(f"   -> Preliminary match. Check for duplicates for user {user_id}...")
            
            history = await db.get_user_history(user_id)
            is_dup = await engine.is_duplicate(text, history)
            
            if is_dup:
                print(f"   -> CANCELLED. Duplicate detected.")
            else:
                print(f"   -> ACCEPTED. Queuing notification.")
                
                link = f"https://t.me/{chat_username}/{event.id}"
                
                # queue notification
                await db.add_notification(user_id, text, chat_username, reason, link)
                
                # add to history
                await db.add_to_history(user_id, text)

    # history cleanup occasionally
    if event.id % 50 == 0:
        await db.cleanup_history()

async def main():
    await db.init_db()
    print("Run SCANNER.PY")
    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())