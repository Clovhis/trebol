import json
import logging
import os
import threading
import itertools
import time
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta

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
import re

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
        self.previous_results = None
        self.spinner_running = False
        if HAS_TRAY:
            self.setup_tray()

    def create_widgets(self):
        big_font = ("Helvetica", 16)

        self.loto_frame = tk.Frame(self.root, bg="red", padx=10, pady=10)
        self.loto_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(self.loto_frame, text="Loto Plus", bg="red", fg="white", font=("Helvetica", 18, "bold")).grid(row=0, column=0, columnspan=7, pady=5)
        self.loto_entries = []
        for i in range(6):
            e = tk.Entry(self.loto_frame, width=3, font=big_font, justify="center")
            e.grid(row=1, column=i, padx=3, pady=5)
            self.loto_entries.append(e)

        tk.Label(self.loto_frame, text="Número Plus", bg="red", fg="white", font=big_font).grid(row=2, column=0, columnspan=6, pady=5)
        self.plus_entry = tk.Entry(self.loto_frame, width=2, font=big_font, justify="center")
        self.plus_entry.grid(row=3, column=0, padx=3, pady=5, columnspan=6)

        self.loto_info = tk.Label(self.loto_frame, text="", bg="red", fg="white", font=big_font)
        self.loto_info.grid(row=4, column=0, columnspan=7, pady=5)

        self.text_frame = tk.Frame(self.root, bg="light grey", padx=10, pady=10)
        self.text_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.text = tk.Text(self.text_frame, width=70, height=15, font=("Helvetica", 14), wrap="word")
        self.text.pack(side="left", fill="both", expand=True)
        self.scroll = ttk.Scrollbar(self.text_frame, command=self.text.yview)
        self.scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=self.scroll.set)

        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack()
        btn_style = 'primary.TButton' if tb else 'TButton'
        danger_style = 'danger.TButton' if tb else 'TButton'
        self.check_btn = ttk.Button(btn_frame, text='Checkeá mi jugada', command=self.scrape_once, style=btn_style, width=20)
        self.check_btn.pack(side='left', padx=5)

        self.exit_btn = ttk.Button(self.root, text='Salir', command=self.on_close, style=danger_style)
        self.exit_btn.place(relx=1.0, rely=0.0, anchor='ne', x=-10, y=10)

        self.status_var = tk.StringVar(value='Listo')
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, anchor='w')
        self.status_label.pack(fill='x', padx=5, pady=5)

        if tb:
            for btn in (self.check_btn, self.exit_btn):
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
        # Do not hide the main window automatically so users can interact

    def hide_window(self):
        self.root.withdraw()

    def show_window(self, *args, **kwargs):
        self.root.deiconify()
        self.root.after(0, self.root.lift)

    def load_user_data(self):
        if not os.path.isfile(USERS_FILE):
            return
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        loto = data.get('loto', [])
        for entry, val in zip(self.loto_entries, loto):
            entry.insert(0, str(val).zfill(2))
        if 'plus' in data and data['plus'] is not None:
            self.plus_entry.insert(0, str(data['plus']))

    def save_user_data(self):
        loto = []
        for e in self.loto_entries:
            v = e.get().strip()
            if v.isdigit():
                loto.append(int(v))
        plus = int(self.plus_entry.get()) if self.plus_entry.get().isdigit() else None
        data = {'loto': loto, 'plus': plus}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        logging.info('User data saved')

    def start_spinner(self):
        self.spinner_running = True
        def spin():
            for c in itertools.cycle('|/-\\'):
                if not self.spinner_running:
                    break
                self.status_var.set(f'Buscando los resultados en TuJugada.com... {c}')
                time.sleep(0.1)
        threading.Thread(target=spin, daemon=True).start()

    def stop_spinner(self):
        self.spinner_running = False

    def scrape_once(self):
        logging.info('Starting manual update')
        self.start_spinner()
        loto_results = self.fetch_loto()
        self.stop_spinner()
        self.status_var.set('Analizando resultados...')
        self.root.update_idletasks()
        self.compare_and_display(loto_results)
        self.save_user_data()
        self.status_var.set('Listo')

    def fetch_loto(self):
        """Scrape Loto Plus results using a text proxy."""
        url = 'https://r.jina.ai/https://www.tujugada.com.ar/loto.asp'
        try:
            logging.info('Fetching Loto Plus results')
            text = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
            results = {}
            header = re.search(r"LOTO PLUS Nro: (\d+) - ([0-9/]+)", text)
            if header:
                results['sorteo'] = header.group(1)
                results['fecha'] = header.group(2)
            tokens = text.split('**')
            modalidades = ['TRADICIONAL', 'MATCH', 'DESQUITE', 'SALE O SALE']
            for moda in modalidades:
                try:
                    idx = tokens.index(moda)
                except ValueError:
                    continue
                numbers = []
                i = idx + 1
                while i < len(tokens) and len(numbers) < 6:
                    t = tokens[i].strip()
                    if t.isdigit():
                        numbers.append(int(t))
                    i += 1
                info = {'numeros': numbers}
                try:
                    j = tokens.index(f'PREMIOS SORTEO {moda}')
                    status = tokens[j + 10].strip()
                    pozo = tokens[j + 12].strip()
                    info['ganadores'] = status
                    info['pozo'] = pozo
                except ValueError:
                    pass
                results[moda.capitalize()] = info
            plus_match = re.search(r"N\u00famero plus:\*\*\s*\*\*(\d+)\*\*", text)
            if plus_match:
                results['Plus'] = int(plus_match.group(1))
            logging.info('Fetched Loto Plus results successfully')
            return results
        except Exception as e:
            logging.exception('Error fetching Loto Plus')
            return {'error': str(e)}

    def calculate_next_draw(self, fecha_str: str) -> str:
        try:
            d = datetime.strptime(fecha_str, '%d/%m/%Y')
        except Exception:
            d = datetime.now()
        d += timedelta(days=1)
        while d.weekday() not in (2, 5):  # Wednesday or Saturday
            d += timedelta(days=1)
        d = d.replace(hour=22, minute=0, second=0)
        return d.strftime('%d/%m/%Y %H:%M')

    def compare_and_display(self, loto_results):
        self.text.delete('1.0', tk.END)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.text.insert(tk.END, f'Actualizacion: {now}\n')
        logging.info('Displaying results')

        if 'error' in loto_results:
            self.text.insert(tk.END, f"Error al obtener Loto: {loto_results['error']}\n")
            return

        sorteo = loto_results.get('sorteo', '')
        fecha = loto_results.get('fecha', '')
        trad = loto_results.get('Tradicional', {})
        status = ''
        if trad:
            gan = trad.get('ganadores', '')
            pozo = trad.get('pozo', '')
            status = f'GANADORES : {gan} | POZO: {pozo}'

        next_draw = self.calculate_next_draw(fecha)
        self.loto_info.config(text=f'Sorteo {sorteo} - {fecha} {status} | Próximo sorteo: {next_draw}')

        result_numbers = trad.get('numeros', [])
        plus_num = loto_results.get('Plus')

        for e in self.loto_entries:
            e.config(bg='white', fg='black')
        self.plus_entry.config(bg='white', fg='black')

        for e in self.loto_entries:
            val = e.get().strip()
            if val.isdigit():
                n = int(val)
                if n in result_numbers:
                    e.config(bg='green', fg='white')
                else:
                    e.config(bg='red', fg='white')

        val = self.plus_entry.get().strip()
        if val.isdigit() and plus_num is not None:
            if int(val) == plus_num:
                self.plus_entry.config(bg='green', fg='white')
            else:
                self.plus_entry.config(bg='red', fg='white')

        self.text.insert(tk.END, '--- Loto Plus ---\n')
        for moda, info in loto_results.items():
            if moda in ('sorteo', 'fecha', 'Plus'):
                continue
            nums = info.get('numeros', [])
            gan = info.get('ganadores', '')
            pozo = info.get('pozo', '')
            line = f"{moda}: {nums}"
            if gan or pozo:
                line += f" | GANADORES: {gan} | POZO: {pozo}"
            self.text.insert(tk.END, line + '\n')
        if plus_num is not None:
            self.text.insert(tk.END, f'Plus: {plus_num}\n')

        self.text.insert(tk.END, f'Próximo sorteo: {next_draw}\n')

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
        if HAS_TRAY and hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.destroy()


def main():
    logging.info('Starting Trebol')
    if tb:
        root = tb.Window(themename='superhero')
    else:
        root = tk.Tk()
    root.geometry('700x600')
    app = TrebolApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    try:
        root.mainloop()
    except Exception:
        logging.exception('Unhandled exception in main loop')
        raise

if __name__ == '__main__':
    main()
