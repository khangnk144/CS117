/**
 * Smart Parking System — Frontend Logic
 * Handles video streaming, 2D map rendering, and navigation controls.
 */

// --- State ---
let config = null;
let isPlaying = false;
let socket = null;

// --- DOM Elements ---
const videoFeed = document.getElementById('video-feed');
const videoOverlay = document.getElementById('video-overlay');
const btnPlay = document.getElementById('btn-play');
const btnStep = document.getElementById('btn-step');
const iconPlay = document.getElementById('icon-play');
const iconPause = document.getElementById('icon-pause');
const playText = document.getElementById('play-text');
const frameSlider = document.getElementById('frame-slider');
const frameCounter = document.getElementById('frame-counter');
const startNodeSelect = document.getElementById('start-node');
const statusBadge = document.getElementById('status-badge');
const statusText = document.getElementById('status-text');
const fpsBadge = document.getElementById('fps-badge');
const mapCanvas = document.getElementById('parking-map');
const mapCtx = mapCanvas.getContext('2d');

// Stat elements
const statTotal = document.getElementById('stat-total');
const statVacant = document.getElementById('stat-vacant');
const statOccupied = document.getElementById('stat-occupied');
const statTime = document.getElementById('stat-time');

// Navigation elements
const navTarget = document.getElementById('nav-target');
const navDistance = document.getElementById('nav-distance');
const navPath = document.getElementById('nav-path');

// --- Initialize ---
async function init() {
    try {
        const res = await fetch('/api/config');
        config = await res.json();
        if (config.error) throw new Error(config.error);

        // Populate start node selector
        populateStartNodes(config.graph.nodes);

        // Set slider max
        const statusRes = await fetch('/api/status');
        const status = await statusRes.json();
        frameSlider.max = Math.max(0, status.total_frames - 1);

        // Set status
        statusText.textContent = `${config.parking_lot} — ${config.weather}`;
        statusBadge.classList.remove('offline');

        // Setup WebSocket
        setupSocket();

        // Process first frame
        await processFrame();
    } catch (err) {
        console.error('Init failed:', err);
        statusText.textContent = 'Error: ' + err.message;
        statusBadge.classList.add('offline');
    }
}

function populateStartNodes(nodes) {
    startNodeSelect.innerHTML = '';
    const entrances = nodes.filter(n => n.type === 'entrance');
    const waypoints = nodes.filter(n => n.type === 'waypoint');

    entrances.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n.id;
        opt.textContent = `🚗 ${n.id} (Entrance)`;
        startNodeSelect.appendChild(opt);
    });
    waypoints.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n.id;
        opt.textContent = `📍 ${n.id} (Waypoint)`;
        startNodeSelect.appendChild(opt);
    });
}

// --- WebSocket ---
function setupSocket() {
    socket = io();

    socket.on('connect', () => console.log('WebSocket connected'));
    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        isPlaying = false;
        updatePlayButton();
    });

    socket.on('frame_update', (data) => {
        updateUI(data);
    });
}

// --- API Calls ---
async function processFrame(frameIndex) {
    try {
        const body = { start_node: startNodeSelect.value };
        if (frameIndex !== undefined) body.frame_index = frameIndex;

        const res = await fetch('/api/process_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        updateUI(data);
    } catch (err) {
        console.error('Process frame error:', err);
    }
}

async function stepFrame() {
    try {
        const res = await fetch('/api/next_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_node: startNodeSelect.value }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        updateUI(data);
    } catch (err) {
        console.error('Step frame error:', err);
    }
}

// --- UI Update ---
function updateUI(data) {
    // Video feed
    if (data.annotated_frame) {
        videoFeed.src = 'data:image/jpeg;base64,' + data.annotated_frame;
        videoOverlay.classList.add('hidden');
    }

    // Frame counter & slider
    frameSlider.value = data.frame_index;
    frameCounter.textContent = `${data.frame_index + 1} / ${data.total_frames}`;

    // Stats
    const s = data.summary;
    if (s) {
        statTotal.textContent = s.total_slots;
        statVacant.textContent = s.vacant;
        statOccupied.textContent = s.occupied;
    }
    statTime.textContent = data.processing_time_ms?.toFixed(0) || '--';
    fpsBadge.textContent = `${data.processing_time_ms?.toFixed(0) || '--'} ms`;

    // Navigation
    const nav = data.navigation;
    if (nav) {
        navTarget.textContent = nav.target_slot || 'None';
        navDistance.textContent = nav.distance ? `${nav.distance} m` : '--';
        navPath.textContent = nav.path ? nav.path.join(' → ') : '--';
    }

    // 2D Map
    if (config && data.slot_statuses) {
        drawMap(data.slot_statuses, data.navigation);
    }
}

// --- 2D Map Drawing ---
function drawMap(slotStatuses, navigation) {
    const w = mapCanvas.width;
    const h = mapCanvas.height;
    const imgW = config.image_size?.width || 1280;
    const imgH = config.image_size?.height || 720;
    const scaleX = w / imgW;
    const scaleY = h / imgH;

    mapCtx.clearRect(0, 0, w, h);

    // Background
    mapCtx.fillStyle = '#0d1117';
    mapCtx.fillRect(0, 0, w, h);

    // Grid
    mapCtx.strokeStyle = 'rgba(255,255,255,0.03)';
    mapCtx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
        mapCtx.beginPath(); mapCtx.moveTo(x, 0); mapCtx.lineTo(x, h); mapCtx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
        mapCtx.beginPath(); mapCtx.moveTo(0, y); mapCtx.lineTo(w, y); mapCtx.stroke();
    }

    const targetSlot = navigation?.target_slot;
    const pathNodes = navigation?.path || [];
    const statusMap = {};
    slotStatuses.forEach(s => { statusMap[s.id] = s; });

    // Draw graph edges
    if (config.graph) {
        mapCtx.strokeStyle = 'rgba(148,163,184,0.15)';
        mapCtx.lineWidth = 1;
        const nodeMap = {};
        config.graph.nodes.forEach(n => { nodeMap[n.id] = n; });

        config.graph.edges.forEach(e => {
            const a = nodeMap[e.from], b = nodeMap[e.to];
            if (a && b) {
                // Highlight path edges
                const inPath = pathNodes.includes(e.from) && pathNodes.includes(e.to);
                if (inPath) {
                    mapCtx.strokeStyle = 'rgba(234,179,8,0.6)';
                    mapCtx.lineWidth = 3;
                } else {
                    mapCtx.strokeStyle = 'rgba(148,163,184,0.15)';
                    mapCtx.lineWidth = 1;
                }
                mapCtx.beginPath();
                mapCtx.moveTo(a.x * scaleX, a.y * scaleY);
                mapCtx.lineTo(b.x * scaleX, b.y * scaleY);
                mapCtx.stroke();
            }
        });

        // Draw nodes (entrances/waypoints)
        config.graph.nodes.forEach(n => {
            const x = n.x * scaleX, y = n.y * scaleY;
            if (n.type === 'entrance') {
                mapCtx.fillStyle = '#3b82f6';
                mapCtx.beginPath();
                mapCtx.arc(x, y, 6, 0, Math.PI * 2);
                mapCtx.fill();
                mapCtx.fillStyle = '#fff';
                mapCtx.font = '10px Inter, sans-serif';
                mapCtx.textAlign = 'center';
                mapCtx.fillText(n.id, x, y - 10);
            } else if (n.type === 'waypoint') {
                mapCtx.fillStyle = 'rgba(148,163,184,0.4)';
                mapCtx.beginPath();
                mapCtx.arc(x, y, 3, 0, Math.PI * 2);
                mapCtx.fill();
            }
        });
    }

    // Draw slots
    slotStatuses.forEach(slot => {
        const pts = slot.polygon;
        if (!pts || pts.length < 3) return;

        const isTarget = slot.id === targetSlot;
        let fillColor, strokeColor;
        if (isTarget) {
            fillColor = 'rgba(234,179,8,0.35)';
            strokeColor = '#eab308';
        } else if (slot.status === 'occupied') {
            fillColor = 'rgba(239,68,68,0.25)';
            strokeColor = '#ef4444';
        } else {
            fillColor = 'rgba(34,197,94,0.25)';
            strokeColor = '#22c55e';
        }

        mapCtx.beginPath();
        mapCtx.moveTo(pts[0][0] * scaleX, pts[0][1] * scaleY);
        for (let i = 1; i < pts.length; i++) {
            mapCtx.lineTo(pts[i][0] * scaleX, pts[i][1] * scaleY);
        }
        mapCtx.closePath();
        mapCtx.fillStyle = fillColor;
        mapCtx.fill();
        mapCtx.strokeStyle = strokeColor;
        mapCtx.lineWidth = isTarget ? 3 : 1.5;
        mapCtx.stroke();

        // Label
        const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length * scaleX;
        const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length * scaleY;
        mapCtx.fillStyle = '#fff';
        mapCtx.font = `${isTarget ? 'bold ' : ''}9px Inter, sans-serif`;
        mapCtx.textAlign = 'center';
        mapCtx.textBaseline = 'middle';
        mapCtx.fillText(slot.id, cx, cy);
    });
}

// --- Event Listeners ---
btnPlay.addEventListener('click', () => {
    if (!socket) return;
    isPlaying = !isPlaying;
    if (isPlaying) {
        socket.emit('start_stream');
    } else {
        socket.emit('stop_stream');
    }
    updatePlayButton();
});

btnStep.addEventListener('click', () => {
    if (isPlaying) {
        isPlaying = false;
        socket.emit('stop_stream');
        updatePlayButton();
    }
    stepFrame();
});

frameSlider.addEventListener('input', () => {
    if (isPlaying) {
        isPlaying = false;
        socket.emit('stop_stream');
        updatePlayButton();
    }
    processFrame(parseInt(frameSlider.value));
});

startNodeSelect.addEventListener('change', () => {
    fetch('/api/set_start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_node: startNodeSelect.value }),
    });
    if (!isPlaying) processFrame();
});

function updatePlayButton() {
    iconPlay.style.display = isPlaying ? 'none' : 'inline';
    iconPause.style.display = isPlaying ? 'inline' : 'none';
    playText.textContent = isPlaying ? 'Pause' : 'Play';
}

// --- Start ---
document.addEventListener('DOMContentLoaded', init);
