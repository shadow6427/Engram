import numpy as np

def calculate_recall(retrieved_ids, ground_truth_ids, k):
    """
    retrieved_ids: list of retrieved document IDs
    ground_truth_ids: set of relevant document IDs
    """
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in ground_truth_ids)
    return hits / len(ground_truth_ids) if ground_truth_ids else 0.0

def calculate_metrics(results):
    """
    results: list of dicts: {"latencies": [...], "recalls": {1: [...], 5: [...], 10: [...]}}
    """
    latencies = np.array(results["latencies"]) * 1000  # convert to ms
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    
    avg_recalls = {
        k: np.mean(results["recalls"][k])
        for k in results["recalls"]
    }
    
    return {
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "recall@1": avg_recalls.get(1, 0.0),
        "recall@5": avg_recalls.get(5, 0.0),
        "recall@10": avg_recalls.get(10, 0.0),
    }
