# Gaps between the buyer and the merchandiser, and what was done about them

An audit of the real screens (desktop and phone), walking one order from the buyer's request to the shipped order. Each gap is something a person would have got stuck on. **Fixed** means it is built and covered by the browser journey in `e2e/` or by tests; **Open** means it is still a gap.

## What was wrong

| # | Gap | Who it hurt | Status |
|---|---|---|---|
| 1 | **No way to find anything.** The board filtered by buyer, unit and week; nothing searched by PO, LT number, style or buyer. | Merchandiser | Fixed: search from anywhere (`/` or Ctrl+K), results grouped as orders, requests and buyers |
| 2 | **No "what needs me" on either side.** A countered date was a small pill in a table; the office's warnings, late materials and waiting requests were on different screens. | Both | Fixed: **Needs you** on the order board, **Needs your attention** on the buyer's overview; every card goes straight to the thing, and "nothing waiting" is said plainly |
| 3 | **Questions about a live order had no channel.** A buyer could only send a *change request*, which needs a new date or quantity. | Both | Fixed: a conversation on every order, visible to both sides, with the board and the order page showing who owes a reply |
| 4 | **The buyer's home was one 4,600-pixel page** with every order's full detail repeated and no way to scan, search or go back. | Buyer | Fixed: overview, orders list with search and tabs, one page per order with tabs |
| 5 | **The buyer's header had no navigation**, only the company name and a back link. | Buyer | Fixed: Overview, Orders, Requests (with a count when their answer is needed), and **+ New request** |
| 6 | **Pages were ordered by data type, not by what to do.** On a request the *Agree* button sat under a Files card; the merchandiser's four decision buttons sat under the files too, with nothing about the buyer to decide with. | Both | Fixed: the buyer's request opens with **Your turn** and the action; the office request opens with the decision, and a side panel shows the buyer's live orders and how they are going |
| 7 | **The office bar mixed daily work with setup** (Templates, Units) and treated "New order" as a page. | Merchandiser | Fixed: Orders, Requests, Buyers, then **Set up** (templates, units); **+ New order** is a button |
| 8 | **The order page was about 2,600 pixels with no way to jump around**, and the buyer's name was plain text. | Merchandiser | Fixed: breadcrumbs, a sticky section bar, the buyer's name links to all their orders, the conversation sits near the top |
| 9 | **The office could not see what the buyer sees.** | Merchandiser | Fixed: **What the buyer sees** on every order opens the buyer's own page for it |
| 10 | **No "new since I last looked".** | Buyer | Fixed in the browser: a "New reply" card and dot that clear once read. Open: it is remembered per browser, not on the server |
| 11 | A buyer on a **phone**: request rows were squeezed to one letter per line, the office's "needs you" cards stacked a screen tall, the bar wrapped awkwardly. | Both | Fixed: rows reflow, the cards slide sideways, and the browser journey fails if a page scrolls sideways or a title is squeezed into a sliver |
| 12 | `npm run seed` **failed once the app had been used**, because it did not clear requests and files. | Whoever resets the demo | Fixed |

## Still open

| Gap | Why it matters | Note |
|---|---|---|
| Nothing reaches people **outside the app** | A buyer who does not open the page does not know their merchandiser replied | Email is still mocked; WhatsApp is the realistic channel for Tiruppur. In TODO |
| The office cannot tell whether the buyer has **seen** a delay notice or a reply | The merchandiser cannot tell "ignored" from "not seen" | Needs read tracking on the server. In TODO |
| **One conversation per order**, not per topic | A long order will mix sample talk with shipping talk | Fine for the size of these orders; threads or tags if it grows |
| Request and order conversations are **separate threads** | A request's talk stays on the request after it becomes an order | Both are one click apart (request page links to the order, order page lists its request) |
| Buyer **accounts** cannot be limited to read-only | Every account for a buyer can do what the link can | In TODO |
| Sub-pages for **supervisors** were not part of this pass | The phone screens for the floor are a different audience | Audited earlier; no known navigation problems |

## How this is checked

`e2e/` holds the scripted browser journeys. The journey that guards this work walks the flow end to end: the office finds the buyer's message from the board, answers it, the buyer sees and reads the reply, a countered date is agreed and accepted into an order and the buyer follows it to the order, and 13 pages are checked at phone width for sideways scrolling and squeezed titles. It found two layout bugs in this very pass that the type-checker and the unit tests could not.
