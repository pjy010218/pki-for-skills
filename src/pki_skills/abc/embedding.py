"""
ABC Embeddings using Sentence Transformers.
"""
from abc import ABC, abstractmethod
import numpy as np


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_trace(self, trace_text: str) -> np.ndarray:
        """Convert an execution trace string to a dense vector."""
        pass


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed_trace(self, trace_text: str) -> np.ndarray:
        # Returns a 1D numpy array
        return self.model.encode(trace_text)
