import { test, expect } from '@playwright/test';

test.describe('Creator Reality Check E2E Review Flow', () => {
  const token = 'mock_creator_token_12345678901234567890';

  test('Creator opens private review link, rates 3 clips, fills survey, and completes submission', async ({ page }) => {
    // 1. Mock the public review session endpoint
    await page.route(`**/review/${token}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '11111111-2222-3333-4444-555555555555',
          video_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
          token,
          creator_name: 'Aarav Sharma',
          status: 'open',
          expires_at: '2026-10-30T00:00:00Z',
          created_at: '2026-10-08T00:00:00Z',
          video_title: 'SaaS Architecture & Growth Podcast.mp4',
          consent_notice: 'Feedback and video snippets are used solely to evaluate AI clip selection quality.',
          clips: [
            {
              clip_id: 'c1111111-1111-1111-1111-111111111111',
              moment_id: 'm1111111-1111-1111-1111-111111111111',
              rank: 1,
              title: 'The #1 Rule of Micro-SaaS',
              hook_text: 'Stop building features nobody asked for',
              start_ms: 5000,
              end_ms: 35000,
              duration_seconds: 30,
              variant_length_s: 'auto',
              video_urls: {
                vertical_center: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                horizontal: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
              },
            },
            {
              clip_id: 'c2222222-2222-2222-2222-222222222222',
              moment_id: 'm2222222-2222-2222-2222-222222222222',
              rank: 2,
              title: 'Pricing Mistakes Founders Make',
              hook_text: 'Why charging ₹500 is killing your margins',
              start_ms: 45000,
              end_ms: 75000,
              duration_seconds: 30,
              variant_length_s: 'auto',
              video_urls: {
                vertical_center: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                horizontal: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
              },
            },
            {
              clip_id: 'c3333333-3333-3333-3333-333333333333',
              moment_id: 'm3333333-3333-3333-3333-333333333333',
              rank: 3,
              title: 'Hiring vs Automating with AI',
              hook_text: 'We replaced 3 manual steps with 1 script',
              start_ms: 80000,
              end_ms: 110000,
              duration_seconds: 30,
              variant_length_s: 'auto',
              video_urls: {
                vertical_center: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                horizontal: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
              },
            },
          ],
        }),
      });
    });

    // Mock ratings endpoint
    await page.route(`**/review/${token}/ratings/*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'r-mock-id', verdict: 'post_as_is' }),
      });
    });

    // Mock survey endpoint
    await page.route(`**/review/${token}/survey`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 's-mock-id', status: 'saved' }),
      });
    });

    // Mock submit endpoint
    await page.route(`**/review/${token}/submit`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'submitted', message: 'Thank you!' }),
      });
    });

    // 2. Open public review link
    await page.goto(`/review/${token}`);

    // Verify Intro Screen
    await expect(page.locator('text=Crucial Note: Raw Preview Cuts')).toBeVisible();
    await expect(page.locator('text=SaaS Architecture & Growth Podcast.mp4')).toBeVisible();
    await expect(page.locator('text=Aarav Sharma')).toBeVisible();

    // 3. Start Clip Review
    await page.click('button:has-text("Start Clip Review")');

    // --- Clip 1 ---
    await expect(page.locator('text=Clip 1 of 3')).toBeVisible();
    await expect(page.locator('text=The #1 Rule of Micro-SaaS')).toBeVisible();
    await page.click('button:has-text("Post as is")');
    await page.click('button:has-text("Next Clip")');

    // --- Clip 2 ---
    await expect(page.locator('text=Clip 2 of 3')).toBeVisible();
    await expect(page.locator('text=Pricing Mistakes Founders Make')).toBeVisible();
    await page.click('button:has-text("Post w/ edits")');
    // Select reason tag
    await page.click('button:has-text("Bad start / Hook cut")');
    await page.click('button:has-text("Next Clip")');

    // --- Clip 3 ---
    await expect(page.locator('text=Clip 3 of 3')).toBeVisible();
    await expect(page.locator('text=Hiring vs Automating with AI')).toBeVisible();
    await page.click('button:has-text("No")');
    await page.click('button:has-text("Needs context")');

    // 4. Continue to Survey
    await page.click('button:has-text("Continue to Survey")');

    // Verify Survey Screen
    await expect(page.locator('h1:has-text("Almost Done! Help Us Price & Build")')).toBeVisible();

    // Fill Survey
    await page.fill('textarea[placeholder*="Dynamic karaoke subtitles"]', 'Dynamic animated captions and face tracking.');
    await page.fill('textarea[placeholder*="InShot on iPhone"]', 'CapCut manual editing.');
    await page.fill('input[placeholder*="8 hours every weekend"]', '₹10,000/mo.');
    await page.fill('input[placeholder="2500"]', '2500');

    // Subscriptions
    await page.click('div:has-text("Would you subscribe at ₹1,500/month?") >> button:has-text("Yes")');
    await page.click('div:has-text("Would you subscribe at ₹4,000/month?") >> button:has-text("No")');

    // Upload intent
    await page.click('button:has-text("yes")');

    // Submit Survey
    await page.click('button:has-text("Submit Feedback & Complete Review")');

    // Verify Thank You screen
    await expect(page.locator('h1:has-text("Thank You, Aarav Sharma!")')).toBeVisible();
    await expect(page.locator('text=Review Submitted')).toBeVisible();
  });
});
