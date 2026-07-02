"""
Chunk 2 - Retriever
Two functions:
  - build_index(catalog)   : runs once at startup, returns (index, model)
  - retrieve(query, ...)   : runs per request, returns top-k catalog items
"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from config import settings


def build_index(catalog):
    """
    Takes the prepared catalog list.
    Embeds every item's search_text into a vector.
    Stores all vectors in a FAISS index.
    Returns the index and the model (both needed later for retrieval).
    """

    print(f"Loading embedding model: {settings.embedding_model}")
    model = SentenceTransformer(settings.embedding_model)
    # all-MiniLM-L6-v2 is small, fast, and free
    # it converts any text into a vector of 384 numbers
    # similar text = similar vectors

    # Collect the search_text field from every catalog item
    print("Collecting search texts...")
    search_texts = []
    for item in catalog:
        search_texts.append(item["search_text"])

    # Convert all search texts to vectors in one batch call
    # encode() returns a 2D numpy array of shape (377, 384)
    print(f"Embedding {len(search_texts)} catalog items...")
    embeddings = model.encode(search_texts, show_progress_bar=True)

    # FAISS needs float32 specifically - convert just in case
    embeddings = np.array(embeddings, dtype="float32")

    # Create an empty FAISS index
    # 384 is the vector dimension - must match the embedding model output
    # IndexFlatL2 means: store all vectors, use L2 (euclidean) distance
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)

    # Add all 377 vectors to the index
    # FAISS stores them internally and assigns positions 0, 1, 2, ...
    # position 0 = catalog[0], position 1 = catalog[1], and so on
    index.add(embeddings)
    print(f"FAISS index built with {index.ntotal} vectors")

    return index, model


def retrieve(query, index, model, catalog, top_k=settings.top_k):
    """
    Takes a user query string.
    Converts it to a vector using the same model.
    Asks FAISS which catalog vectors are closest.
    Returns the top_k matching catalog items as a list of dicts.
    """

    # Embed the user query into a vector
    # encode() on a single string returns a 1D array of 384 numbers
    query_vector = model.encode([query])

    # FAISS needs float32 and a 2D array shape (1, 384)
    query_vector = np.array(query_vector, dtype="float32")

    # Search the index
    # distances: how far each result is (lower = more similar)
    # indices:   positions in the catalog list of the top_k matches
    distances, indices = index.search(query_vector, top_k)

    # indices is a 2D array - we only have one query so take row [0]
    top_indices = indices[0]

    # Look up the actual catalog items using the positions FAISS returned
    results = []
    for i in top_indices:
        results.append(catalog[i])

    return results


# --- Manual test - run this file directly to verify it works ---
if __name__ == "__main__":
    # Load the prepared catalog
    with open(settings.resolve_path(settings.prepared_catalog_path), "r") as f:
        catalog = json.load(f)

    # Build the index
    index, model = build_index(catalog)

    # Test queries
    test_queries = [
        "I need to hire a Java developer",
        "entry level call center agents",
        "senior executive leadership selection",
        "graduate management trainees cognitive personality",
        "safety critical plant operators",
    ]

    print("\n--- Retrieval Test ---")
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = retrieve(query, index, model, catalog, top_k=5)
        for r in results:
            print(f"  {r['name']}  [{r['test_type']}]")
