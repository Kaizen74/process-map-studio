# Process Map Studio

Turn SME interview transcripts and process documents into a clear, evidence-backed swimlane process map. Claude drafts the map; you review every step and publish it. Everything runs on your own computer.

> Version 1.0.0 · Last updated 2026-09-29 · For how to *use* the app, see [GUIDE.md](GUIDE.md). What changed in this version: [release notes](docs/RELEASE_NOTES_v1.0.0.md).

## What you need
- A Mac (macOS 13 or later) or a Windows 10/11 PC, with at least 8 GB of memory and 2 GB of free disk space.
- An internet connection (the app sends your documents to Claude to draft the map).
- A **Claude API key** from the Claude Console (step 4 below). Using the app costs a small amount per draft, billed to your Anthropic account.
- A **GitHub account** with access to this private repository.
- About 30 minutes for the one-time setup.

## One-time setup

### 1. Install the three free tools
1. **Python 3.12** — go to python.org → Downloads → download Python 3.12 for your computer → open the installer.
   - **Windows only:** on the first installer screen, tick **"Add python.exe to PATH"** before clicking Install Now.
2. **Node.js (LTS version)** — go to nodejs.org → download the version marked **LTS** → open the installer → accept the defaults.
3. **GitHub Desktop** — go to desktop.github.com → download → install → open it → **Sign in to GitHub.com** with your GitHub account.

### 2. Get the app onto your computer
1. In GitHub Desktop: **File → Clone repository**.
2. Choose the **GitHub.com** tab, select `Kaizen74/process-map-studio`.
3. Under **Local path**, choose where to keep it (for example your Documents folder). Click **Clone**.
4. When it finishes, click **Show in Finder** (Mac) or **Show in Explorer** (Windows). This is your app folder.

### 3. Run setup (one time, and again after each update)
- **Mac:** double-click **Setup.command**. If macOS says it can't be opened, right-click (or Control-click) the file → **Open** → **Open**.
- **Windows:** double-click **setup.bat**. If Windows shows "Windows protected your PC", click **More info** → **Run anyway**.

A window opens and shows progress. It takes about 5–10 minutes the first time. You're done when it says **"Setup complete. You can now start Process Map Studio."** You can close the window.

### 4. Get your Claude API key
1. Go to platform.claude.com and sign in (or create an account and add billing).
2. Open **API keys** → **Create key** → give it a name like "Process Map Studio" → **Create**.
3. Copy the key now; it is shown only once. You'll paste it into the app in the next step.

### 5. First start
1. **Mac:** double-click **Start.command**. **Windows:** double-click **start.bat**.
2. Your browser opens Process Map Studio at http://127.0.0.1:8000 (bookmark it).
3. The home screen shows a three-step **Get started** checklist. Click **Add your Claude API key** → paste the key into the **Claude API key** box → **Save key** → **Test connection**. You want **Pass** or **Yes** on every line of the results. (You can also reach **Settings** from the top-right corner at any time.)

Your key is stored only on this computer, never in GitHub.

## Everyday use
- **Start:** double-click **Start.command** (Mac) or **start.bat** (Windows). Keep the small window it opens; it shows "Process Map Studio is running."
- **Stop:** close that small window.
- **Use:** see [GUIDE.md](GUIDE.md) for how to set up an engagement, upload sources, review and publish.

## Update to the latest version
1. Stop the app (close its window).
2. Open **GitHub Desktop**. Check the top-left says **Current repository: process-map-studio**.
3. Click **Fetch origin**. If the button changes to **Pull origin**, click it. When it says **"Last fetched just now"** with no Pull button, you have the latest version.
4. Double-click **Setup.command** (Mac) or **setup.bat** (Windows) and wait for **"Setup complete"**.
5. Start the app as usual. Your engagements and settings are kept; the app backs up its database automatically before applying any update.

If GitHub Desktop lists changed files on the left that you didn't make, don't commit or discard them: open Claude Code in the app folder and paste the Bug-fix prompt with a description of what GitHub Desktop shows.

## Install on another computer
1. On the new computer, follow **One-time setup** steps 1–5 (use the same or a new API key).
2. To bring your existing work across (optional): stop the app on the old computer, copy its **data** folder to the same place inside the app folder on the new computer, replacing the empty one. Then start the app.

The **data** folder contains your confidential transcripts and documents. Move it only on company-approved, encrypted storage, and delete temporary copies afterwards.

## Back up and restore your work
- **Back up:** stop the app, then copy the **data** folder to a secure, company-approved location. Do this after every important review or publish.
- **Restore:** stop the app, replace the **data** folder with your backup copy, start the app.
- Automatic safety copies of the database are also kept in **data/backups** (one per start that applied an update).

## What is never uploaded to GitHub
Your API key (the `.env` file) and the **data** folder (all transcripts, documents, images and maps) never go to GitHub. A built-in check blocks them even if someone tries.

## If something goes wrong
| What you see | What to do |
|---|---|
| "Python 3.12 was not found" during setup | Install Python 3.12 (setup step 1). On Windows, reinstall and tick "Add python.exe to PATH". Then run setup again |
| "Node.js was not found" during setup | Install the LTS version from nodejs.org, then run setup again |
| "Node.js … is too old" during setup | Go to nodejs.org, download the version marked **LTS** and install it (it replaces the old version; accept the defaults). Close the setup window, then run setup again |
| macOS: "can't be opened because it is from an unidentified developer" | Right-click the file → Open → Open |
| Windows: "Windows protected your PC" | More info → Run anyway |
| The browser doesn't open after Start | Open your browser and go to http://127.0.0.1:8000 |
| "Port already in use" | The app is already running. Look for its window, or restart your computer and start again |
| "Your API key was rejected" | Copy a fresh key from platform.claude.com → paste it in Settings → Test connection |
| A file won't upload ("reads .docx, .pdf, .txt, .vtt and .srt files" or "larger than 50 MB") | Save the file as Word (.docx) or PDF, or split a very large file into parts, then upload again |
| A file stays at "Reading…" for more than a minute | Close the app's window and start it again. It finishes any reading that was interrupted when it starts |
| A person's name shows somewhere it shouldn't | On the Sources screen, add the name (and any nickname) under **Names to hide**. It is hidden everywhere except that list, the speaker mapping and the correction editor |
| Drafting stops with an error | Click **Copy details** on the error, open Claude Code in the app folder, paste the Bug-fix prompt from the PRD and the copied details |
| "Web search isn't enabled for your Anthropic organisation" (external best-practice analysis) | Sign in to platform.claude.com, open your organisation's settings and enable web search (or ask your organisation admin). Then in the app: Settings → **Test web search** |
| A gap analysis report says "The search limit was reached" | The research used all the searches you allowed. Start a new external analysis, raise **Most searches** in the brief (up to 20; each search is billed by Anthropic) and run it again |
| Anything else | Open Claude Code in the app folder and paste the Bug-fix prompt from section 8 of [PRD_ProcessMapStudio.md](PRD_ProcessMapStudio.md), describing what you clicked and what you saw |

## For builders
- Specification: [PRD_ProcessMapStudio.md](PRD_ProcessMapStudio.md) · Rules for Claude Code: [CLAUDE.md](CLAUDE.md) · Progress: [PROJECT_STATE.md](PROJECT_STATE.md)
- Stack: FastAPI, SQLite, React + TypeScript, Claude API. Local only; binds to 127.0.0.1.
- Developer set-up (adds the check tools): `python3.12 scripts/setup.py --dev`. Developer mode with live reload: `python3.12 scripts/dev.py` (screens on http://127.0.0.1:5173).
- Run all checks: `./run_checks.sh` (all lines should say PASS). On Windows: `run_checks.bat` (needs Git for Windows).
- Live evaluation with the real Claude model (only when Eric asks; it uses his key and is billed to his Anthropic account): `cd backend && ../.venv/bin/pytest -m live -s`. It drafts the illustrative fixture twice, runs both gap analyses on the first draft and prints the evaluation against the PRD §6.3 P12 thresholds. Without a key it is skipped.
