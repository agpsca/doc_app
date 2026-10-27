"""Detecção leve de stack (linguagem, framework, gerenciador de pacotes).

Determinístico, sem IA: olha arquivos de configuração conhecidos (package.json,
pyproject.toml, go.mod, Cargo.toml, Dockerfile). É usado por `extract.py`, que
coleta o restante dos fatos do projeto.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .textio import read_text

FRONTEND_JS = {"next", "react", "vue", "nuxt", "@angular/core", "svelte",
               "@sveltejs/kit", "solid-js", "@remix-run/react", "vite", "astro"}
BACKEND_JS = {"express", "fastify", "@nestjs/core", "koa", "@hapi/hapi", "hono",
              "@adonisjs/core", "restify", "@trpc/server", "apollo-server",
              "@apollo/server"}
BACKEND_PY = {"fastapi": "FastAPI", "django": "Django", "flask": "Flask",
              "starlette": "Starlette", "aiohttp": "aiohttp", "sanic": "Sanic",
              "litestar": "Litestar", "tornado": "Tornado", "falcon": "Falcon",
              "celery": "Celery"}
BACKEND_GO = re.compile(r"gin-gonic/gin|labstack/echo|gofiber/fiber|go-chi/chi|"
                        r"gorilla/mux|grpc")
BACKEND_RUST = re.compile(r"^\s*(actix-web|axum|rocket|warp|tonic)\s*=", re.M)

KIND_LABELS = {"frontend": "frontend", "backend": "backend",
               "fullstack": "fullstack", "other": "biblioteca/CLI"}


@dataclass
class StackInfo:
    name: str
    language: str | None = None
    framework: str | None = None
    package_manager: str | None = None
    extras: list[str] = field(default_factory=list)
    kind: str = "other"   # frontend | backend | fullstack | other

    def summary(self) -> str:
        parts = [x for x in (self.framework, self.language, self.package_manager) if x]
        parts.append(KIND_LABELS[self.kind])
        return " · ".join(parts)


def detect_stack(app_path: Path) -> StackInfo:
    """Inspeciona a pasta do app e devolve o que conseguir inferir."""
    info = StackInfo(name=app_path.name)
    has_front = has_back = False

    pkg = app_path / "package.json"
    if pkg.is_file():
        info.language = "JavaScript/TypeScript"
        if (app_path / "tsconfig.json").is_file():
            info.language = "TypeScript"
        deps = _read_package_json(pkg, info)
        has_front |= bool(deps & FRONTEND_JS)
        has_back |= bool(deps & BACKEND_JS)

    has_py = ((app_path / "pyproject.toml").is_file()
              or (app_path / "requirements.txt").is_file()
              or bool(list(app_path.glob("*.py"))))
    if has_py:
        if info.language is None:
            info.language = "Python"
        if (app_path / "pyproject.toml").is_file():
            info.package_manager = info.package_manager or "pip/uv"
        elif (app_path / "requirements.txt").is_file():
            info.package_manager = info.package_manager or "pip"
        py_deps = _python_deps(app_path)
        found = [d for d in BACKEND_PY if d in py_deps]
        if found:
            has_back = True
            info.framework = info.framework or BACKEND_PY[found[0]]

    gomod = _read(app_path / "go.mod")
    if gomod is not None:
        info.language = info.language or "Go"
        if BACKEND_GO.search(gomod) or _go_uses_http(app_path):
            has_back = True
    cargo = _read(app_path / "Cargo.toml")
    if cargo is not None:
        info.language = info.language or "Rust"
        info.package_manager = info.package_manager or "cargo"
        has_back |= bool(BACKEND_RUST.search(cargo))
    for build_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
        text = _read(app_path / build_file)
        if text is not None:
            info.language = info.language or ("Kotlin" if build_file.endswith("kts")
                                              else "Java")
            has_back |= "spring-boot" in text or "quarkus" in text or "micronaut" in text

    if (app_path / "Dockerfile").is_file():
        info.extras.append("Docker")

    info.kind = ("fullstack" if has_front and has_back else
                 "frontend" if has_front else
                 "backend" if has_back else "other")
    return info


def _read(path: Path) -> str | None:
    return read_text(path)


def _python_deps(app: Path) -> set[str]:
    names: set[str] = set()
    specs: list[str] = []
    text = _read(app / "pyproject.toml")
    if text:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            data = {}
        specs += data.get("project", {}).get("dependencies", []) or []
        specs += list((data.get("tool", {}).get("poetry", {})
                       .get("dependencies", {}) or {}).keys())
    req = _read(app / "requirements.txt")
    if req:
        specs += [line for line in req.splitlines()
                  if line.strip() and not line.lstrip().startswith(("#", "-"))]
    for spec in specs:
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)", str(spec))
        if m:
            names.add(m.group(1).lower())
    return names


def _go_uses_http(app: Path) -> bool:
    for go_file in list(app.glob("*.go")) + list(app.glob("cmd/*/*.go")):
        text = _read(go_file) or ""
        if '"net/http"' in text and "ListenAndServe" in text:
            return True
    return False


def _read_package_json(pkg: Path, info: StackInfo) -> set[str]:
    """Preenche framework e gerenciador de pacotes; devolve os nomes das deps."""
    try:
        data = json.loads(read_text(pkg) or "")
    except (json.JSONDecodeError, OSError):
        return set()
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

    if "next" in deps:
        info.framework = "Next.js"
    elif "react" in deps:
        info.framework = "React"
    elif "vue" in deps:
        info.framework = "Vue"
    elif "@angular/core" in deps:
        info.framework = "Angular"
    elif "svelte" in deps:
        info.framework = "Svelte"
    elif "@nestjs/core" in deps:
        info.framework = "NestJS"
    elif "fastify" in deps:
        info.framework = "Fastify"
    elif "express" in deps:
        info.framework = "Express"

    pm = data.get("packageManager", "")
    if pm.startswith("pnpm"):
        info.package_manager = "pnpm"
    elif pm.startswith("yarn"):
        info.package_manager = "yarn"
    elif (pkg.parent / "pnpm-lock.yaml").is_file():
        info.package_manager = "pnpm"
    elif (pkg.parent / "yarn.lock").is_file():
        info.package_manager = "yarn"
    elif (pkg.parent / "package-lock.json").is_file():
        info.package_manager = "npm"
    return set(deps)
