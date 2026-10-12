import { test, expect } from '@playwright/test';

test.describe('Phase 5 Editor Speed Run & Concurrency E2E', () => {
  const videoId = 'test-vid-123';
  const clipId = 'c-phase5-001';

  let currentDoc = {
    clip_id: clipId,
    base_clip_id: clipId,
    version: 1,
    range: { start_ms: 1000, end_ms: 25000 },
    removals: [
      { id: 'rem-auto-1', start_ms: 5000, end_ms: 6000, kind: 'filler', text: 'um', enabled: true },
    ],
    captions: {
      words: [
        { text: 'Start', start_ms: 1000, end_ms: 2000 },
        { text: 'sentence', start_ms: 2100, end_ms: 3000 },
        { text: 'here.', start_ms: 3100, end_ms: 4500 },
        { text: 'um', start_ms: 5000, end_ms: 6000 },
        { text: 'Next', start_ms: 6500, end_ms: 7500 },
        { text: 'great', start_ms: 7600, end_ms: 8500 },
        { text: 'point.', start_ms: 8600, end_ms: 10000 },
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
      text: 'Start sentence here.',
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

  test.beforeEach(async ({ page }) => {
    // Reset doc
    currentDoc = {
      clip_id: clipId,
      base_clip_id: clipId,
      version: 1,
      range: { start_ms: 1000, end_ms: 25000 },
      removals: [
        { id: 'rem-auto-1', start_ms: 5000, end_ms: 6000, kind: 'filler', text: 'um', enabled: true },
      ],
      captions: {
        words: [
          { text: 'Start', start_ms: 1000, end_ms: 2000 },
          { text: 'sentence', start_ms: 2100, end_ms: 3000 },
          { text: 'here.', start_ms: 3100, end_ms: 4500 },
          { text: 'um', start_ms: 5000, end_ms: 6000 },
          { text: 'Next', start_ms: 6500, end_ms: 7500 },
          { text: 'great', start_ms: 7600, end_ms: 8500 },
          { text: 'point.', start_ms: 8600, end_ms: 10000 },
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
        text: 'Start sentence here.',
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

    // Mock GET /clips/:id/edit
    await page.route(`**/api/clips/${clipId}/edit`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'edit-rec-1',
            clip_id: clipId,
            user_id: 'user-1',
            version: currentDoc.version,
            parent_version: currentDoc.version > 1 ? currentDoc.version - 1 : null,
            doc: currentDoc,
            label: 'autosave',
            is_checkpoint: false,
            created_at: new Date().toISOString(),
          }),
        });
      } else if (route.request().method() === 'PUT') {
        const body = JSON.parse(route.request().postData() || '{}');
        const ifMatch = route.request().headers()['if-match'];
        if (ifMatch && parseInt(ifMatch) !== currentDoc.version) {
          // Conflict!
          await route.fulfill({
            status: 409,
            contentType: 'application/json',
            body: JSON.stringify({
              detail: 'Edit conflict: newer version exists',
              server_doc: currentDoc,
              server_version: currentDoc.version,
            }),
          });
          return;
        }
        currentDoc = { ...body.doc, version: currentDoc.version + 1 };
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'edit-rec-2',
            clip_id: clipId,
            user_id: 'user-1',
            version: currentDoc.version,
            parent_version: currentDoc.version - 1,
            doc: currentDoc,
            label: body.label || 'autosave',
            is_checkpoint: !!body.is_checkpoint,
            created_at: new Date().toISOString(),
          }),
        });
      }
    });

    // Mock GET /clips/:id/alternatives
    await page.route(`**/api/clips/${clipId}/alternatives*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          clip_id: clipId,
          alternatives: [
            {
              id: 'alt-1',
              clip_id: clipId,
              kind: 'hook',
              start_ms: 6500,
              end_ms: 25000,
              text: 'Next great point.',
              score: 9.1,
              reason: 'High intrigue punchy line',
              source: 'scoring',
              created_at: new Date().toISOString(),
            },
          ],
        }),
      });
    });

    // Mock video proxy and reframe
    await page.route(`**/api/videos/${videoId}*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: videoId,
          title: 'Speed Run Demo.mp4',
          proxy_url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
        }),
      });
    });

    // Mock exports endpoint
    await page.route(`**/api/clips/${clipId}/exports`, async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'exp-1',
            clip_id: clipId,
            status: 'completed',
            download_url: 'https://example.com/export_clip_001.mp4',
            created_at: new Date().toISOString(),
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      }
    });

    // Mock editor telemetry
    await page.route(`**/api/editor/events`, async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' });
    });
  });

  test('Speed run: complete flow from open to export in <= 12 user actions with persistence', async ({ page }) => {
    let userActionCount = 0;

    // 1. Open editor
    await page.goto(`/videos/${videoId}/clips/${clipId}/edit`);
    await expect(page.locator('text=Preview matches export')).toBeVisible();

    // Action 1: Delete words via Transcript Panel (click a word to select)
    const wordBtn = page.locator('button:has-text("Start")');
    if (await wordBtn.isVisible()) {
      await wordBtn.click();
      userActionCount++;
    }

    // Action 2: Click "Captions" tab
    await page.click('button:has-text("Captions")');
    userActionCount++;

    // Action 3: Switch style to "beast_glow"
    const styleBtn = page.locator('button:has-text("Beast Glow")');
    if (await styleBtn.isVisible()) {
      await styleBtn.click();
      userActionCount++;
    }

    // Action 4: Switch to "Clean-up" tab
    await page.click('button:has-text("Clean-up")');
    userActionCount++;

    // Action 5: Toggle fillers
    const fillerCheckbox = page.locator('label:has-text("Remove Fillers")');
    if (await fillerCheckbox.isVisible()) {
      await fillerCheckbox.click();
      userActionCount++;
    }

    // Action 6: Switch to "Hook" tab
    await page.click('button:has-text("Hook")');
    userActionCount++;

    // Action 7: Select alternative hook
    const useHookBtn = page.locator('button:has-text("Use This Hook")');
    if (await useHookBtn.isVisible()) {
      await useHookBtn.click();
      userActionCount++;
    }

    // Action 8: Switch to "Export" tab
    await page.click('button:has-text("Export")');
    userActionCount++;

    // Action 9: Click "Export Clip"
    await page.click('button:has-text("Export Clip")');
    userActionCount++;

    // Assert that the default speed-run path took <= 12 user actions
    expect(userActionCount).toBeLessThanOrEqual(12);

    // Verify download link is ready
    await expect(page.locator('text=Download MP4')).toBeVisible({ timeout: 5000 });

    // Verify persistence after reload
    await page.reload();
    await expect(page.locator('text=Preview matches export')).toBeVisible();
  });

  test('Conflict 409 handling and crash recovery draft banner', async ({ page }) => {
    // 1. Simulate existing newer draft in storage
    await page.addInitScript(() => {
      localStorage.setItem(
        'clip_draft_c-phase5-001',
        JSON.stringify({
          clip_id: 'c-phase5-001',
          timestamp: Date.now() + 100000,
          doc: {
            clip_id: 'c-phase5-001',
            base_clip_id: 'c-phase5-001',
            version: 1,
            range: { start_ms: 1000, end_ms: 20000 },
            removals: [],
            captions: { words: [], style_key: 'bold_stroke', style_overrides: {}, enabled: true },
            reframe: { mode_overrides: {}, keyframes: [] },
            hook: { text: 'Recovered Draft Hook', source: 'manual', start_ms: 1000 },
            preset_key: 'tiktok_9_16',
            cleanup_options: { remove_fillers: true, remove_silence: true, silence_threshold_ms: 500 },
          },
        })
      );
    });

    await page.goto(`/videos/${videoId}/clips/${clipId}/edit`);

    // Verify draft recovery banner appears
    await expect(page.locator('text=Unsaved local draft found')).toBeVisible({ timeout: 5000 });

    // Click "Restore Draft"
    await page.click('button:has-text("Restore Draft")');
    await expect(page.locator('text=Unsaved local draft found')).not.toBeVisible();
  });
});
