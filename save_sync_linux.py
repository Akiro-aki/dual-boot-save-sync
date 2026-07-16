#!/usr/bin/env python3
"""
Save Sync Setup - Linux side
--------------------------------
Points a Steam Proton prefix (or Heroic Wine/Proton prefix) save folder
at your shared NTFS save hub, replacing Proton's freshly-generated save
folder with a symlink.

Works together with save_sync_windows.py via a shared config file
(sync_config.json) stored at the root of your shared GameSaves folder.

No third-party packages required (stdlib only).
"""

import json
import os
import shutil
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


def main() -> None:
    print("=== Save Sync Setup - Linux ===")
    shared_root = get_shared_root()
    config = load_shared_config(shared_root)

    while True:
        print("\n1) Add / update a game")
        print("2) List configured games")
        print("3) Remove a game's Linux link")
        print("4) Exit")
        choice = input("> ").strip()
        if choice == "1":
            add_game(shared_root, config)
        elif choice == "2":
            list_games(config)
        elif choice == "3":
            remove_game(shared_root, config)
        elif choice == "4":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
