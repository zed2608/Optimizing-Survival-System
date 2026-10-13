# Putting a Field Pack on the web for phones (Cloudflare Pages, Direct Upload)

Written for Ayzhiedy and anyone who has never used Cloudflare. Follow it from top to bottom. Nothing here costs money on the free plan, as far as the official pages I read say.

**What you get:** one web address (https) per plan, for example `https://fp-xxxxxxxxxx.pages.dev/<24 random letters and digits>/`. A planter opens it on a phone, allows location, and gets the planting guide of ONE plan (blocks, trees, GPS target, marks, results file).

**What it is not (read this first):**
- It is a **prototype. GPS accuracy has not been field-tested**, and the page says so on every screen.
- **Not offline yet.** The page has to load once with phone signal. The marks are saved on the phone, but if the planter closes the page and reopens it with no signal, it may not load. (Offline use is the next stage.)
- **Anyone who has the address can read the plan inside it** (block places, species, zone names). The random name keeps it out of casual reach and out of search engines; it is not a password.
- It is **not** the place for real names, scores or LGU files: the page contains none (checked by tests), only the plan of that one kit.

## How to read the marks

- **[RE-CHECK: where]** = I wrote this from the official pages I could read, or from memory of how Cloudflare looks. Cloudflare changes its screens and rules. Look at the place named in the brackets; **trust what you see there over what I wrote**.
- **UNKNOWN** = nobody has tried it yet. The first real upload is the first test.
- If a screen does not look like my description: stop and send it to Claude Code (section 12).

## What I read on Cloudflare's official pages (13 Oct 2026)

- Direct Upload = you upload ready-made files with the dashboard (drag and drop a folder or a zip) or with a tool called Wrangler. **Drag and drop: up to 1,000 files per upload; 25 MiB per file.** Our site has 3 files. **[RE-CHECK: developers.cloudflare.com/pages/get-started/direct-upload/]**
- The address of a project is `<PROJECT_NAME>.pages.dev`; if the name is taken, Cloudflare adds a few random characters. **[RE-CHECK: same page]**
- Pages free plan: 20,000 files per site, 500 builds a month, 100 projects per account. Requests to static files are free and unlimited on the free plan. **[RE-CHECK: developers.cloudflare.com/pages/platform/limits/ and /pages/functions/pricing/]**
- "If you choose Direct Upload, you cannot switch to Git integration later." (We do not need Git for this.)
- A Cloudflare account is needed (the steps assume one). **Whether a credit card is asked: the pages I read do not say. [RE-CHECK: the sign-up screens]**
- `_headers` files are documented for Pages. **Whether they work with Direct Upload is NOT stated: section 5 tests it.**

---

## 1. Make the folder to upload

You do this on your laptop, in the project folder. The kit zip is the one you download from the dashboard (Field kit tab).

1. Open PowerShell in `C:\Users\user\Desktop\Optimizing_Survival_System`.
2. Run (change the first path to your kit zip, the second is the folder that will be made):

```
python scripts\build_field_pack.py "C:\Users\user\Downloads\field_kit_plan_urban_XXXXXXXX_XXXXXX.zip" --site "C:\Users\user\Desktop\field_pack_site"
```

3. The program prints four things. Keep them:
   - **DRAG THIS FOLDER**: the folder to upload (here `C:\Users\user\Desktop\field_pack_site`).
   - **Suggested project name**: a random name such as `fp-ab12cd34ef`. Use it as the Cloudflare project name.
   - **The address will be**: `https://<project name>.pages.dev/<24 random characters>/`. This is the link for the planters.
4. The folder holds exactly three kinds of file (a test checks this): `_headers`, `robots.txt` and one folder with a random name that contains `index.html` (the pack). The random name comes from the computer's secure random generator (`secrets` in Python), **not** from the plan number or the check code, so nobody can work it out.
5. To add a second plan later, run the same command again with the same `--site` folder: it adds another random folder and never deletes or changes the others. The program refuses a folder that holds anything else.

If the program says "not part of a field pack site": you chose a folder with other files in it. Choose a new, empty folder.

---

## 2. Create the Cloudflare account (first time only)

1. Open **https://dash.cloudflare.com/sign-up** in your browser. **[RE-CHECK: the address; Cloudflare may redirect]**
2. Type your email address and a new password (not the one for your email). Click the sign-up button. **[RE-CHECK: button name]**
3. Cloudflare sends you an email. Open it and click the verification link. **[RE-CHECK]**
4. Cloudflare may offer to add a website/domain: **skip it**, you do not have a domain and do not need one.
5. If anything asks for a **credit card or payment method, stop** and tell the adviser/Claude Code before you type anything.

---

## 3. Create the project and upload the folder

1. Log in at **https://dash.cloudflare.com**.
2. In the left menu click **Workers & Pages**. **[RE-CHECK: left menu name]**
3. Click **Create application**. **[RE-CHECK: button name]**
4. Look for the **Pages** choice and **Get started**, then **Drag and drop your files** (or "Upload your static files"). **[RE-CHECK: the official page says: Workers & Pages > Create application > Get started > Drag and drop your files]**
5. **Project name:** type the **suggested project name** from step 1 (random, lower-case, with a hyphen). Do not use a name that says what the project is (no "san-mateo", no "planting"). **[RE-CHECK: whether Cloudflare accepts the name]**
6. Click **Create project**. **[RE-CHECK: button name]**
7. **Drag the folder** `field_pack_site` from File Explorer onto the upload box (or click to choose it). Drag the folder itself, not a zip of the whole project folder and not the `Optimizing_Survival_System` folder. The official page says drag and drop accepts a folder or a zip. **[RE-CHECK: drop area wording]**
8. Cloudflare lists the files it found. You should see **3 files**: `_headers`, `robots.txt` and `<random name>/index.html`. If you see more or other names, stop (see "what to send" in section 12).
9. Click **Deploy site**, then **Save and Deploy** if it asks. **[RE-CHECK: the official page names these two buttons]**
10. Wait for the "Success / Your site is deployed" screen. It shows the project address `https://<project name>.pages.dev`. Click **Continue to project**. **[RE-CHECK]**
11. **Where to see the address later:** Workers & Pages > click your project > the address is at the top (and in the **Deployments** tab). **[RE-CHECK]**
12. The planters' link is that address **plus** `/<random name>/` and the final slash, for example `https://fp-ab12cd34ef.pages.dev/smzx…/`.

**Does the folder name become part of the address?** It should not: the contents of the folder you drop should be the site's root. **Test it now:** open `https://<project name>.pages.dev/<random name>/` in your browser. If you get the page (yellow banner on top), all is as planned. If you get "Not found", try `https://<project name>.pages.dev/field_pack_site/<random name>/`; if that works, Cloudflare kept the folder name: tell Claude Code (then `_headers` and `robots.txt` are not at the root either, and section 5 will say so). **[RE-CHECK: this is exactly the kind of thing only the first upload can tell]**

The address of the project **root** (`https://<project name>.pages.dev/` with nothing after) should show "Not found" or an empty page: that is correct, the pack is only at its random address.

---

## 4. Look at it on your computer first

1. Open the planters' link.
2. You should see: the yellow banner "Prototype. GPS accuracy not yet field-tested.", the title "Planting guide", the plan number and the check code of your kit, and a list of blocks.
3. Check that the plan number and check code are the ones of the kit you meant.
4. Click a block and click **Start GPS**. Your browser asks for location: **Allow**. On a laptop the position may be rough (Wi-Fi); that is normal. The page must show a distance and a direction. If it says that location is blocked, see section 6.

---

## 5. Test whether `_headers` and `robots.txt` work (noindex)

The folder contains `_headers` (it asks the web server to add `X-Robots-Tag: noindex, nofollow`, which tells search engines not to list the page) and `robots.txt` (disallows everything). The page itself also says `noindex` in its code, so it is covered either way, but we want to know if `_headers` works with Direct Upload. **UNKNOWN until you test it.**

**Test A (a browser):**
1. Open the planters' link in Edge or Chrome on the laptop.
2. Press **F12**, click the **Network** tab, press **Ctrl+R** to reload.
3. Click the first line (the name is the random name or "index.html").
4. In the right panel click **Headers**, scroll to **Response Headers**.
5. Look for `x-robots-tag: noindex, nofollow` (also `x-frame-options: DENY`, `x-content-type-options: nosniff`, `referrer-policy: no-referrer`).
   - **Present** = `_headers` works with Direct Upload.
   - **Absent** = it does not, or the file is not at the root of the site. Write "headers: absent" in your report to Claude Code. The page is still protected by its own `noindex` and by `robots.txt`; nothing breaks.

**Test B (PowerShell, same answer):** `curl.exe -I https://<project name>.pages.dev/<random name>/` — look for the `x-robots-tag` line.

**Test C:** open `https://<project name>.pages.dev/robots.txt`. It should show `User-agent: *` and `Disallow: /`.

---

## 6. For the planters: open it in Chrome or Safari, NOT inside Messenger or Facebook

Chat and social apps open links in their own small built-in browser. **Location permission and "Add to Home Screen" may not work in it** (I believe so; not verified here). So send these lines with the link:

> Open this link in **Chrome** (Android) or **Safari** (iPhone), **not inside Messenger, Facebook or WhatsApp**. Copy the link and paste it in the address bar of Chrome/Safari, or tap the "⋯" / share button of the app and choose **Open in browser**. When the page asks for your location, tap **Allow**. Switch location (GPS) on in the phone settings.

**If the location was refused by mistake**, to allow it again: **[RE-CHECK all of these, they are from memory]**
- *Android Chrome:* tap the lock (or tune) icon left of the address > **Permissions** > **Location** > **Allow**; then reload.
- *iPhone Safari:* tap **aA** (left of the address) > **Website Settings** > **Location** > **Allow**; also check Settings > Privacy & Security > Location Services is **On** and Safari Websites is **While Using the App**.

**Tell the planters honestly:**
- GPS shows where the phone thinks it is, within the accuracy the page shows. It cannot prove that a tree was planted. Under trees it can be wrong by many metres.
- Open the page once with signal **before** going into the field, keep it open, and press **Save results file** at the end of the day (the marks stay on the phone, but a phone can lose them if the browser data is cleared).
- Send the results file to the team leader (chat). The leader imports it in the dashboard with **Import field checks (CSV)**.

---

## 7. A first real-phone test (about 20 minutes)

Do this before you rely on the page. Write down what happens; the report goes to Claude Code.
1. Phone on mobile data (not your Wi-Fi). Open the link in Chrome / Safari.
2. Does the page load? How long? Does the location question appear? Do you get a distance? What accuracy does it say?
3. Stand outside in the open, then under a tree, then near a building: how does the accuracy change?
4. Mark a tree planted, close the page, reopen it (with signal): are the marks still there?
5. Press **Save results file**: what happens (download, share sheet)? Send it to yourself by chat.
6. Which phone and which browser? (For example "Samsung A14, Chrome" / "iPhone 12, Safari".)

---

## 8. Take it down

When the planting is over (or if the link went to the wrong people):

**Delete everything (recommended):**
1. Workers & Pages > click your project. **[RE-CHECK]**
2. Open **Settings** (tab). Scroll to the bottom. Click **Delete project**. **[RE-CHECK: name and place]**
3. Type the project name if asked and confirm.
4. Test: open the planters' link: it must no longer show the page. (A phone that has already opened it may still hold a copy in its browser: ask planters to clear it or just delete the results they sent.)

**Delete only old versions:** open the project > **Deployments** > the three-dots menu of an old deployment > **Delete deployment**. Every upload makes a new deployment, and **each deployment can keep its own address** (`<code>.<project>.pages.dev`) until you delete it, so delete the old ones if they held a plan you do not want online. Cloudflare may refuse to delete the latest (production) deployment: then delete the project. **[RE-CHECK all of this on the Deployments page]**

**Keep nothing public you do not need:** the packs are also on your laptop in the `field_pack_site` folder. Delete a random folder there to remove that plan from the next upload (the program never deletes anything itself).

---

## 9. A new plan, or a changed plan

- A **changed plan = a new kit = a new check code**. Build the page again from the new kit zip: you get a **new random address**. The old page keeps working with its old plan until you delete it; results from an old page are refused by the dashboard if the plan changed (the check code does not match).
- To put the new page online: run section 1 with the same `--site` folder (it adds a new random folder), then in the project open **Deployments** and use the button to create a new deployment (**Create deployment**), and drag the folder again. **[RE-CHECK: the button name; Direct Upload makes a new deployment from what you drop, so drop a folder that still contains the plans you want to keep]**

---

## 10. Who can see what

- The page contains: plan number, check code, the kit's blocks (species, number of trees, spacing, coordinates, barangay and zone names, the kit's notes), the data version, and a short text "provisional, not yet signed off by the agriculturist". It contains **no** scores, no interview notes, no names of LGU staff or the agriculturist, no real field checks, and no outlines of LGU polygons.
- The page makes **no network calls** (a test checks this): the planter's marks and name stay on the phone until the results file is sent by chat.
- **Cloudflare holds a copy of the page** while the project exists. Anyone with the link can read it.

---

## 11. What I could not verify (please do not skip)

- That a phone gets location permission and a good position on a `pages.dev` address (Android Chrome, iPhone Safari): **A4 / section 7**.
- Whether a page opened from a downloaded file gets GPS on a phone. (On a laptop browser it did; the page tries and explains if it fails.)
- Whether `_headers` works with Direct Upload (section 5).
- Whether dropping a folder makes the folder name part of the address (section 3, last test).
- Whether Cloudflare asks for a credit card, and the exact button names above.
- That the free plan stays free and available; terms change.

---

## 12. If something fails: what to send to Claude Code

```
Field pack hosting problem (Cloudflare Pages Direct Upload).

What I was doing: (which section and step of FIELD_PACK_HOSTING.md)
What I expected: 
What I saw (exact words on the screen, or a screenshot):
The files Cloudflare listed before "Deploy site": 
The address I opened: (replace the random part with xxxx)
Phone and browser, if it is about a phone: 
Did section 5 show x-robots-tag? (present / absent / not tested)
```

Do not paste your Cloudflare password or any code from an email.
