const canvas = document.getElementById('annotate-canvas');
const ctx = canvas.getContext('2d');
const btnLoad = document.getElementById('btn-load');
const sourcePathInput = document.getElementById('source-path');
const slotListEl = document.getElementById('slot-list');
const btnClearCurrent = document.getElementById('btn-clear-current');
const btnSave = document.getElementById('btn-save');
const saveStatus = document.getElementById('save-status');
const loadingOverlay = document.getElementById('loading-overlay');

let img = new Image();
let slots = [];
let currentPoints = [];
let imageLoaded = false;
let originalWidth = 0;
let originalHeight = 0;
let scale = 1;

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

canvas.addEventListener('mousedown', (e) => {
    if (!imageLoaded) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;
    
    currentPoints.push([Math.round(x), Math.round(y)]);
    
    if (currentPoints.length === 4) {
        slots.push({
            id: 'S' + (slots.length + 1),
            polygon: [...currentPoints]
        });
        currentPoints = [];
        updateSlotList();
    }
    draw();
});

btnClearCurrent.addEventListener('click', () => {
    currentPoints = [];
    draw();
});

function draw() {
    if (!imageLoaded) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    // Draw confirmed slots
    slots.forEach(slot => {
        drawPolygon(slot.polygon, '#a6e3a1', 'rgba(166, 227, 161, 0.3)');
        // Draw ID
        const cx = slot.polygon.reduce((sum, p) => sum + p[0], 0) / 4;
        const cy = slot.polygon.reduce((sum, p) => sum + p[1], 0) / 4;
        ctx.fillStyle = 'white';
        ctx.font = 'bold 14px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(slot.id, cx * scale, cy * scale);
    });
    
    // Draw current points
    if (currentPoints.length > 0) {
        ctx.fillStyle = '#f38ba8';
        currentPoints.forEach(p => {
            ctx.beginPath();
            ctx.arc(p[0] * scale, p[1] * scale, 5, 0, 2 * Math.PI);
            ctx.fill();
        });
        
        ctx.strokeStyle = '#f38ba8';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(currentPoints[0][0] * scale, currentPoints[0][1] * scale);
        for (let i = 1; i < currentPoints.length; i++) {
            ctx.lineTo(currentPoints[i][0] * scale, currentPoints[i][1] * scale);
        }
        ctx.stroke();
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

function updateSlotList() {
    slotListEl.innerHTML = '';
    slots.forEach((slot, index) => {
        const div = document.createElement('div');
        div.className = 'slot-item';
        div.innerHTML = `
            <span>${slot.id}</span>
            <button class="btn" onclick="removeSlot(${index})">Delete</button>
        `;
        slotListEl.appendChild(div);
    });
}

window.removeSlot = function(index) {
    slots.splice(index, 1);
    // Re-index
    slots.forEach((s, i) => s.id = 'S' + (i + 1));
    updateSlotList();
    draw();
};

btnSave.addEventListener('click', async () => {
    if (slots.length === 0) return alert("No slots drawn! Please draw at least one slot.");
    
    btnSave.innerText = "Saving...";
    saveStatus.innerText = "";
    try {
        const res = await fetch('/api/save_config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                slots: slots,
                image_size: { width: originalWidth, height: originalHeight },
                video_path: sourcePathInput.value.trim()
            })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        saveStatus.innerText = "Config saved! You can now return to the Dashboard.";
    } catch (err) {
        alert("Error: " + err.message);
    } finally {
        btnSave.innerText = "Save & Generate Graph";
    }
});
