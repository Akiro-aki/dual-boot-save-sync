#!/usr/bin/env python3
"""
Save Sync Setup - Windows side
---------------------------------
Moves a game's save folder onto your shared NTFS drive and replaces it
with a symlink, so Windows keeps writing to the same shared location
that Linux will also link to.

Works together with save_sync_linux.py via a shared config file
(sync_config.json) stored at the root of your shared GameSaves folder.

Run with a normal Python 3 install (python.org or Microsoft Store).
No third-party packages required.
"""

import ctypes
import json
import os
import shutil
from pathlib import Path

APP_NAME = "SaveSyncTool"
LOCAL_SETTINGS = Path(os.environ["APPDATA"]) / APP_NAME / "settings.json"
CONFIG_FILENAME = "sync_config.json"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


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
            "Enter the path to your shared GameSaves folder (e.g. D:\\GameSaves): "
        ).strip().strip('"')
        p = Path(entered)
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


def create_symlink(link_path: Path, target_path: Path) -> bool:
    """Create a directory symlink. Falls back to 'mklink /D' via cmd if needed."""
    try:
        if link_path.is_symlink():
            link_path.unlink()
        elif link_path.exists():
            raise FileExistsError(f"{link_path} exists and is not a symlink.")
        os.symlink(target_path, link_path, target_is_directory=True)
        return True
    except OSError as e:
        print(f"  ! os.symlink failed: {e}")
        print("  Falling back to 'mklink /D' via cmd ...")
        result = os.system(f'cmd /c mklink /D "{link_path}" "{target_path}"')
        return result == 0


def add_game(shared_root: Path, config: dict) -> None:
    print("\n--- Add / update a game (Windows side) ---")
    name = input("Game name (e.g. Balatro): ").strip()
    if not name:
        print("Name can't be empty.")
        return

    default_guess = Path(os.environ["APPDATA"]) / name
    src_input = input(f"Path to the game's save folder [{default_guess}]: ").strip().strip('"')
    src = Path(src_input) if src_input else default_guess

    shared_game_folder = shared_root / name
    shared_game_folder.mkdir(parents=True, exist_ok=True)

    shared_has_data = any(shared_game_folder.iterdir())
    src_is_symlink = src.is_symlink()
    src_has_data = (
        src.exists() and not src_is_symlink and any(src.iterdir())
        if src.exists() and not src_is_symlink else False
    )

    if src_is_symlink:
        print(f"  {src} is already a symlink; it will be re-pointed to {shared_game_folder}.")
    elif src_has_data and shared_has_data:
        print("  ! Both the source folder and the shared folder already contain data.")
        choice = input(
            "    Keep shared data and delete local copy (s), "
            "or overwrite shared with local copy (l)? [s/l]: "
        ).strip().lower()
        if choice == "l":
            shutil.rmtree(shared_game_folder)
            shutil.move(str(src), str(shared_game_folder))
        else:
            shutil.rmtree(src)
    elif src_has_data and not shared_has_data:
        print(f"  Moving existing save data to {shared_game_folder} ...")
        for item in src.iterdir():
            shutil.move(str(item), str(shared_game_folder / item.name))
        shutil.rmtree(src)
    elif src.exists() and not src_is_symlink:
        src.rmdir()  # empty leftover folder

    print(f"  Linking {src}  ->  {shared_game_folder}")
    if not create_symlink(src, shared_game_folder):
        print("  X Failed to create symlink. Re-run this script as Administrator,")
        print("    or enable Developer Mode (Settings > Privacy & Security > For Developers).")
        return
    print("  Symlink created successfully.")

    entry = config.setdefault("games", {}).setdefault(name, {})
    entry["shared_folder"] = name
    entry["windows"] = {"path": str(src), "linked": True}
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
    name = input("Game name to unlink (Windows side only): ").strip()
    entry = games.get(name)
    if not entry:
        print("Not found.")
        return
    win = entry.get("windows", {})
    path = win.get("path")
    if path and Path(path).is_symlink():
        Path(path).unlink()
        print(f"Removed Windows symlink at {path}. Shared save data is untouched.")
    win["linked"] = False
    save_shared_config(shared_root, config)


def main() -> None:
    print("=== Save Sync Setup - Windows ===")
    if not is_admin():
        print("! Not running as Administrator. Symlink creation may fail unless")
        print("  Developer Mode is enabled. Consider re-running this script as Admin.\n")

    shared_root = get_shared_root()
    config = load_shared_config(shared_root)

    while True:
        print("\n1) Add / update a game")
        print("2) List configured games")
        print("3) Remove a game's Windows link")
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
