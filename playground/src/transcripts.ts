/**
 * BoS Transcript Search & Reader
 *
 * List view: shows all meetings, live-filters against full text when searching.
 * Reader view: renders a single transcript with timestamped 5-minute blocks.
 *
 * URL routing:
 *   /transcripts/         → list view
 *   /transcripts/?clip=35 → reader view for clip 35
 */

const BASE = import.meta.env.BASE_URL; // e.g. "/playground/" in prod, "/" in dev

// ── Types ────────────────────────────────────────────────────────────────────

interface ManifestEntry {
  clip_id: number;
  title: string;
  meeting_date: string;
  meeting_url: string;
  duration: string;
  segment_count: number;
  has_diarization?: boolean;
}

interface IndexEntry {
  clip_id: number;
  meeting_date: string;
  title: string;
  text: string;
}

interface Segment {
  id: number;
  start: number;
  end: number;
  text: string;
  speaker?: string;
}

interface TranscriptData {
  meta: {
    clip_id: number;
    title: string;
    meeting_date: string;
    meeting_url: string;
    transcribed_at: string;
  };
  transcript: string;
  segments: Segment[];
}

// ── State ────────────────────────────────────────────────────────────────────

let manifest: ManifestEntry[] = [];
let searchIndex: IndexEntry[] | null = null;
let indexLoading = false;

// ── DOM refs ─────────────────────────────────────────────────────────────────

const listView = document.getElementById('list-view')!;
const readerView = document.getElementById('reader-view')!;
const readerContent = document.getElementById('reader-content')!;
const resultsEl = document.getElementById('results')!;
const searchEl = document.getElementById('search') as HTMLInputElement;
const searchStatus = document.getElementById('search-status')!;

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  // "2023-04-19" → "April 19, 2023"
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

function fmtTimestamp(seconds: number): string {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`;
}

function escape(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Return an ~200-char excerpt around the first match, with <mark> around it. */
function buildExcerpt(text: string, query: string): string {
  const lower = text.toLowerCase();
  const idx = lower.indexOf(query.toLowerCase());
  if (idx === -1) return escape(text.slice(0, 200)) + '…';

  const radius = 90;
  const start = Math.max(0, idx - radius);
  const end = Math.min(text.length, idx + query.length + radius);
  const before = escape(text.slice(start, idx));
  const match = escape(text.slice(idx, idx + query.length));
  const after = escape(text.slice(idx + query.length, end));
  const prefix = start > 0 ? '…' : '';
  const suffix = end < text.length ? '…' : '';
  return `${prefix}${before}<mark>${match}</mark>${after}${suffix}`;
}

function clipUrl(clipId: number): string {
  // Produce a URL that stays within the same base path
  const base = window.location.pathname.replace(/\?.*$/, '');
  return `${base}?clip=${clipId}`;
}

// ── Render: meeting list ──────────────────────────────────────────────────────

function renderMeetingList(entries: ManifestEntry[]) {
  if (entries.length === 0) {
    resultsEl.innerHTML = '<div class="loading-msg">No meetings found.</div>';
    return;
  }
  resultsEl.innerHTML = entries.map(e => `
    <a class="meeting-item" href="${clipUrl(e.clip_id)}">
      <span class="meeting-date">${e.meeting_date}</span>
      <span class="meeting-title">${escape(e.title)}</span>
      ${e.has_diarization ? '<span class="meeting-badge">speakers</span>' : ''}
      <span class="meeting-duration">${e.duration}</span>
    </a>
  `).join('');
}

// ── Render: search results ────────────────────────────────────────────────────

function renderSearchResults(results: { entry: IndexEntry; excerpt: string }[], total: number, query: string) {
  const shown = results.length;
  const overflow = total - shown;

  resultsEl.innerHTML = results.map(({ entry, excerpt }) => `
    <a class="result-item" href="${clipUrl(entry.clip_id)}">
      <div class="result-meta">${entry.meeting_date} — ${escape(entry.title)}</div>
      <div class="result-excerpt">${excerpt}</div>
    </a>
  `).join('');

  if (overflow > 0) {
    const note = document.createElement('div');
    note.className = 'result-overflow';
    note.textContent = `${overflow} more match${overflow === 1 ? '' : 'es'} — refine your search to narrow results.`;
    resultsEl.appendChild(note);
  }

  searchStatus.textContent = `${total} meeting${total === 1 ? '' : 's'} contain "${query}"`;
}

// ── Search logic ──────────────────────────────────────────────────────────────

async function ensureIndex(): Promise<IndexEntry[]> {
  if (searchIndex) return searchIndex;
  if (indexLoading) {
    // Wait for the in-flight load
    while (indexLoading) await new Promise(r => setTimeout(r, 50));
    return searchIndex!;
  }
  indexLoading = true;
  searchStatus.textContent = 'Loading search index…';
  const res = await fetch(`${BASE}transcripts/index.json`);
  if (!res.ok) throw new Error(`Failed to load index: ${res.status}`);
  searchIndex = await res.json();
  indexLoading = false;
  return searchIndex!;
}

async function runSearch(query: string) {
  const q = query.trim();
  if (q.length < 2) {
    renderMeetingList(manifest);
    searchStatus.textContent = `${manifest.length} meetings`;
    return;
  }

  try {
    const index = await ensureIndex();
    const lower = q.toLowerCase();
    const matches = index.filter(e => e.text.toLowerCase().includes(lower));
    const MAX_SHOWN = 50;
    const results = matches.slice(0, MAX_SHOWN).map(e => ({
      entry: e,
      excerpt: buildExcerpt(e.text, q),
    }));
    renderSearchResults(results, matches.length, q);
  } catch (err) {
    searchStatus.textContent = `Search error: ${err}`;
  }
}

// ── Debounce ──────────────────────────────────────────────────────────────────

function debounce<T extends (...args: any[]) => void>(fn: T, ms: number): T {
  let timer: ReturnType<typeof setTimeout>;
  return ((...args: any[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  }) as T;
}

// ── Speaker colors ────────────────────────────────────────────────────────────

// 15 distinct colors for SPEAKER_00–SPEAKER_14; UNKNOWN gets a neutral grey
const SPEAKER_COLORS = [
  '#00d9ff', '#e94560', '#7bed9f', '#ffd166', '#a29bfe',
  '#fd79a8', '#55efc4', '#fdcb6e', '#74b9ff', '#ff7675',
  '#81ecec', '#fab1a0', '#b2bec3', '#6c5ce7', '#00cec9',
];

function speakerColor(label: string): string {
  if (!label || label === 'UNKNOWN') return '#666';
  const m = label.match(/(\d+)$/);
  if (!m) return '#888';
  return SPEAKER_COLORS[parseInt(m[1], 10) % SPEAKER_COLORS.length];
}

function speakerLabel(label: string): string {
  if (!label || label === 'UNKNOWN') return 'UNKNOWN';
  // SPEAKER_00 → Speaker 1 (1-indexed for readability)
  const m = label.match(/(\d+)$/);
  if (!m) return label;
  return `Speaker ${parseInt(m[1], 10) + 1}`;
}

// ── Reader view ───────────────────────────────────────────────────────────────

const BLOCK_SECONDS = 300; // 5-minute blocks

interface SpeakerTurn {
  speaker: string;
  start: number;
  text: string;
}

function groupIntoTurns(segments: Segment[]): SpeakerTurn[] {
  const turns: SpeakerTurn[] = [];
  let current: SpeakerTurn | null = null;

  for (const seg of segments) {
    const speaker = seg.speaker ?? 'UNKNOWN';
    const text = seg.text.trim();
    if (!text) continue;
    if (current && current.speaker === speaker) {
      current.text += ' ' + text;
    } else {
      if (current) turns.push(current);
      current = { speaker, start: seg.start, text };
    }
  }
  if (current) turns.push(current);
  return turns;
}

function renderReader(data: TranscriptData) {
  const { meta, segments } = data;

  if (!segments || segments.length === 0) {
    readerContent.innerHTML = '<div class="error-msg">No segments found in this transcript.</div>';
    return;
  }

  const hasDiarization = segments.some(s => s.speaker && s.speaker !== 'UNKNOWN');

  let bodyHtml: string;

  if (hasDiarization) {
    // Speaker-turn view
    const turns = groupIntoTurns(segments);
    bodyHtml = turns.map(turn => {
      const color = speakerColor(turn.speaker);
      const label = speakerLabel(turn.speaker);
      return `
        <div class="turn-block">
          <div class="turn-meta">
            <span class="turn-timestamp">${fmtTimestamp(turn.start)}</span>
            <span class="turn-speaker" style="color:${color}">${escape(label)}</span>
          </div>
          <div class="turn-text">${escape(turn.text)}</div>
        </div>
      `;
    }).join('');
  } else {
    // 5-minute block view (no diarization)
    const blocks: { blockStart: number; segs: Segment[] }[] = [];
    let currentBlock: Segment[] = [];
    let blockStart = 0;

    for (const seg of segments) {
      const blockIdx = Math.floor(seg.start / BLOCK_SECONDS);
      if (blockIdx > Math.floor(blockStart / BLOCK_SECONDS) && currentBlock.length > 0) {
        blocks.push({ blockStart, segs: currentBlock });
        blockStart = blockIdx * BLOCK_SECONDS;
        currentBlock = [seg];
      } else {
        currentBlock.push(seg);
      }
    }
    if (currentBlock.length > 0) {
      blocks.push({ blockStart, segs: currentBlock });
    }

    bodyHtml = blocks.map(({ blockStart: bs, segs }) => {
      const text = segs.map(s => s.text.trim()).join(' ');
      return `
        <div class="segment-block">
          <div class="block-timestamp">[${fmtTimestamp(bs)}]</div>
          <div class="block-text">${escape(text)}</div>
        </div>
      `;
    }).join('');
  }

  const diarBadge = hasDiarization
    ? '<span class="reader-badge">speaker-diarized</span>'
    : '';

  readerContent.innerHTML = `
    <div class="reader-header">
      <div class="reader-back">← <a href="${window.location.pathname}">All meetings</a></div>
      <div class="reader-title">${escape(meta.title)}</div>
      <div class="reader-meta">
        <span>${fmtDate(meta.meeting_date)}</span>
        <span><a href="${escape(meta.meeting_url)}" target="_blank" rel="noopener">Watch on Granicus ↗</a></span>
        <span>${segments.length} segments</span>
        ${diarBadge}
      </div>
    </div>
    ${bodyHtml}
  `;
}

async function showReader(clipId: number) {
  listView.style.display = 'none';
  readerView.classList.add('active');
  readerContent.innerHTML = '<div class="loading-msg">Loading transcript…</div>';

  try {
    const res = await fetch(`${BASE}transcripts/clip${clipId}.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: TranscriptData = await res.json();
    renderReader(data);
  } catch (err) {
    readerContent.innerHTML = `<div class="error-msg">Failed to load transcript: ${err}</div>`;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  // Check for reader route
  const params = new URLSearchParams(window.location.search);
  const clipParam = params.get('clip');
  if (clipParam) {
    const clipId = parseInt(clipParam, 10);
    if (!isNaN(clipId)) {
      await showReader(clipId);
      return;
    }
  }

  // List view
  try {
    const res = await fetch(`${BASE}transcripts/manifest.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    manifest = await res.json();
  } catch (err) {
    resultsEl.innerHTML = `<div class="error-msg">Failed to load meeting list: ${err}</div>`;
    return;
  }

  renderMeetingList(manifest);
  searchStatus.textContent = `${manifest.length} meetings`;

  const debouncedSearch = debounce(runSearch, 300);
  searchEl.addEventListener('input', () => debouncedSearch(searchEl.value));
  searchEl.focus();
}

init();
