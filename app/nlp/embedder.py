import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Union
import logging
import pickle

logger = logging.getLogger(__name__)

class TextEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the text embedder with sentence-transformers model.
        Using all-MiniLM-L6-v2 as specified in the README for Phase 0.
        """
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise
    
    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            return np.zeros(self.model.get_sentence_embedding_dimension())
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return np.zeros(self.model.get_sentence_embedding_dimension())
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return np.array([])
        
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            return np.zeros((len(texts), self.model.get_sentence_embedding_dimension()))
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts."""
        emb1 = self.embed_text(text1)
        emb2 = self.embed_text(text2)
        
        # Normalize embeddings
        emb1_norm = emb1 / (np.linalg.norm(emb1) + 1e-8)
        emb2_norm = emb2 / (np.linalg.norm(emb2) + 1e-8)
        
        return np.dot(emb1_norm, emb2_norm)
    
    def find_most_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[tuple]:
        """Find most similar texts to a query."""
        if not candidates:
            return []
        
        query_embedding = self.embed_text(query)
        candidate_embeddings = self.embed_batch(candidates)
        
        # Calculate similarities
        similarities = []
        for i, candidate_emb in enumerate(candidate_embeddings):
            # Normalize
            candidate_norm = candidate_emb / (np.linalg.norm(candidate_emb) + 1e-8)
            query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
            
            sim = np.dot(query_norm, candidate_norm)
            similarities.append((candidates[i], sim, i))
        
        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def embedding_to_bytes(self, embedding: np.ndarray) -> bytes:
        """Convert numpy array to bytes for database storage."""
        return pickle.dumps(embedding)
    
    def bytes_to_embedding(self, embedding_bytes: bytes) -> np.ndarray:
        """Convert bytes back to numpy array from database."""
        return pickle.loads(embedding_bytes) 