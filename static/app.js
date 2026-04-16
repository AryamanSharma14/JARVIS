/* ═══════════════════════════════════════════════════════════════
   ARVIS Iron Man HUD — app.js
   Socket.IO client + Arc Reactor canvas animation
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Socket.IO ────────────────────────────────────────────────────
const socket = io({ transports: ['websocket', 'polling'] });

socket.on('status', ({ text, state }) => {
  document.getElementById('status-text').textContent = text;
  document.body.className = `state-${state || 'idle'}`;
});

socket.on('history', ({ text, tag }) => {
  const chat = document.getElementById('chat-history');
  const div = document.createElement('div');
  div.className = `chat-msg ${tag}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
});

socket.on('typing_enabled', ({ enabled }) => {
  const inp = document.getElementById('user-input');
  const btn = document.getElementById('send-btn');
  inp.disabled = !enabled;
  btn.disabled = !enabled;
  if (enabled) inp.focus();
});

socket.on('llm_status', ({ online, model }) => {
  const badge = document.getElementById('llm-badge');
  const label = document.getElementById('llm-label');
  badge.className = online ? 'llm-online' : 'llm-offline';
  label.textContent = online ? `LLM ● ${model.toUpperCase()}` : 'LLM OFFLINE';
});

socket.on('stats', ({ cpu, mem, pwr }) => {
  setStat('cpu', cpu);
  setStat('mem', mem);
  setStat('pwr', pwr);
});

function setStat(id, val) {
  const pct = Math.min(100, Math.max(0, val || 0));
  document.getElementById(`bar-${id}`).style.width = `${pct}%`;
  document.getElementById(`val-${id}`).textContent = `${Math.round(pct)}%`;
}

// ── User input ───────────────────────────────────────────────────
const inputEl = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

function sendInput() {
  const text = inputEl.value.trim();
  if (!text) return;
  socket.emit('user_input', { text });
  inputEl.value = '';
}

sendBtn.addEventListener('click', sendInput);
inputEl.addEventListener('keydown', e => { if (e.key === 'Enter') sendInput(); });

// ── Clock ────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const ss = String(now.getSeconds()).padStart(2, '0');
  document.getElementById('clock').textContent = `${hh}:${mm}:${ss}`;
}
updateClock();
setInterval(updateClock, 1000);

// ── Arc Reactor Canvas ───────────────────────────────────────────
const canvas = document.getElementById('arc-canvas');
const ctx    = canvas.getContext('2d');

const CYAN     = '#00d1ff';
const CYAN_DIM = '#0077ff';
const W = canvas.width;
const H = canvas.height;
const CX = W / 2;
const CY = H / 2;

// Ring config: [radius, dashLen, gapLen, rotationSpeed]
const RINGS = [
  [98, 18, 10, 0.003],
  [82, 14,  8, 0.009],
  [66, 10,  6, -0.014],
  [50,  8,  5,  0.022],
];

let angles    = RINGS.map(() => 0);
let t         = 0;

function drawRing(radius, dashLen, gapLen, angle) {
  const circumference = 2 * Math.PI * radius;
  const dashCount = Math.floor(circumference / (dashLen + gapLen));
  const dashAngle = (2 * Math.PI) / dashCount;

  ctx.save();
  ctx.translate(CX, CY);
  ctx.rotate(angle);

  for (let i = 0; i < dashCount; i++) {
    const a = i * dashAngle;
    ctx.beginPath();
    ctx.arc(0, 0, radius, a, a + (dashAngle * dashLen / (dashLen + gapLen)));
    ctx.stroke();
  }
  ctx.restore();
}

function isActive() {
  return document.body.classList.contains('state-listening') ||
         document.body.classList.contains('state-processing');
}

function drawFrame() {
  ctx.clearRect(0, 0, W, H);

  // Glow intensity
  const active = isActive();
  const glow = active
    ? 0.7 + 0.3 * Math.sin(t * 3.0)
    : 0.5 + 0.2 * Math.sin(t * 1.2);

  // Outer glow circle
  const grad = ctx.createRadialGradient(CX, CY, 30, CX, CY, 110);
  grad.addColorStop(0, `rgba(0, 209, 255, ${0.08 * glow})`);
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(CX, CY, 110, 0, 2 * Math.PI);
  ctx.fill();

  // Rings
  RINGS.forEach(([radius, dashLen, gapLen, speed], i) => {
    angles[i] += speed;
    ctx.strokeStyle = CYAN;
    ctx.lineWidth   = 1.5;
    ctx.shadowColor = CYAN;
    ctx.shadowBlur  = 8 * glow;
    drawRing(radius, dashLen, gapLen, angles[i]);
  });

  // Inner filled circle
  ctx.shadowBlur = 18 * glow;
  ctx.shadowColor = CYAN;
  ctx.fillStyle  = `rgba(0, 119, 255, ${0.15 * glow})`;
  ctx.beginPath();
  ctx.arc(CX, CY, 38, 0, 2 * Math.PI);
  ctx.fill();

  ctx.strokeStyle = CYAN_DIM;
  ctx.lineWidth   = 1;
  ctx.beginPath();
  ctx.arc(CX, CY, 38, 0, 2 * Math.PI);
  ctx.stroke();

  // Central "A" glyph
  ctx.shadowBlur  = 20 * glow;
  ctx.shadowColor = CYAN;
  ctx.fillStyle   = CYAN;
  ctx.font        = `bold 26px Orbitron, sans-serif`;
  ctx.textAlign   = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('A', CX, CY + 1);

  ctx.shadowBlur = 0;
  t += 0.016;
  requestAnimationFrame(drawFrame);
}

drawFrame();
