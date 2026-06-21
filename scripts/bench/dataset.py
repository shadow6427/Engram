import numpy as np
from datasets import load_dataset
from sentence_transformers import SentenceTransformer

def load_beir_subset(dataset_name="scifact", max_corpus=5000, max_queries=100):
    print(f"Loading {dataset_name} dataset...")
    # SciFact is small enough for a quick benchmark
    corpus = load_dataset(f"BeIR/{dataset_name}", "corpus", split="corpus")
    queries = load_dataset(f"BeIR/{dataset_name}", "queries", split="queries")
    qrels = load_dataset(f"BeIR/{dataset_name}-qrels", split="test")

    # Limit sizes for faster benching
    corpus = corpus.select(range(min(len(corpus), max_corpus)))
    queries = queries.select(range(min(len(queries), max_queries)))
    
    # Filter qrels to only include our selected queries
    query_ids = set(queries["_id"])
    valid_qrels = [q for q in qrels if q["query-id"] in query_ids]
    
    return {
        "corpus": corpus,
        "queries": queries,
        "qrels": valid_qrels
    }

def embed_texts(texts: list[str], model_name="all-MiniLM-L6-v2") -> np.ndarray:
    print(f"Embedding {len(texts)} texts using {model_name}...")
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    return embeddings
