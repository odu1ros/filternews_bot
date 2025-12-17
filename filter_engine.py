import asyncio
from concurrent.futures import ThreadPoolExecutor
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer, util
import config

class FilterEngine:
    def __init__(self):
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

    # --- SYNC INTERNAL METHODS ---
    def _check_topic_zeroshot(self, text, topic):
        """
        Checks whether the text matches the topic
        Uses either 
            - Zero-Shot Classification or 
            - Vector Similarity
        depending on the length of the topic
        """
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
        
        print(f"👯 Dedup Score: {best_score:.4f}")
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
        return keyword.lower() in text.lower()
    
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
            if self.check_keyword(text, val):
                return True, f"Keyword: {val}"
        
        # topics
        topic_filters = [val for f_type, val in filters if f_type == 'topic']
        for val in topic_filters:
            if await self.check_semantic(analysis_text, val):
                return True, f"Topic: {val}"
        
        return False, None