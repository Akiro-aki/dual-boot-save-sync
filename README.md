# Save Sync Setup

Automatically sync PC game saves between **Windows** and **Linux** in a dual-boot setup, using symlinks pointed at a shared NTFS drive. No cloud services, no manual copying — both operating systems write to and read from the exact same save files.

Works with **Steam (Proton)** and **Heroic Games Launcher** (Epic/GOG, Wine or Proton) on the Linux side.

---

## How it works

Normally, Windows and Linux each keep their own separate copy of a game's save data:

- Windows: `C:\Users\<You>\AppData\Roaming\<Game>`
- Linux (via Proton/Wine): `.../compatdata/<AppID>/pfx/drive_c/users/steamuser/AppData/Roaming/<Game>`

These scripts move the *real* save data onto a shared NTFS partition that both operating systems can read and write to, then replace each OS's original save folder with a **symlink** pointing at that shared location. The game itself doesn't know anything changed — it just sees a normal folder. In reality, both OSes are reading/writing the same physical files.

Result: play on Linux, reboot into Windows, and your progress is already there. No sync delay, no conflicts, no cloud save quirks.

```
Windows AppData\Roaming\Game ──────┐
                                   ├──►  D:\GameSaves\Game  (real files, on shared NTFS drive)
Linux prefix AppData\Roaming\Game ─┘
```

---

## Requirements

- A dual-boot Windows + Linux setup with a **shared NTFS (or exFAT) partition/drive** accessible from both operating systems
- **Python 3** installed on both OSes (no third-party packages needed — standard library only)
  - Windows: [python.org](https://www.python.org/downloads/) or Microsoft Store
  - Linux: usually pre-installed; if not, `sudo pacman -S python` (Arch) / `sudo apt install python3` (Debian/Ubuntu)
- **Windows Fast Startup disabled** (critical — see below)
- Administrator access on Windows (for the first symlink creation)

### ⚠️ Disable Windows Fast Startup first

If Fast Startup is left on, Windows hibernates the shared drive on shutdown instead of releasing it cleanly. When you then boot Linux, the NTFS partition mounts **read-only** to prevent corruption — and your saves silently stop working.

To disable it:
1. Control Panel → Power Options → *Choose what the power buttons do*
2. Click *Change settings that are currently unavailable*
3. Uncheck **Turn on fast startup**
4. Save changes

---

## Files

| File | Platform | Purpose |
|---|---|---|
| `save_sync_windows.py` | Windows | Moves a game's save folder to the shared drive and symlinks it back |
| `save_sync_linux.py` | Linux | Points a Steam/Heroic prefix's save folder at the same shared drive via symlink |

Both scripts write to a shared `sync_config.json` file inside your chosen shared saves folder, so either OS can see which games have already been linked on the other side. Both scripts also support backing that shared folder up to (and restoring it from) a private git repo — see [Git backup & restore](#git-backup--restore) below.

---

## Setup

### 1. Windows side

1. Download `save_sync_windows.py` to your Windows machine.
2. Right-click your terminal (Command Prompt / PowerShell / Windows Terminal) and choose **Run as Administrator**.
3. Run the script:
   ```
   python save_sync_windows.py
   ```
4. First run: enter the path to a folder on your shared drive where saves will live, e.g. `D:\GameSaves`. This is cached for future runs.
5. Choose **1) Add / update a game**.
6. Enter:
   - **Game name** — pick a clear, consistent name (e.g. `Balatro`). You'll use this exact name again on the Linux side.
   - **Save folder path** — defaults to `%APPDATA%\<GameName>`; edit if the game saves somewhere else (check `%LOCALAPPDATA%`, `Documents\My Games`, etc.)
7. The script moves your existing save data to the shared drive and creates a symlink in its place.
8. Repeat step 5–7 for each game you want synced.

If symlink creation fails, either:
- Confirm you're running the terminal as Administrator, **or**
- Enable Developer Mode: *Settings → Privacy & Security → For Developers → Developer Mode*

### 2. Linux side

1. Download `save_sync_linux.py` to your Linux machine (same machine, dual-boot).
2. Make sure your shared NTFS drive is mounted (check `lsblk` or your file manager) and that Fast Startup was disabled on the Windows side.
3. **Launch the game at least once through Steam or Heroic**, then fully close it. This forces Proton/Wine to generate its prefix and default save folders — the script needs that folder to exist so it can find and replace it.
4. Run the script:
   ```bash
   python3 save_sync_linux.py
   ```
5. First run: enter the same type of shared folder path from the Windows side, using its Linux mount point, e.g. `/mnt/shared/GameSaves` or `/run/media/<you>/SharedDrive/GameSaves`.
6. Choose **1) Add / update a game**.
7. Enter the **same game name** you used on Windows — this is how the script matches the two sides together.
8. Choose your launcher:
   - **Steam** — enter the game's **AppID** (find it on [SteamDB](https://steamdb.info/) or in the Steam store URL, e.g. `steamcommunity.com/app/2379780`). The script tries to auto-locate the Proton prefix; if it can't, paste the `compatdata/<AppID>` path manually.
   - **Heroic** — paste the full prefix path from Heroic's game settings (*right-click game → Settings → Wine/Proton tab*, look for "Wine Prefix"). Default location is usually `~/Games/Heroic/Prefixes/<GameName>`.
   - **Custom** — paste the exact save folder path if neither of the above fits.
9. If prompted, confirm or correct the **AppData subpath** (e.g. `Roaming/Balatro` or `Local/Balatro` — check inside the prefix if unsure which one the game actually uses).
10. If both the shared folder and the local prefix already contain save data (conflict), the script will ask which to keep — choose **s** to keep the shared copy (your real progress) unless you have a reason to do otherwise.
11. The script deletes the empty/duplicate local folder and creates a symlink to the shared drive.
12. Repeat steps 6–11 for each game.

### 3. Verify it worked

- Launch the game on either OS and confirm it loads existing progress.
- Make a small change (start a run, save manually), quit, and check the file timestamps inside your shared `GameSaves/<Game>` folder updated.
- Boot the other OS, launch the game, and confirm the change carried over.

---

## Managing games later

Both scripts share the same menu:

```
1) Add / update a game
2) List configured games
3) Remove a game's link (that OS only)
4) Backup saves to git repo
5) Restore saves from git repo
6) Exit
```

- **List configured games** shows the sync status for both Windows and Linux side by side, read from the shared `sync_config.json`.
- **Remove a game's link** deletes the symlink on that OS only — the shared save data on the drive is never deleted, so you can always re-link later.
- Re-running **Add / update a game** with the same name is safe — it detects the existing symlink and simply re-confirms/re-points it.

---

## Git backup & restore

Your shared drive is the single copy of every save — great for keeping Windows and Linux in sync, but it's still one drive. Backup/restore options **4** and **5** push that shared folder to a private git repo (GitHub, GitLab, a self-hosted server, etc.) so you have an off-drive copy, and can pull it down again onto a reinstalled OS or a new machine.

**How it works:** the shared saves folder itself becomes the git working directory — there's no separate copy step. Backup stages, commits, and pushes whatever changed since the last backup; restore clones or pulls the repo straight into that folder. Either OS can run either option; the repo URL is saved to `sync_config.json` the first time you enter it, so you won't be asked again on the other side.

### Requirements

- `git` installed and on your `PATH` on whichever OS you're backing up/restoring from
  - Windows: [git-scm.com](https://git-scm.com/download/win) or `winget install Git.Git`
  - Linux: `sudo apt install git` (Debian/Ubuntu) or `sudo pacman -S git` (Arch)
- A **private** repo already created on whatever host you use (e.g. a new private repo on GitHub), with push/pull access already working from the command line *before* you run the script's backup option. The scripts don't handle authentication — they just run `git` and show you whatever it reports.

### Setting up GitHub authentication (HTTPS)

If your repo URL looks like `https://github.com/you/your-repo.git`, GitHub will reject your normal account password — it only accepts a **Personal Access Token** or SSH key for Git operations over HTTPS, a change GitHub made in 2021. You'll see an error like:

```
remote: Invalid username or token. Password authentication is not supported for Git operations.
```

To fix it:

1. Go to [github.com/settings/tokens/new](https://github.com/settings/tokens/new) (or: profile picture → Settings → Developer settings, near the bottom of the sidebar → Personal access tokens → Tokens (classic) → Generate new token (classic)).
2. Give it a name (e.g. `save-sync`), set an expiration you're comfortable with, and check the top-level **`repo`** scope — that one checkbox covers everything needed for a private repo; leave the rest unchecked.
3. Click **Generate token** and copy it immediately (it starts with `ghp_...`) — GitHub only shows it once.
4. Run the push again (either via the script's backup option, or `git push -u origin HEAD` directly inside the shared folder). When prompted for a username, enter your GitHub username; when prompted for a password, paste the token instead.
5. So you're not prompted every time, run `git config --global credential.helper store` once and push again — the token gets cached locally after that. (On Windows, Git for Windows usually ships with Git Credential Manager already handling this via a popup, so you may not need the `credential.helper` step there.)

You'll need to do this once per OS — credentials aren't shared between Windows and Linux even though they point at the same repo.

**Prefer SSH instead?** Generate a key with `ssh-keygen -t ed25519`, add the public key under GitHub → Settings → SSH and GPG keys, then use an SSH-style remote (`git@github.com:you/your-repo.git`) instead of HTTPS. No token needed, and it won't expire the way a token can.

### Backing up

Choose **4) Backup saves to git repo**. First run:
- If no repo URL is saved yet, you'll be asked for one (e.g. `git@github.com:you/game-saves-backup.git` or `https://github.com/you/game-saves-backup.git`).
- The shared folder is turned into a git repo in place (`git init`, with `core.fileMode` disabled since NTFS doesn't track Unix permission bits reliably) and the remote is added.

Every run after that just stages, commits, and pushes whatever changed. If nothing changed since the last backup, the script says so and does nothing — note that this check only looks at the working tree, so if a previous push failed after the commit already succeeded (e.g. an auth error), the script won't retry that push on its own; push manually with `git push -u origin HEAD` to clear it, after which future backups resume normally.

### Restoring

Choose **5) Restore saves from git repo** — typically after a fresh Windows/Linux install, or when setting up a new machine:
- If the shared folder is already a git repo (i.e. you've backed up from here before), this pulls the latest changes.
- If the shared folder is empty, this clones the repo into it.
- If the shared folder already has files in it but isn't a git repo yet, you're offered three choices:
  - **Adopt** — keeps the local files where they are and merges the remote's history into them (`git init` in place, then a merge with unrelated histories allowed). If a game exists on both sides with conflicting file changes, git leaves that game's files conflicted for you to resolve by hand with `git status` / `git add` / `git commit`; anything that doesn't conflict merges automatically.
  - **Override** — moves the current local folder aside to a timestamped `..._local_backup_<date>` folder next to it, then clones the remote in fresh. Nothing is deleted — your previous files are just relocated, so you can pull anything out of the backup folder afterward if the remote turns out to be missing something.
  - **Cancel** — does nothing, so you can back things up manually first if you'd rather.

After restoring, saves exist on the shared drive again, but the local symlinks on this OS don't exist yet — run **1) Add / update a game** for each game you want linked, same as initial setup.

### Notes

- This is a plain git repo, so very large or frequently-changing binary save files will bloat it over time; if that becomes a problem, look into [Git LFS](https://git-lfs.com/) for the games affected.
- The repo only ever contains save data, never `sync_config.json`'s per-machine settings (those live outside the shared folder) or the game installations themselves.
- The default branch the script creates is whatever your local `git init` defaults to (often `master`); it doesn't need to match any particular name, since both `backup` and `restore` just track whatever `origin`'s current branch is.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Saves don't carry over between OSes | Fast Startup is still enabled, or the shared drive isn't actually the same physical partition on both sides |
| Windows: symlink creation fails | Not running as Administrator, and Developer Mode isn't enabled |
| Linux: `PermissionError` creating symlink | The shared drive is mounted read-only — check Fast Startup, or check your fstab mount options |
| Game doesn't see old saves after linking | Wrong AppData subpath (`Roaming` vs `Local`) — check inside the prefix for the actual save folder name |
| Heroic prefix path not found | Prefix hasn't been generated yet — launch the game once through Heroic first, or the path shown in Heroic's settings uses a different layout than expected (some don't have a `pfx` subfolder) |
| `sync_config.json` shows a game as "not set up" on one side | You haven't run **Add / update a game** for that OS yet, or used a different game name than the other side |
| Backup fails with `fatal: protocol '...' is not supported` | The remote URL is malformed (often an SSH prefix and an `https://` URL pasted together). Run `git remote -v` in the shared folder to see the actual URL, fix it with `git remote set-url origin <correct-url>`, and update `"git_remote"` in `sync_config.json` to match |
| Push fails with `Password authentication is not supported for Git operations` | You're using an HTTPS remote and GitHub rejected your account password — see [Setting up GitHub authentication](#setting-up-github-authentication-https) above; you need a Personal Access Token (or switch to an SSH remote) |
| Backup says "Nothing new to back up" right after a failed push | The commit succeeded even though the push didn't, so there's nothing new left to commit. Push manually with `git push -u origin HEAD` inside the shared folder once auth is fixed |
| Restore says the shared folder "already has files but isn't a git repo" | It has save data from before you started using backups; choose **Adopt** to merge the remote in with it, **Override** to back the local copy up and clone fresh, or **Cancel** to handle it manually |

---

## Notes & limitations

- This only works for games that store saves in a single, self-contained folder. Games using cloud saves tied to a platform account, or that write to the registry, aren't covered by this method.
- Both OSes should not have the game **running simultaneously** — always fully close the game before switching OS, to avoid the save file being written by two processes at once.
- This project only creates symlinks and moves files; it never touches the game's installation files or executables.
