import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { EditDecisionList, clipEditDocToEDL } = require('../dist/index.js');

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const fixturesPath = path.resolve(__dirname, '../../../tests/fixtures/edl_parity_vectors.json');
const fixtures = JSON.parse(fs.readFileSync(fixturesPath, 'utf-8'));

test('TS EditDecisionList matches shared parity vectors', () => {
  for (const tc of fixtures.cases) {
    const edl = new EditDecisionList(tc.clip_start_ms, tc.clip_end_ms, tc.removals);

    assert.equal(
      edl.durationMs,
      tc.expected_out_duration_ms,
      `Case ${tc.name}: duration mismatch`
    );
    assert.equal(
      edl.removedMs,
      tc.expected_removed_ms,
      `Case ${tc.name}: removedMs mismatch`
    );

    assert.equal(
      edl.keepSegments.length,
      tc.expected_keep_segments.length,
      `Case ${tc.name}: segment count mismatch`
    );

    for (let i = 0; i < tc.expected_keep_segments.length; i++) {
      const exp = tc.expected_keep_segments[i];
      const actual = edl.keepSegments[i];
      assert.deepEqual(
        {
          src_start_ms: actual.src_start_ms,
          src_end_ms: actual.src_end_ms,
          out_start_ms: actual.out_start_ms,
          out_end_ms: actual.out_end_ms,
        },
        exp,
        `Case ${tc.name}: segment[${i}] mismatch`
      );
    }
  }
});

test('TS EditDecisionList remaps captions matching shared parity words fixture', () => {
  const wf = fixtures.words_fixture;
  const edl = new EditDecisionList(wf.clip_start_ms, wf.clip_end_ms, wf.removals);
  const remapped = edl.remapCaptions(wf.words);

  assert.equal(remapped.length, wf.expected_remapped_words.length);

  for (let i = 0; i < wf.expected_remapped_words.length; i++) {
    const exp = wf.expected_remapped_words[i];
    const act = remapped[i];
    assert.equal(act.text, exp.text);
    assert.equal(act.start_ms, exp.start_ms);
    assert.equal(act.end_ms, exp.end_ms);
    assert.equal(act.src_start_ms, exp.src_start_ms);
    assert.equal(act.src_end_ms, exp.src_end_ms);
  }
});

test('clipEditDocToEDL honors disabled removals', () => {
  const doc = {
    clip_id: 'c1',
    base_clip_id: 'c1',
    version: 1,
    range: { start_ms: 0, end_ms: 10000 },
    removals: [
      { id: 'r1', start_ms: 2000, end_ms: 4000, kind: 'filler', enabled: true },
      { id: 'r2', start_ms: 5000, end_ms: 7000, kind: 'silence', enabled: false }, // disabled!
    ],
    captions: { words: [], style_key: 'bold_stroke', enabled: true },
    reframe: { mode_overrides: {}, keyframes: [] },
    hook: { text: 'Test', source: 'auto', start_ms: 0 },
    preset_key: 'tiktok_9_16',
    cleanup_options: { remove_fillers: true, remove_silence: true, silence_threshold_ms: 500 },
  };

  const edl = clipEditDocToEDL(doc);
  // Only r1 is enabled, so duration should be 10000 - 2000 = 8000
  assert.equal(edl.durationMs, 8000);
  assert.equal(edl.keepSegments.length, 2);
  assert.equal(edl.keepSegments[0].out_start_ms, 0);
  assert.equal(edl.keepSegments[0].out_end_ms, 2000);
  assert.equal(edl.keepSegments[1].out_start_ms, 2000);
  assert.equal(edl.keepSegments[1].out_end_ms, 8000);
});

test('EditDecisionList mapSrcToOut and mapOutToSrc roundtrip inside keep segments', () => {
  const edl = new EditDecisionList(1000, 11000, [
    { start_ms: 4000, end_ms: 6000, kind: 'filler' }
  ]);

  // Before cut: src 2000 -> out 1000
  assert.equal(edl.mapSrcToOut(2000), 1000);
  assert.equal(edl.mapOutToSrc(1000), 2000);

  // Inside cut: src 5000 -> snaps to boundary out 3000
  assert.equal(edl.mapSrcToOut(5000), 3000);

  // After cut: src 8000 -> out 5000
  assert.equal(edl.mapSrcToOut(8000), 5000);
  assert.equal(edl.mapOutToSrc(5000), 8000);
});
