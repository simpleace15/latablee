# LaTablée — Design System

> Generated with [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
> (`design_system.py`, v2.x, MIT — design-time only, no runtime dependency), briefed on
> LaTablée's north star: the **Wife Acceptance Factor** — a non-technical spouse must be able
> to do everything daily, at 6pm, with messy hands and a toddler on her hip.
>
> Deviation note: the generator's raw suggestion (dark-only background, hero-marketing
> pattern, full Claymorphism) was adapted — a household app is *used* daily, not *visited*,
> so it needs first-class light + dark modes, an app-UX pattern, and warmth without toy-like
> styling. Both palettes below keep the generator's terracotta/green core.

## 1. Identity

- **Feel:** warm, modern, friendly — a table set for people you love, not a dashboard.
- **Voice:** plain kitchen language ("What's for dinner?", "Add to list"). No jargon
  (no "meal planner", no "CRUD", no "sync") in UI copy.
- **Register:** cozy-clean. Rounded but not bubbly. Big, calm, confident.

## 2. Pattern: Today-First App UX

- **Primary surface:** *Today* — what's for dinner tonight + the active shopping list,
  one tap each. The planner, recipes, and AI helpers orbit it.
- **Conversion goal (app analog):** time-to-first-action < 3 seconds from home screen.
- **Navigation:** bottom tab bar on mobile (Today · Plan · Recipes · List · Settings),
  48px+ touch targets, one-handed reach.
- **First run:** onboarding wizard is the hero — name the household, set allergies/
  dislikes/favorites, invite the spouse by link. Done in under 2 minutes.

## 3. Style

- **Name:** Soft Warm Modern (claymorphism, dialed down)
- **Keywords:** soft depth, chunky-rounded (16–20px radius), tactile press states, warm
- **Borders:** 1px subtle, cards carry depth via soft shadows — not thick outlines
- **Best for:** family apps, daily-use tools, kitchen environments

## 4. Colors — Light mode (default)

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#9A3412` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#C2410C` | `--color-secondary` |
| On Secondary | `#FFFFFF` | `--color-on-secondary` |
| Accent / CTA | `#059669` | `--color-accent` |
| On Accent | `#FFFFFF` | `--color-on-accent` |
| Background | `#FAF7F2` | `--color-background` |
| Foreground | `#2D2A26` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#2D2A26` | `--color-card-foreground` |
| Muted | `#F1EBE3` | `--color-muted` |
| Muted Foreground | `#6B655D` | `--color-muted-foreground` |
| Border | `#E7DFD5` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring / Focus | `#059669` | `--color-ring` |

*Notes: warm cream backgrounds, terracotta primary, fresh green for done/check-off states.*

## 5. Colors — Dark mode (equal citizen, not an afterthought)

| Role | Hex | CSS Variable (same names) |
|------|-----|--------------|
| Primary | `#C86B3C` | lightened terracotta for dark |
| On Primary | `#1C1006` | |
| Secondary | `#E8845A` | |
| On Secondary | `#1C1006` | |
| Accent / CTA | `#34D399` | |
| On Accent | `#06281C` | |
| Background | `#171412` | warm near-black, not blue-black |
| Foreground | `#F3EEE8` | |
| Card | `#201C19` | |
| Card Foreground | `#F3EEE8` | |
| Muted | `#2A2521` | |
| Muted Foreground | `#B8B0A6` | ≥ #b0b0b8-class brightness, no dim gray |
| Border | `#3A332D` | |
| Destructive | `#F87171` | |
| On Destructive | `#1C1006` | |
| Ring / Focus | `#34D399` | |

## 6. Typography

- **Heading:** Varela Round (soft, rounded, friendly)
- **Body:** Nunito Sans (300–700)
- **Mood:** soft, approachable, warm
- **Kitchen-legibility rules:**
  - Cook-mode step text ≥ 18px/1.5, high contrast — readable at arm's length with messy hands
  - Min body size 16px everywhere; check-off list rows ≥ 44px tall
  - Google Fonts import (self-host in build for offline PWA):
    ```css
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@300;400;500;600;700&family=Varela+Round&display=swap');
    ```

## 7. Key Effects

- Soft inner+outer shadows (subtle, no hard lines) — depth without gloss
- Press state: scale 0.98 + shadow tighten, 150–200ms ease-out
- Check-off: satisfying strike-through + fade-to-muted, 200ms
- Empty states: friendly illustration + one plain-language action ("Add your first recipe")

## 8. Avoid (anti-patterns)

- Dashboard clutter / stats walls — this is a kitchen, not mission control
- Muted low-energy colors; neon; AI purple/pink gradients
- Emoji as icons (SVG only: Lucide)
- Toy-like full claymorphism (3D excess) — keep the warmth, drop the toy
- Tiny dense lists — grocery check-off must work with one thumb and flour on the screen
- Feature cleverness that needs explanation — if a screen needs a wiki, it's wrong

## 9. Pre-Delivery Checklist (per-screen QA gate — from ui-ux-pro-max)

- [ ] No emojis as icons (use SVG: Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover/press states with smooth transitions (150–300ms)
- [ ] Text contrast ≥ 4.5:1 in **both** light and dark modes (tool: verify each pair above)
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected (no pulsing/bouncing)
- [ ] Text/chips/badges reflow without clipping
- [ ] Responsive at 375 / 768 / 1024 / 1440px
- [ ] WAF gate: could a non-technical spouse use this at 6pm, one-handed, without help?