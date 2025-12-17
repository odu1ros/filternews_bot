import asyncio
from telethon import TelegramClient, functions, errors
from telethon.tl.types import User, Channel, Chat
import config
import database as db
import time

# manager session name
SESSION_NAME = "manager_session"

async def main():
    print("Running background subscriptions manager")
    
    await db.init_db()
    
    client = TelegramClient(SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start()
    print("Session started")

    current_subscriptions = set()
    last_full_sync = 0
    SYNC_INTERVAL = 600

    while True:
        try:
            # database channels
            target_channels = await db.get_all_sources()
            target_set = {ch.lower() for ch in target_channels}
            
            if not target_set:
                await asyncio.sleep(30)
                continue

            # syncronize with telegram
            now = time.time()
            if now - last_full_sync > SYNC_INTERVAL or not current_subscriptions:
                print("Telegram sync")
                current_subscriptions.clear()
                
                # iterate dialogs
                async for dialog in client.iter_dialogs():
                    if dialog.is_channel and dialog.entity.username:
                        current_subscriptions.add(dialog.entity.username.lower())
                
                last_full_sync = now
                print(f"Current subscriptions: {len(current_subscriptions)}")

            channels_to_join = target_set - current_subscriptions
            
            if not channels_to_join:
                pass
            else:
                print(f"\nFound {len(channels_to_join)} new channels")
                
                for channel in channels_to_join:
                    try:
                        try:
                            entity = await client.get_entity(channel)
                        except ValueError:
                            print("Not found.")
                            continue

                        # if user
                        if isinstance(entity, User):
                            print("Ready to listen the user")
                            current_subscriptions.add(channel)
                            
                        # if channel / chat
                        elif isinstance(entity, (Channel, Chat)):
                            print("Joining channel", end=" ")
                            await client(functions.channels.JoinChannelRequest(channel))
                            print("Done!")
                            current_subscriptions.add(channel)
                        
                        await asyncio.sleep(2)
                        
                    except errors.FloodWaitError as e:
                        print(f"\n   Faced limit, wait {e.seconds} seconds")
                        await asyncio.sleep(e.seconds + 2)
                    except ValueError:
                        print(" Channel entity not found (ValueError).")
                    except Exception as e:
                        print(f" Error: {e}")

        except Exception as e:
            print(f"Global loop error: {e}")
            await asyncio.sleep(5)

        # check database every 30 secs
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())