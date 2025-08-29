# RDV Préfecture Monitor

Este proyecto es un script en Python que ayuda a **vigilar la disponibilidad de citas (créneaux)** en la página de la prefectura.

⚠️ Importante:  
El script **no evade captchas**. Tú tienes que pasar el captcha y llegar a la página donde aparece “no hay disponibilidad” antes de que empiece a vigilar.

---

## 🚀 Qué hace
- Abre la página oficial de la prefectura.  
- Tú resuelves el CAPTCHA y llegas a la página de créneaux.  
- El script refresca automáticamente cada cierto tiempo.  
- Si detecta disponibilidad:
  - Hace un **beep** en la consola.  
  - Guarda una **captura de pantalla** en la carpeta `screenshots/`.  
  - Opcional: manda una alerta por **Telegram** (si lo configuras).  

---

## 🔧 Requisitos
- **Python 3.9+**  
- **Playwright** para Python  

Instalación rápida:
```bash
pip install playwright
playwright install
