"""Static validation for stock screen plugins (no arbitrary exec in-process)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "math",
        "statistics",
        "decimal",
        "datetime",
        "typing",
        "collections",
        "functools",
        "itertools",
        "operator",
        "re",
        "json",
        "pandas",
        "numpy",
        "nivesh_screens",
    }
)

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "pathlib",
        "shutil",
        "pickle",
        "ctypes",
        "multiprocessing",
        "threading",
        "asyncio",
        "importlib",
        "builtins",
        "requests",
        "urllib",
        "http",
        "ftplib",
        "psycopg2",
        "psycopg",
        "sqlalchemy",
        "yfinance",
        "mftool",
    }
)

PARAM_TYPES = frozenset({"float", "int", "str", "bool"})


@dataclass
class ValidationResult:
    ok: bool
    path: str
    screen_id: str | None = None
    meta: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": self.path,
            "screen_id": self.screen_id,
            "meta": self.meta,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _import_root(name: str | None) -> str | None:
    if not name:
        return None
    return name.split(".", 1)[0]


def _check_imports(tree: ast.AST) -> list[str]:
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _import_root(alias.name)
                if root in FORBIDDEN_IMPORT_ROOTS or (root and root not in ALLOWED_IMPORT_ROOTS):
                    errors.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                errors.append("relative imports are not allowed")
                continue
            root = _import_root(node.module)
            if root in FORBIDDEN_IMPORT_ROOTS or (root and root not in ALLOWED_IMPORT_ROOTS):
                errors.append(f"forbidden import: {node.module}")
    return errors


def _literal_assign(tree: ast.AST, name: str) -> Any:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(node.value)
                except Exception:
                    return "__UNRESOLVED__"
    return None


def _has_screen_fn(tree: ast.AST) -> bool:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "screen":
            if isinstance(node, ast.AsyncFunctionDef):
                return False
            args = node.args
            positional = len(args.posonlyargs) + len(args.args)
            # Expect screen(stocks, params) — allow defaults but require two slots.
            return positional >= 2
    return False


def _validate_meta(meta: Any, *, expected_asset_class: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(meta, dict):
        return None, ["SCREEN_META must be a literal dict"]
    name = meta.get("name")
    version = meta.get("version")
    description = meta.get("description")
    asset_class = meta.get("asset_class")
    parameters = meta.get("parameters", [])
    if not isinstance(name, str) or not name.strip():
        errors.append("SCREEN_META.name is required")
    if not isinstance(version, str) or not version.strip():
        errors.append("SCREEN_META.version is required")
    if not isinstance(description, str):
        errors.append("SCREEN_META.description must be a string")
    if asset_class != expected_asset_class:
        errors.append(f"SCREEN_META.asset_class must be '{expected_asset_class}'")
    if not isinstance(parameters, list):
        errors.append("SCREEN_META.parameters must be a list")
        parameters = []
    cleaned_params: list[dict[str, Any]] = []
    for index, param in enumerate(parameters):
        if not isinstance(param, dict):
            errors.append(f"parameters[{index}] must be an object")
            continue
        pname = param.get("name")
        ptype = param.get("type")
        if not isinstance(pname, str) or not pname.strip():
            errors.append(f"parameters[{index}].name is required")
        if ptype not in PARAM_TYPES:
            errors.append(f"parameters[{index}].type must be one of {sorted(PARAM_TYPES)}")
        if "default" not in param:
            errors.append(f"parameters[{index}].default is required")
        cleaned_params.append(
            {
                "name": pname,
                "type": ptype,
                "default": param.get("default"),
                "description": param.get("description"),
            }
        )
    if errors:
        return None, errors
    return {
        "name": name.strip(),
        "version": version.strip(),
        "description": str(description).strip(),
        "asset_class": asset_class,
        "parameters": cleaned_params,
    }, []


def validate_screen_file(
    path: Path,
    *,
    expected_asset_class: str = "stock",
    disabled_ids: set[str] | None = None,
) -> ValidationResult:
    rel = str(path)
    result = ValidationResult(ok=False, path=rel)
    if path.suffix != ".py":
        result.errors.append("only .py files are allowed")
        return result
    if path.name.startswith("_"):
        result.errors.append("private modules (leading underscore) are skipped")
        return result
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"cannot read file: {exc}")
        return result
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        result.errors.append(f"syntax error: {exc.msg} (line {exc.lineno})")
        return result

    result.errors.extend(_check_imports(tree))

    screen_id = _literal_assign(tree, "SCREEN_ID")
    if screen_id is None:
        result.errors.append("SCREEN_ID is required")
    elif screen_id == "__UNRESOLVED__":
        result.errors.append("SCREEN_ID must be a string literal")
    elif not isinstance(screen_id, str) or not screen_id.strip():
        result.errors.append("SCREEN_ID must be a non-empty string")
    else:
        result.screen_id = screen_id.strip()

    raw_meta = _literal_assign(tree, "SCREEN_META")
    if raw_meta is None:
        result.errors.append("SCREEN_META is required")
    elif raw_meta == "__UNRESOLVED__":
        result.errors.append("SCREEN_META must be a literal dict")
    else:
        meta, meta_errors = _validate_meta(raw_meta, expected_asset_class=expected_asset_class)
        result.errors.extend(meta_errors)
        result.meta = meta

    if not _has_screen_fn(tree):
        result.errors.append("screen(stocks, params) function is required")

    if result.screen_id and disabled_ids and result.screen_id in disabled_ids:
        result.errors.append(f"screen '{result.screen_id}' is disabled in registry")

    result.ok = not result.errors
    return result
