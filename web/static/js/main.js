/**
 * Smart Parking System — Frontend Logic
 * Handles video streaming, 2D map rendering, and navigation controls.
 * Click on video to set your start position.
 */

let config = null;
let isPlaying = false;
let socket = null;
let userClickPosition = null; // {x, y, displayX, displayY} — clicked position on video

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

const statTotal = document.getElementById('stat-total');
const statVacant = document.getElementById('stat-vacant');
const statOccupied = document.getElementById('stat-occupied');
const statTime = document.getElementById('stat-time');
const navTarget = document.getElementById('nav-target');
const navDistance = document.getElementById('nav-distance');
const navPath = document.getElementById('nav-path');

async function init() {
    try {
        const res = await fetch('/api/config');
        config = await res.json();
        if (config.error) throw new Error(config.error);
        populateStartNodes(config.graph.nodes);
        const statusRes = await fetch('/api/status');
        const status = await statusRes.json();
        frameSlider.max = Math.max(0, status.total_frames - 1);
        statusText.textContent = `${config.parking_lot} — ${config.weather}`;
        statusBadge.classList.remove('offline');
        setupSocket();
        await processFrame();

        // Click on video to set user position
        videoFeed.addEventListener('click', (e) => {
            if (!config) return;
            const rect = videoFeed.getBoundingClientRect();
            const scaleX = config.image_size.width / rect.width;
            const scaleY = config.image_size.height / rect.height;
            const x = Math.round((e.clientX - rect.left) * scaleX);
            const y = Math.round((e.clientY - rect.top) * scaleY);

            // Show the click marker on the video
            const marker = document.getElementById('click-marker');
            marker.style.left = (e.clientX - rect.left) + 'px';
            marker.style.top = (e.clientY - rect.top) + 'px';
            marker.style.display = 'block';

            // Hide the hint after first click
            const hint = document.getElementById('click-hint');
            if (hint) hint.style.display = 'none';

            // Show position info and clear button
            userClickPosition = { x, y, displayX: e.clientX - rect.left, displayY: e.clientY - rect.top };
            const posDisplay = document.getElementById('user-pos-display');
            const posText = document.getElementById('user-pos-text');
            const btnClear = document.getElementById('btn-clear-pos');
            posDisplay.style.display = 'block';
            posText.textContent = `(${x}, ${y})`;
            btnClear.style.display = 'inline-block';

            fetch('/api/set_user_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x, y })
            }).then(() => {
                processFrame();
            });
        });

        // Clear position button
        document.getElementById('btn-clear-pos').addEventListener('click', () => {
            clearClickedPosition();
            // Reset to dropdown node
            fetch('/api/set_user_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x: null, y: null })
            }).then(() => processFrame());
        });
    } catch (err) {
        console.error('Init failed:', err);
        statusText.textContent = 'Error: ' + err.message;
        statusBadge.classList.add('offline');
    }
}

function clearClickedPosition() {
    userClickPosition = null;
    document.getElementById('click-marker').style.display = 'none';
    document.getElementById('user-pos-display').style.display = 'none';
    document.getElementById('btn-clear-pos').style.display = 'none';
    const hint = document.getElementById('click-hint');
    if (hint) hint.style.display = 'block';
}

function populateStartNodes(nodes) {
    startNodeSelect.innerHTML = '';
    nodes.filter(n => n.type === 'entrance').forEach(n => {
        let opt = document.createElement('option');
        opt.value = n.id;
        opt.textContent = `🚗 ${n.id} (Entrance)`;
        startNodeSelect.appendChild(opt);
    });
    nodes.filter(n => n.type === 'waypoint').forEach(n => {
        let opt = document.createElement('option');
        opt.value = n.id;
        opt.textContent = `📍 ${n.id} (Waypoint)`;
        startNodeSelect.appendChild(opt);
    });
}

function setupSocket() {
    socket = io();
    socket.on('connect', () => console.log('WebSocket connected'));
    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        isPlaying = false;
        updatePlayButton();
    });
    socket.on('frame_update', (data) => updateUI(data));
}

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

function updateUI(data) {
    if (data.annotated_frame) {
        videoFeed.src = 'data:image/jpeg;base64,' + data.annotated_frame;
        videoOverlay.classList.add('hidden');
    }
    frameSlider.value = data.frame_index;
    frameCounter.textContent = `${data.frame_index + 1} / ${data.total_frames}`;
    if (data.summary) {
        statTotal.textContent = data.summary.total_slots;
        statVacant.textContent = data.summary.vacant;
        statOccupied.textContent = data.summary.occupied;
    }
    statTime.textContent = data.processing_time_ms?.toFixed(0) || '--';
    fpsBadge.textContent = `${data.processing_time_ms?.toFixed(0) || '--'} ms`;

    const nav = data.navigation;
    if (nav) {
        navTarget.textContent = nav.target_slot || 'None';
        navDistance.textContent = nav.distance ? `${nav.distance} m` : '--';
        navPath.textContent = nav.path ? nav.path.join(' → ') : '--';
    }
    if (config && data.slot_statuses) {
        drawMap(data.slot_statuses, data.navigation);
    }
}

function drawMap(slotStatuses, navigation) {
    const w = mapCanvas.width;
    const h = mapCanvas.height;
    const imgW = config.image_size?.width || 1280;
    const imgH = config.image_size?.height || 720;
    const scaleX = w / imgW;
    const scaleY = h / imgH;
    mapCtx.clearRect(0, 0, w, h);
    mapCtx.fillStyle = '#0d1117';
    mapCtx.fillRect(0, 0, w, h);
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
    if (config.graph) {
        const nodeMap = {};
        config.graph.nodes.forEach(n => { nodeMap[n.id] = n; });
        config.graph.edges.forEach(e => {
            const a = nodeMap[e.from], b = nodeMap[e.to];
            if (!a || !b) return;
            const inPath = pathNodes.includes(e.from) && pathNodes.includes(e.to);
            mapCtx.strokeStyle = inPath ? 'rgba(234,179,8,0.6)' : 'rgba(148,163,184,0.15)';
            mapCtx.lineWidth = inPath ? 3 : 1;
            mapCtx.beginPath();
            mapCtx.moveTo(a.x * scaleX, a.y * scaleY);
            mapCtx.lineTo(b.x * scaleX, b.y * scaleY);
            mapCtx.stroke();
        });

        // Draw custom click position and its path connection
        if (userClickPosition && pathNodes.length > 1 && pathNodes[0].startsWith('TEMP_')) {
            const nextNode = nodeMap[pathNodes[1]];
            if (nextNode) {
                mapCtx.strokeStyle = 'rgba(234,179,8,0.6)'; // yellow path
                mapCtx.lineWidth = 3;
                mapCtx.beginPath();
                mapCtx.moveTo(userClickPosition.x * scaleX, userClickPosition.y * scaleY);
                mapCtx.lineTo(nextNode.x * scaleX, nextNode.y * scaleY);
                mapCtx.stroke();
            }
            // Draw the user click node marker
            mapCtx.fillStyle = '#ef4444'; // Red color for user start
            mapCtx.beginPath();
            mapCtx.arc(userClickPosition.x * scaleX, userClickPosition.y * scaleY, 6, 0, Math.PI * 2);
            mapCtx.fill();
            mapCtx.fillStyle = '#fff';
            mapCtx.font = '10px Inter, sans-serif';
            mapCtx.textAlign = 'center';
            mapCtx.fillText('You', userClickPosition.x * scaleX, userClickPosition.y * scaleY - 10);
        }

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

        const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length * scaleX;
        const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length * scaleY;
        mapCtx.fillStyle = '#fff';
        mapCtx.font = `${isTarget ? 'bold ' : ''}9px Inter, sans-serif`;
        mapCtx.textAlign = 'center';
        mapCtx.textBaseline = 'middle';
        mapCtx.fillText(slot.id, cx, cy);
    });
}

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
    // When user picks from dropdown, clear any clicked position
    clearClickedPosition();
    fetch('/api/set_user_position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x: null, y: null })
    });
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

document.addEventListener('DOMContentLoaded', init);