import numpy as np
from sentence_transformers import SentenceTransformer

# First run downloads ~80MB of weights, then caches them locally forever.
model = SentenceTransformer("all-MiniLM-L6-v2")

sentences = [
    "On weekends I get time for myself.",   # 0
    "We have little party at our home where we can relax and eat.",# 1  (same meaning, different words)
    "Elderly are walking on the sidewalk near the lake.",           # 2  (unrelated civic topic)
    "I baked sourdough bread on Sunday morning.",                    # 3  (unrelated, non-civic)
]

vecs = model.encode(sentences, normalize_embeddings=True)

# Because vectors are normalized, cosine similarity == dot product.
def cos(a, b):
    return float(np.dot(a, b))

print("0 vs 1 (paraphrase):    ", round(cos(vecs[0], vecs[1]), 3))
print("0 vs 2 (both civic):    ", round(cos(vecs[0], vecs[2]), 3))
print("0 vs 3 (totally off):   ", round(cos(vecs[0], vecs[3]), 3))