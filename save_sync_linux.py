#!/usr/bin/env python3
"""
Save Sync Setup - Linux side
--------------------------------
Points a Steam Proton prefix (or Heroic Wine/Proton prefix) save folder
at your shared NTFS save hub, replacing Proton's freshly-generated save
folder with a symlink.

Works together with save_sync_windows.py via a shared config file
(sync_config.json) stored at the root of your shared GameSaves folder.

Also supports backing up the shared GameSaves folder to a private git
repo, and restoring it from there onto a fresh machine.

No third-party packages required (stdlib only; git backup/restore needs
the `git` command available on PATH).
"""

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

LOCAL_SETTINGS = Path.home() / ".config" / "save-sync" / "settings.json"
CONFIG_FILENAME = "sync_config.json"

COMMON_STEAM_ROOTS = [
    Path.home() / ".local/share/Steam/steamapps/compatdata",
    Path.home() / ".steam/steam/steamapps/compatdata",
    Path.home() / ".steam/root/steamapps/compatdata",
]


def load_local_settings() -> dict:
    if LOCAL_SETTINGS.exists():
        return json.loads(LOCAL_SETTINGS.read_text())
    return {}


def save_local_settings(data: dict) -> None:
    LOCAL_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SETTINGS.write_text(json.dumps(data, indent=2))


def get_shared_root() -> Path:
    settings = load_local_settings()
    root = settings.get("shared_root")
    if root and Path(root).exists():
        return Path(root)
    while True:
        entered = input(
            "Enter path to your shared GameSaves folder (e.g. /mnt/shared/GameSaves): "
        ).strip()
        p = Path(entered).expanduser()
        if not p.exists():
            create = input(f"{p} doesn't exist. Create it? (y/n): ").strip().lower()
            if create == "y":
                p.mkdir(parents=True, exist_ok=True)
            else:
                continue
        settings["shared_root"] = str(p)
        save_local_settings(settings)
        return p


def load_shared_config(shared_root: Path) -> dict:
    cfg_path = shared_root / CONFIG_FILENAME
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return {"games": {}}


def save_shared_config(shared_root: Path, config: dict) -> None:
    (shared_root / CONFIG_FILENAME).write_text(json.dumps(config, indent=2))


def find_steam_appid_prefix(appid: str):
    for root in COMMON_STEAM_ROOTS:
        candidate = root / appid
        if candidate.exists():
            return candidate
    return None


def build_prefix_appdata_path(prefix_root: Path, username: str, relative_appdata: str) -> Path:
    return prefix_root / "pfx" / "drive_c" / "users" / username / "AppData" / relative_appdata


def create_symlink(link_path: Path, target_path: Path) -> bool:
    try:
        if link_path.is_symlink():
            link_path.unlink()
        elif link_path.is_dir():
            if any(link_path.iterdir()):
                print(f"  ! {link_path} still has files in it after the merge step; aborting.")
                return False
            link_path.rmdir()
        elif link_path.exists():
            link_path.unlink()
        link_path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target_path, link_path, target_is_directory=True)
        return True
    except OSError as e:
        print(f"  X Failed to create symlink: {e}")
        return False


def add_game(shared_root: Path, config: dict) -> None:
    print("\n--- Add / update a game (Linux side) ---")
    name = input("Game name (must match the name used on Windows, e.g. Balatro): ").strip()
    if not name:
        print("Name can't be empty.")
        return

    print("Which launcher/runner is this game under?")
    print("  1) Steam (Proton)")
    print("  2) Heroic (Epic / GOG, Wine or Proton)")
    print("  3) Custom / manual prefix path")
    launcher = input("> ").strip()

    username = "steamuser"
    relative_appdata = f"Roaming/{name}"

    if launcher == "1":
        appid = input("Steam AppID (find it on SteamDB or the Steam store URL): ").strip()
        prefix_root = find_steam_appid_prefix(appid)
        if not prefix_root:
            manual = input(
                "Couldn't auto-find that AppID. Enter the full compatdata/<appid> path manually: "
            ).strip()
            prefix_root = Path(manual).expanduser()
        rel = input(f"AppData subpath relative to .../AppData [{relative_appdata}]: ").strip()
        if rel:
            relative_appdata = rel
        prefix_appdata = build_prefix_appdata_path(prefix_root, username, relative_appdata)

    elif launcher == "2":
        prefix_path = input(
            "Full path to this game's Heroic prefix (the folder containing 'pfx' or 'drive_c'): "
        ).strip()
        prefix_root = Path(prefix_path).expanduser()
        uname = input(f"Wine username in this prefix [{username}]: ").strip()
        if uname:
            username = uname
        rel = input(f"AppData subpath relative to .../AppData [{relative_appdata}]: ").strip()
        if rel:
            relative_appdata = rel
        if (prefix_root / "pfx").exists():
            prefix_appdata = build_prefix_appdata_path(prefix_root, username, relative_appdata)
        else:
            prefix_appdata = prefix_root / "drive_c" / "users" / username / "AppData" / relative_appdata

    else:
        manual = input("Full path to the exact save folder Proton/Wine created: ").strip()
        prefix_appdata = Path(manual).expanduser()

    shared_game_folder = shared_root / name
    shared_game_folder.mkdir(parents=True, exist_ok=True)

    shared_has_data = any(shared_game_folder.iterdir())
    target_exists = prefix_appdata.exists() and not prefix_appdata.is_symlink()
    target_has_data = target_exists and any(prefix_appdata.iterdir())

    if target_has_data and shared_has_data:
        print("  ! Both the prefix folder and the shared folder already contain data.")
        choice = input(
            "    Keep shared data and delete local prefix copy (s), "
            "or overwrite shared with local copy (l)? [s/l]: "
        ).strip().lower()
        if choice == "l":
            shutil.rmtree(shared_game_folder)
            shutil.move(str(prefix_appdata), str(shared_game_folder))
        else:
            shutil.rmtree(prefix_appdata)
    elif target_has_data and not shared_has_data:
        print(f"  Moving existing prefix save data to {shared_game_folder} ...")
        for item in prefix_appdata.iterdir():
            shutil.move(str(item), str(shared_game_folder / item.name))
        shutil.rmtree(prefix_appdata)
    elif target_exists:
        prefix_appdata.rmdir()

    print(f"  Linking {prefix_appdata}  ->  {shared_game_folder}")
    if not create_symlink(prefix_appdata, shared_game_folder):
        return
    print("  Symlink created successfully.")

    entry = config.setdefault("games", {}).setdefault(name, {})
    entry["shared_folder"] = name
    entry["linux"] = {"path": str(prefix_appdata), "linked": True}
    save_shared_config(shared_root, config)
    print(f"  '{name}' saved to shared config.\n")


def list_games(config: dict) -> None:
    games = config.get("games", {})
    if not games:
        print("\nNo games configured yet.\n")
        return
    print("\n--- Configured games ---")
    for name, entry in games.items():
        win = entry.get("windows", {})
        lin = entry.get("linux", {})
        print(f"* {name}")
        print(f"    Windows: {'linked -> ' + win['path'] if win.get('linked') else 'not set up'}")
        print(f"    Linux:   {'linked -> ' + lin['path'] if lin.get('linked') else 'not set up'}")
    print()


def remove_game(shared_root: Path, config: dict) -> None:
    games = config.get("games", {})
    if not games:
        print("No games to remove.")
        return
    name = input("Game name to unlink (Linux side only): ").strip()
    entry = games.get(name)
    if not entry:
        print("Not found.")
        return
    lin = entry.get("linux", {})
    path = lin.get("path")
    if path and Path(path).is_symlink():
        Path(path).unlink()
        print(f"Removed Linux symlink at {path}. Shared save data is untouched.")
    lin["linked"] = False
    save_shared_config(shared_root, config)


# --- Git backup / restore -------------------------------------------------
#
# The shared GameSaves folder already holds the real save files for every
# linked game (that's the whole point of the symlink setup), so it doubles
# as a perfectly good git working directory. Backing up just means
# committing + pushing that folder to a private remote; restoring on a
# fresh machine means cloning it back down, after which the normal
# "Add / update a game" flow re-creates the local symlinks.
#
# The remote URL is stored in the shared sync_config.json so either OS
# only has to enter it once. This script does NOT handle git
# authentication — set up an SSH key or credential manager for the
# remote yourself before using these options.

def check_git_available() -> bool:
    return shutil.which("git") is not None


def run_git(args, cwd, check=True):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  X git {' '.join(args)} failed:")
        print("    " + result.stderr.strip().replace("\n", "\n    "))
    return result


def get_git_remote(shared_root: Path, config: dict) -> str:
    remote = config.get("git_remote")
    if remote:
        return remote
    print(
        "\n  No backup repo configured yet. Enter the URL of a private git repo\n"
        "  to use for save backups (e.g. git@github.com:you/game-saves-backup.git).\n"
        "  Make sure you already have push/pull access set up (SSH key or\n"
        "  credential manager) — this script won't handle authentication for you."
    )
    remote = input("  Repo URL: ").strip()
    config["git_remote"] = remote
    save_shared_config(shared_root, config)
    return remote


def ensure_gitignore(shared_root: Path) -> None:
    gitignore = shared_root / ".gitignore"
    wanted = ["Thumbs.db", "desktop.ini", ".DS_Store", ".directory", ".Trash-*"]
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    merged = existing + [w for w in wanted if w not in existing]
    gitignore.write_text("\n".join(merged) + "\n")


def ensure_git_repo(shared_root: Path, remote_url: str) -> bool:
    if not (shared_root / ".git").exists():
        print(f"  Initializing git repo in {shared_root} ...")
        if run_git(["init"], shared_root).returncode != 0:
            return False
        # NTFS doesn't track unix permission bits reliably; ignore mode-only diffs.
        run_git(["config", "core.fileMode", "false"], shared_root, check=False)
        run_git(["remote", "add", "origin", remote_url], shared_root, check=False)
    else:
        current = run_git(["remote", "get-url", "origin"], shared_root, check=False)
        if current.returncode != 0:
            run_git(["remote", "add", "origin", remote_url], shared_root, check=False)
        elif current.stdout.strip() != remote_url:
            run_git(["remote", "set-url", "origin", remote_url], shared_root, check=False)
    return True


def git_backup(shared_root: Path, config: dict) -> None:
    print("\n--- Backup saves to git repo ---")
    if not check_git_available():
        print("  X git isn't installed or isn't on PATH. Install it (e.g. `sudo apt install git`")
        print("    or `sudo pacman -S git`) and try again.")
        return
    remote_url = get_git_remote(shared_root, config)
    if not ensure_git_repo(shared_root, remote_url):
        return
    ensure_gitignore(shared_root)

    run_git(["add", "-A"], shared_root, check=False)
    status = run_git(["status", "--porcelain"], shared_root, check=False)
    if not status.stdout.strip():
        print("  Nothing new to back up — shared saves already match the last commit.")
        return

    msg = f"Save backup {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (linux)"
    if run_git(["commit", "-m", msg], shared_root).returncode != 0:
        return
    print("  Pushing to remote ...")
    push = run_git(["push", "-u", "origin", "HEAD"], shared_root, check=False)
    if push.returncode != 0:
        print("  X Push failed (see above). The backup was committed locally, so it's")
        print("    safe to retry once the issue (auth, network, etc.) is fixed.")
        return
    print("  Backup pushed successfully.\n")


def _adopt_merge_restore(shared_root: Path, remote_url: str) -> None:
    """Turn shared_root into a git repo in place and merge the remote's
    history into the local files that are already there, instead of
    replacing them."""
    print(f"  Initializing git repo in {shared_root} and merging remote history ...")
    if run_git(["init"], shared_root).returncode != 0:
        return
    run_git(["config", "core.fileMode", "false"], shared_root, check=False)
    run_git(["remote", "add", "origin", remote_url], shared_root, check=False)
    if run_git(["fetch", "origin"], shared_root).returncode != 0:
        return
    # Commit the existing local files first so the merge has something on
    # this side to merge into (an empty repo has no commit to merge onto).
    ensure_gitignore(shared_root)
    run_git(["add", "-A"], shared_root, check=False)
    if run_git(["status", "--porcelain"], shared_root, check=False).stdout.strip():
        run_git(["commit", "-m", "Existing local saves before restore"], shared_root, check=False)
    merge = run_git(
        ["merge", "--allow-unrelated-histories", "-m", "Merge remote save backup", "FETCH_HEAD"],
        shared_root,
        check=False,
    )
    if merge.returncode != 0:
        print("  ! Merge finished with conflicts. Inspect them with `git status` inside")
        print(f"    {shared_root}, resolve manually, then `git add` + `git commit` to finish.")
    else:
        print("  Remote history merged with your existing local saves.")


def _override_clone_restore(shared_root: Path, remote_url: str) -> bool:
    """Move the current contents of shared_root aside, then clone the
    remote in fresh."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = shared_root.parent / f"{shared_root.name}_local_backup_{timestamp}"
    print(f"  Moving existing local folder to {backup_path} ...")
    shutil.move(str(shared_root), str(backup_path))
    shared_root.mkdir(parents=True, exist_ok=True)
    print(f"  Cloning backup repo into {shared_root} ...")
    result = subprocess.run(
        ["git", "clone", remote_url, str(shared_root)], capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  X Clone failed:")
        print("    " + result.stderr.strip().replace("\n", "\n    "))
        print(f"    Your original files are safe at {backup_path}.")
        return False
    run_git(["config", "core.fileMode", "false"], shared_root, check=False)
    print("  Shared saves restored from remote.")
    print(f"  Your previous local files are kept at {backup_path} in case you need them.")
    return True


def git_restore(shared_root: Path, config: dict) -> None:
    print("\n--- Restore saves from git repo ---")
    if not check_git_available():
        print("  X git isn't installed or isn't on PATH. Install it and try again.")
        return
    remote_url = get_git_remote(shared_root, config)

    if (shared_root / ".git").exists():
        print("  Pulling latest changes ...")
        if run_git(["pull", "--ff-only", "origin"], shared_root).returncode != 0:
            print("  X Pull failed. If local changes conflict with the remote, resolve")
            print(f"    them manually with git inside {shared_root}, then retry.")
        else:
            print("  Shared saves updated from remote.")
    elif any(shared_root.iterdir()):
        print(f"  ! {shared_root} already has files in it but isn't a git repo yet.")
        print("  a) Adopt  — keep the local files and merge the remote's history into them")
        print("              (conflicts, if any, are left for you to resolve with git)")
        print("  o) Override — move the local files aside to a backup folder, then clone fresh")
        print("  c) Cancel and do nothing")
        choice = input("  Choice [a/o/c]: ").strip().lower()
        if choice == "a":
            _adopt_merge_restore(shared_root, remote_url)
        elif choice == "o":
            if not _override_clone_restore(shared_root, remote_url):
                return
        else:
            print("  Cancelled — nothing was changed.")
            return
    else:
        print(f"  Cloning backup repo into {shared_root} ...")
        result = subprocess.run(
            ["git", "clone", remote_url, str(shared_root)], capture_output=True, text=True
        )
        if result.returncode != 0:
            print("  X Clone failed:")
            print("    " + result.stderr.strip().replace("\n", "\n    "))
            return
        run_git(["config", "core.fileMode", "false"], shared_root, check=False)
        print("  Shared saves restored from remote.")

    print(
        "\n  Now run 'Add / update a game' for each game you want linked on this OS —\n"
        "  the shared save data is already in place, this just re-creates the local symlink.\n"
    )


def main() -> None:
    print("=== Save Sync Setup - Linux ===")
    shared_root = get_shared_root()
    config = load_shared_config(shared_root)

    while True:
        print("\n1) Add / update a game")
        print("2) List configured games")
        print("3) Remove a game's Linux link")
        print("4) Backup saves to git repo")
        print("5) Restore saves from git repo")
        print("6) Exit")
        choice = input("> ").strip()
        if choice == "1":
            add_game(shared_root, config)
        elif choice == "2":
            list_games(config)
        elif choice == "3":
            remove_game(shared_root, config)
        elif choice == "4":
            git_backup(shared_root, config)
        elif choice == "5":
            git_restore(shared_root, config)
        elif choice == "6":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
