from __future__ import annotations

import networkx as nx
import pandas as pd


def build_interaction_graph(df: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for row in df.itertuples(index=False):
        graph.add_node(row.source)
        graph.add_node(row.target)
        weight = getattr(row, "severity", 0.1) + getattr(row, "graph_score", 0.1)
        graph.add_edge(row.source, row.target, weight=float(weight), phase=row.phase, scenario=row.scenario)
    return graph


def graph_scores(graph: nx.DiGraph) -> dict[str, float]:
    if graph.number_of_nodes() == 0:
        return {}
    centrality = nx.pagerank(graph, alpha=0.9)
    max_score = max(centrality.values()) or 1.0
    return {node: score / max_score for node, score in centrality.items()}


def attach_graph_scores(df: pd.DataFrame, graph: nx.DiGraph) -> pd.DataFrame:
    scores = graph_scores(graph)
    enriched = df.copy()
    enriched["source_graph_rank"] = enriched["source"].map(scores).fillna(0.0)
    enriched["target_graph_rank"] = enriched["target"].map(scores).fillna(0.0)
    enriched["graph_score"] = ((enriched["graph_score"] + enriched["source_graph_rank"] + enriched["target_graph_rank"]) / 3.0).clip(0.0, 1.0)
    return enriched

