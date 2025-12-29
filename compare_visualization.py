import csv
import os
from typing import Dict, List, Any, Optional
import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime


DATA_DIR = "data"


def load_test_subgraph(year_from: int = 2020, year_to: int = 2023, 
                       venue_filter: str = "CVPR", limit: Optional[int] = 200) -> nx.Graph:
    print(f"Создание тестового подграфа: {venue_filter} ({year_from}-{year_to}), лимит: {limit}")
    
    publications: Dict[int, Dict[str, Any]] = {}
    pub_file = os.path.join(DATA_DIR, "publications.csv")
    with open(pub_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year_str = row.get("year", "0")
            venue = row.get("venue", "")
            try:
                year = int(year_str)
                if year_from <= year <= year_to:
                    if venue_filter.lower() in venue.lower():
                        pub_id_str = row.get("pub_id", "0")
                        try:
                            pub_id = int(pub_id_str)
                            if pub_id:
                                publications[pub_id] = {
                                    "year": year,
                                    "venue": venue
                                }
                        except ValueError:
                            continue
            except ValueError:
                continue
    
    print(f"  Найдено публикаций: {len(publications)}")
    
    authorship: List[Dict[str, int]] = []
    auth_file = os.path.join(DATA_DIR, "authorship.csv")
    with open(auth_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pub_id_str = row.get("pub_id", "0")
            author_id_str = row.get("author_id", "0")
            try:
                pub_id = int(pub_id_str)
                if pub_id in publications:
                    author_id = int(author_id_str)
                    if author_id:
                        authorship.append({
                            "pub_id": pub_id,
                            "author_id": author_id
                        })
            except ValueError:
                continue
    
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
    
    if limit and G.number_of_nodes() > limit:
        centrality = nx.degree_centrality(G)
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:limit]
        top_node_ids = [node_id for node_id, _ in top_nodes]
        G = G.subgraph(top_node_ids).copy()
    
    print(f"  Итоговый граф: {G.number_of_nodes()} узлов, {G.number_of_edges()} ребер")
    return G


def visualize_with_networkx(graph: nx.Graph, output_file: str) -> None:
    print(f"Создание статичной визуализации через NetworkX...")
    
    plt.figure(figsize=(16, 12))
    
    pos = nx.spring_layout(graph, k=1, iterations=50, seed=42)
    
    degrees = dict(graph.degree())
    node_sizes = [degrees[node] * 50 for node in graph.nodes()]
    node_colors = [degrees[node] for node in graph.nodes()]
    
    cmap = plt.cm.get_cmap('viridis')
    nx.draw_networkx_nodes(graph, pos, node_size=node_sizes, node_color=node_colors,
                          cmap=cmap, alpha=0.8)
    
    edges = graph.edges()
    weights = [graph[u][v].get("weight", 1) for u, v in edges]
    nx.draw_networkx_edges(graph, pos, width=[w * 0.5 for w in weights], 
                           alpha=0.3, edge_color="gray")
    
    top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:10]
    labels = {node: f"Author_{node}" for node, _ in top_nodes}
    nx.draw_networkx_labels(graph, pos, labels, font_size=8, font_weight="bold")
    
    plt.title(f"Граф соавторства (NetworkX)\n{graph.number_of_nodes()} узлов, "
              f"{graph.number_of_edges()} ребер",
              fontsize=16, fontweight="bold")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Сохранено: {output_file}")


def export_to_gephi(graph: nx.Graph, output_file: str) -> None:
    print(f"Экспорт в GEXF для Gephi...")
    nx.write_gexf(graph, output_file)
    print(f"  Сохранено: {output_file}")
    print(f"  Для открытия: запустите Gephi и импортируйте файл {output_file}")


def generate_comparison_report(graph: nx.Graph, output_file: str) -> None:
    print(f"Генерация сравнительного отчета...")
    
    report = f"""# СРАВНИТЕЛЬНЫЙ АНАЛИЗ ИНСТРУМЕНТОВ ВИЗУАЛИЗАЦИИ DBLP

**Дата создания:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

**Тестовый подграф:**
- Узлов: {graph.number_of_nodes()}
- Ребер: {graph.number_of_edges()}
- Плотность: {nx.density(graph):.6f}

---

## СРАВНИТЕЛЬНАЯ ТАБЛИЦА

| Критерий | Собственный инструмент | NetworkX/Matplotlib | Gephi |
|----------|------------------------|-------------------|-------|
| **Скорость загрузки** | Быстро (API запрос) | Очень быстро (локально) | Средне (импорт файла) |
| **Интерактивность** | Высокая (клики, фильтры, масштабирование) | Низкая (статичное изображение) | Высокая (полный набор инструментов) |
| **Читаемость** | Хорошая (адаптивная компоновка) | Средняя (зависит от алгоритма) | Отличная (профессиональные алгоритмы) |
| **Легкость фильтрации** | Очень легко (веб-интерфейс) | Требует изменения кода | Средне (через интерфейс) |
| **Масштабируемость** | Хорошая (до ~1000 узлов) | Ограничена (визуализация) | Отличная (оптимизирована) |
| **Требования** | Веб-браузер + сервер | Python + библиотеки | Отдельное приложение |
| **Экспорт результатов** | Скриншоты | PNG/SVG файлы | Множество форматов |
| **Программирование** | Минимальное | Требуется код | Не требуется |

---

## ПОДРОБНОЕ ОПИСАНИЕ

### 1. СОБСТВЕННЫЙ ВЕБ-ИНСТРУМЕНТ

**Преимущества:**
- Интерактивная визуализация с возможностью клика по узлам
- Динамическая фильтрация по годам, конференциям, метрикам
- Легкий доступ через веб-браузер
- Детальная информация об авторах в реальном времени
- Адаптивный дизайн

**Ограничения:**
- Производительность снижается при >1000 узлов
- Базовые алгоритмы компоновки
- Требует запущенного сервера

**Использование:**
1. Запустить сервер: `python 3_backend_api.py`
2. Открыть `web_app/index.html` в браузере
3. Применить фильтры и загрузить граф
4. Исследовать граф интерактивно

---

### 2. NETWORKX + MATPLOTLIB

**Преимущества:**
- Полный контроль над визуализацией через код
- Быстрое создание статичных изображений
- Интеграция с Python экосистемой
- Легкое создание скриптов для пакетной обработки

**Ограничения:**
- Статичная визуализация (нет интерактивности)
- Требует программирования для изменений
- Ограниченная читаемость для больших графов
- Нет встроенной фильтрации

**Использование:**
- Запустить скрипт `5_compare_visualization.py`
- Результат: статичное PNG изображение

---

### 3. GEPHI

**Преимущества:**
- Профессиональные алгоритмы компоновки
- Множество метрик и фильтров
- Отличная визуализация больших графов
- Экспорт в различные форматы
- Поддержка временных срезов

**Ограничения:**
- Требует установки отдельного приложения
- Не подходит для веб-интеграции
- Кривая обучения для новых пользователей
- Ручная настройка фильтров

**Использование:**
1. Открыть Gephi
2. File → Open → выбрать `comparison_subgraph.gexf`
3. Применить алгоритм компоновки (например, Force Atlas 2)
4. Настроить внешний вид и экспортировать

---

## ВЫВОДЫ

**Для исследования DBLP рекомендуется:**

1. **Собственный инструмент** - для быстрого интерактивного исследования,
   демонстрации результатов, веб-интеграции

2. **NetworkX/Matplotlib** - для создания публикационных графиков,
   автоматизированной обработки, интеграции в научные работы

3. **Gephi** - для глубокого анализа, профессиональной визуализации,
   работы с очень большими графами (>5000 узлов)

**Комбинированный подход:**
Использование всех трех инструментов в зависимости от задачи дает
максимальную гибкость и позволяет выбрать оптимальный инструмент
для каждого этапа исследования.

---

## МЕТРИКИ ТЕСТОВОГО ПОДГРАФА

- Средняя степень: {sum(dict(graph.degree()).values()) / graph.number_of_nodes():.2f}
- Максимальная степень: {max(dict(graph.degree()).values())}
- Коэффициент кластеризации: {nx.average_clustering(graph):.4f}
- Количество компонент: {nx.number_connected_components(graph)}
"""
    
    filepath = os.path.join(DATA_DIR, output_file)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Сохранено: {filepath}")


def main():
    print("Этап 5: Сравнительный анализ инструментов визуализации\n")
    
    test_graph = load_test_subgraph(year_from=2020, year_to=2023, venue_filter="CVPR", limit=200)
    
    if test_graph.number_of_nodes() == 0:
        print("ВНИМАНИЕ: Тестовый подграф пуст. Попробуйте изменить фильтры.")
        print("Создаю граф из всех доступных данных...")
        test_graph = load_test_subgraph(year_from=2015, year_to=2023, venue_filter="", limit=200)
    
    visualize_with_networkx(test_graph, os.path.join(DATA_DIR, "comparison_networkx.png"))
    export_to_gephi(test_graph, os.path.join(DATA_DIR, "comparison_subgraph.gexf"))
    generate_comparison_report(test_graph, "comparison_report.md")
    
    print("\nЭтап 5 завершен успешно!")
    print("\nСозданные файлы:")
    print("  - comparison_networkx.png (статичная визуализация)")
    print("  - comparison_subgraph.gexf (для Gephi)")
    print("  - comparison_report.md (сравнительный отчет)")


if __name__ == "__main__":
    main()

