"""
Interfaccia grafica Tkinter per il validatore di indirizzi.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional
import queue

from . import __version__
from .config import (
    API_KEY,
    GLS_SEDE,
    GLS_CODICE_CLIENTE,
    GLS_PASSWORD,
    GLS_CODICE_CONTRATTO,
)
from .excel_io import read_excel, write_errors, write_validated, find_excel_files
from .formats import FileFormat, format_name
from .processor import AddressProcessor
from .gls_models import GLSCredentials
from .gls_processor import GLSProcessor


class RedirectText:
    """Redirige stdout/stderr verso un widget Text."""

    def __init__(self, text_widget, message_queue):
        self.text_widget = text_widget
        self.queue = message_queue

    def write(self, string):
        self.queue.put(string)

    def flush(self):
        pass


class ValidatorGUI:
    """Interfaccia grafica principale."""

    def __init__(self, root):
        self.root = root
        self.root.title(f"Validatore Indirizzi v{__version__}")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)

        # Variabili validazione
        self.files = []
        self.api_key_var = tk.StringVar(value=API_KEY or "")
        self.dry_run_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.BooleanVar(value=False)
        self.processing = False
        self.message_queue = queue.Queue()

        # Variabili GLS
        self.gls_files = []
        self.gls_sede_var = tk.StringVar(value=GLS_SEDE or "")
        self.gls_cliente_var = tk.StringVar(value=GLS_CODICE_CLIENTE or "")
        self.gls_password_var = tk.StringVar(value=GLS_PASSWORD or "")
        self.gls_contratto_var = tk.StringVar(value=GLS_CODICE_CONTRATTO or "")
        self.gls_colli_var = tk.StringVar(value="1")
        self.gls_peso_var = tk.StringVar(value="3.0")
        self.gls_skip_uploaded_var = tk.BooleanVar(value=True)
        self.gls_close_workday_var = tk.BooleanVar(value=False)
        self.gls_generate_pdf_var = tk.BooleanVar(value=False)
        self.gls_processing = False
        self.gls_message_queue = queue.Queue()

        # Stile
        self.style = ttk.Style()
        self.style.configure("Title.TLabel", font=("Helvetica", 14, "bold"))
        self.style.configure("Status.TLabel", font=("Helvetica", 10))

        self._create_widgets()
        self._check_queue()
        self._check_gls_queue()

    def _create_widgets(self):
        """Crea tutti i widget dell'interfaccia."""
        # Frame principale con padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Notebook per le tab
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Tab Validazione
        validation_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(validation_frame, text="Validazione Indirizzi")
        validation_frame.columnconfigure(0, weight=1)

        # Tab GLS
        gls_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(gls_frame, text="Upload GLS")
        gls_frame.columnconfigure(0, weight=1)

        # Crea contenuti delle tab
        self._create_validation_tab(validation_frame)
        self._create_gls_tab(gls_frame)

    def _create_validation_tab(self, main_frame):
        """Crea il contenuto della tab Validazione."""
        main_frame.columnconfigure(0, weight=1)

        # === SEZIONE FILE ===
        file_frame = ttk.LabelFrame(main_frame, text="File Excel", padding="10")
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)

        # Lista file
        self.file_listbox = tk.Listbox(file_frame, height=4, selectmode=tk.EXTENDED)
        self.file_listbox.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        # Scrollbar per lista
        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

        # Pulsanti file
        btn_frame = ttk.Frame(file_frame)
        btn_frame.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        ttk.Button(btn_frame, text="Aggiungi File", command=self._add_files).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Aggiungi Cartella", command=self._add_folder).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Rimuovi", command=self._remove_files).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Pulisci", command=self._clear_files).pack(fill="x", pady=2)

        # Label conteggio
        self.file_count_label = ttk.Label(file_frame, text="0 file selezionati")
        self.file_count_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # === SEZIONE API KEY ===
        api_frame = ttk.LabelFrame(main_frame, text="Google Maps API Key", padding="10")
        api_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        api_frame.columnconfigure(1, weight=1)

        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.api_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=50)
        self.api_entry.grid(row=0, column=1, sticky="ew")

        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            api_frame, text="Mostra", variable=self.show_key_var, command=self._toggle_key_visibility
        ).grid(row=0, column=2, padx=(10, 0))

        ttk.Label(
            api_frame, text="Imposta GOOGLE_MAPS_API_KEY come variabile d'ambiente per evitare di inserirla ogni volta",
            font=("Helvetica", 9), foreground="gray"
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # === SEZIONE OPZIONI ===
        opt_frame = ttk.LabelFrame(main_frame, text="Opzioni", padding="10")
        opt_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ttk.Checkbutton(opt_frame, text="Dry Run (simula senza scrivere file)", variable=self.dry_run_var).pack(anchor="w")
        ttk.Checkbutton(opt_frame, text="Verbose (mostra dettagli)", variable=self.verbose_var).pack(anchor="w")

        # === SEZIONE PULSANTI AZIONE ===
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(
            action_frame, text="▶ Avvia Validazione", command=self._start_processing, style="Accent.TButton"
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.stop_btn = ttk.Button(action_frame, text="⏹ Interrompi", command=self._stop_processing, state="disabled")
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # === PROGRESS BAR ===
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress.grid(row=4, column=0, sticky="ew", pady=(0, 5))

        self.status_label = ttk.Label(main_frame, text="Pronto", style="Status.TLabel")
        self.status_label.grid(row=5, column=0, sticky="w", pady=(0, 10))

        # === LOG OUTPUT ===
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # Pulsante pulisci log
        ttk.Button(log_frame, text="Pulisci Log", command=self._clear_log).grid(row=1, column=0, sticky="e", pady=(5, 0))

        # === SEZIONE OUTPUT ===
        out_frame = ttk.Frame(main_frame)
        out_frame.grid(row=7, column=0, sticky="ew")

        ttk.Button(out_frame, text="📂 Apri Cartella Output", command=self._open_output_folder).pack(side="left")
        ttk.Label(out_frame, text=f"v{__version__}", foreground="gray").pack(side="right")

    def _toggle_key_visibility(self):
        """Mostra/nasconde la API key."""
        if self.show_key_var.get():
            self.api_entry.configure(show="")
        else:
            self.api_entry.configure(show="*")

    def _add_files(self):
        """Aggiunge file Excel."""
        files = filedialog.askopenfilenames(
            title="Seleziona file Excel",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        for f in files:
            if f not in self.files and not f.endswith(("_VALIDATO.xlsx", "_NON_VALIDATI.xlsx")):
                self.files.append(f)
                self.file_listbox.insert(tk.END, Path(f).name)
        self._update_file_count()

    def _add_folder(self):
        """Aggiunge tutti i file Excel da una cartella."""
        folder = filedialog.askdirectory(title="Seleziona cartella")
        if folder:
            excel_files = find_excel_files(folder)
            for f in excel_files:
                f_str = str(f)
                if f_str not in self.files:
                    self.files.append(f_str)
                    self.file_listbox.insert(tk.END, f.name)
            self._update_file_count()

    def _remove_files(self):
        """Rimuove i file selezionati."""
        selected = list(self.file_listbox.curselection())
        for i in reversed(selected):
            self.file_listbox.delete(i)
            del self.files[i]
        self._update_file_count()

    def _clear_files(self):
        """Rimuove tutti i file."""
        self.file_listbox.delete(0, tk.END)
        self.files = []
        self._update_file_count()

    def _update_file_count(self):
        """Aggiorna il conteggio file."""
        count = len(self.files)
        self.file_count_label.configure(text=f"{count} file selezionat{'o' if count == 1 else 'i'}")

    def _log(self, message: str):
        """Aggiunge messaggio al log."""
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        """Pulisce il log."""
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")

    def _check_queue(self):
        """Controlla la coda messaggi per aggiornare il log."""
        while True:
            try:
                message = self.message_queue.get_nowait()
                self._log(message)
            except queue.Empty:
                break
        self.root.after(100, self._check_queue)

    def _start_processing(self):
        """Avvia l'elaborazione in un thread separato."""
        if not self.files:
            messagebox.showwarning("Attenzione", "Seleziona almeno un file Excel")
            return

        api_key = self.api_key_var.get().strip()
        if not api_key and not self.dry_run_var.get():
            messagebox.showerror("Errore", "Inserisci la API key Google Maps\n\nPuoi ottenerla da:\nhttps://console.cloud.google.com/apis/credentials")
            return

        self.processing = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_var.set(0)
        self._clear_log()

        # Avvia thread elaborazione
        thread = threading.Thread(target=self._process_files, daemon=True)
        thread.start()

    def _stop_processing(self):
        """Interrompe l'elaborazione."""
        self.processing = False
        self.status_label.configure(text="Interruzione in corso...")

    def _process_files(self):
        """Elabora i file (eseguito in thread separato)."""
        import sys
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = RedirectText(self.log_text, self.message_queue)
        sys.stderr = RedirectText(self.log_text, self.message_queue)

        try:
            api_key = self.api_key_var.get().strip() or None
            dry_run = self.dry_run_var.get()
            verbose = self.verbose_var.get()

            processor = AddressProcessor(api_key=api_key, verbose=verbose)
            total_files = len(self.files)
            total_valid = 0
            total_invalid = 0

            for i, file_path in enumerate(self.files):
                if not self.processing:
                    self.message_queue.put("\n⚠ Elaborazione interrotta dall'utente\n")
                    break

                self.root.after(0, lambda p=(i / total_files * 100): self.progress_var.set(p))
                self.root.after(0, lambda f=Path(file_path).name, n=i+1, t=total_files:
                    self.status_label.configure(text=f"Elaborazione {n}/{t}: {f}"))

                try:
                    stats = processor.process_file(file_path, dry_run=dry_run)

                    if not dry_run and "valid" in stats:
                        total_valid += stats.get("valid", 0)
                        total_invalid += stats.get("invalid", 0)

                except Exception as e:
                    self.message_queue.put(f"\n❌ ERRORE: {e}\n")

            # Riepilogo finale
            self.root.after(0, lambda: self.progress_var.set(100))

            if not dry_run and self.processing:
                self.message_queue.put(f"\n{'='*50}\n")
                self.message_queue.put(f"COMPLETATO: {total_valid} validati, {total_invalid} errori\n")
                self.message_queue.put(f"{'='*50}\n")

            self.root.after(0, lambda: self.status_label.configure(
                text="Completato" if self.processing else "Interrotto"
            ))

        except Exception as e:
            self.message_queue.put(f"\n❌ ERRORE CRITICO: {e}\n")
            self.root.after(0, lambda: self.status_label.configure(text="Errore"))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.processing = False
            self.root.after(0, lambda: self.start_btn.configure(state="normal"))
            self.root.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def _open_output_folder(self):
        """Apre la cartella del primo file."""
        if self.files:
            folder = Path(self.files[0]).parent
        else:
            folder = Path.cwd()

        if os.name == "nt":  # Windows
            os.startfile(folder)
        elif os.name == "posix":  # macOS/Linux
            import subprocess
            subprocess.run(["open" if os.uname().sysname == "Darwin" else "xdg-open", str(folder)])

    # ==================== SEZIONE GLS ====================

    def _create_gls_tab(self, main_frame):
        """Crea il contenuto della tab Upload GLS."""
        main_frame.columnconfigure(0, weight=1)

        # === SEZIONE CREDENZIALI GLS ===
        cred_frame = ttk.LabelFrame(main_frame, text="Credenziali GLS", padding="10")
        cred_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        cred_frame.columnconfigure(1, weight=1)
        cred_frame.columnconfigure(3, weight=1)

        ttk.Label(cred_frame, text="Sede:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ttk.Entry(cred_frame, textvariable=self.gls_sede_var, width=10).grid(row=0, column=1, sticky="w")

        ttk.Label(cred_frame, text="Codice Cliente:").grid(row=0, column=2, sticky="w", padx=(20, 5))
        ttk.Entry(cred_frame, textvariable=self.gls_cliente_var, width=15).grid(row=0, column=3, sticky="w")

        ttk.Label(cred_frame, text="Password:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.gls_pwd_entry = ttk.Entry(cred_frame, textvariable=self.gls_password_var, show="*", width=20)
        self.gls_pwd_entry.grid(row=1, column=1, sticky="w", pady=(5, 0))

        ttk.Label(cred_frame, text="Contratto:").grid(row=1, column=2, sticky="w", padx=(20, 5), pady=(5, 0))
        ttk.Entry(cred_frame, textvariable=self.gls_contratto_var, width=10).grid(row=1, column=3, sticky="w", pady=(5, 0))

        ttk.Button(cred_frame, text="Test Connessione", command=self._test_gls_connection).grid(
            row=0, column=4, rowspan=2, padx=(20, 0), sticky="ns"
        )

        ttk.Label(
            cred_frame,
            text="Imposta GLS_SEDE, GLS_CODICE_CLIENTE, GLS_PASSWORD, GLS_CODICE_CONTRATTO nel file .env",
            font=("Helvetica", 9), foreground="gray"
        ).grid(row=2, column=0, columnspan=5, sticky="w", pady=(5, 0))

        # === SEZIONE FILE VALIDATI ===
        file_frame = ttk.LabelFrame(main_frame, text="File Validati", padding="10")
        file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)

        # Lista file
        self.gls_file_listbox = tk.Listbox(file_frame, height=4, selectmode=tk.EXTENDED)
        self.gls_file_listbox.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.gls_file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.gls_file_listbox.configure(yscrollcommand=scrollbar.set)

        # Pulsanti file
        btn_frame = ttk.Frame(file_frame)
        btn_frame.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        ttk.Button(btn_frame, text="Aggiungi File", command=self._gls_add_files).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Cerca *_VALIDATO", command=self._gls_find_validated).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Rimuovi", command=self._gls_remove_files).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Pulisci", command=self._gls_clear_files).pack(fill="x", pady=2)

        self.gls_file_count_label = ttk.Label(file_frame, text="0 file selezionati")
        self.gls_file_count_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # === SEZIONE CONFIGURAZIONE SPEDIZIONE ===
        config_frame = ttk.LabelFrame(main_frame, text="Configurazione Spedizione", padding="10")
        config_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(config_frame, text="Colli:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        colli_spin = ttk.Spinbox(config_frame, textvariable=self.gls_colli_var, from_=1, to=99, width=5)
        colli_spin.grid(row=0, column=1, sticky="w")

        ttk.Label(config_frame, text="Peso (kg):").grid(row=0, column=2, sticky="w", padx=(20, 5))
        peso_spin = ttk.Spinbox(config_frame, textvariable=self.gls_peso_var, from_=0.1, to=999, increment=0.5, width=8)
        peso_spin.grid(row=0, column=3, sticky="w")

        ttk.Label(
            config_frame,
            text="Per file OLD: 1 collo, 3kg | Per file NEW: 2 colli, 3kg",
            font=("Helvetica", 9), foreground="gray"
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(5, 0))

        # === SEZIONE OPZIONI GLS ===
        opt_frame = ttk.LabelFrame(main_frame, text="Opzioni Upload", padding="10")
        opt_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        ttk.Checkbutton(
            opt_frame, text="Salta righe già caricate", variable=self.gls_skip_uploaded_var
        ).grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(
            opt_frame, text="Chiudi giornata (CloseWorkDay)", variable=self.gls_close_workday_var
        ).grid(row=0, column=1, sticky="w", padx=(20, 0))

        ttk.Checkbutton(
            opt_frame, text="Genera PDF etichette", variable=self.gls_generate_pdf_var
        ).grid(row=0, column=2, sticky="w", padx=(20, 0))

        # === PULSANTI AZIONE GLS ===
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)

        self.gls_start_btn = ttk.Button(
            action_frame, text="▶ Upload a GLS", command=self._start_gls_upload
        )
        self.gls_start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.gls_stop_btn = ttk.Button(
            action_frame, text="⏹ Interrompi", command=self._stop_gls_upload, state="disabled"
        )
        self.gls_stop_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # === PROGRESS BAR GLS ===
        self.gls_progress_var = tk.DoubleVar(value=0)
        self.gls_progress = ttk.Progressbar(main_frame, variable=self.gls_progress_var, maximum=100)
        self.gls_progress.grid(row=5, column=0, sticky="ew", pady=(0, 5))

        self.gls_status_label = ttk.Label(main_frame, text="Pronto", style="Status.TLabel")
        self.gls_status_label.grid(row=6, column=0, sticky="w", pady=(0, 10))

        # === LOG GLS ===
        log_frame = ttk.LabelFrame(main_frame, text="Log Upload", padding="5")
        log_frame.grid(row=7, column=0, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)

        self.gls_log_text = scrolledtext.ScrolledText(log_frame, height=10, state="disabled", wrap="word")
        self.gls_log_text.grid(row=0, column=0, sticky="nsew")

        ttk.Button(log_frame, text="Pulisci Log", command=self._gls_clear_log).grid(
            row=1, column=0, sticky="e", pady=(5, 0)
        )

    def _check_gls_queue(self):
        """Controlla la coda messaggi GLS."""
        while True:
            try:
                message = self.gls_message_queue.get_nowait()
                self._gls_log(message)
            except queue.Empty:
                break
        self.root.after(100, self._check_gls_queue)

    def _gls_log(self, message: str):
        """Aggiunge messaggio al log GLS."""
        self.gls_log_text.configure(state="normal")
        self.gls_log_text.insert(tk.END, message)
        self.gls_log_text.see(tk.END)
        self.gls_log_text.configure(state="disabled")

    def _gls_clear_log(self):
        """Pulisce il log GLS."""
        self.gls_log_text.configure(state="normal")
        self.gls_log_text.delete(1.0, tk.END)
        self.gls_log_text.configure(state="disabled")

    def _gls_add_files(self):
        """Aggiunge file validati per GLS."""
        files = filedialog.askopenfilenames(
            title="Seleziona file validati",
            filetypes=[("File validati", "*_VALIDATO.xlsx"), ("Excel files", "*.xlsx")]
        )
        for f in files:
            if f not in self.gls_files:
                self.gls_files.append(f)
                self.gls_file_listbox.insert(tk.END, Path(f).name)
        self._gls_update_file_count()

    def _gls_find_validated(self):
        """Cerca file *_VALIDATO.xlsx nella cartella."""
        folder = filedialog.askdirectory(title="Seleziona cartella")
        if folder:
            for f in Path(folder).glob("*_VALIDATO.xlsx"):
                f_str = str(f)
                if f_str not in self.gls_files:
                    self.gls_files.append(f_str)
                    self.gls_file_listbox.insert(tk.END, f.name)
            self._gls_update_file_count()

    def _gls_remove_files(self):
        """Rimuove i file selezionati dalla lista GLS."""
        selected = list(self.gls_file_listbox.curselection())
        for i in reversed(selected):
            self.gls_file_listbox.delete(i)
            del self.gls_files[i]
        self._gls_update_file_count()

    def _gls_clear_files(self):
        """Rimuove tutti i file dalla lista GLS."""
        self.gls_file_listbox.delete(0, tk.END)
        self.gls_files = []
        self._gls_update_file_count()

    def _gls_update_file_count(self):
        """Aggiorna il conteggio file GLS."""
        count = len(self.gls_files)
        self.gls_file_count_label.configure(text=f"{count} file selezionat{'o' if count == 1 else 'i'}")

    def _get_gls_credentials(self) -> Optional[GLSCredentials]:
        """Ottiene le credenziali GLS validate."""
        creds = GLSCredentials(
            sede=self.gls_sede_var.get().strip(),
            codice_cliente=self.gls_cliente_var.get().strip(),
            password=self.gls_password_var.get().strip(),
            codice_contratto=self.gls_contratto_var.get().strip(),
        )
        if not creds.is_valid():
            return None
        return creds

    def _test_gls_connection(self):
        """Testa la connessione a GLS."""
        creds = self._get_gls_credentials()
        if not creds:
            messagebox.showerror("Errore", "Inserisci tutte le credenziali GLS")
            return

        try:
            processor = GLSProcessor(creds)
            success, message = processor.test_credentials()
            if success:
                messagebox.showinfo("Successo", f"Connessione riuscita!\n{message}")
            else:
                messagebox.showerror("Errore", f"Connessione fallita:\n{message}")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore di connessione:\n{e}")

    def _start_gls_upload(self):
        """Avvia l'upload GLS in un thread separato."""
        if not self.gls_files:
            messagebox.showwarning("Attenzione", "Seleziona almeno un file validato")
            return

        creds = self._get_gls_credentials()
        if not creds:
            messagebox.showerror("Errore", "Inserisci tutte le credenziali GLS")
            return

        try:
            colli = int(self.gls_colli_var.get())
            peso = float(self.gls_peso_var.get())
        except ValueError:
            messagebox.showerror("Errore", "Colli e Peso devono essere numeri validi")
            return

        self.gls_processing = True
        self.gls_start_btn.configure(state="disabled")
        self.gls_stop_btn.configure(state="normal")
        self.gls_progress_var.set(0)
        self._gls_clear_log()

        thread = threading.Thread(
            target=self._process_gls_upload,
            args=(creds, colli, peso),
            daemon=True
        )
        thread.start()

    def _stop_gls_upload(self):
        """Interrompe l'upload GLS."""
        self.gls_processing = False
        self.gls_status_label.configure(text="Interruzione in corso...")

    def _process_gls_upload(self, creds: GLSCredentials, colli: int, peso: float):
        """Elabora l'upload GLS (eseguito in thread separato)."""
        try:
            skip_uploaded = self.gls_skip_uploaded_var.get()
            close_workday = self.gls_close_workday_var.get()
            generate_pdf = self.gls_generate_pdf_var.get()

            def progress_callback(current, total, message):
                if total > 0:
                    pct = (current / total) * 100
                    self.root.after(0, lambda: self.gls_progress_var.set(pct))
                self.root.after(0, lambda m=message: self.gls_status_label.configure(text=m))

            processor = GLSProcessor(
                creds,
                skip_uploaded=skip_uploaded,
                progress_callback=progress_callback,
            )

            total_files = len(self.gls_files)
            total_uploaded = 0
            total_failed = 0
            total_skipped = 0

            for i, file_path in enumerate(self.gls_files):
                if not self.gls_processing:
                    self.gls_message_queue.put("\n⚠ Upload interrotto dall'utente\n")
                    break

                file_name = Path(file_path).name
                self.gls_message_queue.put(f"\n{'='*50}\n")
                self.gls_message_queue.put(f"File {i+1}/{total_files}: {file_name}\n")

                # Determina colli/peso automatici per OLD/NEW
                default_config = processor.get_default_parcel_config(file_path)
                file_colli = default_config.get("colli") or colli
                file_peso = default_config.get("peso") or peso

                self.gls_message_queue.put(f"Configurazione: {file_colli} colli, {file_peso} kg\n")

                try:
                    result = processor.process_file(
                        file_path,
                        colli=file_colli,
                        peso=file_peso,
                        generate_pdf=generate_pdf,
                        close_workday=close_workday and (i == total_files - 1),
                    )

                    total_uploaded += result.uploaded
                    total_failed += result.failed
                    total_skipped += result.skipped

                    self.gls_message_queue.put(f"\n{result.summary()}\n")

                    if result.errors:
                        self.gls_message_queue.put("\nErrori:\n")
                        for err in result.errors[:10]:  # Max 10 errori
                            self.gls_message_queue.put(f"  - {err}\n")
                        if len(result.errors) > 10:
                            self.gls_message_queue.put(f"  ... e altri {len(result.errors) - 10} errori\n")

                except Exception as e:
                    self.gls_message_queue.put(f"\n❌ ERRORE: {e}\n")
                    total_failed += 1

            # Riepilogo finale
            self.root.after(0, lambda: self.gls_progress_var.set(100))

            if self.gls_processing:
                self.gls_message_queue.put(f"\n{'='*50}\n")
                self.gls_message_queue.put(f"COMPLETATO\n")
                self.gls_message_queue.put(f"Caricati: {total_uploaded}\n")
                self.gls_message_queue.put(f"Saltati: {total_skipped}\n")
                self.gls_message_queue.put(f"Errori: {total_failed}\n")
                self.gls_message_queue.put(f"{'='*50}\n")

            self.root.after(0, lambda: self.gls_status_label.configure(
                text="Completato" if self.gls_processing else "Interrotto"
            ))

        except Exception as e:
            self.gls_message_queue.put(f"\n❌ ERRORE CRITICO: {e}\n")
            self.root.after(0, lambda: self.gls_status_label.configure(text="Errore"))

        finally:
            self.gls_processing = False
            self.root.after(0, lambda: self.gls_start_btn.configure(state="normal"))
            self.root.after(0, lambda: self.gls_stop_btn.configure(state="disabled"))


def main():
    """Entry point per la GUI."""
    root = tk.Tk()

    # Icona (opzionale)
    try:
        # Su macOS, imposta come app normale
        if os.name == "posix" and os.uname().sysname == "Darwin":
            root.createcommand('tk::mac::ReopenApplication', lambda: root.lift())
    except:
        pass

    app = ValidatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
