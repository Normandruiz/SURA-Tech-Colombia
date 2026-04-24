"""Helpers compartidos por los extractores."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from slugify import slugify as _slugify

from src.config import RAW_DIR


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def seguro_slug(seguro: str) -> str:
    return _slugify(seguro)


def raw_dir_for(seguro: str) -> Path:
    d = RAW_DIR / seguro_slug(seguro)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_screenshot(page, seguro: str, tag: str) -> Path:
    path = raw_dir_for(seguro) / f"{tag}_{ts()}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def wait_quiet(page, timeout_ms: int = 15_000) -> None:
    """Espera a que la UI de Google Ads quede estable."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass


def soft_goto(page, url: str, timeout_ms: int = 60_000) -> None:
    """Navegacion 'soft' via window.location.href = '...'.

    Emula un click del usuario - Google no lo detecta como navegacion
    programatica, a diferencia de page.goto() que dispara anti-automation.
    """
    try:
        with page.expect_navigation(timeout=timeout_ms, wait_until="domcontentloaded"):
            page.evaluate(f"window.location.href = {url!r}")
    except Exception:
        # Fallback por si expect_navigation falla
        page.evaluate(f"window.location.href = {url!r}")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
    wait_quiet(page, 20_000)
