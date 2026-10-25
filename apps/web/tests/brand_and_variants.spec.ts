import { test, expect } from '@playwright/test';

test.describe('Phase 7a: Brand Kit and Auto-Variants Workflow', () => {
  test('Brand Settings page renders safe zone preview, contrast indicator, and kit controls', async ({ page }) => {
    // Intercept billing & brand API calls
    await page.route('**/billing/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'user_123',
          email: 'creator@example.com',
          plan: {
            key: 'creator',
            name: 'Creator Plan',
            price_inr_monthly: 1499,
            watermark: false,
            features: { brand_kit: true, auto_variants: true, max_brand_kits: 1 },
          },
          watermark_required: false,
        }),
      });
    });

    await page.route('**/brand-kits', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'kit_1',
            user_id: 'user_123',
            name: 'Acme Media Kit',
            is_default: true,
            primary_color: '#8B5CF6',
            secondary_color: '#000000',
            logo_position: 'top_right',
            logo_opacity: 0.85,
            logo_scale: 0.15,
            font_family: 'Inter',
            intro_mode: 'none',
            outro_mode: 'none',
          },
        ]),
      });
    });

    // 1. Visit Brand Settings
    await page.goto('/settings/brand');

    // 2. Verify page header
    await expect(page.locator('h1')).toContainText('Brand Kit & Visual Identity');

    // 3. Verify 9:16 Canvas and Safe Zone indicators
    await expect(page.locator('text=9:16 Safe Zone Preview')).toBeVisible();
    await expect(page.locator('text=TikTok / Reels Safe Zone')).toBeVisible();

    // 4. Verify Brand Kit Name input
    const nameInput = page.locator('input[placeholder="e.g. Acme Media Kit"]');
    await expect(nameInput).toHaveValue('Acme Media Kit');

    // 5. Verify WCAG contrast badge
    await expect(page.locator('text=WCAG 2.1 Contrast')).toBeVisible();

    // 6. Verify Save button exists and is active
    await expect(page.locator('button:has-text("Save Brand Kit")')).toBeVisible();
  });

  test('Clip Studio Editor renders Variants tab and generation panel', async ({ page }) => {
    // Intercept video, clip edit, and variants API calls
    await page.route('**/videos/vid-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'vid-1',
          user_id: 'user_123',
          original_filename: 'interview.mp4',
          status: 'ready',
          created_at: new Date().toISOString(),
        }),
      });
    });

    await page.route('**/clips/clip-1/edit', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          clip_id: 'clip-1',
          base_clip_id: 'clip-1',
          version: 1,
          updated_at: new Date().toISOString(),
          doc: {
            clip_id: 'clip-1',
            base_clip_id: 'clip-1',
            version: 1,
            range: { start_ms: 0, end_ms: 15000 },
            removals: [],
            captions: {
              words: [
                { text: 'Start', start_ms: 0, end_ms: 1000, emphasis: false, deleted: false },
                { text: 'testing', start_ms: 1000, end_ms: 2000, emphasis: false, deleted: false },
              ],
              style_key: 'bold_pop',
              style_overrides: {},
              enabled: true,
            },
            reframe: {
              mode_overrides: {},
              keyframes: [{ t_ms: 0, x_center: 0.5, y_center: 0.5 }],
            },
            hook: {
              text: 'Master this one trick',
              source: 'auto',
              start_ms: 0,
            },
            cta: {
              text: 'Follow for part 2',
              position: 'bottom',
            },
            preset_key: 'tiktok_9_16',
            brand: {
              apply_logo: true,
              apply_intro: false,
              apply_outro: false,
            },
            cleanup_options: {
              remove_fillers: false,
              remove_silence: false,
            },
          },
        }),
      });
    });

    await page.route('**/clips/clip-1/variants', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'set_1',
          clip_id: 'clip-1',
          created_at: new Date().toISOString(),
          variants: [
            {
              id: 'var_1',
              variant_set_id: 'set_1',
              label: 'Variant A (Baseline)',
              hook_text: 'Master this one trick',
              caption_style_key: 'bold_pop',
              cta_text: 'Follow for part 2',
              diff_summary: { hook: 'Baseline', style: 'bold_pop' },
            },
            {
              id: 'var_2',
              variant_set_id: 'set_1',
              label: 'Variant B',
              hook_text: 'Stop making this mistake',
              caption_style_key: 'cinematic',
              cta_text: 'Follow for part 2',
              diff_summary: { hook: 'Alternative', style: 'cinematic' },
            },
          ],
        }),
      });
    });

    await page.route('**/billing/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'user_123',
          email: 'creator@example.com',
          plan: { key: 'creator', watermark: false, features: { brand_kit: true, auto_variants: true } },
          watermark_required: false,
        }),
      });
    });

    // 1. Visit Editor
    await page.goto('/videos/vid-1/clips/clip-1/edit');

    // 2. Click Variants Tab
    const variantsTabButton = page.locator('button:has-text("Variants")');
    await expect(variantsTabButton).toBeVisible();
    await variantsTabButton.click();

    // 3. Verify Auto-Variants Generator UI
    await expect(page.locator('text=Auto-Variants Matrix')).toBeVisible();
    await expect(page.locator('text=Variant A (Baseline)')).toBeVisible();
    await expect(page.locator('text=Variant B')).toBeVisible();
    await expect(page.locator('text=Batch Export Selected')).toBeVisible();
    await expect(page.locator('text=Export All & Download ZIP')).toBeVisible();
  });
});
