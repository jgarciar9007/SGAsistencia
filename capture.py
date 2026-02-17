import asyncio
from playwright.async_api import async_playwright
import os

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = r"C:\Users\jgarc\.gemini\antigravity\brain\c2f5abcc-b372-49a5-868a-95c688f87abf\screenshots"

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()

        # 1. Login
        print("Navigating to login...")
        await page.goto(f"{BASE_URL}/login/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "login.png"))
        
        print("Logging in...")
        await page.fill("input[name='username']", "admin_manual")
        await page.fill("input[name='password']", "password123")
        # Assuming there is a submit button, often type='submit' or just enter
        await page.click("button[type='submit']") 
        try:
             await page.wait_for_url(f"{BASE_URL}/dashboard/", timeout=5000)
        except:
             print("Login might have failed or redirect is different. Current URL:", page.url)

        # 2. Dashboard
        print("Capturing Dashboard...")
        await page.goto(f"{BASE_URL}/dashboard/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "dashboard.png"))

        # 3. Empleados
        print("Capturing Empleados...")
        await page.goto(f"{BASE_URL}/empleados/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "empleados_lista.png"))
        
        # 4. Nuevo Empleado
        print("Capturing Nuevo Empleado...")
        await page.goto(f"{BASE_URL}/empleados/nuevo/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "empleados_nuevo.png"))

        # 5. Reportes
        print("Capturing Reportes...")
        await page.goto(f"{BASE_URL}/reportes/asistencia/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "reportes_asistencia.png"))
        
        await page.goto(f"{BASE_URL}/reportes/ausencias/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "reportes_ausencias.png"))

        await page.goto(f"{BASE_URL}/reportes/nomina/calculo/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "reportes_nomina.png"))

        # Payroll Preview (Generated)
        # Using a fixed date range or dynamic current month
        import datetime
        now = datetime.date.today()
        start = now.replace(day=1)
        next_month = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        end = next_month - datetime.timedelta(days=1)
        
        preview_url = f"{BASE_URL}/reportes/nomina/preview/?inicio={start}&fin={end}"
        print(f"Capturing Nomina Preview: {preview_url}")
        await page.goto(preview_url)
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "reportes_nomina_preview.png"))

        # 6. Config/Dispositivos
        print("Capturing Configuración...")
        await page.goto(f"{BASE_URL}/config/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "configuracion.png"))
        
        # 7. Admin (Django)
        print("Capturing Admin...")
        await page.goto(f"{BASE_URL}/admin/")
        await page.screenshot(path=os.path.join(OUTPUT_DIR, "admin_django.png"))

        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(capture())
