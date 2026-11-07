# Putting the app on a supervisor's phone

LoomTrack is a web app that installs to the home screen (a PWA). There is no app store, no APK and nothing to approve: the supervisor opens one link, taps Install, and gets an icon that opens full screen, works with no network, and queues their updates until the network is back.

## What has to be true first (once, for the company)

| Need | Why |
|---|---|
| The app runs at an **https** address (for example `https://track.yourmill.com`) | Phones only offer to install, and only allow the camera and microphone, on https. `http://192.168.x.x` on the Wi-Fi will open the site but **will not install**. `localhost` counts as secure, but only on the computer itself. |
| Set `LOOMTRACK_PUBLIC_URL` in `backend/.env` to that address | Links in emails and WhatsApp messages use it. |
| Each supervisor has an account | Office, **Units and capacity** is where units are; accounts are created at seed time today (phone number and a 4-digit PIN). |

For a quick trial without buying anything, a free Cloudflare tunnel (`cloudflared tunnel --url http://localhost:4000`) gives an https address that works on any phone. For the real thing, put the server behind a domain with a certificate (Caddy and Let's Encrypt are free).

## The office does this, once per supervisor

1. Open **Units and capacity**. The first card, *Supervisors' phone app*, shows the install link (`https://your-address/install`). Press **Copy**.
2. Send it to the supervisor on WhatsApp together with their **phone number and PIN** (the PIN is their password; the office hands it over in person or by call, not in the same message if you can help it).

## The supervisor does this, once

1. **Tap the link.** A Tamil page opens: *உங்கள் ஃபோனில் LoomTrack நிறுவுங்கள்* (English one tap away).
2. **Android (Chrome):** tap **நிறுவு / Install**, then **Install** in the phone's own box. If no button appears (some browsers), the page lists the menu steps: ⋮, *Install app* or *Add to Home screen*.
   **iPhone (Safari only):** the page lists three steps: *Share*, *Add to Home Screen*, *Add*. An iPhone has no install button for any website; nothing can change that.
3. **Open the new LoomTrack icon** on the home screen. It opens full screen on the sign-in page.
4. **Sign in** with the phone number and PIN. The language switches to Tamil (or whatever is set on their account).
5. A short **welcome in Tamil** appears once on this phone: update your order each day, allow the camera and microphone when the phone asks, no internet is fine. Tap **புரிந்தது** (Got it).
6. The orders for their unit are listed. The first photo or voice note makes the phone ask for the camera or microphone: tap **Allow**. It asks once.

If they signed in in the browser before installing, the home page shows a one-line *Put LoomTrack on your phone* offer with **Later**, which is remembered.

## Every day after that

Tap the icon, tap the order, enter pieces, add a photo or voice note if needed, **Send**. With no network the update is saved on the phone (*waiting to send*) and goes by itself when the network returns; a refused update is kept with the reason and a **Discard** button. The list of orders was saved the last time the phone was online, so it opens in a lift or a basement.

The header says *Offline* when the phone cannot reach the server, including when it is on Wi-Fi that has no internet.

## When something changes

| Situation | What happens |
|---|---|
| A new version of the app is deployed | The next time the phone is online and the app is opened, it loads the new version (pages are checked every time; the stored copy is only the fallback). Close and reopen once if a screen looks old. |
| Supervisor gets a new phone | Send the same link, sign in again. Anything still queued on the old phone is lost, so ask them to open the app online first so it sends. |
| Forgot the PIN | The office resets it; there is no self-service reset for the floor yet. |
| Removed the app by mistake | Open the link again and install again. Their data is on the server. |
| Signed in on a shared phone | Use **Sign out** (bottom of the home screen). The welcome is remembered per person on that phone. |

## What was checked, and what was not

Checked with `python e2e/pwa.py` (Chromium with phone settings): the manifest and its icons, that Chrome reports nothing in the way of installing, that the app and its scripts are stored, that the app opens and lists orders with the network switched off, that the Android page and the iPhone page give the right instructions, that the welcome shows once, and that *Later* is remembered.

**Not checked: a real phone.** Installing to a home screen, the install box and the camera permission prompt behave slightly differently on every phone make and browser, and the sandbox cannot show them. Try the link on one Android phone and one iPhone before the first supervisor gets it. Things to look for on the iPhone in particular: the camera and microphone prompt inside the installed app, and voice transcription (the browser's speech service is limited on iOS; the audio is always kept for the merchandiser either way).

The Tamil wording of the new messages was written for this build and should be read by a Tamil speaker from the floor before rollout.
