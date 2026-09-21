"""
Embedding Engine — Zero-Hardcode Semantic Matching
===================================================
Uses semantic vector embeddings and cosine similarity to map transaction 
narrations to client ledgers without hardcoded keywords.

Supports:
1. Google text-embedding-004 (online high-precision API with LRU cache)
2. Character/Word N-gram Cosine Similarity Vectorizer (fast offline fallback)
"""

import math
import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Tuple, Optional

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

class TextEmbeddingEngine:
    """
    Semantic Embedding Engine for Ledger Mapping.
    Combines fast local N-gram filtering with Google text-embedding-004.
    """

    def __init__(self, api_key: str = "", model_name: str = "models/text-embedding-004"):
        self.api_key = api_key
        self.model_name = model_name
        self._vector_cache = {}  # text -> vector (in-memory LRU cache)

    def _get_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        try:
            from core.config import get_gemini_api_key_pool
            keys = get_gemini_api_key_pool()
            if keys:
                return keys[0]
        except Exception:
            pass
        return ""

    def get_gemini_embedding(self, text: str) -> Optional[List[float]]:
        """
        Fetches text-embedding-004 float vector from Google Gemini REST API.
        Uses in-memory cache to eliminate duplicate API requests.
        """
        clean_text = text.strip()
        if not clean_text:
            return None
        if clean_text in self._vector_cache:
            return self._vector_cache[clean_text]

        key = self._get_api_key()
        if not key:
            return None

        model_path = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:embedContent?key={key}"
        payload = json.dumps({
            "model": model_path,
            "content": {"parts": [{"text": clean_text}]}
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "MiracleAutoEntry/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        # Store in cache (limit max cache size to 2000 entries)
                        if len(self._vector_cache) > 2000:
                            self._vector_cache.clear()
                        self._vector_cache[clean_text] = values
                        return values
        except Exception:
            pass
        return None

    def _normalize_phonetic(self, text: str) -> str:
        """Applies Indian accounting phonetic normalization (V/W, EE/I, OU/AU, etc.)."""
        t = text.upper()
        t = re.sub(r'\bSHREE\b|\bSHRI\b', 'SRI', t)
        t = re.sub(r'W', 'V', t)
        t = re.sub(r'EE', 'I', t)
        t = re.sub(r'OU', 'AU', t)
        t = re.sub(r'CHH', 'CH', t)
        t = re.sub(r'PH', 'F', t)
        t = re.sub(r'SHT', 'ST', t)
        t = re.sub(r'ENTERPRISE[S]?', 'ENT', t)
        t = re.sub(r'TRADER[S]?', 'TRD', t)
        t = re.sub(r'TRADING', 'TRD', t)
        t = re.sub(r'COMPANY|CO\b', 'CO', t)
        t = re.sub(r'LIMITED|LTD\b', 'LTD', t)
        t = re.sub(r'PRIVATE|PVT\b', 'PVT', t)
        return re.sub(r'[^A-Z0-9\s]', ' ', t).strip()

    def _get_ngram_vector(self, text: str) -> Dict[str, float]:
        """Offline n-gram character/word TF vectorizer with Indian phonetic normalization."""
        norm_text = self._normalize_phonetic(text)
        words = [w for w in norm_text.split() if len(w) >= 2]
        features = {}
        
        # Word n-grams & char 3-grams
        for w in words:
            features[w] = features.get(w, 0) + 3.0
            for i in range(len(w) - 2):
                gram = w[i:i+3]
                features[gram] = features.get(gram, 0) + 1.0
                
        return features

    def compute_similarity_offline(self, text1: str, text2: str) -> float:
        """Fast offline character/word overlap cosine similarity with word boost."""
        f1 = self._get_ngram_vector(text1)
        f2 = self._get_ngram_vector(text2)
        
        all_keys = set(f1.keys()) | set(f2.keys())
        if not all_keys:
            return 0.0
            
        dot = sum(f1.get(k, 0) * f2.get(k, 0) for k in all_keys)
        n1 = math.sqrt(sum(v * v for v in f1.values()))
        n2 = math.sqrt(sum(v * v for v in f2.values()))
        if n1 == 0 or n2 == 0:
            return 0.0
        
        base_cos = dot / (n1 * n2)

        # Phonetic Word Token Overlap Boost (e.g. 'BHAGVATI' matches 'BHAGWATI')
        norm1 = self._normalize_phonetic(text1)
        norm2 = self._normalize_phonetic(text2)
        words1 = set(w for w in norm1.split() if len(w) >= 3)
        words2 = set(w for w in norm2.split() if len(w) >= 3)
        shared_words = words1.intersection(words2)
        
        boost = 0.0
        if shared_words:
            boost = 0.20 * len(shared_words)

        return min(1.0, base_cos + boost)

    def find_best_semantic_match(
        self, 
        narration: str, 
        existing_ledgers: List[str], 
        cutoff: float = 0.50
    ) -> Tuple[Optional[str], float]:
        """
        Finds the closest ledger for a narration using 2-Step Hybrid Embedding Engine:
        Step 1: Fast local N-gram cosine similarity filtering (0ms, 0 cost).
        Step 2: If score is intermediate, verify top candidates with Google text-embedding-004.
        Returns: (best_ledger_name, match_score)
        """
        if not narration or not existing_ledgers:
            return None, 0.0

        clean_narr = narration.strip()
        if not clean_narr:
            return None, 0.0

        # Step 1: Local N-Gram Fast Filter across all candidate ledgers
        scored_candidates = []
        for ledger in existing_ledgers:
            if not ledger:
                continue
            ledger_str = ledger.get('name') or ledger.get('print_name') or '' if isinstance(ledger, dict) else str(ledger)
            ledger_str = ledger_str.strip()
            if not ledger_str:
                continue
            sim = self.compute_similarity_offline(clean_narr, ledger_str)
            scored_candidates.append((ledger_str, sim))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        if not scored_candidates:
            return None, 0.0

        best_offline_ledger, best_offline_score = scored_candidates[0]

        # High Confidence Local Match (>= 0.85): Accept instantly (0ms, $0 cost)
        if best_offline_score >= 0.85:
            return best_offline_ledger, best_offline_score

        # Step 2: Intermediate Confidence (0.45 - 0.84): Elevate Top 3 candidates to Gemini Embedding
        top_candidates = [item[0] for item in scored_candidates[:3] if item[1] >= 0.35]
        if top_candidates:
            narr_vec = self.get_gemini_embedding(clean_narr)
            if narr_vec:
                best_gemini_ledger = None
                best_gemini_score = 0.0
                for cand in top_candidates:
                    cand_vec = self.get_gemini_embedding(cand)
                    if cand_vec:
                        g_sim = cosine_similarity(narr_vec, cand_vec)
                        if g_sim > best_gemini_score:
                            best_gemini_score = g_sim
                            best_gemini_ledger = cand

                if best_gemini_ledger and best_gemini_score >= cutoff:
                    return best_gemini_ledger, best_gemini_score

        # Fallback to best offline match if offline score meets cutoff
        if best_offline_score >= cutoff:
            return best_offline_ledger, best_offline_score

        return None, best_offline_score

