const API_BASE = "http://127.0.0.1:5000/api";
let network = null;
let currentData = null;
let currentLevel = "cluster";
let currentClusterId = null;

function initNetwork() {
    const container = document.getElementById("graph-container");
    
    if (!container) {
        console.error("Контейнер graph-container не найден!");
        return;
    }
    
    if (network) {
        try {
            network.destroy();
        } catch (e) {
            console.warn("Ошибка при уничтожении network:", e);
        }
        network = null;
    }
    
    container.innerHTML = "";
    
    const parentRect = container.parentElement.getBoundingClientRect();
    const containerWidth = Math.max(400, parentRect.width || 800);
    const containerHeight = Math.max(400, parentRect.height || 600);
    
    container.style.width = containerWidth + "px";
    container.style.height = containerHeight + "px";
    container.style.position = "relative";
    container.style.display = "block";
    container.style.overflow = "hidden";
    
    console.log("Инициализация network. Размер контейнера:", containerWidth, "x", containerHeight);
    console.log("offsetWidth x offsetHeight:", container.offsetWidth, "x", container.offsetHeight);
    
    if (container.offsetWidth === 0 || container.offsetHeight === 0) {
        console.error("Контейнер имеет нулевой размер! Принудительно устанавливаем размеры...");
        container.style.width = "800px";
        container.style.height = "600px";
    }
    
    const data = {
        nodes: new vis.DataSet([]),
        edges: new vis.DataSet([])
    };
    
    const getPhysicsOptions = (numNodes) => {
        const baseSpringLength = 200;
        const springLengthMultiplier = Math.max(1, Math.sqrt(numNodes / 10));
        const springLength = baseSpringLength * springLengthMultiplier;
        
        if (numNodes <= 20) {
            return {
                enabled: true,
                stabilization: {
                    iterations: 250,
                    updateInterval: 50,
                    onlyDynamicEdges: false
                },
                barnesHut: {
                    gravitationalConstant: -1500,
                    centralGravity: 0.05,
                    springLength: springLength,
                    springConstant: 0.01,
                    damping: 0.5,
                    avoidOverlap: 1.0
                }
            };
        } else if (numNodes <= 50) {
            return {
                enabled: true,
                stabilization: {
                    iterations: 350,
                    updateInterval: 100,
                    onlyDynamicEdges: false
                },
                barnesHut: {
                    gravitationalConstant: -1500,
                    centralGravity: 0.05,
                    springLength: springLength,
                    springConstant: 0.01,
                    damping: 0.6,
                    avoidOverlap: 1.0
                }
            };
        } else {
            return {
                enabled: true,
                stabilization: {
                    iterations: 500,
                    updateInterval: 150,
                    onlyDynamicEdges: false
                },
                barnesHut: {
                    gravitationalConstant: -1500,
                    centralGravity: 0.05,
                    springLength: springLength,
                    springConstant: 0.01,
                    damping: 0.7,
                    avoidOverlap: 1.0
                }
            };
        }
    };
    
    const options = {
        nodes: {
            shape: 'dot',
            font: {
                size: 12,
                face: 'Arial',
                color: '#333'
            },
            borderWidth: 1,
            shadow: false,
            size: 8,
            fixed: false
        },
        edges: {
            width: 0.5,
            shadow: false,
            smooth: {
                type: 'continuous',
                roundness: 0.5
            }
        },
        physics: getPhysicsOptions(0),
        interaction: {
            hover: true,
            tooltipDelay: 100,
            zoomView: true,
            dragView: true,
            dragNodes: true
        },
        layout: {
            improvedLayout: true
        }
    };
    
    try {
        network = new vis.Network(container, data, options);
        console.log("Network создан успешно");
        
        const checkCanvas = () => {
            const canvas = container.querySelector('canvas');
            if (canvas) {
                console.log("Canvas создан:", canvas.width, "x", canvas.height);
                if (canvas.width === 0 || canvas.height === 0) {
                    console.error("Canvas имеет нулевой размер! Принудительно устанавливаем размеры...");
                    canvas.width = container.offsetWidth;
                    canvas.height = container.offsetHeight;
                    network.setSize(container.offsetWidth + "px", container.offsetHeight + "px");
                }
            } else {
                console.warn("Canvas еще не создан, проверка через 200ms...");
                setTimeout(checkCanvas, 200);
            }
        };
        
        setTimeout(checkCanvas, 100);
        
        network.on("click", (params) => {
            if (params.nodes.length > 0) {
                const clickedNodeId = params.nodes[0];
                
                if (typeof clickedNodeId === 'string' && clickedNodeId.startsWith('cluster_')) {
                    const clusterId = parseInt(clickedNodeId.replace('cluster_', ''));
                    if (!isNaN(clusterId)) {
                        currentLevel = "node";
                        currentClusterId = clusterId;
                        loadGraph();
                    }
                } else {
                    const nodeId = parseInt(clickedNodeId);
                    if (!isNaN(nodeId)) {
                        loadNodeInfo(nodeId);
                    }
                }
            }
        });
        
        network.on("stabilizationProgress", (params) => {
            updateStabilizationProgress(params.iterations, params.total);
            if (params.iterations % 25 === 0) {
                console.log("Стабилизация:", params.iterations, "/", params.total);
            }
        });
        
    } catch (error) {
        console.error("Ошибка при создании network:", error);
        container.innerHTML = `<div style='text-align: center; padding: 50px; color: #d32f2f;'>
            <h3>Ошибка инициализации графа</h3>
            <p>${error.message}</p>
        </div>`;
    }
}

function showGraphLoading() {
    const loadingOverlay = document.getElementById("graph-loading");
    const progressText = document.getElementById("stabilization-progress");
    if (loadingOverlay) {
        loadingOverlay.style.display = "flex";
        if (progressText) {
            progressText.style.display = "none";
        }
    }
}

function hideGraphLoading() {
    const loadingOverlay = document.getElementById("graph-loading");
    if (loadingOverlay) {
        loadingOverlay.style.display = "none";
    }
}

let stabilizationTimeout = null;

function updateStabilizationProgress(current, total) {
    const progressText = document.getElementById("stabilization-progress");
    if (progressText) {
        progressText.style.display = "block";
        const percent = Math.round((current / total) * 100);
        progressText.textContent = `Стабилизация графа: ${percent}% (${current}/${total})`;
        
        if (current >= total) {
            clearTimeout(stabilizationTimeout);
            stabilizationTimeout = setTimeout(() => {
                hideGraphLoading();
            }, 500);
        }
    }
    
    clearTimeout(stabilizationTimeout);
    stabilizationTimeout = setTimeout(() => {
        console.warn("Таймаут стабилизации - скрываем индикатор");
        hideGraphLoading();
    }, 10000);
}

function showNodeLoading() {
    const nodeLoading = document.getElementById("node-loading");
    if (nodeLoading) {
        nodeLoading.style.display = "block";
    }
}

function hideNodeLoading() {
    const nodeLoading = document.getElementById("node-loading");
    if (nodeLoading) {
        nodeLoading.style.display = "none";
    }
}

function loadGraph() {
    const yearFrom = document.getElementById("yearFrom").value;
    const yearTo = document.getElementById("yearTo").value;
    const venue = document.getElementById("venue").value;
    const limit = document.getElementById("limit").value || 100;
    const useAggregation = document.getElementById("useAggregation").checked;
    const minClusterSize = document.getElementById("minClusterSize").value || 3;
    
    let url;
    if (useAggregation && currentLevel === "cluster") {
        url = `${API_BASE}/graph_aggregated?level=cluster&min_cluster_size=${minClusterSize}`;
        if (limit) url += `&limit=${limit}`;
        if (yearFrom) url += `&year_from=${yearFrom}`;
        if (yearTo) url += `&year_to=${yearTo}`;
        if (venue) url += `&venue=${encodeURIComponent(venue)}`;
    } else if (useAggregation && currentLevel === "node" && currentClusterId !== null) {
        url = `${API_BASE}/graph_aggregated?level=node&cluster_id=${currentClusterId}`;
        if (yearFrom) url += `&year_from=${yearFrom}`;
        if (yearTo) url += `&year_to=${yearTo}`;
        if (venue) url += `&venue=${encodeURIComponent(venue)}`;
    } else {
        url = `${API_BASE}/graph?limit=${limit}`;
        if (yearFrom) url += `&year_from=${yearFrom}`;
        if (yearTo) url += `&year_to=${yearTo}`;
        if (venue) url += `&venue=${encodeURIComponent(venue)}`;
    }
    
    console.log("Загрузка графа с URL:", url);
    
    const container = document.getElementById("graph-container");
    if (!container) {
        console.error("Контейнер graph-container не найден!");
        return;
    }
    
    showGraphLoading();
    
    fetch(url)
        .then(response => {
            console.log("Ответ сервера:", response.status, response.statusText);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Данные получены. Узлов:", data?.nodes?.length, "Ребер:", data?.edges?.length);
            console.log("Первые 3 узла:", data?.nodes?.slice(0, 3));
            console.log("Первые 3 ребра:", data?.edges?.slice(0, 3));
            
            if (!data || !data.nodes || !data.edges) {
                hideGraphLoading();
                throw new Error("Неверный формат данных от сервера. Получено: " + JSON.stringify(data).substring(0, 200));
            }
            if (data.nodes.length === 0) {
                hideGraphLoading();
                if (network) {
                    try {
                        network.destroy();
                    } catch (e) {}
                    network = null;
                }
                container.innerHTML = "<div style='text-align: center; padding: 50px; color: #666;'>Граф пуст. Попробуйте изменить фильтры.</div>";
                updateStats({num_nodes: 0, num_edges: 0});
                return;
            }
            
            console.log("Начинаем рендеринг графа...");
            
            currentData = data;
            
            const backButton = document.getElementById("backToClusters");
            if (data.level === "cluster") {
                currentLevel = "cluster";
                currentClusterId = null;
                if (backButton) backButton.style.display = "none";
            } else if (data.level === "node") {
                currentLevel = "node";
                currentClusterId = data.cluster_id;
                if (backButton) backButton.style.display = "block";
            } else {
                if (backButton) backButton.style.display = "none";
            }
            
            try {
                renderGraph(data);
                updateStats(data.stats);
                console.log("Граф успешно отрендерен!");
            } catch (error) {
                hideGraphLoading();
                console.error("Ошибка при рендеринге графа:", error);
                container.innerHTML = `<div style='text-align: center; padding: 50px; color: #d32f2f;'>
                    <h3>Ошибка при отображении графа</h3>
                    <p>${error.message}</p>
                    <p style='font-size: 12px; margin-top: 20px;'>Проверьте консоль браузера (F12) для подробностей</p>
                </div>`;
            }
        })
        .catch(error => {
            hideGraphLoading();
            console.error("Ошибка загрузки графа:", error);
            container.innerHTML = `<div style='text-align: center; padding: 50px; color: #d32f2f;'>
                <h3>Ошибка загрузки данных</h3>
                <p>${error.message}</p>
                <p style='font-size: 12px; margin-top: 20px;'>
                    Убедитесь, что:<br>
                    1. Сервер запущен на http://127.0.0.1:5000<br>
                    2. Данные обработаны (запущены скрипты 1_parse_dblp.py и 2_build_analyze_graphs.py)<br>
                    3. Проверьте консоль браузера (F12) для подробностей
                </p>
            </div>`;
            updateStats({num_nodes: 0, num_edges: 0});
        });
}

function renderGraph(data) {
    console.log("renderGraph вызван. Узлов:", data.nodes.length, "Ребер:", data.edges.length);
    
    const container = document.getElementById("graph-container");
    if (!container) {
        console.error("Контейнер не найден!");
        return;
    }
    
    if (!network) {
        console.log("Инициализация network...");
        initNetwork();
        
        const waitForCanvas = (attempts = 0) => {
            if (attempts > 10) {
                console.error("Canvas не создан после 10 попыток!");
                container.innerHTML = "<div style='text-align: center; padding: 50px; color: #d32f2f;'>Ошибка: Canvas не создан. Проверьте размеры контейнера.</div>";
                return;
            }
            
            const canvas = container.querySelector('canvas');
            if (canvas && canvas.width > 0 && canvas.height > 0) {
                console.log("Canvas найден и имеет размер:", canvas.width, "x", canvas.height);
                doRenderGraph(data);
            } else {
                console.log(`Ожидание canvas... попытка ${attempts + 1}/10`);
                setTimeout(() => waitForCanvas(attempts + 1), 200);
            }
        };
        
        setTimeout(() => waitForCanvas(), 100);
    } else {
        doRenderGraph(data);
    }
}

function doRenderGraph(data) {
    const container = document.getElementById("graph-container");
    
    if (!network) {
        console.error("Network не инициализирован в doRenderGraph!");
        return;
    }
    
    const canvas = container.querySelector('canvas');
    if (!canvas || canvas.width === 0 || canvas.height === 0) {
        console.error("Canvas не готов! Размер:", canvas ? `${canvas.width}x${canvas.height}` : "не найден");
        const rect = container.getBoundingClientRect();
        console.log("Размер контейнера:", rect.width, "x", rect.height);
        if (rect.width > 0 && rect.height > 0) {
            container.style.width = rect.width + "px";
            container.style.height = rect.height + "px";
            network.setSize(rect.width + "px", rect.height + "px");
            setTimeout(() => doRenderGraph(data), 200);
            return;
        }
    }
    
    const numNodes = data.nodes.length;
    console.log("Преобразование данных для", numNodes, "узлов...");
    
    const nodes = data.nodes.map(node => {
        const isCluster = node.type === "cluster" || String(node.id).startsWith('cluster_');
        const nodeSize = isCluster 
            ? Math.max(15, Math.min(40, (node.size || 10) * 2))
            : Math.max(3, Math.min(20, (node.degree || 1) * 1.5));
        
        const nodeColor = isCluster ? '#ff6b6b' : getNodeColor(node.degree || 1);
        
        const title = isCluster
            ? `${node.label || 'Кластер'}\nУзлов: ${node.size || 0}\nСтепень: ${node.degree || 0}\n(Кликните для детализации)`
            : `${node.label || 'Unknown'}\nСтепень: ${node.degree || 0}`;
        
        return {
            id: String(node.id),
            label: String(node.label || `Node ${node.id}`).substring(0, 30),
            value: nodeSize,
            color: nodeColor,
            title: title,
            shape: isCluster ? 'box' : 'dot',
            borderWidth: isCluster ? 3 : 1
        };
    });
    
    const edges = data.edges.map(edge => ({
        from: String(edge.source),
        to: String(edge.target),
        value: Math.min(3, edge.weight || 1),
        title: `Вес: ${edge.weight || 1}`
    }));
    
    console.log("Создание DataSet. Узлов:", nodes.length, "Ребер:", edges.length);
    const nodesDataSet = new vis.DataSet(nodes);
    const edgesDataSet = new vis.DataSet(edges);
    
    const getPhysicsOptions = (numNodes) => {
        const baseSpringLength = 200;
        const springLengthMultiplier = Math.max(1, Math.sqrt(numNodes / 10));
        const springLength = baseSpringLength * springLengthMultiplier;
        
        if (numNodes <= 20) {
            return {
                enabled: true,
                stabilization: {
                    iterations: 250,
                    updateInterval: 50,
                    onlyDynamicEdges: false
                },
                barnesHut: {
                    gravitationalConstant: -1500,
                    centralGravity: 0.05,
                    springLength: springLength,
                    springConstant: 0.01,
                    damping: 0.5,
                    avoidOverlap: 1.0
                }
            };
        } else if (numNodes <= 50) {
            return {
                enabled: true,
                stabilization: {
                    iterations: 350,
                    updateInterval: 100,
                    onlyDynamicEdges: false
                },
                barnesHut: {
                    gravitationalConstant: -1500,
                    centralGravity: 0.05,
                    springLength: springLength,
                    springConstant: 0.01,
                    damping: 0.6,
                    avoidOverlap: 1.0
                }
            };
        } else {
            return {
                enabled: true,
                stabilization: {
                    iterations: 500,
                    updateInterval: 150,
                    onlyDynamicEdges: false
                },
                barnesHut: {
                    gravitationalConstant: -1500,
                    centralGravity: 0.05,
                    springLength: springLength,
                    springConstant: 0.01,
                    damping: 0.7,
                    avoidOverlap: 1.0
                }
            };
        }
    };
    
    const physicsOptions = getPhysicsOptions(numNodes);
    console.log("Настройка физики для", numNodes, "узлов. Длина пружины:", physicsOptions.barnesHut.springLength);
    network.setOptions({ physics: physicsOptions });
    
    console.log("Установка данных в network...");
    try {
        network.setData({
            nodes: nodesDataSet,
            edges: edgesDataSet
        });
        console.log("Данные установлены");
        
        const stabilizationHandler = () => {
            console.log("Стабилизация завершена, отключение физики и центрирование...");
            clearTimeout(stabilizationTimeout);
            
            network.setOptions({ 
                physics: { 
                    enabled: false 
                } 
            });
            console.log("Физика отключена для предотвращения дергания");
            
            hideGraphLoading();
            
            setTimeout(() => {
                network.fit({
                    animation: {
                        duration: 800,
                        easingFunction: 'easeInOutQuad'
                    }
                });
                
                console.log("Граф отрендерен и отцентрован. Узлов:", nodes.length, "Ребер:", edges.length);
            }, 200);
        };
        
        network.once("stabilizationEnd", stabilizationHandler);
        
        network.on("stabilizationProgress", (params) => {
            updateStabilizationProgress(params.iterations, params.total);
            if (params.iterations % 25 === 0) {
                console.log("Стабилизация:", params.iterations, "/", params.total);
            }
            
            if (params.iterations >= params.total) {
                setTimeout(() => {
                    if (document.getElementById("graph-loading")?.style.display !== "none") {
                        console.log("Принудительное скрытие индикатора после завершения стабилизации");
                        hideGraphLoading();
                    }
                }, 1000);
            }
        });
        
    } catch (error) {
        console.error("Ошибка при установке данных:", error);
        container.innerHTML = `<div style='text-align: center; padding: 50px; color: #d32f2f;'>
            <h3>Ошибка при отображении графа</h3>
            <p>${error.message}</p>
        </div>`;
        throw error;
    }
}

function getNodeColor(degree) {
    const maxDegree = 50;
    const normalized = Math.min(1, degree / maxDegree);
    const hue = 240 - (normalized * 120);
    return {
        background: `hsl(${hue}, 70%, 50%)`,
        border: `hsl(${hue}, 70%, 30%)`
    };
}

function updateStats(stats) {
    document.getElementById("nodeCount").textContent = stats.num_nodes;
    document.getElementById("edgeCount").textContent = stats.num_edges;
}

function loadNodeInfo(nodeId) {
    showNodeLoading();
    const infoPanel = document.getElementById("nodeInfo");
    if (infoPanel) {
        infoPanel.innerHTML = "";
    }
    
    fetch(`${API_BASE}/node_info/${nodeId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            hideNodeLoading();
            displayNodeInfo(data);
        })
        .catch(error => {
            hideNodeLoading();
            console.error("Ошибка загрузки информации об узле:", error);
            const infoPanel = document.getElementById("nodeInfo");
            if (infoPanel) {
                infoPanel.innerHTML = `<div style='text-align: center; padding: 20px; color: #d32f2f;'>
                    <p>Ошибка загрузки информации</p>
                    <p style='font-size: 0.9em;'>${error.message}</p>
                </div>`;
            }
        });
}

function displayNodeInfo(data) {
    const infoPanel = document.getElementById("nodeInfo");
    
    let html = `<div class="author-name">${data.name}</div>`;
    
    html += `<div class="info-section">
        <h3>Общая информация</h3>
        <div class="info-item">Всего публикаций: <strong>${data.total_publications}</strong></div>
        <div class="info-item">Соавторов: <strong>${data.total_coauthors}</strong></div>
        <div class="info-item">Годы активности: ${data.years_active.join(", ") || "Нет данных"}</div>
    </div>`;
    
    if (data.publications && data.publications.length > 0) {
        html += `<div class="info-section">
            <h3>Публикации (последние 10)</h3>`;
        data.publications.slice(0, 10).forEach(pub => {
            html += `<div class="publication-item">
                <div class="publication-title">${pub.title}</div>
                <div class="publication-meta">${pub.year} | ${pub.venue} | ${pub.type}</div>
            </div>`;
        });
        html += `</div>`;
    }
    
    if (data.coauthors && data.coauthors.length > 0) {
        html += `<div class="info-section">
            <h3>Соавторы (топ 10)</h3>`;
        data.coauthors.slice(0, 10).forEach(coauthor => {
            html += `<div class="coauthor-item">
                ${coauthor.name} (${coauthor.collaborations} совместных работ)
            </div>`;
        });
        html += `</div>`;
    }
    
    infoPanel.innerHTML = html;
}

function resetView() {
    if (network) {
        network.fit({
            animation: {
                duration: 500,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM загружен. Проверка vis-network...");
    
    if (typeof vis === 'undefined' || !vis.Network) {
        console.error("vis-network не загружен!");
        document.getElementById("graph-container").innerHTML = 
            "<div style='text-align: center; padding: 50px; color: #d32f2f;'>" +
            "<h3>Ошибка: библиотека vis-network не загружена</h3>" +
            "<p>Проверьте подключение к интернету или скачайте библиотеку локально</p>" +
            "</div>";
        return;
    }
    
    console.log("vis-network загружен успешно");
    initNetwork();
    
    document.getElementById("loadGraph").addEventListener("click", loadGraph);
    document.getElementById("resetView").addEventListener("click", resetView);
    
    const useAggregationCheckbox = document.getElementById("useAggregation");
    if (useAggregationCheckbox) {
        useAggregationCheckbox.addEventListener("change", function() {
            const minClusterSizeGroup = document.getElementById("minClusterSizeGroup");
            if (this.checked) {
                if (minClusterSizeGroup) minClusterSizeGroup.style.display = "block";
                currentLevel = "cluster";
                currentClusterId = null;
            } else {
                if (minClusterSizeGroup) minClusterSizeGroup.style.display = "none";
                currentLevel = "node";
                currentClusterId = null;
            }
        });
    }
    
    const backToClustersBtn = document.getElementById("backToClusters");
    if (backToClustersBtn) {
        backToClustersBtn.addEventListener("click", function() {
            currentLevel = "cluster";
            currentClusterId = null;
            loadGraph();
        });
    }
    
    document.getElementById("yearFrom").addEventListener("keypress", (e) => {
        if (e.key === "Enter") loadGraph();
    });
    
    document.getElementById("yearTo").addEventListener("keypress", (e) => {
        if (e.key === "Enter") loadGraph();
    });
    
    document.getElementById("venue").addEventListener("keypress", (e) => {
        if (e.key === "Enter") loadGraph();
    });
    
    console.log("Запуск начальной загрузки графа...");
    loadGraph();
});
