import csv
import os
from typing import Dict, List, Any
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np


DATA_DIR = "data"


def load_authors() -> Dict[int, str]:
    authors: Dict[int, str] = {}
    filepath = os.path.join(DATA_DIR, "authors.csv")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            author_id = int(row.get("author_id", "0"))
            author_name = row.get("author_name", "")
            if author_id and author_name:
                authors[author_id] = author_name
    return authors


def load_publications() -> Dict[int, Dict[str, Any]]:
    publications: Dict[int, Dict[str, Any]] = {}
    filepath = os.path.join(DATA_DIR, "publications.csv")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pub_id = int(row.get("pub_id", "0"))
            if pub_id:
                publications[pub_id] = {
                    "title": row.get("title", ""),
                    "year": int(row.get("year", "0")),
                    "venue": row.get("venue", ""),
                    "type": row.get("type", "")
                }
    return publications


def load_authorship() -> List[Dict[str, int]]:
    authorship: List[Dict[str, int]] = []
    filepath = os.path.join(DATA_DIR, "authorship.csv")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pub_id = int(row.get("pub_id", "0"))
            author_id = int(row.get("author_id", "0"))
            if pub_id and author_id:
                authorship.append({
                    "pub_id": pub_id,
                    "author_id": author_id
                })
    return authorship


def build_coauthorship_graph(authorship):
    print("Построение графа соавторства...")
    
    pub_to_authors = {}
    for rel in authorship:
        pub_id = rel["pub_id"]
        author_id = rel["author_id"]
        pub_to_authors.setdefault(pub_id, []).append(author_id)
    
    G = nx.Graph()
    
    for pub_id, authors_list in pub_to_authors.items():
        for i in range(len(authors_list)):
            for j in range(i + 1, len(authors_list)):
                author1 = authors_list[i]
                author2 = authors_list[j]
                if G.has_edge(author1, author2):
                    G[author1][author2]["weight"] += 1
                else:
                    G.add_edge(author1, author2, weight=1)
    
    print(f"  Узлов: {G.number_of_nodes()}")
    print(f"  Ребер: {G.number_of_edges()}")
    return G


def build_bipartite_graph(authorship):
    print("Построение двудольного графа автор-публикация...")
    
    B = nx.Graph()
    
    for rel in authorship:
        author_id = rel["author_id"]
        pub_id = rel["pub_id"]
        B.add_edge(f"author_{author_id}", f"pub_{pub_id}")
    
    print(f"  Узлов-авторов: {sum(1 for n in B.nodes() if n.startswith('author_'))}")
    print(f"  Узлов-публикаций: {sum(1 for n in B.nodes() if n.startswith('pub_'))}")
    print(f"  Ребер: {B.number_of_edges()}")
    return B


def calculate_network_metrics(G, graph_name):
    print(f"\nВычисление метрик для {graph_name}...")
    
    metrics = {
        "graph_name": graph_name,
        "num_nodes": G.number_of_nodes(),
        "num_edges": G.number_of_edges(),
        "density": nx.density(G),
    }
    
    if G.number_of_nodes() == 0:
        return metrics
    
    degrees = [d for n, d in G.degree()]
    metrics["avg_degree"] = np.mean(degrees)
    metrics["max_degree"] = max(degrees) if degrees else 0
    metrics["min_degree"] = min(degrees) if degrees else 0
    
    if nx.is_connected(G):
        metrics["is_connected"] = True
        metrics["diameter"] = nx.diameter(G)
        metrics["avg_path_length"] = nx.average_shortest_path_length(G)
    else:
        metrics["is_connected"] = False
        components = list(nx.connected_components(G))
        largest_component = max(components, key=len)
        metrics["num_components"] = len(components)
        metrics["largest_component_size"] = len(largest_component)
        if len(largest_component) > 1:
            G_lcc = G.subgraph(largest_component)
            metrics["lcc_diameter"] = nx.diameter(G_lcc)
            metrics["lcc_avg_path_length"] = nx.average_shortest_path_length(G_lcc)
    
    clustering = nx.clustering(G)
    metrics["avg_clustering"] = np.mean(list(clustering.values()))
    metrics["global_clustering"] = nx.transitivity(G)
    
    return metrics


def plot_degree_distribution(G, output_file):
    print(f"Создание гистограммы распределения степеней...")
    
    degrees = [d for n, d in G.degree()]
    if not degrees:
        print("  Граф пуст, пропускаем визуализацию")
        return
    
    plt.figure(figsize=(10, 6))
    plt.hist(degrees, bins=50, edgecolor="black", alpha=0.7)
    plt.xlabel("Степень узла", fontsize=12)
    plt.ylabel("Количество узлов", fontsize=12)
    plt.title("Распределение степеней узлов в графе соавторства", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Сохранено: {output_file}")


def save_graph_stats(metrics_list, output_file):
    filepath = os.path.join(DATA_DIR, output_file)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("МЕТРИКИ СЛОЖНОЙ СЕТИ DBLP\n")
        f.write("=" * 50 + "\n\n")
        
        for metrics in metrics_list:
            f.write(f"{metrics['graph_name']}\n")
            f.write("-" * 50 + "\n")
            f.write(f"Количество узлов: {metrics['num_nodes']}\n")
            f.write(f"Количество ребер: {metrics['num_edges']}\n")
            f.write(f"Плотность графа: {metrics['density']:.6f}\n")
            f.write(f"Средняя степень: {metrics['avg_degree']:.2f}\n")
            f.write(f"Максимальная степень: {metrics['max_degree']}\n")
            f.write(f"Минимальная степень: {metrics['min_degree']}\n")
            f.write(f"Средний коэффициент кластеризации: {metrics['avg_clustering']:.6f}\n")
            f.write(f"Глобальный коэффициент кластеризации: {metrics['global_clustering']:.6f}\n")
            
            if metrics.get("is_connected", False):
                f.write(f"Граф связный\n")
                f.write(f"Диаметр: {metrics['diameter']}\n")
                f.write(f"Средняя длина пути: {metrics['avg_path_length']:.2f}\n")
            else:
                f.write(f"Граф несвязный\n")
                f.write(f"Количество компонент: {metrics['num_components']}\n")
                f.write(f"Размер гигантской компоненты: {metrics['largest_component_size']}\n")
                if "lcc_diameter" in metrics:
                    f.write(f"Диаметр гигантской компоненты: {metrics['lcc_diameter']}\n")
                    f.write(f"Средняя длина пути в ГК: {metrics['lcc_avg_path_length']:.2f}\n")
            
            f.write("\n")
    
    print(f"Сохранено: {filepath}")


def main():
    print("Этап 2: Базовый анализ и построение графов\n")
    
    authors = load_authors()
    publications = load_publications()
    authorship = load_authorship()
    
    print(f"Загружено авторов: {len(authors)}")
    print(f"Загружено публикаций: {len(publications)}")
    print(f"Загружено связей: {len(authorship)}\n")
    
    coauthorship_G = build_coauthorship_graph(authorship)
    bipartite_B = build_bipartite_graph(authorship)
    
    coauthorship_metrics = calculate_network_metrics(coauthorship_G, "Граф соавторства")
    bipartite_metrics = calculate_network_metrics(bipartite_B, "Двудольный граф автор-публикация")
    
    save_graph_stats([coauthorship_metrics, bipartite_metrics], "network_stats.txt")
    
    plot_degree_distribution(coauthorship_G, os.path.join(DATA_DIR, "degree_distribution.png"))
    
    nx.write_graphml(coauthorship_G, os.path.join(DATA_DIR, "coauthorship_graph.graphml"))
    nx.write_gexf(coauthorship_G, os.path.join(DATA_DIR, "coauthorship_graph.gexf"))
    nx.write_graphml(bipartite_B, os.path.join(DATA_DIR, "bipartite_graph.graphml"))
    
    print("\nЭтап 2 завершен успешно!")


if __name__ == "__main__":
    main()




