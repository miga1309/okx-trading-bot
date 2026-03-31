from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class UpdateError(RuntimeError):
    pass


@dataclass
class FileMapping:
    source: Path
    target: Path
    target_rel: str


@dataclass
class LoadedManifest:
    manifest_path: Path
    payload_dir: Path
    manifest: dict[str, Any]
    files: list[FileMapping]
    version: str
    restart_app: bool
    description: str


class UpdateManager:
    def __init__(self, project_root: Path, runtime_dir: Path, logger: logging.Logger | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.runtime_dir = Path(runtime_dir).resolve()
        self.updates_root = self.project_root / "updates"
        self.backups_root = self.runtime_dir / "remote_backups"
        self.log = logger or logging.getLogger("remote_control.update")
        self.allowed_components = {
            "scanner",
            "stop_engine",
            "gui",
            "telegram_module",
            "analysis_export",
            "trade_engine",
            "position_engine",
            "balance_engine",
            "health_monitor",
            "remote_control",
        }

    def load_component_manifest(self, component: str) -> LoadedManifest:
        component = str(component or "").strip()
        if not component:
            raise UpdateError("component name is required")
        if component not in self.allowed_components:
            raise UpdateError(f"unsupported component: {component}")
        base = self.updates_root / "components" / component
        manifest_path = base / "manifest.json"
        if not manifest_path.exists():
            raise UpdateError(f"manifest not found: {manifest_path}")
        return self._load_manifest(manifest_path, default_description=f"component:{component}")

    def load_full_manifest(self) -> LoadedManifest:
        base = self.updates_root / "full"
        direct = base / "manifest.json"
        if direct.exists():
            return self._load_manifest(direct, default_description="full")
        candidates = sorted(
            [p for p in base.glob("*/manifest.json") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise UpdateError(f"full update manifest not found under {base}")
        return self._load_manifest(candidates[0], default_description=f"full:{candidates[0].parent.name}")

    def _load_manifest(self, manifest_path: Path, *, default_description: str) -> LoadedManifest:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise UpdateError(f"failed to read manifest {manifest_path.name}: {exc}") from exc
        payload_dir = manifest_path.parent / str(manifest.get("payload_dir") or "payload")
        if not payload_dir.exists():
            payload_dir = manifest_path.parent
        files_raw = manifest.get("files")
        if not isinstance(files_raw, list) or not files_raw:
            raise UpdateError("manifest files list is empty")
        files: list[FileMapping] = []
        for item in files_raw:
            if isinstance(item, str):
                target_rel = item.replace("\\", "/").strip("/")
                source_rel = target_rel
            elif isinstance(item, dict):
                target_rel = str(item.get("target") or "").replace("\\", "/").strip("/")
                source_rel = str(item.get("source") or target_rel).replace("\\", "/").strip("/")
            else:
                raise UpdateError("manifest file entry must be string or object")
            if not target_rel:
                raise UpdateError("manifest contains empty target path")
            source = (payload_dir / source_rel).resolve()
            target = (self.project_root / target_rel).resolve()
            if not str(source).startswith(str(payload_dir.resolve())):
                raise UpdateError(f"invalid source path outside payload: {source_rel}")
            if not str(target).startswith(str(self.project_root)):
                raise UpdateError(f"invalid target path outside project: {target_rel}")
            if not source.exists() or not source.is_file():
                raise UpdateError(f"payload file missing: {source}")
            files.append(FileMapping(source=source, target=target, target_rel=target_rel))
        version = str(manifest.get("version") or manifest_path.parent.name or "unknown")
        restart_app = bool(manifest.get("restart_app", False))
        description = str(manifest.get("description") or default_description)
        return LoadedManifest(
            manifest_path=manifest_path,
            payload_dir=payload_dir,
            manifest=manifest,
            files=files,
            version=version,
            restart_app=restart_app,
            description=description,
        )

    def create_backup(self, loaded: LoadedManifest, *, stage: str) -> Path:
        self.backups_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        archive_path = self.backups_root / f"{stage}_{stamp}.zip"
        meta = {
            "stage": stage,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "manifest": str(loaded.manifest_path),
            "version": loaded.version,
            "description": loaded.description,
            "files": [m.target_rel for m in loaded.files],
        }
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
            zf.writestr("manifest.json", json.dumps(loaded.manifest, ensure_ascii=False, indent=2))
            for mapping in loaded.files:
                if mapping.target.exists() and mapping.target.is_file():
                    zf.write(mapping.target, arcname=f"files/{mapping.target_rel}")
        return archive_path

    def apply_loaded(self, loaded: LoadedManifest) -> list[str]:
        changed: list[str] = []
        for mapping in loaded.files:
            mapping.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(mapping.source, mapping.target)
            changed.append(mapping.target_rel)
        return changed

    def restore_backup(self, backup_zip: Path) -> list[str]:
        if not backup_zip.exists():
            raise UpdateError(f"backup archive not found: {backup_zip}")
        restored: list[str] = []
        with zipfile.ZipFile(backup_zip, "r") as zf:
            for name in zf.namelist():
                if not name.startswith("files/") or name.endswith("/"):
                    continue
                rel = name[len("files/"):]
                target = (self.project_root / rel).resolve()
                if not str(target).startswith(str(self.project_root)):
                    raise UpdateError(f"backup contains invalid target: {rel}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                restored.append(rel)
        return restored

    def schedule_app_restart(self, *, main_py: str = "main.py", delay_sec: float = 1.5) -> Path:
        helper_dir = self.runtime_dir / "remote_restart"
        helper_dir.mkdir(parents=True, exist_ok=True)
        script_path = helper_dir / "restart_app.bat"
        python_exe = sys.executable
        main_path = (self.project_root / main_py).resolve()
        content = (
            "@echo off\r\n"
            f"timeout /t {max(1, int(round(delay_sec)))} /nobreak >nul\r\n"
            f"cd /d \"{self.project_root}\"\r\n"
            f"start \"\" \"{python_exe}\" \"{main_path}\"\r\n"
        )
        script_path.write_text(content, encoding="utf-8")
        return script_path

    def launch_restart_script(self, script_path: Path) -> None:
        if os.name == "nt":
            os.spawnl(os.P_NOWAIT, os.environ.get("COMSPEC", "cmd.exe"), os.environ.get("COMSPEC", "cmd.exe"), "/c", str(script_path))
        else:
            os.spawnl(os.P_NOWAIT, "/bin/sh", "/bin/sh", str(script_path))
