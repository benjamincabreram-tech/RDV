# monitor_rdv.py
"""
RDV Préfecture slot monitor (human-in-the-loop, headless-friendly)

- Por defecto corre en HEADLESS=True para funcionar en VMs sin XServer.
- Si instalas un entorno gráfico (xrdp/xfce) puedes lanzar con HEADLESS=false.
- En modo headless NO podrás pasar el CAPTCHA desde la VM; úsalo como monitor.
"""

import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = os.getenv("RDV_URL", "https://www.rdv-prefecture.interieur.gouv.fr/rdvpref/reservation/demarche/4443/creneau/")
REFRESH_SECONDS = int(os.getenv("RDV_REFRESH_SECONDS", "30"))
SCREENSHOT_DIR = Path(os.getenv("RDV_SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Modo headless configurable por env var (default: true)
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Opcional: notificaciones por Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def notify_console(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def notify_beep() -> None:
    # Beep básico en consola (si está soportado)
    try:
        print("\a", end="", flush=True)
    except Exception:
        pass


def send_telegram(msg: str) -> Optional[int]:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        return r.status_code
    except Exception as e:
        notify_console(f"Telegram send failed: {e}")
        return None


def looks_like_no_availability(text: str) -> bool:
    patterns = [
        r"aucun(?:e)?\s+cr[ée]neau\s+disponible",
        r"pas\s+de\s+cr[ée]neau",
        r"plus\s+de\s+plage\s+horaire",
        r"plus\s+de\s+disponibilit[ée]s?",
        r"aucune\s+disponibilit[ée]",
    ]
    text_low = re.sub(r"\s+", " ", text.lower())
    return any(re.search(p, text_low) for p in patterns)


def looks_like_timeslot(text: str) -> bool:
    patterns = [
        r"\b\d{1,2}[:hH]\d{2}\b",  # 09:15 o 14h30
        r"\b\d{1,2}h\b",           # 9h, 14h
    ]
    text_low = re.sub(r"\s+", " ", text.lower())
    return any(re.search(p, text_low) for p in patterns)


def ensure_on_slot_page_if_needed(page) -> None:
    """
    En modo con ventana (HEADLESS=False), pedimos al usuario que llegue a la página de créneaux.
    En headless, saltamos la espera (no hay interfaz), pero avisamos limitaciones.
    """
    if HEADLESS:
        notify_console("HEADLESS=True → No hay interfaz gráfica. Si el sitio requiere CAPTCHA/autenticación, este script no podrá pasarlo aquí.")
        notify_console("Usos típicos en headless/xvfb: monitoreo posterior o páginas públicas sin CAPTCHA.")
        return
    notify_console("⚠️ Navega manualmente hasta la página de selección de horarios (créneaux).")
    notify_console("Resuelve cualquier CAPTCHA y haz clic en 'Suivant' según sea necesario.")
    try:
        input(">> Presiona ENTER aquí cuando estés en la página donde se ven horarios o el mensaje de 'no disponibilidad'… ")
    except KeyboardInterrupt:
        raise


def capture(page, label: str) -> None:
    fname = SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}.png"
    try:
        page.screenshot(path=str(fname), full_page=True)
        notify_console(f"📸 Captura guardada: {fname}")
    except Exception as e:
        notify_console(f"Screenshot failed: {e}")


def main():
    notify_console(f"🚀 Iniciando Playwright… (HEADLESS={HEADLESS})")
    with sync_playwright() as p:
        # Args útiles en entornos headless/VM
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context()
        page = context.new_page()

        notify_console(f"Abrir {URL}")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            notify_console("⏳ Timeout al cargar la página inicial; reintentando tras el primer ciclo.")
        
        ensure_on_slot_page_if_needed(page)

        notify_console(f"Monitoreando cada {REFRESH_SECONDS}s… (Ctrl+C para detener)")
        last_status = None

        while True:
            try:
                # A veces el body puede tardar; toleramos timeout
                content_text = page.inner_text("body", timeout=5000)
            except PlaywrightTimeoutError:
                content_text = ""

            has_slots = looks_like_timeslot(content_text) and not looks_like_no_availability(content_text)
            status = "AVAILABLE" if has_slots else "NONE"

            if status != last_status:
                if has_slots:
                    msg = "⚠️ RDV DETECTADO: Parece que hay horarios disponibles. ¡Corre a reservar!"
                    notify_console(msg)
                    notify_beep()
                    capture(page, "slots_detected")
                    send_telegram(msg)
                else:
                    notify_console("⏳ Aún no hay disponibilidad.")
                    capture(page, "none")
                last_status = status

            # Refresco periódico
            try:
                page.reload(wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                notify_console("🔁 Timeout en reload; continúo al siguiente ciclo.")
            time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Monitor detenido por el usuario.")
        sys.exit(0)
