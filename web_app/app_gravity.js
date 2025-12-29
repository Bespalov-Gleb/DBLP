const gravityGraphModule = require('@gravity-ui/graph');
const Graph = gravityGraphModule.Graph || gravityGraphModule.default || gravityGraphModule;

if (typeof window !== 'undefined') {
    window.Graph = Graph;
    window.GravityGraph = Graph;
}

const API_BASE = "http://127.0.0.1:5000/api";

function convertToGravityFormat(apiData) {
    const { nodes, edges } = apiData;
    
    const blocks = nodes.map((node, index) => {
        const angle = (index / nodes.length) * 2 * Math.PI;
        const radius = Math.sqrt(nodes.length) * 80;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        return {
            is: "block-action",
            id: `node_${node.id}`,
            x: x,
            y: y,
            width: 140,
            height: 90,
            name: node.label || `Author ${node.id}`,
            degree: node.degree || 0,
            nodeId: node.id,
            anchors: [
                {
                    id: `anchor_out_${node.id}`,
                    blockId: `node_${node.id}`,
                    type: "OUT",
                    index: 0
                },
                {
                    id: `anchor_in_${node.id}`,
                    blockId: `node_${node.id}`,
                    type: "IN",
                    index: 0
                }
            ]
        };
    });

    const connections = edges.map((edge, index) => {
        return {
            id: `conn_${index}`,
            sourceBlockId: `node_${edge.source}`,
            sourceAnchorId: `anchor_out_${edge.source}`,
            targetBlockId: `node_${edge.target}`,
            targetAnchorId: `anchor_in_${edge.target}`,
            weight: edge.weight || 1
        };
    });

    return { blocks, connections };
}

function initGravityGraph(container) {
    const GraphClass = Graph || window.Graph || window.GravityGraph;
    
    if (!GraphClass) {
        throw new Error('@gravity-ui/graph не загружен. Выполните setup_gravity.bat/setup_gravity.sh для сборки bundle.');
    }

    const graph = new GraphClass({
        configurationName: "dblp-graph",
        blocks: [],
        connections: [],
        settings: {
            canDragCamera: true,
            canZoomCamera: true,
            useBezierConnections: true,
            showConnectionArrows: true,
            gridSize: 20,
            minZoom: 0.1,
            maxZoom: 5.0
        }
    }, container);

    graph.start();
    
    return graph;
}

async function loadGraphToGravity(graph, params = {}) {
    const { yearFrom, yearTo, venue, limit = 500 } = params;
    
    let url = `${API_BASE}/graph?limit=${limit}`;
    if (yearFrom) url += `&year_from=${yearFrom}`;
    if (yearTo) url += `&year_to=${yearTo}`;
    if (venue) url += `&venue=${encodeURIComponent(venue)}`;

    console.log("Загрузка графа:", url);
    
    const response = await fetch(url);
    const data = await response.json();

    if (data.error) {
        throw new Error(data.error);
    }

    console.log("Получены данные:", data.nodes.length, "узлов,", data.edges.length, "ребер");

    const { blocks, connections } = convertToGravityFormat(data);

    graph.setEntities({
        blocks: blocks,
        connections: connections
    });

    setTimeout(() => {
        graph.zoomTo("center", { padding: 100 });
    }, 100);

    return {
        nodes: blocks.length,
        edges: connections.length,
        data: data
    };
}

function setupNodeClickHandler(graph, onNodeClick) {
    if (graph.on) {
        graph.on('block-click', (event) => {
            const blockId = event.blockId;
            const nodeId = blockId.replace('node_', '');
            if (onNodeClick) {
                onNodeClick(parseInt(nodeId));
            }
        });
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initGravityGraph,
        loadGraphToGravity,
        convertToGravityFormat,
        setupNodeClickHandler,
        Graph
    };
}

if (typeof window !== 'undefined') {
    window.GravityGraphLib = {
        initGravityGraph,
        loadGraphToGravity,
        convertToGravityFormat,
        setupNodeClickHandler
    };
    
    if (Graph) {
        window.Graph = Graph;
    }
}

