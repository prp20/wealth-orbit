"""Discover and cache validated stock screen plugins from registry roots."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import registry_path, resolve_plugin_root
from .validator import ValidationResult, validate_screen_file

_CACHE: dict[str, Any] | None = None


@dataclass
class ScreenEntry:
    screen_id: str
    path: str
    enabled: bool
    status: str  # ok | failed | disabled
    meta: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    root: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_registry() -> dict[str, Any]:
    path = registry_path()
    if not path.is_file():
        raise FileNotFoundError(f"screen registry missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("screen registry must be a mapping")
    roots = data.get("plugin_roots") or []
    if not isinstance(roots, list) or not roots:
        raise ValueError("registry.plugin_roots must be a non-empty list")
    disabled = data.get("disabled_ids") or []
    if not isinstance(disabled, list):
        raise ValueError("registry.disabled_ids must be a list")
    timeout = data.get("timeout_seconds", 15)
    try:
        timeout_seconds = max(1, min(int(timeout), 60))
    except (TypeError, ValueError) as exc:
        raise ValueError("registry.timeout_seconds must be an integer") from exc
    return {
        "version": data.get("version", 1),
        "asset_class": data.get("asset_class", "stock"),
        "plugin_roots": [str(item) for item in roots],
        "disabled_ids": {str(item) for item in disabled},
        "timeout_seconds": timeout_seconds,
        "entries": data.get("entries") or [],
    }


def _iter_plugin_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files = [
        path
        for path in sorted(root.glob("*.py"))
        if path.is_file() and not path.name.startswith("_") and path.name != "__init__.py"
    ]
    return files


def discover_screens(*, use_cache: bool = True) -> dict[str, Any]:
    global _CACHE
    if use_cache and _CACHE is not None:
        return _CACHE

    registry = load_registry()
    expected_asset = str(registry["asset_class"])
    disabled_ids: set[str] = registry["disabled_ids"]
    seen_ids: dict[str, str] = {}
    screens: list[ScreenEntry] = []
    validations: list[dict[str, Any]] = []

    for relative_root in registry["plugin_roots"]:
        root = resolve_plugin_root(relative_root)
        for path in _iter_plugin_files(root):
            result: ValidationResult = validate_screen_file(
                path,
                expected_asset_class=expected_asset,
                disabled_ids=set(),  # evaluate disable after uniqueness
            )
            validations.append(result.as_dict())
            screen_id = result.screen_id
            if not result.ok or not screen_id:
                screens.append(
                    ScreenEntry(
                        screen_id=screen_id or path.stem,
                        path=_rel_path(path),
                        enabled=False,
                        status="failed",
                        meta=result.meta,
                        errors=result.errors,
                        warnings=result.warnings,
                        root=relative_root,
                    )
                )
                continue

            if screen_id in seen_ids:
                screens.append(
                    ScreenEntry(
                        screen_id=screen_id,
                        path=_rel_path(path),
                        enabled=False,
                        status="failed",
                        meta=result.meta,
                        errors=[f"duplicate SCREEN_ID '{screen_id}' (also in {seen_ids[screen_id]})"],
                        root=relative_root,
                    )
                )
                continue

            seen_ids[screen_id] = _rel_path(path)
            if screen_id in disabled_ids:
                screens.append(
                    ScreenEntry(
                        screen_id=screen_id,
                        path=_rel_path(path),
                        enabled=False,
                        status="disabled",
                        meta=result.meta,
                        errors=[f"screen '{screen_id}' is disabled in registry"],
                        warnings=result.warnings,
                        root=relative_root,
                    )
                )
                continue

            screens.append(
                ScreenEntry(
                    screen_id=screen_id,
                    path=_rel_path(path),
                    enabled=True,
                    status="ok",
                    meta=result.meta,
                    errors=[],
                    warnings=result.warnings,
                    root=relative_root,
                )
            )

    payload = {
        "registry_version": registry["version"],
        "asset_class": expected_asset,
        "timeout_seconds": registry["timeout_seconds"],
        "screens": [item.as_dict() for item in screens],
        "validations": validations,
    }
    _CACHE = payload
    return payload


def _rel_path(path: Path) -> str:
    from .paths import repo_root

    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


def refresh_screens() -> dict[str, Any]:
    """Rescan roots, revalidate, and dry-run runnable screens in isolation."""
    global _CACHE
    _CACHE = None
    payload = discover_screens(use_cache=False)
    from .paths import repo_root
    from .runner import dry_run_screen

    timeout = int(payload.get("timeout_seconds") or 15)
    updated: list[dict[str, Any]] = []
    for item in payload["screens"]:
        if item.get("status") != "ok" or not item.get("enabled"):
            updated.append(item)
            continue
        plugin_path = repo_root() / item["path"]
        dry = dry_run_screen(plugin_path, timeout_seconds=timeout)
        if not dry.get("ok"):
            errors = list(item.get("errors") or [])
            message = dry.get("error") or "dry-run failed"
            errors.append(f"dry-run: {message}")
            item = {
                **item,
                "enabled": False,
                "status": "failed",
                "errors": errors,
            }
        updated.append(item)
    payload["screens"] = updated
    _CACHE = payload
    return payload


def list_screens(*, runnable_only: bool = False) -> list[dict[str, Any]]:
    payload = discover_screens(use_cache=True)
    screens = payload["screens"]
    if runnable_only:
        return [item for item in screens if item.get("enabled") and item.get("status") == "ok"]
    return screens


def get_runnable_screen(screen_id: str) -> dict[str, Any] | None:
    for item in list_screens(runnable_only=True):
        if item["screen_id"] == screen_id:
            return item
    return None
