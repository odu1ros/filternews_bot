import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ML_MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
ML_MODEL_NAME_TOPICS = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"