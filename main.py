import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont
import img2pdf
import os
import time
import threading
import io
import sys
import shutil
import subprocess

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def resource_path(relative_path):
    """ Gestion des chemins pour PyInstaller (icônes, images, etc.) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SushiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SushiScan Downloader - Created by Endam")
        self.geometry("700x800")
        self.driver = None
        self._cancel_event = threading.Event()
        self.image_paths = []
        # Dossier de profil isolé
        self.profile_dir = os.path.expanduser("~/SushiProfile")
        self._setup_ui()
        
        # Petit check au démarrage
        self.after(1000, self._check_dependencies)

    def _check_dependencies(self):
        """ Vérifie si les outils système sont là """
        browser = shutil.which("chromium-browser") or shutil.which("chromium")
        driver = shutil.which("chromedriver")
        
        if not browser or not driver:
            msg = "⚠️ Dépendances manquantes !\n\nsudo dnf install chromium chromedriver"
            messagebox.showwarning("Logiciel Manquant", msg)

    def _setup_ui(self):
        frame_top = tk.Frame(self)
        frame_top.pack(pady=10, padx=10, fill="x")

        lbl_instr = tk.Label(
            frame_top,
            text="L'application gère le lancement de Chromium.\nPlacez-vous sur le premier scan du chapitre une fois ouvert.",
            fg="#d32f2f", justify=tk.LEFT
        )
        lbl_instr.pack(side=tk.TOP, pady=5)

        frame_input = tk.Frame(frame_top)
        frame_input.pack(pady=5)

        tk.Label(frame_input, text="Nombre de pages :").pack(side=tk.LEFT)
        self.entry_pages = tk.Entry(frame_input, width=10)
        self.entry_pages.pack(side=tk.LEFT, padx=5)
        self.entry_pages.insert(0, "64")

        self.btn_start = tk.Button(
            frame_top, text="🚀 Démarrer le téléchargement",
            command=self._on_start, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
        )
        self.btn_start.pack(side=tk.TOP, fill="x", pady=(10, 4))

        self.btn_cancel = tk.Button(
            frame_top, text="⛔ Annuler",
            command=self._on_cancel, bg="#e53935", fg="white", font=("Arial", 11, "bold"),
            state="disabled",
        )
        self.btn_cancel.pack(side=tk.TOP, fill="x", pady=(0, 6))

        self.lbl_info = tk.Label(self, text="Prêt.", fg="blue")
        self.lbl_info.pack(pady=5)

        self.log_text = tk.Text(self, height=15, width=80)
        self.log_text.pack(padx=10, pady=5)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def lancer_chromium_automatique(self):
        """ Nettoie les verrous et lance Chromium via un Shell Bash explicite """
        self.log("🧹 Nettoyage des sessions...")
        os.system("pkill -f chromium")
        
        lock_file = os.path.join(self.profile_dir, "SingletonLock")
        if os.path.exists(lock_file):
            try: os.unlink(lock_file)
            except: pass

        browser_bin = shutil.which("chromium-browser") or shutil.which("chromium")
        if not browser_bin: return False

        self.log(f"🚀 Tentative de lancement via Bash : {browser_bin}")
        
        # On enveloppe la commande dans 'bash -c' pour garantir l'exécution du '&'
        inner_cmd = f'{browser_bin} --remote-debugging-port=9222 --user-data-dir="{self.profile_dir}" --no-sandbox --disable-dev-shm-usage --start-maximized https://sushiscan.net'
        full_cmd = f"/bin/bash -c '{inner_cmd} &' &"
        
        try:
            # On utilise subprocess.Popen pour détacher complètement le processus du binaire Python
            subprocess.Popen(full_cmd, shell=True, preexec_fn=os.setsid)
            self.log("⏳ Attente de l'ouverture (6s)...")
            time.sleep(6)
            return True
        except Exception as e:
            self.log(f"❌ Erreur critique : {e}")
            return False

    def connect_driver(self):
        """Se connecte à la session Chromium ouverte par le launcher"""
        self.log("🔗 Tentative de connexion au port 9222...")
        
        options = Options()
        # On utilise l'IP exacte que netstat a confirmée
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        options.add_argument("--no-sandbox")
        # CRITIQUE : Autorise Selenium à discuter avec Chromium sur Linux
        options.add_argument("--remote-allow-origins=*")
        
        # Détection dynamique du driver sur Raspberry Pi
        driver_bin = shutil.which("chromedriver") or "/usr/bin/chromedriver"
        service = Service(executable_path=driver_bin)

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.log("✅ Connexion réussie ! Pilote prêt.")
            return self.driver
        except Exception as e:
            self.log(f"❌ Erreur de connexion : {str(e)[:100]}")
            messagebox.showerror("Erreur de liaison", 
                "L'appli n'arrive pas à piloter la fenêtre Chromium.\n\n"
                "Vérifiez que le launcher est bien actif.")
            return None

    def _ajouter_filigrane(self, original_image):
        try:
            base = original_image.convert("RGBA")
            txt_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            text = "Created by Endam"
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            x, y = base.width - (bbox[2]-bbox[0]) - 10, base.height - (bbox[3]-bbox[1]) - 10
            draw.text((x, y), text, font=font, fill=(150, 150, 150, 180))
            return Image.alpha_composite(base, txt_layer).convert("RGB")
        except: return original_image

    def demarrer(self):
        """Orchestre le téléchargement et la capture précise."""
        val = self.entry_pages.get()
        if not val.isdigit():
            messagebox.showerror("Erreur", "Nombre de pages invalide")
            self._reset_boutons()
            return
            
        max_pages = int(val)
        self.driver = self.connect_driver()
        if not self.driver:
            self._reset_boutons()
            return

        self.log("✅ Connecté. Ajustement du format...")
        self.driver.set_window_size(1600, 2600)
        
        os.makedirs("Downloads", exist_ok=True)
        self.image_paths = [] # Correction point 1 : On utilise self pour la persistance

        for i in range(1, max_pages + 1):
            if self._cancel_event.is_set():
                self.log("⛔ Annulation demandée.")
                break

            self.lbl_info.config(text=f"Progression : {i}/{max_pages}")
            
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div#readerarea img"))
                )
                
                # Fix Lazy Load
                self.driver.execute_script("window.scrollTo(0, 800);")
                time.sleep(0.5)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1.5)

                target_img = self.driver.find_element(By.CSS_SELECTOR, "div#readerarea img")
                
                # Calcul précis du format pour éviter les bandes noires
                rect = self.driver.execute_script("""
                    var rect = arguments[0].getBoundingClientRect();
                    return {
                        left: rect.left + window.pageXOffset,
                        top: rect.top + window.pageYOffset,
                        width: rect.width,
                        height: rect.height
                    };
                """, target_img)

                png_data = self.driver.get_screenshot_as_png()
                full_img = Image.open(io.BytesIO(png_data)).convert("RGB")

                left, top = int(rect['left']), int(rect['top'])
                right, bottom = left + int(rect['width']), top + int(rect['height'])

                final_img = full_img.crop((
                    max(0, left), 
                    max(0, top), 
                    min(right, full_img.width), 
                    min(bottom, full_img.height)
                ))

                final_img = self._ajouter_filigrane(final_img)
                # Utilisation de chemins absolus pour éviter les pertes PyInstaller
                fname = os.path.abspath(f"Downloads/page_{i:03d}.jpg")
                final_img.save(fname, quality=95, subsampling=0)
                
                self.image_paths.append(fname)
                self.log(f"✅ Page {i} capturée.")

                if i < max_pages:
                    try:
                        next_btn = self.driver.find_element(By.CSS_SELECTOR, "div.nextprev a.ch-next-btn")
                        self.driver.execute_script("arguments[0].click();", next_btn)
                        time.sleep(3) 
                    except:
                        self.log("Fin de chapitre détectée.")
                        break

            except Exception as e:
                self.log(f"❌ Erreur page {i}: {e}")
                break

        # Correction point 1 : Appel de la création du PDF
        if self.image_paths and not self._cancel_event.is_set():
            self.log(f"📦 Création du PDF avec {len(self.image_paths)} images...")
            self._creer_pdf(self.image_paths)
        elif self.image_paths:
             self.log("⚠️ Images conservées dans /Downloads (Annulation).")
        
        self._reset_boutons()

    def _creer_pdf(self, image_paths):
        self.lbl_info.config(text="Génération du PDF...")
        pdf_path = f"Downloads/SushiScan_{int(time.time())}.pdf"
        try:
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(image_paths))
            self.log(f"🎉 PDF créé avec succès : {pdf_path}")
            # Nettoyage
            for p in image_paths:
                if os.path.exists(p): os.remove(p)
        except Exception as e:
            self.log(f"❌ Erreur assemblage PDF: {e}")

    def _on_start(self):
        self._cancel_event.clear()
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        threading.Thread(target=self.demarrer, daemon=True).start()

    def _on_cancel(self):
        self._cancel_event.set()
        self.btn_cancel.config(state="disabled")

    def _reset_boutons(self):
        self.btn_start.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.lbl_info.config(text="Prêt.")

if __name__ == "__main__":
    app = SushiApp()
    app.mainloop()
