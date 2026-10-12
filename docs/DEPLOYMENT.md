# Putting the system on a public link (Render, free plan)

Written for Ayzhiedy, who is not a developer. Follow it from top to bottom. Nothing here costs money if you stay on the free plan.

**What you get:** one link like `https://optimizing-survival-xxxx.onrender.com` that the adviser, the panel and the team can open. It shows the dashboard and runs the planning service from the **deploy-sandbox** branch in a "demo / sandbox" mode (a yellow notice at the top; entries are throwaway and reset).

**What it is not:** it is not the thesis system's permanent home, not a place to keep real field checks, and not a promise of uptime. The laptop demo stays the backup for the defense (section 15).

## How to read the marks in this guide

- **[RE-CHECK: ...]** = I wrote this from memory of how Render looked when I last knew it. Render changes its pages and its free-plan rules. Before you rely on it, look at the page or menu named in the brackets and trust what you see there over what I wrote.
- **[FROM THE REPO]** = checked by me in this project's files and tests.
- **UNKNOWN** = nobody has tested it yet. The first real deploy is the first test on Linux.

If a screen on Render does not look like my description, **stop and send it to Claude Code** (section 12 has a template). Do not guess.

---

## 0. Before you start (5 minutes)

1. You need: your GitHub login, an email address for Render, a phone or second device (to test the link from outside your Wi-Fi).
2. Check that the branch exists on GitHub: open `https://github.com/zed2608/Optimizing-Survival-System`, click the branch drop-down at the top left, and look for **deploy-sandbox**. [FROM THE REPO: pushed, last commit 57eae4e at the time of writing.]
3. Read section 1 (public or private repository) before you connect anything.
4. Re-check Render's free-plan rules now (credit card, hours, limits): open **https://render.com/pricing** and **https://render.com/docs/free** and read what they say about *free web services*. Write down: does it ask for a credit card? How many free hours per month? How much memory? What happens after 15 minutes without visitors? **[RE-CHECK: render.com/pricing and render.com/docs/free]**

---

## 1. Is our GitHub repository public or private, and what does it mean?

### How to check (any time)
- Open the repository page. Next to the name there is a small grey label: **Public** or **Private**.
- Or open the address in a private/incognito window where you are **not** logged in to GitHub. If you can see the files, it is public.
- The place where it is changed is **Settings > General > Danger Zone > Change repository visibility**. **I did not and will not change it; that is your decision.**

### What I found (13 Oct 2026)
- I looked it up without logging in: the repository **`zed2608/Optimizing-Survival-System` is PUBLIC** and has **no licence file** (GitHub reports `license: null`).
- The real field-check database is **not** in the repository (git ignores it; `git ls-files data/field` is empty). I searched the code and notes for keys, passwords and tokens and found none. That search covered `.py`, `.js`, `.jsx` and `.md` files only, not every file type.

### What this means for the files in `deploy/`
`deploy/` holds three files the Docker image needs: the packed score database (`site_scores.db.gz`, 9.8 MB), `score_run.json` and `rf_site_suitability_meta.json`.
- Because the repository is public, **anyone on the internet can download them**, today. They contain our **provisional** scores (rule scores and the Random Forest `s_prob`), not signed off by the agriculturist. The dashboard says "provisional"; a downloaded file does not.
- They are derived from data that came from the LGU (zoning, soil map, boundaries) and from the species sources. They contain scores per grid square and species, not the LGU files themselves.
- Everything else the deployment needs is **already public** in the repository: `data/processed/` (species table with cited sources, purpose scores, site grid, land-cover shares, interview notes, nursery list), the LGU shapefiles `data/BRGY_BOUNDARY.*`, `data/LandUses.*`, `data/SMR_WATERBODIES_POLY.*`, and the digitized soil layer. **Git keeps history**: deleting a file later does not remove it from old commits or from anyone's copy.

### Things to decide BEFORE you share the link widely (list, I did not change any of them)
1. **No licence.** With no licence file, the default is "all rights reserved": people may look but have no permission to reuse. If the university or the adviser wants a licence (or wants none), that is their rule to decide. Ask the adviser.
2. **LGU data.** The zoning, boundary and waterways files and the soil map came from the LGU of San Mateo. I found **no written permission to publish them** in the repository (the credits in the dashboard say "provided by the LGU for this research; no licence text was supplied"). Ask the MPDC/LGU whether publishing is fine. If not, those files would have to be removed **and** the history rewritten, which is hard once others have copies.
3. **People's names.** Names and job titles of LGU staff (MPDC, MAO) and the agriculturist's marks appear in 10 tracked files: `CLAUDE.md`, `docs/DATA_SOURCES.md`, `docs/INTERVIEW_FINDINGS.md`, `docs/SAMPLE_VALIDATION_RESULT.md`, `data/validation/agri_sample_marks_20261007.csv`, `data/processed/grid_report.txt`, `pipeline/rebuild_site_grid.py`, `pipeline/site_rules.py`, `scripts/score_agri_sample.py`, `tests/test_species_extras.py`. Interview notes are in `data/processed/interview_notes.csv`. Check that these people agreed to be named in a public place.
4. **Your email** (`ayzhiedy26reyes@gmail.com`) is in the commit history (normal for GitHub, but public).
5. **Provisional data.** The scores are not signed off. The public link carries a notice; the public repository does not. A line in the README already says "not signed off yet".
6. **Housekeeping I noticed:** some old model files (`data/*.pkl`) and mock data are tracked, although the project rule says not to commit model pickles. They are old, not used by the service. Not a danger, just untidy.

**If you decide to make the repository private:** Render can still deploy it (next section). GitHub keeps the existing pull request and branches. Anyone who already copied the repository keeps their copy.

### Can Render deploy a **private** repository? Does the free plan allow it?
- Yes, I believe so: when you connect GitHub, Render asks you to install the **Render GitHub App** and to choose which repositories it may read ("All repositories" or "Only select repositories"). Choose **Only select repositories** and tick just this one. Render then clones it with that permission.
- I believe the free web-service plan is allowed to use private repositories, but I am **not sure**. **[RE-CHECK: render.com/docs/free and render.com/docs/github (the page about connecting GitHub and private repositories)]**
- If the repository stays **public**, there is a simpler option: **Public Git Repository** (paste the repository address, no GitHub login needed). The downside I know of: no automatic update when you push. That is fine because we use manual deploys anyway.

---

## 2. Create the Render account

1. Open **https://render.com** and click **Get Started** (or **Sign Up**). **[RE-CHECK: render.com, top right button name]**
2. Choose **GitHub** as the sign-up method (easiest, it also lets Render see your repositories). Or use your email.
3. If Render asks for a **credit card**, **stop and read what it says**. I believe free web services do not need a card, but I am **not sure**. If a card is required, tell the adviser/team before continuing; do not add a card if you do not want to. **[RE-CHECK: the sign-up screens and render.com/docs/free]**
4. Verify your email if asked.
5. If asked for a **workspace** name, use any name (for example "Optimizing Survival").

---

## 3. Create the web service (Option A: by hand, recommended the first time)

All of this is on the Render **Dashboard** (https://dashboard.render.com).

1. Click **New +** (top right) > **Web Service**. **[RE-CHECK: Dashboard > New +]**
2. Under **Source Code**, pick **Git Provider** and **GitHub**. If you see "Configure account" / "Connect GitHub", follow it:
   - GitHub opens and asks you to install **Render**. Choose **Only select repositories** and tick **Optimizing-Survival-System**. Click **Install** / **Save**. **[RE-CHECK: the GitHub page that opens]**
   - (If the repository is public and you prefer not to connect GitHub: use the **Public Git Repository** tab and paste `https://github.com/zed2608/Optimizing-Survival-System`.)
3. Click the repository name > **Connect**.
4. Fill in the form. Use this table; the right-hand column tells you where to double-check each item.

| Field on the form | Value to enter | Where it came from | Re-check here |
|---|---|---|---|
| **Name** | `optimizing-survival` (the link will be `https://<name>.onrender.com`, with extra letters if the name is taken) | my suggestion | the form itself |
| **Region** | the one closest to the Philippines that is offered (for example **Singapore**) | my suggestion, from memory | **[RE-CHECK: Region drop-down; free instances may be limited to some regions]** |
| **Branch** | `deploy-sandbox` | [FROM THE REPO] | Branch drop-down must list `deploy-sandbox` |
| **Root Directory** | leave **empty** | from memory | **[RE-CHECK: form field "Root Directory (optional)"]** |
| **Runtime / Language** | **Docker** | `render.yaml` says `runtime: docker` (from memory of the blueprint format) | **[RE-CHECK: the "Language" or "Runtime" drop-down on the form]** |
| **Dockerfile Path** | `./Dockerfile` (the default) | `render.yaml`, from memory | **[RE-CHECK: Dashboard > your service > Settings > Build & Deploy > Dockerfile Path]** |
| **Instance Type** | **Free** | `render.yaml` says `plan: free`, from memory | **[RE-CHECK: Instance Type cards; read its memory, CPU, "spins down after inactivity" text. Our measurements say the app needs about 260 MB; the free instance is expected to have 512 MB]** |
| **Health Check Path** | `/health` | [FROM THE REPO: the Dockerfile and tests use `/health`]; the field's existence and name are from memory | **[RE-CHECK: Settings > Health Checks > Health Check Path (may be under "Advanced" on the creation form)]** |
| **Auto-Deploy** | **No** / "Off" (so nothing changes while the panel is looking) | `render.yaml` says `autoDeploy: false`, from memory | **[RE-CHECK: Settings > Build & Deploy > Auto-Deploy; the name and the options may have changed]** |
| **Environment variables** | none needed (see section 4) | [FROM THE REPO] | Environment tab |

5. Click **Deploy Web Service** (or **Create Web Service**). The first build starts.

### Option B: by blueprint (`render.yaml`) — only if Option A confuses you
1. **New +** > **Blueprint**, pick the repository and the branch `deploy-sandbox`. Render reads `render.yaml` and shows what it will create. **[RE-CHECK: the field names inside `render.yaml` against render.com/docs/blueprint-spec — I wrote them from memory: `type: web`, `runtime: docker`, `plan: free`, `branch`, `dockerfilePath`, `healthCheckPath`, `autoDeploy`, `envVars`]**
2. If Render reports an error about a field, **do not edit the file yourself**: send the message to Claude Code (section 12).

---

## 4. Environment variables

**You do not have to set any.** The Dockerfile already sets everything the sandbox needs (`OS_PUBLIC_MODE=1`, where the throwaway state lives, where the dashboard is). **Render itself sets `PORT`** (I believe 10000) and the service listens on it. **[RE-CHECK: Dashboard > your service > Environment; and render.com/docs/web-services (the page about the PORT variable)]**

Optional ones, only if Claude Code tells you to (all in **your service > Environment > Add Environment Variable**):

| Name | What it does | Default |
|---|---|---|
| `OS_RESET_HOURS` | empty the sandbox after this many hours (first request after that) | 24 |
| `OS_TRUST_PROXY_HOPS` | which visitor address the limits use behind Render's proxy | 1 |
| `OS_RATE_PLAN`, `OS_RATE_KIT`, `OS_RATE_FIELD`, `OS_RATE_COMPUTE` | requests allowed per visitor (plans/hour 20, kits/hour 6, field checks/hour 60, calculations/minute 60) | see left |
| `OS_MAX_PLANS`, `OS_MAX_KITS`, `OS_MAX_FIELD_EVENTS` | how many things the sandbox may hold (200, 30, 2000) | see left |

**Never** type a password or secret here for this project: it needs none.

---

## 5. Watch the first build and find the link

1. After you click create, Render shows the **Logs** page. The first build takes a while (I guess **5 to 10 minutes**: it installs the dashboard tools, builds the page, installs the Python packages and unpacks the score database). **UNKNOWN until you try.**
2. The log ends with a line like `Your service is live` and the status at the top changes to **Live** (green). **[RE-CHECK: wording and colour on Render's page]**
3. The **link** is at the top of the service page, under the name, shaped like `https://optimizing-survival-xxxx.onrender.com`. Click it.
4. If the status says **Failed** or the log shows red errors, go to section 11.

---

## 6. Check that it works (10 minutes, do it every time after a deploy)

Open the link on your laptop first, then on your phone using mobile data (not your Wi-Fi), so you know it works from outside.

| # | Do this | You should see |
|---|---|---|
| 1 | Open the link | A yellow strip at the very top: "Demo / sandbox. Data is provisional and not yet signed off by the agriculturist. Entries reset regularly." and the map of San Mateo. The first load after sleeping can take about a minute. |
| 2 | Open the link followed by `/health` (for example `https://....onrender.com/health`) | A page of text starting `{"status":"ok"` and containing `"s_source":"rf"` and `"public_mode":{"on":true`. If you see `"s_source":"rules"` the Random Forest scores were not loaded: send it to Claude Code. |
| 3 | Open the link followed by `/docs` | "Not found" (this is on purpose) |
| 4 | Click on the map in the green area | A panel with ranked species for that spot |
| 5 | Make a small plan (sidebar steps; pick an area, a purpose, 20 trees) and press **Create plan** | A result card with trees, blocks and hectares |
| 6 | Open the **Field kit** tab of the plan and press **Build field kit**, then **Download** | A .zip file downloads (this is the heaviest step: it can take 10 to 20 seconds) |
| 7 | **More > Data credits** | A list of 8 sources, including ESA WorldCover, the LGU soil map, Esri, OpenStreetMap and Open-Meteo |
| 8 | **Weather** tab | A forecast (it needs Render to reach the internet) |
| 9 | The "Old dashboard" links | Should be **absent** from More in the sandbox |

If you test the limits: press **Create plan** many times quickly. After about 20 in an hour you should see "Too many requests...". If it happens much sooner (for example for 3 or 4 plans), the visitor addresses are probably all counted as one: tell Claude Code (this is the "proxy" guess I could not test).

---

## 7. Sharing the link

- Send the link and one sentence: "This is a demo sandbox. The first page can take about a minute to wake up. Data is provisional. Anything you enter is thrown away regularly."
- Everyone shares the same sandbox: plans made by one person appear in the list of the others (the Campaign Logs). Observer names typed into field checks are visible to everybody. **Tell people not to type real personal information.**

---

## 8. Update the link after a change

1. On your laptop, when Claude Code has changed something and pushed it to `deploy-sandbox`:
2. Render > your service > **Manual Deploy** (button, top right) > **Deploy latest commit**. **[RE-CHECK: the button name and menu on the service page]**
3. Wait for **Live**, then repeat section 6.
4. If you ever rebuild the scores on the laptop (`python scripts/rebuild_scores.py`), Claude Code must also run `python scripts/deploy_pack.py` and push, **otherwise the public link shows the old scores** (a test fails to warn about it).

---

## 9. Reset the sandbox

The sandbox empties itself:
- every time the service **restarts or is deployed** (the free plan's disk is thrown away), and
- **24 hours** after it started (first request after that).

To empty it **now**, before a demo:
1. Render > your service > the **Manual Deploy** menu > **Restart service** (or the three dots menu next to the name). **[RE-CHECK: exact menu; in some versions "Restart" is under the three-dot menu or "Settings"]**
2. Wait until it is **Live** again and the first load finishes, then open `/field-checks/summary` on the link: it must say `"events":0`.

Note: field checks cannot be deleted one by one, by design. A reset is the only way.

---

## 10. Look at the logs

Render > your service > **Logs** (left menu). **[RE-CHECK: left menu name]** You see what the service printed. Normal lines are short, such as the start-up line from `uvicorn`. The **Events** tab lists each deploy with its result.
To send logs to Claude Code: select the last 100 lines, copy, paste (template in section 12).

---

## 11. If the build or the start fails

### Step 1: read the log
Render > your service > **Logs** (or **Events** > click the failed deploy). Scroll to the **bottom** and look upwards for the first red line or the word `error` / `Error` / `failed`. The cause is usually in the 10 lines before the final failure.

### Step 2: the usual causes
| What the log says (words to look for) | Probable cause | What to do |
|---|---|---|
| `COPY failed`, `file not found`, `no such file or directory` | A file the Dockerfile copies is not in the repository (for example the `deploy/` files, or `data/config/`) | Send the log to Claude Code. Do not try to fix files yourself. |
| `Killed`, `out of memory`, `OOMKilled`, `exit code 137` | The build or the running service ran out of memory (the free instance has little) | Send the log. We measured about 260 MB at run time on Windows; the build may need more. Linux is UNKNOWN. |
| `No matching distribution found`, `requires Python`, `Could not find a version` | A package is not available for Python 3.12, or a version rule is too strict | Send the log. (The tests passed on Python 3.12.6 on Windows; Linux could differ.) |
| `npm ERR!`, `npm ci`, `vite` errors | The dashboard did not build | Send the log. |
| `Timed out`, `Build exceeded`, `deadline` | The build took longer than Render allows for the free plan | Send the log and say how long it ran. **[RE-CHECK: render.com/docs/free or the pricing page, for the build time limit]** |
| The build says "Live" but the page does not open, or Render says "Port scan timeout" / "No open ports detected" | The service did not listen on Render's port in time | Send the log. The service uses `PORT` automatically; this should not happen, so it is important to report. |
| `Health check failed` | `/health` did not answer in time (slow start) | Wait 1 minute and reload. If it repeats, send the log. Also check Settings > Health Check Path is exactly `/health`. |
| `Not Found` on the main page but `/health` works | The dashboard files were not found | Send the log. |
| `remote: Repository not found` / permission error at the start | Render cannot read the repository (private repository without access) | Section 1 and section 3 step 2: give the Render GitHub App access to this repository. |

### Step 3: do not
- Do not change the Dockerfile, `render.yaml` or anything in `deploy/` by hand.
- Do not click "Clear build cache" unless Claude Code says so (it only makes the next build slower).
- Do not upgrade to a paid plan to "make it work" without asking the adviser.

---

## 12. What to send to Claude Code (copy this, fill the gaps, paste the log)

```
Deployment problem on Render (free plan).

What I was doing: (for example "first deploy", "Manual Deploy of the latest commit", "opening the link")
Branch and last commit: deploy-sandbox, (the short code shown on Render's Events tab, e.g. 57eae4e)
Status shown on Render: (Failed / Live but the page is blank / Deploy canceled / ...)
Which step failed: (build / start / health check / the page opens but ...)
Time it took before failing: (about N minutes)
Did the free-plan page say anything different from DEPLOYMENT.md? (yes/no, what)

The last 100 lines of the log (Render > Logs, copy and paste, include the first red line):
<paste here>

What I see in the browser (text on screen, or a screenshot):
<paste here>
```

Also paste the **first** error line, not only the last lines, because the first one is usually the real cause.

---

## 13. If the link is slow or "asleep"

- The free plan puts the service to sleep after about **15 minutes without visitors** **[RE-CHECK: render.com/docs/free]**. The next visitor waits for it to wake up (roughly 30 to 60 seconds plus about 4 seconds for loading the data; **UNKNOWN on Render until tried**). The page may show a Render "waking up" screen first: wait, do not keep refreshing.
- After a sleep the sandbox is **empty again**: plans made before the sleep are gone.
- If it stays blank for more than 3 minutes: open `/health` on the link; if that works, reload the main page with Ctrl+F5.
- If `/health` does not work after 5 minutes: look at Logs (section 10) and use section 12.

---

## 14. Pre-demo checklist (the day of a demo with the link)

**3 minutes before (or earlier):**
- [ ] Open the link on your laptop. If it was asleep, wait until the map and the yellow notice show.
- [ ] Open `…/health`: you see `"status":"ok"`, `"s_source":"rf"`, `"public_mode":{"on":true`.
- [ ] Click a green spot on the map: the species panel fills.
- [ ] Make one small plan (20 trees) and check the result card. (This also warms the service.)
- [ ] If you want a clean start for the audience: do a **restart** (section 9) at least 10 minutes before, then wake it again with the steps above.
- [ ] Open the link on a phone with mobile data once.
- [ ] Have the laptop fallback ready (next section) in case the free service is down or slow.
- [ ] Tell the people who will open it: "Open it now, the first page takes up to a minute."

**Do not** run the kit build on the day with many people at the same time: only one kit can be built at a time.

## 15. Laptop fallback checklist (the defense backup, no internet needed except map pictures and weather)

Do this the day before, and again 30 minutes before.
- [ ] Laptop plugged in, power plan not "sleep after 5 minutes".
- [ ] Open a PowerShell window in the project folder and run `.\scripts\start_dev.ps1 -CheckOnly` — it only checks; every line should be fine (virtual environment, packages, node, data, free ports). If it complains about missing packages, ask Claude Code (do not install things in a hurry).
- [ ] Run `.\scripts\start_dev.ps1 -Demo` (the `-Demo` switch keeps demo field checks out of the saved file). Two windows open; wait for the line saying the backend answers `/health`.
- [ ] Open `http://localhost:5173` in the browser. Click a spot, make a plan. The scores come from the laptop's own files.
- [ ] Map pictures and the weather need the internet; without it, the map background is grey and the Weather tab says it is not available. `docs/DEMO_SCRIPT.md` has the offline backup plan and honest answers.
- [ ] To stop: `.\scripts\start_dev.ps1 -Stop`.
- [ ] Keep `docs/DEMO_SCRIPT.md` open on a second screen or printed.

---

## 16. What the free plan does NOT promise

Re-check each against Render's official pages **[RE-CHECK: render.com/docs/free and render.com/pricing]**:
- **No always-on service:** it sleeps after inactivity, so the first visitor waits.
- **No saved data:** the disk is thrown away at every restart, sleep-and-wake or deploy. Our sandbox is built for that; do not put real field data on it.
- **No guaranteed speed:** a small shared CPU and little memory; many people building kits at once will be slow (we allow one kit at a time).
- **No guaranteed hours:** the free plan has a monthly limit of running hours and may suspend the service when it is used up (check the number). A suspended service does not answer until the next month or until you act.
- **No custom domain or paid features** (the link ends in `.onrender.com`).
- **No guaranteed support:** if Render has an outage, the link is down; use the laptop.
- **No promise that the free plan stays as it is today.** Terms change.
- **Our own limits:** a visitor can make about 20 plans, 6 kits and 60 field checks per hour; the sandbox holds at most 200 plans, 30 kits and 2,000 field checks.
- **Not a security system:** there is no login. The sandbox is protected by throwaway state and limits, not by passwords. Do not use it for anything private.

---

## 17. Everything I wrote from memory (one list to check on Render's pages)

| Item | Where to check |
|---|---|
| Does the free plan need a credit card? | Sign-up screens; render.com/docs/free |
| Free web service: memory (I assume 512 MB), CPU, sleep after about 15 minutes, free hours per month, build time limit | render.com/docs/free; render.com/pricing; Instance Type cards on the creation form |
| Private GitHub repositories allowed on the free plan? | render.com/docs/github; the connect screens |
| Name and place of: **New +**, **Web Service**, **Blueprint**, **Public Git Repository** | Dashboard top right; the New menu |
| `render.yaml` fields: `type`, `runtime`, `plan`, `branch`, `dockerfilePath`, `healthCheckPath`, `autoDeploy`, `envVars` | render.com/docs/blueprint-spec |
| **Region** choices (is Singapore offered for free?) | Region drop-down on the creation form |
| **Dockerfile Path** | Service > Settings > Build & Deploy |
| **Health Check Path** | Service > Settings > Health Checks (or "Advanced" on the creation form) |
| **Auto-Deploy** switch and its wording | Service > Settings > Build & Deploy |
| `PORT` set by Render (I assume 10000) | render.com/docs/web-services; Service > Environment |
| **Manual Deploy** > **Deploy latest commit** | top right of the service page |
| **Restart service** location | three-dot menu next to the service name, or Manual Deploy menu |
| **Logs** and **Events** tabs | left menu of the service |
| Link address (`https://<name>.onrender.com`) | top of the service page |
| Whether Render adds its own proxy in front so that the visitor-address guess (`OS_TRUST_PROXY_HOPS=1`) is right | test in section 6 (the plan-limit test) |
| Whether `/health` is allowed as the health check (it returns a larger JSON; if Render times out on it, Claude Code can add a tiny `/ping`) | the Events tab after the first deploy |

---

## 18. Things only the first real deploy can tell us (UNKNOWN today)

- The image size and whether Render accepts it on the free plan.
- The build time and whether the free build limit is enough.
- Memory on Linux (Windows measurement: 185 MB after start, 257 MB after one plan and one kit).
- Whether any library behaves differently on Linux (the full test suite passed on Python 3.12 on Windows, 735 tests, plus the 5 deployment tests).
- Whether the visitor-address guess is right (see sections 6 and 17).
- Whether the terms of Esri World Imagery, OpenStreetMap tiles and Open-Meteo allow this kind of public demo. The dashboard's credits page says "terms to be checked" for these three. Open **https://www.openstreetmap.org/copyright**, **https://open-meteo.com/en/terms** and the Esri World Imagery terms before you share the link outside the panel and team.
