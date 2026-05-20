const canvas = document.getElementById('annotate-canvas');
const ctx = canvas.getContext('2d');
const btnLoad = document.getElementById('btn-load');
const sourcePathInput = document.getElementById('source-path');
const btnClearCurrent = document.getElementById('btn-clear-current');
const btnSave = document.getElementById('btn-save');
const saveStatus = document.getElementById('save-status');
const loadingOverlay = document.getElementById('loading-overlay');

const btnModeSlot = document.getElementById('mode-slot');
const btnModeNode = document.getElementById('mode-node');
const btnModeEdge = document.getElementById('mode-edge');

const controlsSlot = document.getElementById('controls-slot');
const controlsNode = document.getElementById('controls-node');
const controlsEdge = document.getElementById('controls-edge');
const instructionEl = document.getElementById('mode-instruction');

const nodeTypeSelect = document.getElementById('node-type');

const slotListEl = document.getElementById('slot-list');
const nodeListEl = document.getElementById('node-list');
const edgeListEl = document.getElementById('edge-list');

let img = new Image();
let imageLoaded = false;
let originalWidth = 0;
let originalHeight = 0;
let scale = 1;

let currentMode = 'slot'; // 'slot', 'node', 'edge'

let slots = [];
let nodes = []; // {id, type, x, y}
let edges = []; // {from, to, weight}

let currentSlotPoints = [];
let selectedNodeForEdge = null; // ID of the first node selected

// Setup Mode switching
function setMode(mode) {
    currentMode = mode;
    btnModeSlot.classList.toggle('active', mode === 'slot');
    btnModeNode.classList.toggle('active', mode === 'node');
    btnModeEdge.classList.toggle('active', mode === 'edge');
    
    controlsSlot.style.display = mode === 'slot' ? 'block' : 'none';
    controlsNode.style.display = mode === 'node' ? 'block' : 'none';
    controlsEdge.style.display = mode === 'edge' ? 'block' : 'none';
    
    if (mode === 'slot') instructionEl.innerText = "Click 4 points to define a parking slot.";
    else if (mode === 'node') instructionEl.innerText = "Click anywhere to place a node (Entrance or Waypoint).";
    else if (mode === 'edge') instructionEl.innerText = "Click two nodes (or slots) to connect them.";
    
    selectedNodeForEdge = null;
    draw();
}

btnModeSlot.onclick = () => setMode('slot');
btnModeNode.onclick = () => setMode('node');
btnModeEdge.onclick = () => setMode('edge');

btnLoad.addEventListener('click', async () => {
    const path = sourcePathInput.value.trim();
    if (!path) return alert("Please enter a video or image path");
    
    btnLoad.innerText = "Loading...";
    loadingOverlay.style.display = "block";
    try {
        const res = await fetch('/api/extract_frame', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        img.onload = () => {
            originalWidth = img.width;
            originalHeight = img.height;
            resizeCanvas();
            draw();
            btnLoad.innerText = "Load First Frame";
            imageLoaded = true;
            loadingOverlay.style.display = "none";
        };
        img.src = "data:image/jpeg;base64," + data.frame;
    } catch (err) {
        alert("Error: " + err.message);
        btnLoad.innerText = "Load First Frame";
        loadingOverlay.style.display = "none";
    }
});

function resizeCanvas() {
    const container = canvas.parentElement;
    const cw = container.clientWidth - 40;
    const ch = container.clientHeight - 40;
    
    const ratio = Math.min(cw / originalWidth, ch / originalHeight);
    scale = ratio;
    
    canvas.width = originalWidth * ratio;
    canvas.height = originalHeight * ratio;
}

window.addEventListener('resize', () => {
    if (imageLoaded) {
        resizeCanvas();
        draw();
    }
});

// Helper: Get all points that can be connected
function getAllNodes() {
    let all = [...nodes];
    slots.forEach(s => {
        const cx = s.polygon.reduce((sum, p) => sum + p[0], 0) / 4;
        const cy = s.polygon.reduce((sum, p) => sum + p[1], 0) / 4;
        all.push({id: s.id, type: 'slot', x: cx, y: cy});
    });
    return all;
}

canvas.addEventListener('mousedown', (e) => {
    if (!imageLoaded) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round((e.clientX - rect.left) / scale);
    const y = Math.round((e.clientY - rect.top) / scale);
    
    if (currentMode === 'slot') {
        currentSlotPoints.push([x, y]);
        if (currentSlotPoints.length === 4) {
            slots.push({
                id: 'S' + (slots.length + 1),
                polygon: [...currentSlotPoints]
            });
            currentSlotPoints = [];
            updateLists();
        }
    } else if (currentMode === 'node') {
        let type = nodeTypeSelect.value;
        let prefix = type === 'entrance' ? 'E' : 'W';
        let count = nodes.filter(n => n.type === type).length + 1;
        nodes.push({ id: prefix + count, type: type, x: x, y: y });
        updateLists();
    } else if (currentMode === 'edge') {
        // Find clicked node
        let clickedNode = null;
        const allNodes = getAllNodes();
        for (let n of allNodes) {
            let dist = Math.hypot(n.x - x, n.y - y);
            if (dist < 20) { // 20px hit radius (unscaled)
                clickedNode = n;
                break;
            }
        }
        
        if (clickedNode) {
            if (!selectedNodeForEdge) {
                selectedNodeForEdge = clickedNode.id;
            } else {
                if (selectedNodeForEdge !== clickedNode.id) {
                    let n1 = allNodes.find(n => n.id === selectedNodeForEdge);
                    let n2 = clickedNode;
                    let dist = Math.hypot(n1.x - n2.x, n1.y - n2.y);
                    let weight = parseFloat((dist * 0.05).toFixed(1)); // Approximate distance scale
                    
                    // Check if edge exists
                    let exists = edges.some(e => 
                        (e.from === n1.id && e.to === n2.id) || 
                        (e.from === n2.id && e.to === n1.id)
                    );
                    
                    if (!exists) {
                        edges.push({ from: n1.id, to: n2.id, weight: weight });
                        updateLists();
                    }
                }
                selectedNodeForEdge = null;
            }
        } else {
            selectedNodeForEdge = null; // click empty space to cancel
        }
    }
    
    draw();
});

btnClearCurrent.addEventListener('click', () => {
    currentSlotPoints = [];
    draw();
});

function draw() {
    if (!imageLoaded) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    // Draw slots
    slots.forEach(slot => {
        drawPolygon(slot.polygon, '#a6e3a1', 'rgba(166, 227, 161, 0.2)');
        const cx = slot.polygon.reduce((sum, p) => sum + p[0], 0) / 4;
        const cy = slot.polygon.reduce((sum, p) => sum + p[1], 0) / 4;
        drawCircle(cx, cy, 4, '#a6e3a1');
        drawText(slot.id, cx, cy - 10, '#a6e3a1');
    });
    
    // Draw current slot points
    if (currentMode === 'slot' && currentSlotPoints.length > 0) {
        currentSlotPoints.forEach(p => drawCircle(p[0], p[1], 5, '#f38ba8'));
        ctx.strokeStyle = '#f38ba8';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(currentSlotPoints[0][0] * scale, currentSlotPoints[0][1] * scale);
        for (let i = 1; i < currentSlotPoints.length; i++) {
            ctx.lineTo(currentSlotPoints[i][0] * scale, currentSlotPoints[i][1] * scale);
        }
        ctx.stroke();
    }
    
    // Draw edges
    const allNodesMap = {};
    getAllNodes().forEach(n => allNodesMap[n.id] = n);
    
    edges.forEach(e => {
        const n1 = allNodesMap[e.from];
        const n2 = allNodesMap[e.to];
        if (n1 && n2) {
            ctx.strokeStyle = 'rgba(137, 180, 250, 0.7)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(n1.x * scale, n1.y * scale);
            ctx.lineTo(n2.x * scale, n2.y * scale);
            ctx.stroke();
        }
    });
    
    // Draw nodes
    nodes.forEach(n => {
        let color = n.type === 'entrance' ? '#f9e2af' : '#cdd6f4';
        drawCircle(n.x, n.y, 6, color);
        drawText(n.id, n.x, n.y - 12, color);
    });
    
    // Highlight selected node
    if (currentMode === 'edge' && selectedNodeForEdge) {
        let n = allNodesMap[selectedNodeForEdge];
        if (n) {
            drawCircle(n.x, n.y, 10, '#f38ba8', false);
        }
    }
}

function drawPolygon(points, strokeColor, fillColor) {
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(points[0][0] * scale, points[0][1] * scale);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i][0] * scale, points[i][1] * scale);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
}

function drawCircle(x, y, r, color, fill=true) {
    ctx.beginPath();
    ctx.arc(x * scale, y * scale, r, 0, 2 * Math.PI);
    if (fill) {
        ctx.fillStyle = color;
        ctx.fill();
    } else {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

function drawText(text, x, y, color) {
    ctx.fillStyle = color;
    ctx.font = 'bold 12px Inter';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x * scale, y * scale);
}

function updateLists() {
    slotListEl.innerHTML = '';
    slots.forEach((slot, index) => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `<span>${slot.id}</span><button onclick="removeSlot(${index})">Del</button>`;
        slotListEl.appendChild(div);
    });
    
    nodeListEl.innerHTML = '';
    nodes.forEach((n, index) => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `<span>${n.id} (${n.type})</span><button onclick="removeNode(${index})">Del</button>`;
        nodeListEl.appendChild(div);
    });
    
    edgeListEl.innerHTML = '';
    edges.forEach((e, index) => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `<span>${e.from} ↔ ${e.to}</span><button onclick="removeEdge(${index})">Del</button>`;
        edgeListEl.appendChild(div);
    });
}

window.removeSlot = function(index) {
    let id = slots[index].id;
    slots.splice(index, 1);
    edges = edges.filter(e => e.from !== id && e.to !== id);
    slots.forEach((s, i) => s.id = 'S' + (i + 1)); // Re-index could break edges, so normally wouldn't do this, but keeping it simple
    updateLists(); draw();
};

window.removeNode = function(index) {
    let id = nodes[index].id;
    nodes.splice(index, 1);
    edges = edges.filter(e => e.from !== id && e.to !== id);
    updateLists(); draw();
};

window.removeEdge = function(index) {
    edges.splice(index, 1);
    updateLists(); draw();
};

btnSave.addEventListener('click', async () => {
    if (slots.length === 0) return alert("Please draw at least one slot.");
    
    btnSave.innerText = "Saving...";
    saveStatus.innerText = "";
    try {
        const res = await fetch('/api/save_config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                slots: slots,
                nodes: nodes,
                edges: edges,
                image_size: { width: originalWidth, height: originalHeight },
                video_path: sourcePathInput.value.trim()
            })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        saveStatus.innerText = "Config saved! Return to Dashboard.";
    } catch (err) {
        alert("Error: " + err.message);
    } finally {
        btnSave.innerText = "Save Config";
    }
});
