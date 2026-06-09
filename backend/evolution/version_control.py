import os
import json
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
from backend.core.config import settings


class VersionControl:
    def __init__(self, strategy_dir: Optional[str] = None):
        self.strategy_dir = strategy_dir or settings.STRATEGY_DIR
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.strategy_dir):
            os.makedirs(self.strategy_dir, exist_ok=True)

    def get_latest_version(self) -> Optional[str]:
        versions = self.list_versions()
        if not versions:
            return None
        return versions[-1]

    def _version_key(self, version: str) -> tuple:
        parts = version.lstrip("v").split(".")
        key = []
        for part in parts:
            try:
                key.append(int(part))
            except ValueError:
                key.append(0)
        return tuple(key)

    def list_versions(self) -> List[str]:
        versions = []
        if not os.path.exists(self.strategy_dir):
            return versions
        for item in os.listdir(self.strategy_dir):
            item_path = os.path.join(self.strategy_dir, item)
            if os.path.isdir(item_path) and item.startswith("v"):
                versions.append(item)
        return sorted(versions, key=self._version_key)

    def get_version_path(self, version: str) -> str:
        return os.path.join(self.strategy_dir, version)

    def version_exists(self, version: str) -> bool:
        return os.path.exists(self.get_version_path(version))

    def create_version(self, version: str, parent_version: Optional[str] = None, 
                  prompts: Optional[Dict[str, str]] = None,
                  changes: Optional[List[str]] = None,
                  metadata_extra: Optional[Dict[str, Any]] = None,
                  update_latest: bool = True) -> bool:
        if self.version_exists(version):
            return False

        version_path = self.get_version_path(version)
        os.makedirs(version_path, exist_ok=True)

        if parent_version and self.version_exists(parent_version):
            parent_path = self.get_version_path(parent_version)
            for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
                src_file = os.path.join(parent_path, f"{role}.txt")
                dst_file = os.path.join(version_path, f"{role}.txt")
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dst_file)

        if prompts:
            for role, prompt in prompts.items():
                prompt_file = os.path.join(version_path, f"{role}.txt")
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(prompt)

        metadata = {
            "version": version,
            "parent": parent_version,
            "created_at": datetime.now().isoformat(),
            "changes": changes or [],
            "test_games": 0,
            "win_rate": {
                "werewolves": 0.5,
                "villagers": 0.5
            }
        }
        if metadata_extra:
            metadata.update(metadata_extra)

        metadata_file = os.path.join(version_path, "metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        stats_file = os.path.join(version_path, "stats.json")
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump({"games": [], "metrics": {}}, f, ensure_ascii=False, indent=2)

        if update_latest:
            self._update_latest_pointer(version)
        return True

    def promote_version(self, version: str) -> bool:
        if not self.version_exists(version):
            return False
        self._update_latest_pointer(version)
        return True

    def get_prompt(self, version: str, role: str) -> Optional[str]:
        version_path = self.get_version_path(version)
        prompt_file = os.path.join(version_path, f"{role}.txt")
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def set_prompt(self, version: str, role: str, prompt: str) -> bool:
        if not self.version_exists(version):
            return False
        version_path = self.get_version_path(version)
        prompt_file = os.path.join(version_path, f"{role}.txt")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)
        return True

    def get_metadata(self, version: str) -> Optional[Dict[str, Any]]:
        if not self.version_exists(version):
            return None
        version_path = self.get_version_path(version)
        metadata_file = os.path.join(version_path, "metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def update_metadata(self, version: str, metadata: Dict[str, Any]) -> bool:
        if not self.version_exists(version):
            return False
        version_path = self.get_version_path(version)
        metadata_file = os.path.join(version_path, "metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return True

    def get_stats(self, version: str) -> Optional[Dict[str, Any]]:
        if not self.version_exists(version):
            return None
        version_path = self.get_version_path(version)
        stats_file = os.path.join(version_path, "stats.json")
        if os.path.exists(stats_file):
            with open(stats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def add_game_result(self, version: str, game_result: Dict[str, Any]) -> bool:
        if not self.version_exists(version):
            return False
        stats = self.get_stats(version) or {"games": [], "metrics": {}}
        stats["games"].append(game_result)
        
        total_games = len(stats["games"])
        werewolf_wins = sum(1 for g in stats["games"] if g.get("winner") == "werewolves")
        villager_wins = sum(1 for g in stats["games"] if g.get("winner") == "villagers")
        
        stats["metrics"] = {
            "total_games": total_games,
            "werewolf_win_rate": werewolf_wins / total_games if total_games > 0 else 0,
            "villager_win_rate": villager_wins / total_games if total_games > 0 else 0,
        }
        
        version_path = self.get_version_path(version)
        stats_file = os.path.join(version_path, "stats.json")
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        metadata = self.get_metadata(version)
        if metadata:
            metadata["test_games"] = total_games
            metadata["win_rate"] = {
                "werewolves": stats["metrics"]["werewolf_win_rate"],
                "villagers": stats["metrics"]["villager_win_rate"]
            }
            self.update_metadata(version, metadata)
        
        return True

    def _update_latest_pointer(self, version: str):
        latest_file = os.path.join(self.strategy_dir, "latest.json")
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump({"latest_version": version, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

    def get_latest_pointer(self) -> Optional[str]:
        latest_file = os.path.join(self.strategy_dir, "latest.json")
        if os.path.exists(latest_file):
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("latest_version")
        return None

    def get_next_version(self, base_version: Optional[str] = None) -> str:
        if not base_version:
            base_version = self.get_latest_version() or "v0.0.0"
        
        parts = base_version[1:].split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        
        patch += 1
        return f"v{major}.{minor}.{patch}"

    def rollback(self, version: str) -> bool:
        if not self.version_exists(version):
            return False
        self._update_latest_pointer(version)
        return True

    def delete_version(self, version: str) -> bool:
        if not self.version_exists(version):
            return False
        version_path = self.get_version_path(version)
        shutil.rmtree(version_path)
        
        latest = self.get_latest_pointer()
        if latest == version:
            versions = self.list_versions()
            if versions:
                self._update_latest_pointer(versions[-1])
            else:
                latest_file = os.path.join(self.strategy_dir, "latest.json")
                if os.path.exists(latest_file):
                    os.remove(latest_file)
        return True
