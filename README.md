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

Both scripts write to a shared `sync_config.json` file inside your chosen shared saves folder, so either OS can see which games have already been linked on the other side.

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
4) Exit
```

- **List configured games** shows the sync status for both Windows and Linux side by side, read from the shared `sync_config.json`.
- **Remove a game's link** deletes the symlink on that OS only — the shared save data on the drive is never deleted, so you can always re-link later.
- Re-running **Add / update a game** with the same name is safe — it detects the existing symlink and simply re-confirms/re-points it.

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

---

## Notes & limitations

- This only works for games that store saves in a single, self-contained folder. Games using cloud saves tied to a platform account, or that write to the registry, aren't covered by this method.
- Both OSes should not have the game **running simultaneously** — always fully close the game before switching OS, to avoid the save file being written by two processes at once.
- This project only creates symlinks and moves files; it never touches the game's installation files or executables.



