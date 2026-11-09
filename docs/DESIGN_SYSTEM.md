# The interface: tokens, type, spacing and parts

Everything visual lives in [web/src/styles.css](../web/src/styles.css) as named tokens, and a small set of shared parts in [web/src/components/](../web/src/components/). The public home page has its own stylesheet, [web/src/components/home/home.css](../web/src/components/home/home.css), built from the same tokens. A screen should use these and nothing of its own.

## Principles

- **Minimal and neutral.** White paper, near-black ink, hairline borders. Colour is for status; one violet accent marks the active item and focus, nothing else.
- **Flat.** Hairline borders, no shadows, no coloured card edges, no gradients (the home page has one soft background gradient behind its first screen).
- **Status is a dot and a word.** Never a coloured capsule, and never colour alone. Small grey tags only label a thing (kind of file, "Change").
- **One frame.** Every signed-in page sits in the same sidebar (a tab bar with a More sheet on a phone) under a top bar with search, the theme switch and the account menu.
- **One alert pattern.** "Needs you" / "Needs your attention" is one list, one line each, a dot for urgency and one action.
- **Say what to do.** Empty states say what the list is for and what to do about it.
- **Light first.** Light is the default on every device; dark is a full second palette that the person chooses (saved per browser).

## Colour

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--bg` / `--surface` | `#FFFFFF` / `#FFFFFF` | `#0D0D11` / `#14141A` | the page, cards and tables |
| `--sunken` | `#F7F6FB` | `#1B1B23` | hover, selected, empty bars, grouped boxes |
| `--ink` / `--ink-2` / `--ink-3` | `#111114` / `#4B4B58` / `#6C6C7A` | `#F3F3F7` / `#B9B9C6` / `#8E8E9D` | text: main, secondary, tertiary |
| `--line` / `--line-2` | `#E8E6F0` / `#D6D3E4` | `#272731` / `#353542` | hairlines, input borders |
| `--accent` | `#6D4FE0` | `#A78BFA` | the active navigation item, focus ring, unread dot |
| `--green` / `--amber` / `--red` | `#4F6B3A` / `#8F6012` / `#A63C2B` | `#9DBB80` / `#D9A74B` / `#E48B77` | on track / behind or waiting / will miss or late (each has a `-bg` and `-line` partner) |

The status colours are fixed: green, amber and red keep their meaning everywhere, including the public home page.

## Type

| Use | Font | Size |
|---|---|---|
| Page title (h1) | Geist, semibold | 26px |
| Section titles (h2) | Geist, semibold | 14px |
| Body | Geist (Inter as the fallback) | 14px, line height 1.5 |
| Small and secondary | Geist | 12 to 13px |
| Labels, figures in monospace | Geist Mono | 12px |

Tamil text uses Noto Sans Tamil (the supervisor's screens switch to it). Fonts load from Google Fonts and fall back to the system sans, so the layout holds offline.

## Spacing and shape

- Spacing steps: 4, 8, 12, 16, 20, 24, 32. A page has 24 to 32px of padding and 24px between its blocks.
- Radius: 8px for inputs and menus, 12px for cards, pill (999px) for buttons, chips and the search box.
- Controls are 34 to 36px high (30px for small), and 44px or more on a phone's tab bar and on the supervisor's screens.

## Shared parts

| Part | File | What it is |
|---|---|---|
| `AppShell` | components/AppShell.tsx | sidebar with line icons, labels and counts, primary action, top bar with search, theme switch and account menu; tab bar and "More" sheet on a phone; skip link |
| `Icon` | components/Icon.tsx | the line icons, one stroke weight |
| `PageHeader`, `StatusPill`, `Progress`, `Swatch` | components/ui.tsx | breadcrumbs, title, status and actions; the dot-and-word status; a thin progress bar in the status colour; a colour chip |
| `EmptyState`, `Skeleton`, `Toast`, `Modal`, `useApi`, `useCanWrite` | components/ui.tsx | an empty list that says what to do; grey bars while loading; a confirmation line; a dialog; data loading with an error state; whether a view-only buyer may change things |
| `Attention` | components/Attention.tsx | the "needs you" list |
| `NotificationFeed` | components/NotificationFeed.tsx | what the app has told this person, newest first, grouped by day |
| `RequestParts` | components/RequestParts.tsx | a request's summary, its status and its conversation, shared by both sides |
| `NoticeCard` | components/NoticeCard.tsx | the buyer's delay notice and its acknowledgement |
| `Activity` | components/Activity.tsx | the order timeline |
| `CapacityCheck`, `PlanBars` | components/ | the units' load for a ship date; the time-and-action chart |
| `Attachments`, `ChangeForm`, `MyDetails`, `SearchPalette` | components/ | files on a request or order; a change request; the person's own details; search (press `/`) |
| `home/` | components/home/ | the public home page, one small component per section on one width and one spacing scale |

## Rules a new screen follows

1. Start with `PageHeader`; put the page's one primary action there, not a second copy of what the sidebar already offers (on a phone, where the sidebar is a tab bar, mark that button `phone-only`).
2. A list that leads somewhere is a table with `rows-link`; the whole row is the link.
3. Status uses `StatusPill` or a `pill pill-*`; labels use `tag`.
4. Anything that needs the person goes into `Attention`, not into a new kind of card.
5. Give every list an `EmptyState` and a `Skeleton`.
6. A view-only buyer must not see a button the server would refuse (`useCanWrite`).
7. Check it at 390px wide and in dark mode before calling it done; `e2e/journey.py` fails on sideways scrolling.
