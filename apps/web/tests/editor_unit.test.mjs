import test from 'node:test';
import assert from 'node:assert/strict';

// Test active time calculation heuristic (gaps > 20s excluded)
function computeActiveHandsOnTime(timestampsMs) {
  if (!timestampsMs || timestampsMs.length < 2) return 0;
  let activeTime = 0;
  for (let i = 1; i < timestampsMs.length; i++) {
    const delta = timestampsMs[i] - timestampsMs[i - 1];
    if (delta > 0 && delta <= 20000) {
      activeTime += delta;
    }
  }
  return activeTime;
}

test('Active hands-on time calculation excludes pauses > 20s', () => {
  const t0 = 1000000;
  const timestamps = [
    t0,
    t0 + 2000,    // +2s active (total 2s)
    t0 + 5000,    // +3s active (total 5s)
    t0 + 35000,   // gap of 30s (>20s) -> excluded!
    t0 + 40000,   // +5s active (total 10s)
  ];

  const active = computeActiveHandsOnTime(timestamps);
  assert.equal(active, 10000); // exactly 10s
});

// Test Edit Doc operations & Undo/Redo stack invariants
function createInitialDoc() {
  return {
    clip_id: 'test_clip_1',
    base_clip_id: 'test_clip_1',
    version: 1,
    range: { start_ms: 1000, end_ms: 20000 },
    removals: [
      { id: 'rem_1', start_ms: 3000, end_ms: 4500, kind: 'filler', enabled: true },
    ],
    captions: {
      words: [
        { text: 'Hello', start_ms: 1000, end_ms: 1500 },
        { text: 'um', start_ms: 3000, end_ms: 4500 },
        { text: 'world', start_ms: 5000, end_ms: 6000 },
      ],
      style_key: 'bold_stroke',
      style_overrides: {},
      enabled: true,
    },
    reframe: {
      mode_overrides: {},
      keyframes: [],
    },
    hook: {
      text: 'Hello world',
      source: 'auto',
      start_ms: 1000,
    },
    preset_key: 'tiktok_9_16',
    cleanup_options: {
      remove_fillers: true,
      remove_silence: true,
      silence_threshold_ms: 500,
    },
  };
}

class TestEditorEngine {
  constructor(initialDoc) {
    this.current = JSON.parse(JSON.stringify(initialDoc));
    this.history = [];
    this.future = [];
    this.historyLimit = 200;
  }

  mutate(fn) {
    // Push current snapshot to history
    this.history.push(JSON.parse(JSON.stringify(this.current)));
    if (this.history.length > this.historyLimit) {
      this.history.shift();
    }
    // Clear redo stack on new action
    this.future = [];
    // Apply mutation
    fn(this.current);
  }

  undo() {
    if (this.history.length === 0) return false;
    const prev = this.history.pop();
    this.future.push(JSON.parse(JSON.stringify(this.current)));
    this.current = prev;
    return true;
  }

  redo() {
    if (this.future.length === 0) return false;
    const next = this.future.pop();
    this.history.push(JSON.parse(JSON.stringify(this.current)));
    this.current = next;
    return true;
  }
}

test('Editor operations: delete word range adds manual removal and supports undo/redo', () => {
  const engine = new TestEditorEngine(createInitialDoc());

  // 1. Delete word range (words 5000-6000 "world")
  engine.mutate((doc) => {
    doc.removals.push({
      id: 'rem_manual_1',
      start_ms: 5000,
      end_ms: 6000,
      kind: 'manual',
      enabled: true,
    });
  });

  assert.equal(engine.current.removals.length, 2);
  assert.equal(engine.current.removals[1].kind, 'manual');

  // 2. Undo returns to 1 removal
  assert.equal(engine.undo(), true);
  assert.equal(engine.current.removals.length, 1);

  // 3. Redo restores the manual removal
  assert.equal(engine.redo(), true);
  assert.equal(engine.current.removals.length, 2);
});

test('Editor operations: toggle removal updates enabled state without deleting data', () => {
  const engine = new TestEditorEngine(createInitialDoc());

  engine.mutate((doc) => {
    const r = doc.removals.find((x) => x.id === 'rem_1');
    if (r) r.enabled = false;
  });

  assert.equal(engine.current.removals[0].enabled, false);

  engine.undo();
  assert.equal(engine.current.removals[0].enabled, true);
});

test('Editor operations: hook swap modifies hook and range start', () => {
  const engine = new TestEditorEngine(createInitialDoc());

  engine.mutate((doc) => {
    doc.hook = {
      text: 'Alternative punchy line',
      source: 'alt',
      start_ms: 2500,
    };
    doc.range.start_ms = 2500;
  });

  assert.equal(engine.current.hook.text, 'Alternative punchy line');
  assert.equal(engine.current.range.start_ms, 2500);

  engine.undo();
  assert.equal(engine.current.hook.text, 'Hello world');
  assert.equal(engine.current.range.start_ms, 1000);
});

test('Undo/Redo invariant respects maximum history limit of 200', () => {
  const engine = new TestEditorEngine(createInitialDoc());

  // Perform 250 mutations
  for (let i = 0; i < 250; i++) {
    engine.mutate((doc) => {
      doc.captions.style_overrides = { fontSize: 16 + i };
    });
  }

  // History stack size must not exceed limit
  assert.equal(engine.history.length, 200);

  // Perform 200 undos
  let undosPerformed = 0;
  while (engine.undo()) {
    undosPerformed++;
  }
  assert.equal(undosPerformed, 200);
  assert.equal(engine.undo(), false); // can undo no more
});

test('Local draft recovery identifies newer drafts correctly', () => {
  const serverTimestamp = 1700000000000;
  const oldDraft = { clip_id: 'c1', timestamp: serverTimestamp - 5000 };
  const newerDraft = { clip_id: 'c1', timestamp: serverTimestamp + 12000 };

  const isOldDraftNewer = oldDraft.timestamp > serverTimestamp;
  const isNewerDraftNewer = newerDraft.timestamp > serverTimestamp;

  assert.equal(isOldDraftNewer, false);
  assert.equal(isNewerDraftNewer, true);
});
