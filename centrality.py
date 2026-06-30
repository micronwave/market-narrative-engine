import logging

import networkx as nx
import numpy as np

from vector_store import VectorStore

logger = logging.getLogger(__name__)


def build_narrative_graph(
    narratives: list[dict],
    vector_store: VectorStore,
    similarity_threshold: float = 0.40,
    *,
    unrecoverable_missing_ids: set[str] | None = None,
) -> nx.Graph:
    """
    Build an undirected graph where each node is an active narrative.
    An edge is added between two narratives when their centroid cosine
    similarity exceeds similarity_threshold.

    Edge weight is stored as distance (1 - similarity) so that
    betweenness_centrality with weight='weight' treats high-similarity
    pairs as shorter paths, which is the correct semantics for a
    similarity graph.

    For L2-normalized centroid vectors, cosine similarity = dot product.
    """
    graph = nx.Graph()

    for n in narratives:
        graph.add_node(n["narrative_id"])

    if len(narratives) < 2:
        return graph

    # Retrieve centroid vectors for all narratives in one pass.
    narrative_ids = [n["narrative_id"] for n in narratives]
    vectors: dict[str, np.ndarray] = {}
    unrecoverable_missing_ids = unrecoverable_missing_ids or set()
    benign_missing_ids: list[str] = []
    unrecoverable_missing_seen: list[str] = []
    for nid in narrative_ids:
        v = vector_store.get_vector(nid)
        if v is not None:
            vectors[nid] = v.astype(np.float32)
        else:
            if nid in unrecoverable_missing_ids:
                unrecoverable_missing_seen.append(nid)
            else:
                benign_missing_ids.append(nid)

    if unrecoverable_missing_seen:
        logger.warning(
            "Missing centroid vectors after backfill for %d narratives — excluded from graph edges: %s",
            len(unrecoverable_missing_seen),
            ", ".join(unrecoverable_missing_seen[:5]),
        )
    elif benign_missing_ids:
        logger.debug(
            "Missing centroid vectors for %d narratives with no backfill history — excluded from graph edges: %s",
            len(benign_missing_ids),
            ", ".join(benign_missing_ids[:5]),
        )

    ids_with_vecs = list(vectors.keys())
    n_vecs = len(ids_with_vecs)

    # Warn early: O(N²) all-pairs scan is unavoidable here without an ANN index.
    if n_vecs > 500:
        logger.warning(
            "build_narrative_graph: O(N²) similarity scan over %d vectors — "
            "graph build may be slow; consider an ANN index at this scale",
            n_vecs,
        )

    edge_count = 0
    for i in range(n_vecs):
        for j in range(i + 1, n_vecs):
            nid_a = ids_with_vecs[i]
            nid_b = ids_with_vecs[j]
            # Cosine similarity for L2-normalized vectors = dot product.
            sim = float(np.dot(vectors[nid_a], vectors[nid_b]))
            if sim > similarity_threshold:
                # Store distance so betweenness_centrality(weight='weight')
                # treats high-similarity edges as shorter paths.
                graph.add_edge(nid_a, nid_b, weight=1.0 - sim)
                edge_count += 1

    n_components = nx.number_connected_components(graph)
    logger.info(
        "build_narrative_graph: nodes=%d edges=%d components=%d threshold=%.2f",
        graph.number_of_nodes(), edge_count, n_components, similarity_threshold,
    )
    if n_components > 1:
        logger.warning(
            "build_narrative_graph: graph has %d components — %d isolated nodes; "
            "centrality will be 0 for all isolates",
            n_components,
            sum(1 for n in graph.nodes() if graph.degree(n) == 0),
        )

    return graph


def compute_centrality(
    graph: nx.Graph,
    *,
    exact_max_nodes: int = 200,
    approx_k: int = 50,
) -> dict[str, float]:
    """
    Compute betweenness centrality for all narrative nodes.

    Uses weighted shortest paths (weight='weight', where weight = 1 - similarity)
    so that high-similarity edges are preferred paths. Returns networkx's
    size-normalized scores directly — no secondary rescaling — so values are
    comparable across runs and graph sizes.

    Uses exact betweenness for graphs with <= exact_max_nodes nodes.
    Above that threshold, uses approximate betweenness (k pivot nodes, seed=42).
    """
    if graph.number_of_nodes() < 2:
        return {}

    kwargs: dict = {"normalized": True, "weight": "weight"}

    if graph.number_of_nodes() <= exact_max_nodes:
        raw_scores: dict[str, float] = nx.betweenness_centrality(graph, **kwargs)
    else:
        k = min(approx_k, graph.number_of_nodes())
        logger.info(
            "compute_centrality: large graph (%d nodes) — using approximate betweenness (k=%d)",
            graph.number_of_nodes(), k,
        )
        raw_scores = nx.betweenness_centrality(graph, k=k, seed=42, **kwargs)

    return raw_scores


def flag_catalysts(
    centrality_scores: dict[str, float],
    *,
    top_fraction: float = 0.10,
) -> list[str]:
    """
    Return narrative_ids in the top `top_fraction` by centrality score.
    If fewer than 1/top_fraction narratives, return the top 1.
    Returns empty list if centrality_scores is empty or all scores are zero.
    """
    if not centrality_scores:
        return []
    if max(centrality_scores.values()) <= 0.0:
        return []

    n = len(centrality_scores)
    top_count = max(1, int(n * top_fraction))

    sorted_ids = sorted(
        centrality_scores, key=centrality_scores.__getitem__, reverse=True
    )
    return sorted_ids[:top_count]
