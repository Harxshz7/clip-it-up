# Clip-It-Up Font Directory for libass

This directory contains open-licensed typefaces used by libass subtitle rendering.
When FFmpeg runs the `ass` / `subtitles` filter, this directory is passed via `fontsdir=fonts/`.

## Bundled / Recommended Fonts
1. **Montserrat-Bold.ttf** (OFL) - Primary font for `bold_pop` style
2. **Inter-SemiBold.ttf** (OFL) - Primary font for `clean_minimal` style
3. **Poppins-Bold.ttf** (OFL) - Primary font for `karaoke` style
4. **NotoSansDevanagari-Bold.ttf** (OFL) - Hindi / Marathi / Devanagari script support
5. **NotoSansKannada-Bold.ttf** (OFL) - Kannada script support

In Docker containers and Linux CPU workers, HarfBuzz shaping is active in `libass` for Indic rendering.
