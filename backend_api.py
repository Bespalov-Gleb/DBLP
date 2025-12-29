import csv
import os
import pickle
from typing import Dict, List, Any, Optional, Set, Tuple
import networkx as nx
from flask import Flask, jsonify, request
from flask_cors import CORS
from collections import defaultdict


app = Flask(__name__, static_folder='web_app', static_url_path='')
CORS(app)

DATA_DIR = "data"
coauthorship_graph: Optional[nx.Graph] = None
authors_dict: Dict[int, str] = {}
publications_dict: Dict[int, Dict[str, Any]] = {}
author_to_publications: Dict[int, List[int]] = defaultdict(list)
publication_to_authors: Dict[int, List[int]] = defaultdict(list)
publication_years: Dict[int, int] = {}
publication_venues: Dict[int, str] = {}
community_cache: Dict[str, Dict[int, int]] = {}


def load_data():
    global coauthorship_graph, authors_dict, publications_dict
    global author_to_publications, publication_to_authors
    global publication_years, publication_venues
    
    authors_file = os.path.join(DATA_DIR, "authors.csv")
    with open(authors_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            author_id_str = row.get("author_id", "0")
            author_name = row.get("author_name", "")
            try:
                author_id = int(author_id_str)
                if author_id and author_name:
                    authors_dict[author_id] = author_name
            except ValueError:
                continue
    
    publications_file = os.path.join(DATA_DIR, "publications.csv")
    with open(publications_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pub_id_str = row.get("pub_id", "0")
            try:
                pub_id = int(pub_id_str)
                if pub_id:
                    year_str = row.get("year", "0")
                    try:
                        year = int(year_str)
                        publications_dict[pub_id] = {
                            "title": row.get("title", ""),
                            "year": year,
                            "venue": row.get("venue", ""),
                            "type": row.get("type", "")
                        }
                        publication_years[pub_id] = year
                        publication_venues[pub_id] = row.get("venue", "")
                    except ValueError:
                        continue
            except ValueError:
                continue
    
    authorship_file = os.path.join(DATA_DIR, "authorship.csv")
    with open(authorship_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pub_id_str = row.get("pub_id", "0")
            author_id_str = row.get("author_id", "0")
            try:
                pub_id = int(pub_id_str)
                author_id = int(author_id_str)
                if pub_id and author_id:
                    author_to_publications[author_id].append(pub_id)
                    publication_to_authors[pub_id].append(author_id)
            except ValueError:
                continue
    
    graph_file_pickle = os.path.join(DATA_DIR, "coauthorship_graph.pkl")
    graph_file_graphml = os.path.join(DATA_DIR, "coauthorship_graph.graphml")
    
    if os.path.exists(graph_file_pickle):
        with open(graph_file_pickle, 'rb') as f:
            coauthorship_graph = pickle.load(f)
    elif os.path.exists(graph_file_graphml):
        try:
            coauthorship_graph = nx.read_graphml(graph_file_graphml, node_type=int)
            with open(graph_file_pickle, 'wb') as f:
                pickle.dump(coauthorship_graph, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(f"ОШИБКА: GraphML файл поврежден: {e}")
            try:
                os.remove(graph_file_graphml)
            except (OSError, IOError):
                pass
            coauthorship_graph = None
    else:
        coauthorship_graph = None
    
    if coauthorship_graph is None:
        coauthorship_graph = nx.Graph()
        
        for pub_id, authors in publication_to_authors.items():
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    a1, a2 = authors[i], authors[j]
                    if coauthorship_graph.has_edge(a1, a2):
                        coauthorship_graph[a1][a2]["weight"] += 1
                    else:
                        coauthorship_graph.add_edge(a1, a2, weight=1)
        
        with open(graph_file_pickle, 'wb') as f:
            pickle.dump(coauthorship_graph, f, protocol=pickle.HIGHEST_PROTOCOL)


def filter_graph_by_years(year_from: Optional[int], year_to: Optional[int]) -> nx.Graph:
    if coauthorship_graph is None:
        return nx.Graph()
    
    graph = coauthorship_graph
    
    if year_from is None and year_to is None:
        return graph
    
    relevant_pubs: Set[int] = set()
    for pub_id, year in publication_years.items():
        if year_from is not None and year < year_from:
            continue
        if year_to is not None and year > year_to:
            continue
        relevant_pubs.add(pub_id)
    
    relevant_authors: Set[int] = set()
    for pub_id in relevant_pubs:
        authors_list = publication_to_authors.get(pub_id, [])
        relevant_authors.update(authors_list)
    
    filtered_graph = graph.subgraph(relevant_authors).copy()
    return filtered_graph


def filter_graph_by_venue(venue: str) -> nx.Graph:
    if coauthorship_graph is None:
        return nx.Graph()
    
    graph = coauthorship_graph
    
    if not venue:
        return graph
    
    relevant_pubs: Set[int] = set()
    for pub_id, pub_venue in publication_venues.items():
        if venue.lower() in pub_venue.lower():
            relevant_pubs.add(pub_id)
    
    relevant_authors: Set[int] = set()
    for pub_id in relevant_pubs:
        authors_list = publication_to_authors.get(pub_id, [])
        relevant_authors.update(authors_list)
    
    filtered_graph = graph.subgraph(relevant_authors).copy()
    return filtered_graph


def detect_communities(graph: nx.Graph) -> Dict[int, int]:
    """
    Обнаруживает сообщества в графе используя быстрый алгоритм.
    Использует кэширование для ускорения повторных запросов.
    Возвращает словарь: node_id -> community_id
    """
    if graph.number_of_nodes() == 0:
        return {}
    
    num_nodes = graph.number_of_nodes()
    
    nodes_tuple = tuple(sorted(graph.nodes()))
    edges_tuple = tuple(sorted(graph.edges()))
    cache_key = f"{graph.number_of_nodes()}_{graph.number_of_edges()}_{hash(nodes_tuple)}_{hash(edges_tuple)}"
    
    if cache_key in community_cache:
        return community_cache[cache_key]
    
    if num_nodes < 50:
        components = list(nx.connected_components(graph))
        node_to_community: Dict[int, int] = {}
        for community_id, component in enumerate(components):
            for node in component:
                node_to_community[node] = community_id
        community_cache[cache_key] = node_to_community
        return node_to_community
    
    try:
        if num_nodes >= 50:
            if num_nodes > 500:
                try:
                    communities_generator = nx.community.asyn_lpa_communities(graph, seed=42)
                    communities = list(communities_generator)
                except Exception as lpa_error:
                    communities_generator = nx.community.greedy_modularity_communities(graph)
                    communities = list(communities_generator)
            else:
                communities_generator = nx.community.greedy_modularity_communities(graph)
                communities = list(communities_generator)
        else:
            communities = []
        
        node_to_community: Dict[int, int] = {}
        for community_id, community in enumerate(communities):
            for node in community:
                node_to_community[node] = community_id
        
        all_nodes = set(graph.nodes())
        assigned_nodes = set(node_to_community.keys())
        unassigned_nodes = all_nodes - assigned_nodes
        
        if unassigned_nodes:
            next_community_id = len(communities)
            for node in unassigned_nodes:
                node_to_community[node] = next_community_id
                next_community_id += 1
        
        if not node_to_community:
            components = list(nx.connected_components(graph))
            for community_id, component in enumerate(components):
                for node in component:
                    node_to_community[node] = community_id
        
        community_cache[cache_key] = node_to_community
        return node_to_community
    except Exception as e:
        print(f"Ошибка обнаружения сообществ: {e}")
        components = list(nx.connected_components(graph))
        node_to_community: Dict[int, int] = {}
        for community_id, component in enumerate(components):
            for node in component:
                node_to_community[node] = community_id
        community_cache[cache_key] = node_to_community
        return node_to_community


def aggregate_graph(graph: nx.Graph, min_cluster_size: int = 3) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, int]]:
    """
    Агрегирует граф, группируя узлы в кластеры (сообщества).
    Возвращает: (кластеры, связи между кластерами, маппинг узел->кластер)
    """
    if graph.number_of_nodes() == 0:
        return [], [], {}
    
    node_to_community = detect_communities(graph)
    
    clusters: Dict[int, List[int]] = defaultdict(list)
    for node, cluster_id in node_to_community.items():
        clusters[cluster_id].append(node)
    
    large_clusters: Dict[int, List[int]] = {}
    small_nodes: List[int] = []
    
    for cluster_id, nodes in clusters.items():
        if len(nodes) >= min_cluster_size:
            large_clusters[cluster_id] = nodes
        else:
            small_nodes.extend(nodes)
    
    if small_nodes:
        large_clusters[-1] = small_nodes
    
    cluster_nodes: List[Dict[str, Any]] = []
    cluster_id_to_node_id: Dict[int, str] = {}
    
    for cluster_id, nodes in large_clusters.items():
        cluster_node_id = f"cluster_{cluster_id}"
        cluster_id_to_node_id[cluster_id] = cluster_node_id
        
        cluster_degree = sum(graph.degree(node) for node in nodes)
        cluster_size = len(nodes)
        
        central_node = max(nodes, key=lambda n: graph.degree(n))
        
        cluster_nodes.append({
            "id": cluster_node_id,
            "label": f"Кластер {cluster_id} ({cluster_size} узлов)" if cluster_id != -1 else f"Остальные ({cluster_size} узлов)",
            "type": "cluster",
            "size": cluster_size,
            "degree": cluster_degree,
            "cluster_id": cluster_id,
            "nodes": nodes,
            "central_node": central_node
        })
    
    cluster_edges: List[Dict[str, Any]] = []
    cluster_connections: Dict[Tuple[int, int], int] = defaultdict(int)
    
    for u, v in graph.edges():
        u_cluster = node_to_community.get(u, -1)
        v_cluster = node_to_community.get(v, -1)
        
        if u_cluster != v_cluster:
            if u_cluster in large_clusters and v_cluster in large_clusters:
                cluster_pair = (min(u_cluster, v_cluster), max(u_cluster, v_cluster))
                cluster_connections[cluster_pair] += 1
    
    for (c1, c2), weight in cluster_connections.items():
        if c1 in cluster_id_to_node_id and c2 in cluster_id_to_node_id:
            cluster_edges.append({
                "source": cluster_id_to_node_id[c1],
                "target": cluster_id_to_node_id[c2],
                "weight": weight,
                "type": "cluster_edge"
            })
    
    return cluster_nodes, cluster_edges, node_to_community


@app.route("/api/graph", methods=["GET"])
def get_graph():
    if coauthorship_graph is None:
        return jsonify({
            "nodes": [],
            "edges": [],
            "stats": {"num_nodes": 0, "num_edges": 0},
            "error": "Граф не загружен"
        }), 500
    
    limit = request.args.get("limit", type=int)
    year_from = request.args.get("year_from", type=int)
    year_to = request.args.get("year_to", type=int)
    venue = request.args.get("venue", type=str)
    
    graph = coauthorship_graph
    
    if year_from is not None or year_to is not None:
        graph = filter_graph_by_years(year_from, year_to)
    
    if venue:
        graph = filter_graph_by_venue(venue)
    
    if limit and limit > 0:
        if graph.number_of_nodes() == 0:
            return jsonify({
                "nodes": [],
                "edges": [],
                "stats": {
                    "num_nodes": 0,
                    "num_edges": 0
                },
                "error": "Граф пуст после фильтрации. Попробуйте изменить параметры фильтрации."
            })
        degrees = dict(graph.degree())
        top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:limit]
        top_node_ids = [node_id for node_id, _ in top_nodes]
        graph = graph.subgraph(top_node_ids).copy()
    
    nodes = []
    for node_id in graph.nodes():
        degree = graph.degree(node_id)
        nodes.append({
            "id": node_id,
            "label": authors_dict.get(node_id, f"Author_{node_id}"),
            "degree": degree
        })
    
    edges = []
    for u, v, data in graph.edges(data=True):
        weight = data.get("weight", 1)
        edges.append({
            "source": u,
            "target": v,
            "weight": weight
        })
    
    return jsonify({
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "num_nodes": len(nodes),
            "num_edges": len(edges)
        }
    })


@app.route("/api/node_info/<int:node_id>", methods=["GET"])
def get_node_info(node_id):
    if node_id not in authors_dict:
        return jsonify({"error": "Author not found"}), 404
    
    author_name = authors_dict[node_id]
    publications = author_to_publications.get(node_id, [])
    
    pub_list = []
    years = set()
    
    for pub_id in publications:
        pub = publications_dict.get(pub_id, {})
        pub_year = pub.get("year", 0)
        pub_list.append({
            "id": pub_id,
            "title": pub.get("title", "Unknown"),
            "year": pub_year,
            "venue": pub.get("venue", "Unknown"),
            "type": pub.get("type", "Unknown")
        })
        if pub_year:
            years.add(pub_year)
    
    coauthors: Set[int] = set()
    if coauthorship_graph is not None and node_id in coauthorship_graph:
        coauthors = set(coauthorship_graph.neighbors(node_id))
    
    coauthor_list: List[Dict[str, Any]] = []
    if coauthorship_graph is not None:
        coauthor_list = [
            {
                "id": coauthor_id,
                "name": authors_dict.get(coauthor_id, f"Author_{coauthor_id}"),
                "collaborations": coauthorship_graph[node_id][coauthor_id].get("weight", 1)
            }
            for coauthor_id in coauthors
        ]
    
    return jsonify({
        "id": node_id,
        "name": author_name,
        "publications": sorted(pub_list, key=lambda x: x["year"], reverse=True),
        "coauthors": sorted(coauthor_list, key=lambda x: x["collaborations"], reverse=True),
        "years_active": sorted(years),
        "total_publications": len(pub_list),
        "total_coauthors": len(coauthor_list)
    })


@app.route("/api/centrality", methods=["GET"])
def get_centrality():
    if coauthorship_graph is None:
        return jsonify({"error": "Граф не загружен"}), 500
    
    metric = request.args.get("metric", "degree")
    top = request.args.get("top", type=int, default=50)
    
    graph = coauthorship_graph
    
    if metric == "degree":
        centrality = nx.degree_centrality(graph)
    elif metric == "betweenness":
        centrality = nx.betweenness_centrality(graph)
    elif metric == "closeness":
        centrality = nx.closeness_centrality(graph)
    else:
        return jsonify({"error": "Unknown metric"}), 400
    
    top_authors = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top]
    
    result = [
        {
            "id": node_id,
            "name": authors_dict.get(node_id, f"Author_{node_id}"),
            "centrality": value
        }
        for node_id, value in top_authors
    ]
    
    return jsonify({
        "metric": metric,
        "top_authors": result
    })


@app.route("/api/graph_aggregated", methods=["GET"])
def get_graph_aggregated():
    """
    Возвращает агрегированный граф с кластерами вместо отдельных узлов.
    Параметры:
    - level: 'cluster' (по умолчанию) или 'node' (детализация)
    - cluster_id: ID кластера для детализации (если level='node')
    - year_from, year_to, venue: фильтры как в обычном API
    - min_cluster_size: минимальный размер кластера (по умолчанию 3)
    """
    if coauthorship_graph is None:
        return jsonify({
            "nodes": [],
            "edges": [],
            "stats": {"num_nodes": 0, "num_edges": 0},
            "error": "Граф не загружен"
        }), 500
    
    level = request.args.get("level", "cluster")
    cluster_id = request.args.get("cluster_id", type=int)
    year_from = request.args.get("year_from", type=int)
    year_to = request.args.get("year_to", type=int)
    venue = request.args.get("venue", type=str)
    min_cluster_size = request.args.get("min_cluster_size", type=int, default=3)
    limit = request.args.get("limit", type=int)
    
    graph = coauthorship_graph
    
    if year_from is not None or year_to is not None:
        graph = filter_graph_by_years(year_from, year_to)
    
    if venue:
        graph = filter_graph_by_venue(venue)
    
    if limit and limit > 0:
        if graph.number_of_nodes() == 0:
            return jsonify({
                "nodes": [],
                "edges": [],
                "stats": {"num_nodes": 0, "num_edges": 0},
                "error": "Граф пуст после фильтрации"
            })
        degrees = dict(graph.degree())
        top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:limit]
        top_node_ids = [node_id for node_id, _ in top_nodes]
        graph = graph.subgraph(top_node_ids).copy()
    
    if graph.number_of_nodes() == 0:
        return jsonify({
            "nodes": [],
            "edges": [],
            "stats": {"num_nodes": 0, "num_edges": 0},
            "error": "Граф пуст после фильтрации"
        })
    
    if level == "node" and cluster_id is not None:
        cluster_nodes_list, _, node_to_community = aggregate_graph(graph, min_cluster_size)
        
        target_cluster = None
        for cluster_node in cluster_nodes_list:
            if cluster_node.get("cluster_id") == cluster_id:
                target_cluster = cluster_node
                break
        
        if not target_cluster or "nodes" not in target_cluster:
            return jsonify({
                "nodes": [],
                "edges": [],
                "stats": {"num_nodes": 0, "num_edges": 0},
                "error": f"Кластер {cluster_id} не найден"
            })
        
        cluster_nodes = target_cluster["nodes"]
        subgraph = graph.subgraph(cluster_nodes).copy()
        
        nodes = []
        for node_id in subgraph.nodes():
            degree = subgraph.degree(node_id)
            nodes.append({
                "id": node_id,
                "label": authors_dict.get(node_id, f"Author_{node_id}"),
                "degree": degree,
                "type": "node",
                "cluster_id": cluster_id
            })
        
        edges = []
        for u, v, data in subgraph.edges(data=True):
            weight = data.get("weight", 1)
            edges.append({
                "source": u,
                "target": v,
                "weight": weight,
                "type": "node_edge"
            })
        
        return jsonify({
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "num_nodes": len(nodes),
                "num_edges": len(edges)
            },
            "level": "node",
            "cluster_id": cluster_id
        })
    else:
        cluster_nodes, cluster_edges, node_to_community = aggregate_graph(graph, min_cluster_size)
        
        return jsonify({
            "nodes": cluster_nodes,
            "edges": cluster_edges,
            "stats": {
                "num_nodes": len(cluster_nodes),
                "num_edges": len(cluster_edges),
                "total_original_nodes": graph.number_of_nodes()
            },
            "level": "cluster",
            "node_to_community": {str(k): v for k, v in node_to_community.items()}
        })


@app.route("/api/stats", methods=["GET"])
def get_stats():
    graph_nodes = coauthorship_graph.number_of_nodes() if coauthorship_graph is not None else 0
    graph_edges = coauthorship_graph.number_of_edges() if coauthorship_graph is not None else 0
    
    return jsonify({
        "total_authors": len(authors_dict),
        "total_publications": len(publications_dict),
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges
    })


@app.route("/", methods=["GET"])
def index():
    return app.send_static_file('index.html')


@app.route("/api", methods=["GET"])
def api_info():
    return jsonify({
        "message": "DBLP Graph Analysis API",
        "endpoints": {
            "graph": "/api/graph?limit=100&year_from=2020&year_to=2024&venue=journal",
            "graph_aggregated": "/api/graph_aggregated?level=cluster&year_from=2020&year_to=2024",
            "node_info": "/api/node_info/<node_id>",
            "centrality": "/api/centrality?metric=degree&top=50",
            "stats": "/api/stats"
        },
        "note": "Для графа с 3.8M узлов betweenness/closeness centrality может вычисляться очень долго"
    })


if __name__ == "__main__":
    load_data()
    print("\nЗапуск сервера на http://127.0.0.1:5000")
    print("API эндпоинты:")
    print("  GET /api/graph")
    print("  GET /api/node_info/<node_id>")
    print("  GET /api/centrality")
    print("  GET /api/stats")
    app.run(debug=True, host="127.0.0.1", port=5000)
