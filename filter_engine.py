import asyncio
from concurrent.futures import ThreadPoolExecutor
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer, util
import config
import pymorphy3
import re

def remove_emojis_regex(text):
    """
    Removes all the emojis
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+"
    )
    return emoji_pattern.sub(r'', text)

class FilterEngine:
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()
        print("Loading models.")
        # model for deduplication (check whether the news is similar to previous ones)
        self.dedup_model = SentenceTransformer(config.ML_MODEL_NAME)

        # model for topic classification (zero-shot)
        tokenizer = AutoTokenizer.from_pretrained(config.ML_MODEL_NAME_TOPICS)
        model = AutoModelForSequenceClassification.from_pretrained(config.ML_MODEL_NAME_TOPICS)
        self.classifier = pipeline(
            "zero-shot-classification", 
            model=model, 
            tokenizer=tokenizer
        )

        self.executor = ThreadPoolExecutor(max_workers=2)
        print("Models uploaded.")

    # --- LEMMATIZATION HELPER ---
    def _lemmatize_text(self, text):
        """
        Processess text to make it a sequence of normal form of words
        """
        if not text: return ""
        
        # remove commas
        words = re.findall(r'\w+', text.lower())
        
        # lemmatize
        lemmas = [self.morph.parse(word)[0].normal_form for word in words]
        
        return " ".join(lemmas)

    # --- SYNC INTERNAL METHODS ---
    def _check_topic_zeroshot(self, text, topic):
        """
        Checks whether the text matches the topic
        Uses either 
            - Zero-Shot Classification or 
            - Vector Similarity
        depending on the length of the topic
        """
        text = remove_emojis_regex(text).strip()
        words = topic.split()

        # CASE 1: user entered short topic (<= 4 words)
        if len(words) <= 4:            
            result = self.classifier(
                text, 
                candidate_labels=topic, 
                multi_label=True
            )
            score = result['scores'][0]
            print(f"  Zero-Shot (Tag): '{topic}' -> {score:.4f}")
            return score > 0.40

        # CASE 2: user entered long topic (> 4 words)
        else:
            embeddings = self.dedup_model.encode([text, topic], convert_to_tensor=True)
            cosine_score = util.cos_sim(embeddings[0], embeddings[1])
            score = cosine_score.item()
            print(f"  Vector Sim (Long): '{topic[:25]}...' -> {score:.4f}")
            return score > 0.30
    
    def _check_duplicate_sync(self, new_text, history_texts):
        """
        Check whether new_text is a duplicate of any text in history_texts
        using semantic similarity.
        """
        if not history_texts:
            return False
            
        new_emb = self.dedup_model.encode(new_text, convert_to_tensor=True)
        history_embs = self.dedup_model.encode(history_texts, convert_to_tensor=True)
        
        cosine_scores = util.cos_sim(new_emb, history_embs)[0]
        best_score = float(cosine_scores.max())
        
        print(f" Dedup Score: {best_score:.4f}")
        return best_score > 0.85

    # --- ASYNC WRAPPERS ---
    async def check_semantic(self, text, topic):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._check_topic_zeroshot, text, topic)

    async def is_duplicate(self, new_text, history_texts):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self._check_duplicate_sync, new_text, history_texts)

    # --- HELPER METHODS ---
    def check_keyword(self, text, keyword):
        """
        Keyword search with lemmatization
        """
        clean_text = self._lemmatize_text(text)
        clean_keyword = self._lemmatize_text(keyword)

        return clean_keyword in clean_text
    
    # --- MAIN METHOD ---
    async def process_message(self, text, filters):
        if not text: return False, None
        
        # trim text so that models can handle it
        analysis_text = text[:1000] 

        # block filter
        block_filters = [val for f_type, val in filters if f_type == 'block']
        for block_word in block_filters:
            if self.check_keyword(text, block_word):
                return False, None

        # --- CHECK FILTERS ---
        # keywords
        keyword_filters = [val for f_type, val in filters if f_type == 'keyword']
        for val in keyword_filters:
            clean_val = self._lemmatize_text(val)
            if clean_val in lemmatized_text:
                return True, f"Keyword: {val}"
        
        # topics
        topic_filters = [val for f_type, val in filters if f_type == 'topic']
        for val in topic_filters:
            if await self.check_semantic(analysis_text, val):
                return True, f"Topic: {val}"
        
        return False, None