import os
import re
import markdown
import asyncio
from playwright.async_api import async_playwright

# Input/Output paths
ROOT_DIR = os.getcwd() # Should be d:\Proyectos de Programacion\ZKManager
MD_PATH = r"C:\Users\jgarc\.gemini\antigravity\brain\c2f5abcc-b372-49a5-868a-95c688f87abf\manual_de_usuario.md"
PDF_OUTPUT_PATH = os.path.join(ROOT_DIR, "manual_de_usuario.pdf")
HTML_TEMP_PATH = os.path.join(ROOT_DIR, "manual_temp.html")

def md_to_html(md_content):
    # Basic CSS for styling
    css = """
    <style>
        body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; color: #333; }
        h1 { color: #2c3e50; text-align: center; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        h3 { color: #7f8c8d; margin-top: 20px; }
        img { max-width: 100%; height: auto; border: 1px solid #ddd; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); margin: 20px 0; display: block; margin-left: auto; margin-right: auto; }
        ul { margin-bottom: 20px; }
        li { margin-bottom: 5px; }
        code { background: #f8f9fa; padding: 2px 4px; border-radius: 3px; font-family: monospace; }
        hr { border: 0; border-top: 1px solid #eee; margin: 30px 0; }
        @page { margin: 2cm; }
    </style>
    """
    
    # Simple regex to fix image paths if they are absolute windows paths in MD
    # The MD has typically /C:/Users... format which might need adjustment for local file:// access
    # But usually browsers handle file:///C:/... fine.
    
    # Convert MD to HTML
    html_body = markdown.markdown(md_content)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Manual de Usuario</title>
        {css}
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

async def generate_pdf():
    print(f"Reading manual from: {MD_PATH}")
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = md_to_html(md_content)
    
    # Save temp HTML
    with open(HTML_TEMP_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"HTML generated at: {HTML_TEMP_PATH}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Load the HTML file
        file_url = f"file:///{HTML_TEMP_PATH.replace(os.sep, '/')}"
        print(f"Loading page: {file_url}")
        await page.goto(file_url, wait_until="networkidle")
        
        # Generate PDF
        print(f"Saving PDF to: {PDF_OUTPUT_PATH}")
        await page.pdf(path=PDF_OUTPUT_PATH, format="A4", print_background=True)
        
        await browser.close()
    
    # Cleanup
    if os.path.exists(HTML_TEMP_PATH):
        os.remove(HTML_TEMP_PATH)
        print("Temp HTML removed.")
    
    print("PDF generation complete!")

if __name__ == "__main__":
    try:
        # Check if markdown is installed, if not, basic install
        import markdown
        asyncio.run(generate_pdf())
    except ImportError:
        print("Markdown package not found. Please install it first.")
