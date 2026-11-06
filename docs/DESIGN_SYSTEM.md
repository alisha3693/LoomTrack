# The interface: tokens, type, spacing and parts

Everything visual lives in [web/src/styles.css](../web/src/styles.css) as named tokens, and a small set of shared parts in [web/src/components/](../web/src/components/). A screen should use these and nothing of its own. The look was drawn first on a design canvas (home page, the merchandiser's orders, the buyer's overview) and then built to match.

## Principles

- **Minimal and earthy.** Paper, umber, clay, moss and ochre. Colour is for status and for one accent; everything else is neutral.
- **Flat.** Hairline borders, no shadows, no coloured card edges, no gradients.
- **Status is a dot and a word.** Never a coloured capsule. Small grey tags only label a thing (kind of file, "Change").
- **One frame.** Every signed-in page sits in the same sidebar (a tab bar on a phone). No second navigation bar, no side panels on pages.
- **One alert pattern.** "Needs you" / "Needs your attention" is one list, one line each, a dot for urgency and one action.
- **Say what to do.** Empty states say what the list is for and what to do about it.

## Colour (light, with the dark counterpart in the stylesheet)

| Token | Light | Used for |
|---|---|---|
| `--bg` | `#F5F0E6` | the page |
| `--surface` | `#FBF8F2` | cards, the sidebar, tables |
| `--sunken` | `#EDE6D9` | hover, selected, tags, empty bars |
| `--ink` / `--ink-2` / `--ink-3` | `#2A2520` / `#5B5246` / `#756A57` | text: main, secondary, tertiary (all pass 4.5:1 on the surfaces they sit on) |
| `--line` / `--line-2` | `#DDD3C2` / `#CBBFA9` | hairlines, input borders |
| `--accent` | `#A5502F` | the active icon, labels, the "unread" dot |
| `--green` / `--amber` / `--red` | `#4F6B3A` / `#8F6012` / `#A63C2B` | on track / behind or waiting / will miss or late (each has a `-bg` and `-line` partner) |

Dark mode follows the device unless the person chose; the same token names carry a warm dark palette (`#1D1915` ground). A scan with an accessibility checker finds no serious or moderate problems in either (`python e2e/a11y.py light|dark`).

## Type

| Use | Font | Size |
|---|---|---|
| Page title (h1), the wordmark, big figures | Fraunces (serif), regular | 30px, 20px, 28px |
| Section titles (h2) | Inter, semibold | 14px |
| Body | Inter | 14px, line height 1.5 |
| Small and secondary | Inter | 12 to 13px |
| Labels over a section | Inter, uppercase, 0.12em spacing | 12px |

Tamil text uses Noto Sans Tamil. Fonts load from Google Fonts and fall back to Georgia and the system sans, so the layout holds offline.

## Spacing and shape

- Spacing steps: 4, 8, 12, 16, 20, 24, 32. A page has 24 to 32px of padding and 24px between its blocks.
- Radius: 8px for inputs and menus, 12px for cards, pill (999px) for buttons, chips and the search box.
- Controls are 34 to 36px high (30px for small), and 44px or more on a phone's tab bar.

## Shared parts

| Part | File | What it is |
|---|---|---|
| `AppShell` | components/AppShell.tsx | sidebar with line icons, labels and counts, primary action, search, account menu, collapse; tab bar and "More" sheet on a phone; skip link |
| `Icon` | components/Icon.tsx | the line icons, one stroke weight |
| `PageHeader` | components/ui.tsx | breadcrumbs, title, status, subtitle, actions |
| `EmptyState`, `Skeleton` | components/ui.tsx | an empty list that says what to do; grey bars while loading |
| `Attention` | components/Attention.tsx | the "needs you" list |
| `Inbox` | components/Inbox.tsx | the conversation list for both sides |
| `Conversation` | components/Conversation.tsx | a thread with read marks, request history and the composer |
| `ApprovalCard` and friends | components/Approvals.tsx | an approval, its trail, the buyer's and the office's actions |
| `NoticeCard` | components/NoticeCard.tsx | the buyer's delay notice and its acknowledgement |
| `Activity` | components/Activity.tsx | the order timeline |

## Rules a new screen follows

1. Start with `PageHeader`; put the page's one primary action there, not a second copy of what the sidebar already offers (on a phone, where the sidebar is a tab bar, mark that button `phone-only`).
2. A list that leads somewhere is a table with `rows-link`, or an `Inbox`-style list; the whole row is the link.
3. Status uses `StatusPill` or a `pill pill-*`; labels use `tag`.
4. Anything that needs the person goes into `Attention`, not into a new kind of card.
5. Give every list an `EmptyState` and a `Skeleton`.
6. A view-only buyer must not see a button the server would refuse (`useCanWrite`).
7. Check it at 390px wide and in dark mode before calling it done; the browser journey fails on sideways scrolling and on squeezed titles.
