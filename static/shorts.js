function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtTime(t) {
  return t.toFixed(1) + 's';
}

async function doAnalyze() {
  const url = document.getElementById('url').value.trim();
  const btn = document.getElementById('analyzeBtn');
  const spinner = document.getElementById('spinner');
  const errorBox = document.getElementById('error');
  const results = document.getElementById('results');

  if (!url) {
    errorBox.textContent = 'Please paste a YouTube Shorts URL.';
    errorBox.classList.remove('hidden');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Analyzing...';
  spinner.classList.remove('hidden');
  errorBox.classList.add('hidden');
  results.classList.add('hidden');

  try {
    const resp = await fetch('/api/analyze-short', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url})
    });
    const data = await resp.json();

    if (data.error) {
      errorBox.textContent = data.error;
      errorBox.classList.remove('hidden');
      return;
    }

    renderResults(data);
    results.classList.remove('hidden');
  } catch (e) {
    errorBox.textContent = 'Network error: ' + e.message;
    errorBox.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Analyze';
    spinner.classList.add('hidden');
  }
}

function renderResults(data) {
  renderTimeline(data.duration, data.events || []);
  renderTranscript(data.transcript);
}

function renderTimeline(duration, events) {
  const timeline = document.getElementById('timeline');
  const ticksEl = document.getElementById('timelineTicks');
  timeline.innerHTML = '';
  ticksEl.innerHTML = '';

  if (!duration || duration <= 0) duration = 1;

  const typeClass = {cut: 'dot-cut', motion: 'dot-motion', audio: 'dot-audio'};

  events.forEach(ev => {
    const pct = Math.min(100, Math.max(0, (ev.time / duration) * 100));
    const marker = document.createElement('div');
    marker.className = 'timeline-marker ' + (typeClass[ev.type] || '');
    marker.style.left = pct + '%';
    marker.title = `${ev.type} @ ${fmtTime(ev.time)} (intensity ${ev.intensity})`;
    timeline.appendChild(marker);
  });

  const tickInterval = 0.5;
  for (let t = 0; t <= duration + 0.001; t += tickInterval) {
    const pct = Math.min(100, (t / duration) * 100);
    const tick = document.createElement('div');
    tick.className = 'timeline-tick';
    tick.style.left = pct + '%';
    tick.textContent = t.toFixed(1);
    ticksEl.appendChild(tick);
  }
}

function renderTranscript(transcript) {
  const el = document.getElementById('transcript');
  if (!transcript || !transcript.segments || transcript.segments.length === 0) {
    el.innerHTML = `<p class="transcript-line">${escHtml(transcript && transcript.text || 'No speech detected.')}</p>`;
    return;
  }
  el.innerHTML = transcript.segments.map(seg => `
    <div class="transcript-line">
      <span class="transcript-time">${fmtTime(seg.start)} - ${fmtTime(seg.end)}</span>
      <span class="transcript-text">${escHtml(seg.text)}</span>
    </div>
  `).join('');
}

document.getElementById('url').addEventListener('keydown', e => {
  if (e.key === 'Enter') doAnalyze();
});
