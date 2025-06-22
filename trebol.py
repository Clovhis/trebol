import json
import logging
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

try:
    import winsound
except Exception:
    winsound = None

try:
    import ttkbootstrap as tb
    from ttkbootstrap import ttk
except Exception:
    tb = None
    from tkinter import ttk

import requests
from bs4 import BeautifulSoup

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

logging.basicConfig(
    filename="trebol.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)


USERS_FILE = 'numeros_usuario.json'

class TrebolApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Trebol')
        self.style = (tb.Style() if tb else ttk.Style())
        logging.info('TrebolApp initialized')
        self.create_widgets()
        self.load_user_data()
        self.running = True
        self.previous_results = None
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
        if HAS_TRAY:
            self.setup_tray()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(padx=10, pady=10)

        ttk.Label(frame, text='Loto Plus (6 numeros):').grid(row=0, column=0, sticky='w')
        self.loto_entry = ttk.Entry(frame, width=30)
        self.loto_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(frame, text='Numero Plus:').grid(row=1, column=0, sticky='w')
        self.plus_entry = ttk.Entry(frame, width=30)
        self.plus_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(frame, text='Quiniela (hasta 3 numeros):').grid(row=2, column=0, sticky='w')
        self.qui_entry = ttk.Entry(frame, width=30)
        self.qui_entry.grid(row=2, column=1, padx=5, pady=2)

        btn_style = 'primary.TButton' if tb else 'TButton'
        danger_style = 'danger.TButton' if tb else 'TButton'
        self.save_btn = ttk.Button(frame, text='Guardar', command=self.save_user_data, style=btn_style)
        self.save_btn.grid(row=3, column=0, pady=5)
        self.update_btn = ttk.Button(frame, text='Actualizar', command=self.scrape_once, style=btn_style)
        self.update_btn.grid(row=3, column=1, pady=5)
        self.exit_btn = ttk.Button(frame, text='Cerrar aplicacion', command=self.on_close, style=danger_style)
        self.exit_btn.grid(row=4, column=0, columnspan=2, pady=5)

        self.text = tk.Text(self.root, width=60, height=20)
        self.text.pack(padx=10, pady=10)

        if tb:
            for btn in (self.save_btn, self.update_btn, self.exit_btn):
                btn.bind('<Enter>', lambda e, b=btn: b.state(['hover']))
                btn.bind('<Leave>', lambda e, b=btn: b.state(['!hover']))

    def setup_tray(self):
        # Simple icon for tray
        image = Image.new('RGB', (64, 64), color='green')
        d = ImageDraw.Draw(image)
        d.ellipse((16,16,48,48), fill='white')
        self.tray_icon = pystray.Icon('trebol', image, 'Trebol', menu=pystray.Menu(
            pystray.MenuItem('Mostrar', self.show_window),
            pystray.MenuItem('Salir', self.on_close)
        ))
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.root.after(1000, self.hide_window)

    def hide_window(self):
        self.root.withdraw()

    def show_window(self, *args, **kwargs):
        self.root.deiconify()
        self.root.after(0, self.root.lift)

    def load_user_data(self):
        if os.path.isfile(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.loto_entry.insert(0, ','.join(map(str, data.get('loto', []))))
            self.plus_entry.insert(0, str(data.get('plus', '')))
            self.qui_entry.insert(0, ','.join(data.get('quiniela', [])))

    def save_user_data(self):
        loto = [int(n) for n in self.loto_entry.get().split(',') if n.strip().isdigit()]
        plus = int(self.plus_entry.get()) if self.plus_entry.get().isdigit() else None
        qui_raw = [q.strip() for q in self.qui_entry.get().split(',') if q.strip()]
        quiniela = [q.zfill(4) if len(q)<4 else q[-4:] for q in qui_raw][:3]
        data = {'loto': loto, 'plus': plus, 'quiniela': quiniela}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        logging.info('User data saved')
        messagebox.showinfo('Trebol', 'Datos guardados')

    def scrape_once(self):
        logging.info('Starting manual update')
        loto_results = self.fetch_loto()
        quiniela_results = self.fetch_quiniela()
        self.compare_and_display(loto_results, quiniela_results)

    def update_loop(self):
        while self.running:
            logging.info('Checking for updates')
            self.scrape_once()
            time.sleep(15)

    def fetch_loto(self):
        url = 'https://www.tujugada.com.ar/loto.asp'
        try:
            logging.info('Fetching Loto Plus results')
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.select('table')
            results = {}
            modalidades = ['Tradicional', 'Match', 'Desquite', 'Sale o Sale']
            for name, table in zip(modalidades, tables[:4]):
                nums = [int(td.text) for td in table.select('td') if td.text.isdigit()]
                results[name] = nums
            plus_span = soup.find('span', {'class': 'cboloto'})
            plus = int(plus_span.text.strip()) if plus_span else None
            results['Plus'] = plus
            logging.info('Fetched Loto Plus results successfully')
            return results
        except Exception as e:
            logging.exception('Error fetching Loto Plus')
            return {'error': str(e)}

    def fetch_quiniela(self):
        url = 'https://www.tujugada.com.ar/quiniela-de-hoy.asp'
        try:
            logging.info('Fetching Quiniela results')
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.select('table')
            results = {}
            for table in tables:
                heading = table.find_previous('h2')
                if not heading:
                    continue
                jurisdic = heading.text.strip()
                turnos = {}
                for row in table.select('tr')[1:]:
                    cols = [c.text.strip() for c in row.select('td')]
                    if len(cols)>=2:
                        turnos[cols[0]] = cols[1]
                results[jurisdic] = turnos
            logging.info('Fetched Quiniela results successfully')
            return results
        except Exception as e:
            logging.exception('Error fetching Quiniela')
            return {'error': str(e)}

    def compare_and_display(self, loto_results, quiniela_results):
        self.text.delete('1.0', tk.END)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.text.insert(tk.END, f'Actualizacion: {now}\n')
        self.text.insert(tk.END, '--- Loto Plus ---\n')
        user_data = self.load_from_file()
        logging.info('Displaying results')
        if 'error' in loto_results:
            self.text.insert(tk.END, f"Error al obtener Loto: {loto_results['error']}\n")
        else:
            for moda, nums in loto_results.items():
                if moda=='Plus':
                    self.text.insert(tk.END, f'Plus: {nums}\n')
                else:
                    self.text.insert(tk.END, f'{moda}: {nums}\n')
        self.text.insert(tk.END, '\n--- Quiniela ---\n')
        if 'error' in quiniela_results:
            self.text.insert(tk.END, f"Error al obtener Quiniela: {quiniela_results['error']}\n")
        else:
            for jur, tur in quiniela_results.items():
                self.text.insert(tk.END, f'{jur}\n')
                for turno, val in tur.items():
                    self.text.insert(tk.END, f' {turno}: {val}\n')
        self.text.insert(tk.END, '\n')
        if loto_results != self.previous_results:
            self.notify_sound()
        self.previous_results = loto_results

    def notify_sound(self):
        if winsound is None:
            logging.info('winsound not available; skipping beep')
            return
        try:
            winsound.MessageBeep()
        except RuntimeError:
            logging.warning('Failed to play notification sound')

    def load_from_file(self):
        if os.path.isfile(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                logging.info('Loading user data')
                return json.load(f)
        return {}

    def on_close(self, *args, **kwargs):
        logging.info('Application closing')
        self.running = False
        if HAS_TRAY and hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.destroy()


def main():
    logging.info('Starting Trebol')
    if tb:
        root = tb.Window(themename='superhero')
    else:
        root = tk.Tk()
    app = TrebolApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    try:
        root.mainloop()
    except Exception:
        logging.exception('Unhandled exception in main loop')
        raise

if __name__ == '__main__':
    main()
