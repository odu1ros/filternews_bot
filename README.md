# filternews_bot

0. change your credentials in `.env` file
1. `pip install -r requirements.txt`

   NOTE: torch --index_url is for cu128 nightly build
2. run in the first terminal:

   `py manager.py`

   NOTE: at the first run you will be asked of your telegram credentials (phone number, then verification code)
3. 
   
   `py scanner.py`

   NOTE1: at the first run model weights will be loaded. it might take time

   NOTE2: at the first run you will be asked of your telegram credentials (phone number, then verification code) because it uses another session
4. open fresh terminal (do not close previous):
5. 
   `py bot.py`

at this point you are set up. enjoy terminal logs!