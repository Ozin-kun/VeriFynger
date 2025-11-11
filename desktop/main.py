import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import paho.mqtt.client as mqtt
import json
import threading
import time
from datetime import datetime
import sqlite3
import base64
import csv

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ VeriFynger - Sistem Presensi Fingerprint")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # Setup tema dan styling
        self.setup_theme()
        
        # MQTT Configuration
        self.mqtt_broker = "localhost"  # Ganti dengan IP broker Anda
        self.mqtt_port = 1883
        self.mqtt_client = None
        self.is_connected = False
        
        # MQTT Topics
        self.TOPIC_COMMAND = "fingerprint/command"
        self.TOPIC_RESPONSE = "fingerprint/response"
        self.TOPIC_ATTENDANCE = "fingerprint/attendance"
        self.TOPIC_TEMPLATE = "fingerprint/template"
        
        self.users = {}
        
        # Inisialisasi database
        self.init_database()
        
        # Setup UI
        self.setup_ui()
        
        # Load settings
        self.load_settings()
    
    def setup_theme(self):
        """Setup tema warna ungu muda yang menarik"""
        # Warna palette ungu muda
        self.colors = {
            'primary': '#9B7EDE',      # Ungu muda utama
            'secondary': '#C8B6E2',    # Ungu lebih terang
            'accent': '#7B68EE',       # Ungu accent
            'bg_main': '#F5F3FF',      # Background putih ungu
            'bg_frame': '#FFFFFF',     # Background putih bersih
            'text_dark': '#4A4A4A',    # Text gelap
            'text_light': '#FFFFFF',   # Text putih
            'success': '#7CB342',      # Hijau untuk sukses
            'warning': '#FFA726',      # Orange untuk warning
            'error': '#EF5350',        # Merah untuk error
            'hover': '#8B6FD9',        # Ungu hover
        }
        
        # Set background root
        self.root.configure(bg=self.colors['bg_main'])
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure TFrame
        style.configure('TFrame', background=self.colors['bg_main'])
        style.configure('Card.TFrame', background=self.colors['bg_frame'], 
                       relief='flat', borderwidth=0)
        
        # Configure TLabelFrame
        style.configure('TLabelframe', background=self.colors['bg_main'],
                       foreground=self.colors['primary'], font=('Segoe UI', 10, 'bold'))
        style.configure('TLabelframe.Label', background=self.colors['bg_main'],
                       foreground=self.colors['primary'], font=('Segoe UI', 10, 'bold'))
        
        # Configure TLabel
        style.configure('TLabel', background=self.colors['bg_main'],
                       foreground=self.colors['text_dark'], font=('Segoe UI', 9))
        style.configure('Title.TLabel', background=self.colors['bg_main'],
                       foreground=self.colors['primary'], font=('Segoe UI', 14, 'bold'))
        style.configure('Header.TLabel', background=self.colors['bg_main'],
                       foreground=self.colors['primary'], font=('Segoe UI', 11, 'bold'))
        
        # Configure TButton dengan efek hover
        style.configure('TButton', 
                       background=self.colors['primary'],
                       foreground=self.colors['text_light'],
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 9, 'bold'),
                       padding=(15, 8))
        style.map('TButton',
                 background=[('active', self.colors['hover']),
                           ('pressed', self.colors['accent'])])
        
        # Button styles khusus
        style.configure('Accent.TButton',
                       background=self.colors['accent'],
                       foreground=self.colors['text_light'],
                       font=('Segoe UI', 10, 'bold'),
                       padding=(20, 10))
        style.map('Accent.TButton',
                 background=[('active', self.colors['hover']),
                           ('pressed', self.colors['primary'])])
        
        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground=self.colors['text_light'])
        style.map('Success.TButton',
                 background=[('active', '#689F38')])
        
        style.configure('Warning.TButton',
                       background=self.colors['warning'],
                       foreground=self.colors['text_light'])
        style.map('Warning.TButton',
                 background=[('active', '#FB8C00')])
        
        style.configure('Error.TButton',
                       background=self.colors['error'],
                       foreground=self.colors['text_light'])
        style.map('Error.TButton',
                 background=[('active', '#E53935')])
        
        # Configure TEntry
        style.configure('TEntry',
                       fieldbackground='white',
                       foreground=self.colors['text_dark'],
                       borderwidth=2,
                       relief='flat',
                       padding=8)
        
        # Configure TNotebook
        style.configure('TNotebook', background=self.colors['bg_main'], borderwidth=0)
        style.configure('TNotebook.Tab',
                       background=self.colors['secondary'],
                       foreground=self.colors['text_dark'],
                       padding=[20, 10],
                       font=('Segoe UI', 10, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['primary'])],
                 foreground=[('selected', self.colors['text_light'])],
                 expand=[('selected', [1, 1, 1, 0])])
        
        # Configure Treeview
        style.configure('Treeview',
                       background='white',
                       foreground=self.colors['text_dark'],
                       fieldbackground='white',
                       borderwidth=0,
                       font=('Segoe UI', 9))
        style.configure('Treeview.Heading',
                       background=self.colors['primary'],
                       foreground=self.colors['text_light'],
                       borderwidth=0,
                       font=('Segoe UI', 10, 'bold'))
        style.map('Treeview',
                 background=[('selected', self.colors['secondary'])],
                 foreground=[('selected', self.colors['text_dark'])])
        
        # Configure Radiobutton
        style.configure('TRadiobutton',
                       background=self.colors['bg_main'],
                       foreground=self.colors['text_dark'],
                       font=('Segoe UI', 10))
        style.map('TRadiobutton',
                 background=[('active', self.colors['bg_main'])])
    
    def init_database(self):
        """Inisialisasi database SQLite"""
        self.conn = sqlite3.connect('attendance.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Tabel users dengan template fingerprint
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                position TEXT,
                fingerprint_template BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabel attendance logs
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                match_score INTEGER,
                location TEXT DEFAULT 'Default Location',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabel settings
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_user_id ON attendance_logs(user_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_time ON attendance_logs(check_in_time)')
        
        self.conn.commit()
        self.load_users_from_db()
    
    def load_users_from_db(self):
        """Load users dari database"""
        self.cursor.execute('SELECT id, name FROM users')
        for user_id, name in self.cursor.fetchall():
            self.users[user_id] = name
    
    def load_settings(self):
        """Load settings dari database"""
        self.cursor.execute('SELECT key, value FROM settings')
        settings = dict(self.cursor.fetchall())
        
        if 'mqtt_broker' in settings:
            self.mqtt_broker = settings['mqtt_broker']
            self.entry_broker.delete(0, tk.END)
            self.entry_broker.insert(0, self.mqtt_broker)
        
        if 'mqtt_port' in settings:
            self.mqtt_port = int(settings['mqtt_port'])
            self.entry_port.delete(0, tk.END)
            self.entry_port.insert(0, str(self.mqtt_port))
    
    def save_settings(self):
        """Simpan settings ke database"""
        self.cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                          ('mqtt_broker', self.mqtt_broker))
        self.cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                          ('mqtt_port', str(self.mqtt_port)))
        self.conn.commit()
    
    def setup_ui(self):
        """Setup antarmuka"""
        # Header dengan gradient effect
        header_frame = tk.Frame(self.root, bg=self.colors['primary'], height=70)
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, 
                              text="✨ VeriFynger", 
                              bg=self.colors['primary'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 24, 'bold'))
        title_label.pack(side="left", padx=30, pady=15)
        
        subtitle_label = tk.Label(header_frame,
                                 text="Sistem Presensi Fingerprint Berbasis IoT",
                                 bg=self.colors['primary'],
                                 fg=self.colors['text_light'],
                                 font=('Segoe UI', 11))
        subtitle_label.pack(side="left", padx=10, pady=15)
        
        # Frame koneksi MQTT dengan styling modern
        conn_container = ttk.Frame(self.root)
        conn_container.pack(fill="x", padx=20, pady=15)
        
        conn_frame = tk.Frame(conn_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        conn_frame.pack(fill="x", padx=5, pady=5)
        
        # Add shadow effect with multiple frames
        shadow_frame = tk.Frame(conn_container, bg='#E0E0E0', relief='flat', bd=0)
        shadow_frame.place(in_=conn_frame, x=3, y=3, relwidth=1, relheight=1)
        conn_frame.lift()
        
        conn_label = tk.Label(conn_frame, 
                             text="🔌 Koneksi MQTT Broker",
                             bg=self.colors['bg_frame'],
                             fg=self.colors['primary'],
                             font=('Segoe UI', 11, 'bold'))
        conn_label.grid(row=0, column=0, columnspan=6, sticky="w", padx=15, pady=(15, 10))
        
        tk.Label(conn_frame, text="Broker Address:", bg=self.colors['bg_frame'], 
                fg=self.colors['text_dark'], font=('Segoe UI', 9)).grid(row=1, column=0, padx=(15, 5), pady=10, sticky="w")
        self.entry_broker = tk.Entry(conn_frame, width=25, font=('Segoe UI', 10), 
                                     relief='solid', bd=1, bg='white')
        self.entry_broker.grid(row=1, column=1, padx=5, pady=10)
        self.entry_broker.insert(0, self.mqtt_broker)
        
        tk.Label(conn_frame, text="Port:", bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'], font=('Segoe UI', 9)).grid(row=1, column=2, padx=(15, 5), pady=10, sticky="w")
        self.entry_port = tk.Entry(conn_frame, width=10, font=('Segoe UI', 10),
                                   relief='solid', bd=1, bg='white')
        self.entry_port.grid(row=1, column=3, padx=5, pady=10)
        self.entry_port.insert(0, str(self.mqtt_port))
        
        self.btn_connect = tk.Button(conn_frame, text="🔗 Connect", 
                                     command=self.toggle_connection,
                                     bg=self.colors['primary'],
                                     fg=self.colors['text_light'],
                                     font=('Segoe UI', 10, 'bold'),
                                     relief='flat',
                                     padx=20, pady=8,
                                     cursor='hand2',
                                     activebackground=self.colors['hover'],
                                     activeforeground=self.colors['text_light'])
        self.btn_connect.grid(row=1, column=4, padx=15, pady=10)
        
        self.status_label = tk.Label(conn_frame, text="● Disconnected", 
                                     bg=self.colors['bg_frame'],
                                     foreground=self.colors['error'], 
                                     font=('Segoe UI', 11, 'bold'))
        self.status_label.grid(row=1, column=5, padx=15, pady=10)
        
        # Notebook untuk tabs dengan styling
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        # Tab 1: Mode & Pendaftaran
        tab_register = ttk.Frame(notebook)
        notebook.add(tab_register, text="📝 Mode & Pendaftaran")
        self.setup_register_tab(tab_register)
        
        # Tab 2: Daftar User
        tab_users = ttk.Frame(notebook)
        notebook.add(tab_users, text="👥 Daftar User")
        self.setup_users_tab(tab_users)
        
        # Tab 3: Log Presensi
        tab_logs = ttk.Frame(notebook)
        notebook.add(tab_logs, text="📊 Log Presensi")
        self.setup_logs_tab(tab_logs)
        
        # Tab 4: Backup & Restore
        tab_backup = ttk.Frame(notebook)
        notebook.add(tab_backup, text="💾 Backup & Restore")
        self.setup_backup_tab(tab_backup)
    
    def setup_register_tab(self, parent):
        """Tab untuk mode dan pendaftaran"""
        parent.configure(style='TFrame')
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(parent, bg=self.colors['bg_main'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mouse wheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Frame Mode dengan card design
        mode_container = ttk.Frame(scrollable_frame)
        mode_container.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        mode_frame = tk.Frame(mode_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        mode_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow effect
        shadow = tk.Frame(mode_container, bg='#E0E0E0')
        shadow.place(in_=mode_frame, x=3, y=3, relwidth=1, relheight=1)
        mode_frame.lift()
        
        mode_title = tk.Label(mode_frame, 
                             text="⚙️ Mode Sistem",
                             bg=self.colors['bg_frame'],
                             fg=self.colors['primary'],
                             font=('Segoe UI', 12, 'bold'))
        mode_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        self.current_mode = tk.StringVar(value="PRESENSI")
        
        mode_info = tk.Frame(mode_frame, bg=self.colors['bg_frame'])
        mode_info.pack(fill="x", padx=20, pady=10)
        
        # Custom styled radiobuttons
        rb1 = tk.Radiobutton(mode_info, text="🕐 Mode Presensi", 
                            variable=self.current_mode,
                            value="PRESENSI", 
                            command=self.change_mode,
                            bg=self.colors['bg_frame'],
                            fg=self.colors['text_dark'],
                            font=('Segoe UI', 11),
                            activebackground=self.colors['bg_frame'],
                            activeforeground=self.colors['primary'],
                            selectcolor=self.colors['secondary'],
                            cursor='hand2')
        rb1.pack(side="left", padx=20)
        
        rb2 = tk.Radiobutton(mode_info, text="✍️ Mode Daftar", 
                            variable=self.current_mode,
                            value="DAFTAR", 
                            command=self.change_mode,
                            bg=self.colors['bg_frame'],
                            fg=self.colors['text_dark'],
                            font=('Segoe UI', 11),
                            activebackground=self.colors['bg_frame'],
                            activeforeground=self.colors['primary'],
                            selectcolor=self.colors['secondary'],
                            cursor='hand2')
        rb2.pack(side="left", padx=20)
        
        # Separator
        sep = tk.Frame(mode_frame, bg=self.colors['secondary'], height=2)
        sep.pack(fill="x", padx=20, pady=15)
        
        status_frame = tk.Frame(mode_frame, bg=self.colors['bg_frame'])
        status_frame.pack(pady=(10, 20))
        
        tk.Label(status_frame, text="Mode aktif saat ini:", 
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).pack(side="left", padx=5)
        self.mode_status = tk.Label(status_frame, text="PRESENSI", 
                                    bg=self.colors['bg_frame'],
                                    font=('Segoe UI', 13, 'bold'), 
                                    foreground=self.colors['accent'])
        self.mode_status.pack(side="left")
        
        # Frame Pendaftaran dengan card design
        register_container = ttk.Frame(scrollable_frame)
        register_container.pack(fill="both", expand=True, padx=10, pady=(5, 5))
        
        register_frame = tk.Frame(register_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        register_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow effect
        shadow = tk.Frame(register_container, bg='#E0E0E0')
        shadow.place(in_=register_frame, x=3, y=3, relwidth=1, relheight=1)
        register_frame.lift()
        
        reg_title = tk.Label(register_frame,
                            text="📝 Pendaftaran User Baru",
                            bg=self.colors['bg_frame'],
                            fg=self.colors['primary'],
                            font=('Segoe UI', 12, 'bold'))
        reg_title.pack(anchor="w", padx=20, pady=(20, 15))
        
        # Form input dengan styling modern
        form_frame = tk.Frame(register_frame, bg=self.colors['bg_frame'])
        form_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(form_frame, text="ID User (1-127):", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=0, column=0, sticky="w", pady=12, padx=5)
        self.entry_id = tk.Entry(form_frame, width=22, font=('Segoe UI', 10),
                                relief='solid', bd=1, bg='white')
        self.entry_id.grid(row=0, column=1, pady=12, padx=10, sticky="w")
        
        tk.Label(form_frame, text="Nama User:", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=1, column=0, sticky="w", pady=12, padx=5)
        self.entry_name = tk.Entry(form_frame, width=40, font=('Segoe UI', 10),
                                   relief='solid', bd=1, bg='white')
        self.entry_name.grid(row=1, column=1, pady=12, padx=10, sticky="w")
        
        tk.Label(form_frame, text="Email (opsional):", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=2, column=0, sticky="w", pady=12, padx=5)
        self.entry_email = tk.Entry(form_frame, width=40, font=('Segoe UI', 10),
                                    relief='solid', bd=1, bg='white')
        self.entry_email.grid(row=2, column=1, pady=12, padx=10, sticky="w")
        
        tk.Label(form_frame, text="Jabatan (opsional):", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=3, column=0, sticky="w", pady=12, padx=5)
        self.entry_position = tk.Entry(form_frame, width=40, font=('Segoe UI', 10),
                                       relief='solid', bd=1, bg='white')
        self.entry_position.grid(row=3, column=1, pady=12, padx=10, sticky="w")
        
        btn_frame = tk.Frame(register_frame, bg=self.colors['bg_frame'])
        btn_frame.pack(pady=20)
        
        enroll_btn = tk.Button(btn_frame, text="🖐️ Daftarkan Fingerprint", 
                              command=self.enroll_user,
                              bg=self.colors['accent'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 11, 'bold'),
                              relief='flat',
                              padx=25, pady=12,
                              cursor='hand2',
                              activebackground=self.colors['hover'],
                              activeforeground=self.colors['text_light'])
        enroll_btn.pack(side="left", padx=8)
        
        clear_btn = tk.Button(btn_frame, text="🗑️ Clear Form", 
                             command=self.clear_form,
                             bg=self.colors['secondary'],
                             fg=self.colors['text_dark'],
                             font=('Segoe UI', 10, 'bold'),
                             relief='flat',
                             padx=20, pady=12,
                             cursor='hand2',
                             activebackground=self.colors['primary'],
                             activeforeground=self.colors['text_light'])
        clear_btn.pack(side="left", padx=8)
        
        # Log area dengan card design
        log_container = ttk.Frame(scrollable_frame)
        log_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        log_frame = tk.Frame(log_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        log_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow effect
        shadow = tk.Frame(log_container, bg='#E0E0E0')
        shadow.place(in_=log_frame, x=3, y=3, relwidth=1, relheight=1)
        log_frame.lift()
        
        log_title = tk.Label(log_frame,
                            text="📋 Status Log",
                            bg=self.colors['bg_frame'],
                            fg=self.colors['primary'],
                            font=('Segoe UI', 12, 'bold'))
        log_title.pack(anchor="w", padx=20, pady=(15, 10))
        
        log_text_frame = tk.Frame(log_frame, bg=self.colors['bg_frame'])
        log_text_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        self.log_text = scrolledtext.ScrolledText(log_text_frame, height=8, width=70, 
                                                  font=('Consolas', 9),
                                                  bg='#FAFAFA',
                                                  fg=self.colors['text_dark'],
                                                  relief='solid',
                                                  bd=1,
                                                  wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True)
    
    def setup_users_tab(self, parent):
        """Tab untuk daftar user"""
        parent.configure(style='TFrame')
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(parent, bg=self.colors['bg_main'], highlightthickness=0)
        scrollbar_main = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_main.set)
        
        # Bind mouse wheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_main.pack(side="right", fill="y")
        
        # Frame toolbar dengan styling modern
        toolbar_container = ttk.Frame(scrollable_frame)
        toolbar_container.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        toolbar = tk.Frame(toolbar_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        toolbar.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow
        shadow = tk.Frame(toolbar_container, bg='#E0E0E0')
        shadow.place(in_=toolbar, x=3, y=3, relwidth=1, relheight=1)
        toolbar.lift()
        
        btn_container = tk.Frame(toolbar, bg=self.colors['bg_frame'])
        btn_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Styled buttons
        refresh_btn = tk.Button(btn_container, text="🔄 Refresh", 
                               command=self.refresh_user_list,
                               bg=self.colors['primary'],
                               fg=self.colors['text_light'],
                               font=('Segoe UI', 9, 'bold'),
                               relief='flat',
                               padx=15, pady=8,
                               cursor='hand2',
                               activebackground=self.colors['hover'])
        refresh_btn.pack(side="left", padx=5)
        
        edit_btn = tk.Button(btn_container, text="✏️ Edit User", 
                            command=self.edit_user,
                            bg=self.colors['secondary'],
                            fg=self.colors['text_dark'],
                            font=('Segoe UI', 9, 'bold'),
                            relief='flat',
                            padx=15, pady=8,
                            cursor='hand2',
                            activebackground=self.colors['primary'],
                            activeforeground=self.colors['text_light'])
        edit_btn.pack(side="left", padx=5)
        
        delete_btn = tk.Button(btn_container, text="🗑️ Hapus User", 
                              command=self.delete_user,
                              bg=self.colors['error'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 9, 'bold'),
                              relief='flat',
                              padx=15, pady=8,
                              cursor='hand2',
                              activebackground='#E53935')
        delete_btn.pack(side="left", padx=5)
        
        export_btn = tk.Button(btn_container, text="📤 Export CSV", 
                              command=self.export_users,
                              bg=self.colors['success'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 9, 'bold'),
                              relief='flat',
                              padx=15, pady=8,
                              cursor='hand2',
                              activebackground='#689F38')
        export_btn.pack(side="left", padx=5)
        
        # Info label
        self.user_count_label = tk.Label(btn_container, text="Total: 0 users", 
                                         bg=self.colors['bg_frame'],
                                         fg=self.colors['primary'],
                                         font=('Segoe UI', 11, 'bold'))
        self.user_count_label.pack(side="right", padx=15)
        
        # Treeview untuk daftar user dengan card design
        tree_container = ttk.Frame(scrollable_frame)
        tree_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        tree_frame = tk.Frame(tree_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        tree_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow
        shadow = tk.Frame(tree_container, bg='#E0E0E0')
        shadow.place(in_=tree_frame, x=3, y=3, relwidth=1, relheight=1)
        tree_frame.lift()
        
        # Title inside tree frame
        tree_title = tk.Label(tree_frame,
                             text="👥 Daftar User Terdaftar",
                             bg=self.colors['bg_frame'],
                             fg=self.colors['primary'],
                             font=('Segoe UI', 11, 'bold'))
        tree_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Treeview wrapper
        tree_wrapper = tk.Frame(tree_frame, bg=self.colors['bg_frame'])
        tree_wrapper.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        scrollbar_y = ttk.Scrollbar(tree_wrapper)
        scrollbar_y.pack(side="right", fill="y")
        
        scrollbar_x = ttk.Scrollbar(tree_wrapper, orient="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")
        
        self.user_tree = ttk.Treeview(tree_wrapper, 
                                      columns=("ID", "Nama", "Email", "Jabatan", "Template", "Tanggal"), 
                                      show="headings", 
                                      yscrollcommand=scrollbar_y.set,
                                      xscrollcommand=scrollbar_x.set,
                                      height=12)
        scrollbar_y.config(command=self.user_tree.yview)
        scrollbar_x.config(command=self.user_tree.xview)
        
        self.user_tree.heading("ID", text="ID")
        self.user_tree.heading("Nama", text="Nama")
        self.user_tree.heading("Email", text="Email")
        self.user_tree.heading("Jabatan", text="Jabatan")
        self.user_tree.heading("Template", text="Template")
        self.user_tree.heading("Tanggal", text="Tanggal Daftar")
        
        self.user_tree.column("ID", width=60, anchor="center")
        self.user_tree.column("Nama", width=180)
        self.user_tree.column("Email", width=200)
        self.user_tree.column("Jabatan", width=150)
        self.user_tree.column("Template", width=100, anchor="center")
        self.user_tree.column("Tanggal", width=150, anchor="center")
        
        # Alternating row colors
        self.user_tree.tag_configure('oddrow', background='white')
        self.user_tree.tag_configure('evenrow', background='#F9F9FF')
        
        self.user_tree.pack(fill="both", expand=True)
        
        self.refresh_user_list()
    
    def setup_logs_tab(self, parent):
        """Tab untuk log presensi"""
        parent.configure(style='TFrame')
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(parent, bg=self.colors['bg_main'], highlightthickness=0)
        scrollbar_main = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_main.set)
        
        # Bind mouse wheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_main.pack(side="right", fill="y")
        
        # Frame toolbar dengan styling modern
        toolbar_container = ttk.Frame(scrollable_frame)
        toolbar_container.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        toolbar = tk.Frame(toolbar_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        toolbar.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow
        shadow = tk.Frame(toolbar_container, bg='#E0E0E0')
        shadow.place(in_=toolbar, x=3, y=3, relwidth=1, relheight=1)
        toolbar.lift()
        
        btn_container = tk.Frame(toolbar, bg=self.colors['bg_frame'])
        btn_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Buttons
        refresh_btn = tk.Button(btn_container, text="🔄 Refresh", 
                               command=self.refresh_attendance_logs,
                               bg=self.colors['primary'],
                               fg=self.colors['text_light'],
                               font=('Segoe UI', 9, 'bold'),
                               relief='flat',
                               padx=15, pady=8,
                               cursor='hand2',
                               activebackground=self.colors['hover'])
        refresh_btn.pack(side="left", padx=5)
        
        clear_btn = tk.Button(btn_container, text="🗑️ Hapus Semua Log", 
                             command=self.clear_logs,
                             bg=self.colors['error'],
                             fg=self.colors['text_light'],
                             font=('Segoe UI', 9, 'bold'),
                             relief='flat',
                             padx=15, pady=8,
                             cursor='hand2',
                             activebackground='#E53935')
        clear_btn.pack(side="left", padx=5)
        
        export_btn = tk.Button(btn_container, text="📤 Export CSV", 
                              command=self.export_logs,
                              bg=self.colors['success'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 9, 'bold'),
                              relief='flat',
                              padx=15, pady=8,
                              cursor='hand2',
                              activebackground='#689F38')
        export_btn.pack(side="left", padx=5)
        
        # Filter section
        tk.Label(btn_container, text="🔍", 
                bg=self.colors['bg_frame'],
                font=('Segoe UI', 11)).pack(side="left", padx=(20, 5))
        
        self.filter_var = tk.StringVar()
        self.filter_entry = tk.Entry(btn_container, textvariable=self.filter_var, 
                                     width=25, font=('Segoe UI', 9),
                                     relief='solid', bd=1, bg='white')
        self.filter_entry.pack(side="left", padx=5)
        self.filter_entry.bind('<Return>', lambda e: self.filter_logs())
        
        search_btn = tk.Button(btn_container, text="Cari Nama", 
                              command=self.filter_logs,
                              bg=self.colors['accent'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 9, 'bold'),
                              relief='flat',
                              padx=15, pady=8,
                              cursor='hand2',
                              activebackground=self.colors['hover'])
        search_btn.pack(side="left", padx=5)
        
        # Info label
        self.log_count_label = tk.Label(btn_container, text="Total: 0 logs", 
                                        bg=self.colors['bg_frame'],
                                        fg=self.colors['primary'],
                                        font=('Segoe UI', 11, 'bold'))
        self.log_count_label.pack(side="right", padx=15)
        
        # Filter tanggal dengan card design
        filter_date_container = ttk.Frame(scrollable_frame)
        filter_date_container.pack(fill="x", padx=10, pady=(5, 5))
        
        filter_date_frame = tk.Frame(filter_date_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        filter_date_frame.pack(fill="x", padx=0, pady=0)
        
        # Shadow
        shadow = tk.Frame(filter_date_container, bg='#E0E0E0')
        shadow.place(in_=filter_date_frame, x=3, y=3, relwidth=1, relheight=1)
        filter_date_frame.lift()
        
        filter_title = tk.Label(filter_date_frame,
                               text="📅 Filter Berdasarkan Tanggal",
                               bg=self.colors['bg_frame'],
                               fg=self.colors['primary'],
                               font=('Segoe UI', 11, 'bold'))
        filter_title.pack(anchor="w", padx=15, pady=(12, 8))
        
        date_filter_controls = tk.Frame(filter_date_frame, bg=self.colors['bg_frame'])
        date_filter_controls.pack(fill="x", padx=15, pady=(5, 12))
        
        # Tanggal
        tk.Label(date_filter_controls, text="Tanggal:", 
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 9)).pack(side="left", padx=(5, 5))
        
        self.filter_day = tk.StringVar(value="")
        day_combo = ttk.Combobox(date_filter_controls, textvariable=self.filter_day, 
                                 width=10, state='readonly', font=('Segoe UI', 9))
        day_combo['values'] = ['Semua'] + [str(i) for i in range(1, 32)]
        day_combo.set('Semua')
        day_combo.pack(side="left", padx=5)
        
        # Bulan
        tk.Label(date_filter_controls, text="Bulan:", 
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 9)).pack(side="left", padx=(15, 5))
        
        self.filter_month = tk.StringVar(value="")
        month_combo = ttk.Combobox(date_filter_controls, textvariable=self.filter_month, 
                                   width=12, state='readonly', font=('Segoe UI', 9))
        month_combo['values'] = ['Semua', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                                 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        month_combo.set('Semua')
        month_combo.pack(side="left", padx=5)
        
        # Tahun
        tk.Label(date_filter_controls, text="Tahun:", 
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 9)).pack(side="left", padx=(15, 5))
        
        self.filter_year = tk.StringVar(value="")
        current_year = datetime.now().year
        year_combo = ttk.Combobox(date_filter_controls, textvariable=self.filter_year, 
                                  width=10, state='readonly', font=('Segoe UI', 9))
        year_combo['values'] = ['Semua'] + [str(i) for i in range(current_year - 5, current_year + 2)]
        year_combo.set('Semua')
        year_combo.pack(side="left", padx=5)
        
        # Tombol filter tanggal
        filter_date_btn = tk.Button(date_filter_controls, text="🔍 Filter Tanggal", 
                                    command=self.filter_logs_by_date,
                                    bg=self.colors['success'],
                                    fg=self.colors['text_light'],
                                    font=('Segoe UI', 9, 'bold'),
                                    relief='flat',
                                    padx=15, pady=8,
                                    cursor='hand2',
                                    activebackground='#689F38')
        filter_date_btn.pack(side="left", padx=10)
        
        reset_filter_btn = tk.Button(date_filter_controls, text="↺ Reset", 
                                     command=self.reset_date_filter,
                                     bg=self.colors['secondary'],
                                     fg=self.colors['text_dark'],
                                     font=('Segoe UI', 9, 'bold'),
                                     relief='flat',
                                     padx=15, pady=8,
                                     cursor='hand2',
                                     activebackground=self.colors['primary'],
                                     activeforeground=self.colors['text_light'])
        reset_filter_btn.pack(side="left", padx=5)
        
        # Treeview untuk log dengan card design
        tree_container = ttk.Frame(scrollable_frame)
        tree_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        tree_frame = tk.Frame(tree_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        tree_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow
        shadow = tk.Frame(tree_container, bg='#E0E0E0')
        shadow.place(in_=tree_frame, x=3, y=3, relwidth=1, relheight=1)
        tree_frame.lift()
        
        # Title
        tree_title = tk.Label(tree_frame,
                             text="📊 Riwayat Log Presensi",
                             bg=self.colors['bg_frame'],
                             fg=self.colors['primary'],
                             font=('Segoe UI', 11, 'bold'))
        tree_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Treeview wrapper
        tree_wrapper = tk.Frame(tree_frame, bg=self.colors['bg_frame'])
        tree_wrapper.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(tree_wrapper)
        scrollbar.pack(side="right", fill="y")
        
        self.log_tree = ttk.Treeview(tree_wrapper, 
                                     columns=("No", "ID", "Nama", "Waktu", "Score", "Lokasi"), 
                                     show="headings", 
                                     yscrollcommand=scrollbar.set,
                                     height=12)
        scrollbar.config(command=self.log_tree.yview)
        
        self.log_tree.heading("No", text="No")
        self.log_tree.heading("ID", text="ID User")
        self.log_tree.heading("Nama", text="Nama")
        self.log_tree.heading("Waktu", text="Waktu Presensi")
        self.log_tree.heading("Score", text="Score")
        self.log_tree.heading("Lokasi", text="Lokasi")
        
        self.log_tree.column("No", width=50, anchor="center")
        self.log_tree.column("ID", width=80, anchor="center")
        self.log_tree.column("Nama", width=200)
        self.log_tree.column("Waktu", width=180, anchor="center")
        self.log_tree.column("Score", width=80, anchor="center")
        self.log_tree.column("Lokasi", width=150)
        
        # Alternating row colors
        self.log_tree.tag_configure('oddrow', background='white')
        self.log_tree.tag_configure('evenrow', background='#F9F9FF')
        
        self.log_tree.pack(fill="both", expand=True)
        
        self.refresh_attendance_logs()
    
    def setup_backup_tab(self, parent):
        """Tab untuk backup dan restore"""
        parent.configure(style='TFrame')
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(parent, bg=self.colors['bg_main'], highlightthickness=0)
        scrollbar_main = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_main.set)
        
        # Bind mouse wheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_main.pack(side="right", fill="y")
        
        # Info frame dengan card design
        info_container = ttk.Frame(scrollable_frame)
        info_container.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        info_frame = tk.Frame(info_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        info_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow
        shadow = tk.Frame(info_container, bg='#E0E0E0')
        shadow.place(in_=info_frame, x=3, y=3, relwidth=1, relheight=1)
        info_frame.lift()
        
        info_title = tk.Label(info_frame,
                             text="ℹ️ Informasi",
                             bg=self.colors['bg_frame'],
                             fg=self.colors['primary'],
                             font=('Segoe UI', 11, 'bold'))
        info_title.pack(anchor="w", padx=20, pady=(15, 10))
        
        info_text = """Template fingerprint otomatis tersimpan di database saat pendaftaran user baru.
Anda dapat melakukan restore jika sensor fingerprint direset atau template hilang."""
        
        tk.Label(info_frame, text=info_text, 
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 9),
                justify="left").pack(anchor="w", padx=20, pady=(5, 15))
        
        # Backup frame
        backup_container = ttk.Frame(scrollable_frame)
        backup_container.pack(fill="both", expand=True, padx=10, pady=(5, 5))
        
        backup_frame = tk.Frame(backup_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        backup_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        shadow = tk.Frame(backup_container, bg='#E0E0E0')
        shadow.place(in_=backup_frame, x=3, y=3, relwidth=1, relheight=1)
        backup_frame.lift()
        
        backup_title = tk.Label(backup_frame,
                               text="💾 Backup Database",
                               bg=self.colors['bg_frame'],
                               fg=self.colors['primary'],
                               font=('Segoe UI', 11, 'bold'))
        backup_title.pack(anchor="w", padx=20, pady=(15, 10))
        
        tk.Label(backup_frame, text="Backup seluruh database (users + templates + logs) ke file.",
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 9)).pack(anchor="w", padx=20, pady=5)
        
        backup_btn = tk.Button(backup_frame, text="📥 Backup Database", 
                              command=self.backup_database,
                              bg=self.colors['accent'],
                              fg=self.colors['text_light'],
                              font=('Segoe UI', 10, 'bold'),
                              relief='flat',
                              padx=20, pady=10,
                              cursor='hand2',
                              activebackground=self.colors['hover'])
        backup_btn.pack(anchor="w", padx=20, pady=(5, 15))
        
        # Restore frame
        restore_container = ttk.Frame(scrollable_frame)
        restore_container.pack(fill="both", expand=True, padx=10, pady=(5, 5))
        
        restore_frame = tk.Frame(restore_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        restore_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        shadow = tk.Frame(restore_container, bg='#E0E0E0')
        shadow.place(in_=restore_frame, x=3, y=3, relwidth=1, relheight=1)
        restore_frame.lift()
        
        restore_title = tk.Label(restore_frame,
                                text="♻️ Restore Template Fingerprint",
                                bg=self.colors['bg_frame'],
                                fg=self.colors['primary'],
                                font=('Segoe UI', 11, 'bold'))
        restore_title.pack(anchor="w", padx=20, pady=(15, 10))
        
        tk.Label(restore_frame, text="Restore template fingerprint dari database ke sensor AS608.",
                bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'],
                font=('Segoe UI', 9)).pack(anchor="w", padx=20, pady=5)
        
        restore_btn_frame = tk.Frame(restore_frame, bg=self.colors['bg_frame'])
        restore_btn_frame.pack(fill="x", padx=20, pady=(10, 15))
        
        restore_all_btn = tk.Button(restore_btn_frame, text="♻️ Restore Semua User", 
                                    command=self.restore_all_templates,
                                    bg=self.colors['success'],
                                    fg=self.colors['text_light'],
                                    font=('Segoe UI', 10, 'bold'),
                                    relief='flat',
                                    padx=20, pady=10,
                                    cursor='hand2',
                                    activebackground='#689F38')
        restore_all_btn.pack(side="left", padx=(0, 10))
        
        restore_single_btn = tk.Button(restore_btn_frame, text="♻️ Restore User Tertentu", 
                                       command=self.restore_single_template,
                                       bg=self.colors['secondary'],
                                       fg=self.colors['text_dark'],
                                       font=('Segoe UI', 10, 'bold'),
                                       relief='flat',
                                       padx=20, pady=10,
                                       cursor='hand2',
                                       activebackground=self.colors['primary'],
                                       activeforeground=self.colors['text_light'])
        restore_single_btn.pack(side="left")
        
        # Status log
        log_container = ttk.Frame(scrollable_frame)
        log_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        log_frame = tk.Frame(log_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        log_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        shadow = tk.Frame(log_container, bg='#E0E0E0')
        shadow.place(in_=log_frame, x=3, y=3, relwidth=1, relheight=1)
        log_frame.lift()
        
        log_title = tk.Label(log_frame,
                            text="📋 Status Log",
                            bg=self.colors['bg_frame'],
                            fg=self.colors['primary'],
                            font=('Segoe UI', 11, 'bold'))
        log_title.pack(anchor="w", padx=20, pady=(15, 10))
        
        log_text_frame = tk.Frame(log_frame, bg=self.colors['bg_frame'])
        log_text_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        self.backup_log = scrolledtext.ScrolledText(log_text_frame, height=10, 
                                                    font=('Consolas', 9),
                                                    bg='#FAFAFA',
                                                    fg=self.colors['text_dark'],
                                                    relief='solid',
                                                    bd=1,
                                                    wrap=tk.WORD)
        self.backup_log.pack(fill="both", expand=True)
    
    # ============= MQTT Functions =============
    def toggle_connection(self):
        """Toggle MQTT connection"""
        if not self.is_connected:
            self.connect_mqtt()
        else:
            self.disconnect_mqtt()
    
    def connect_mqtt(self):
        """Koneksi ke MQTT Broker"""
        self.mqtt_broker = self.entry_broker.get()
        try:
            self.mqtt_port = int(self.entry_port.get())
        except ValueError:
            messagebox.showerror("Error", "Port harus berupa angka!")
            return
        
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal koneksi ke MQTT Broker:\n{str(e)}")
            self.log(f"❌ Error: {str(e)}")
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback saat berhasil koneksi ke MQTT"""
        if rc == 0:
            self.is_connected = True
            self.status_label.config(text="● Connected", foreground=self.colors['success'])
            self.btn_connect.config(text="🔌 Disconnect", bg=self.colors['error'])
            self.log(f"✅ Terhubung ke MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")
            
            # Subscribe ke topics
            self.mqtt_client.subscribe(self.TOPIC_RESPONSE)
            self.mqtt_client.subscribe(self.TOPIC_ATTENDANCE)
            self.mqtt_client.subscribe(self.TOPIC_TEMPLATE)
            
            # Save settings
            self.save_settings()
            
            # Sync users
            self.sync_users_to_esp()
        else:
            self.log(f"❌ Gagal koneksi: RC={rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback saat disconnect dari MQTT"""
        self.is_connected = False
        self.status_label.config(text="● Disconnected", foreground=self.colors['error'])
        self.btn_connect.config(text="🔗 Connect", bg=self.colors['primary'])
        self.log("⚠️ Terputus dari MQTT Broker")
    
    def disconnect_mqtt(self):
        """Disconnect dari MQTT Broker"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
    
    def on_mqtt_message(self, client, userdata, msg):
        """Callback saat menerima pesan MQTT"""
        try:
            data = json.loads(msg.payload.decode())
            
            if msg.topic == self.TOPIC_RESPONSE:
                status = data.get("status")
                
                if status == "ENROLL_OK":
                    user_id = data["id"]
                    user_name = data["name"]
                    self.log(f"✅ Pendaftaran berhasil: {user_name} (ID: {user_id})")
                
                elif status == "ENROLL_FAIL":
                    user_id = data["id"]
                    self.log(f"❌ Pendaftaran gagal untuk ID: {user_id}")
                    # Hapus dari database jika gagal
                    self.cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                    self.conn.commit()
                
                elif status == "DELETE_OK":
                    user_id = data["id"]
                    self.log(f"✅ User ID {user_id} berhasil dihapus dari sensor")
                
                elif status == "RESTORE_OK":
                    user_id = data["id"]
                    self.backup_log.insert("end", f"✅ Template ID {user_id} berhasil di-restore\n")
                    self.backup_log.see("end")
                
                elif status == "RESTORE_FAIL":
                    user_id = data["id"]
                    self.backup_log.insert("end", f"❌ Template ID {user_id} gagal di-restore\n")
                    self.backup_log.see("end")
            
            elif msg.topic == self.TOPIC_ATTENDANCE:
                user_id = data["id"]
                user_name = data["name"]
                score = data.get("score", 0)
                
                # Simpan ke database
                self.cursor.execute(
                    'INSERT INTO attendance_logs (user_id, user_name, match_score) VALUES (?, ?, ?)',
                    (user_id, user_name, score)
                )
                self.conn.commit()
                
                self.log(f"✅ Presensi: {user_name} (ID: {user_id}, Score: {score})")
                
                # Refresh log tree
                self.root.after(0, self.refresh_attendance_logs)
            
            elif msg.topic == self.TOPIC_TEMPLATE:
                # Simpan template ke database
                user_id = data["id"]
                user_name = data["name"]
                template_b64 = data["template"]
                template_blob = base64.b64decode(template_b64)
                
                self.cursor.execute(
                    'UPDATE users SET fingerprint_template = ? WHERE id = ?',
                    (template_blob, user_id)
                )
                self.conn.commit()
                
                self.log(f"💾 Template {user_name} (ID: {user_id}) tersimpan di database")
                self.root.after(0, self.refresh_user_list)
        
        except Exception as e:
            self.log(f"❌ Error processing message: {str(e)}")
    
    def publish_command(self, command):
        """Publish command ke ESP32"""
        if not self.is_connected:
            messagebox.showwarning("Peringatan", "Belum terkoneksi ke MQTT Broker!")
            return False
        
        try:
            self.mqtt_client.publish(self.TOPIC_COMMAND, json.dumps(command))
            return True
        except Exception as e:
            self.log(f"❌ Error publish: {str(e)}")
            return False
    
    # ============= UI Functions =============
    def change_mode(self):
        """Ubah mode sistem"""
        mode = self.current_mode.get()
        if self.publish_command({"cmd": "SET_MODE", "mode": mode}):
            self.mode_status.config(text=mode)
            self.log(f"🔄 Mode diubah ke: {mode}")
    
    def enroll_user(self):
        """Daftarkan user baru"""
        try:
            user_id = int(self.entry_id.get())
            user_name = self.entry_name.get().strip()
            user_email = self.entry_email.get().strip() or None
            user_position = self.entry_position.get().strip() or None
            
            if not (1 <= user_id <= 127):
                messagebox.showerror("Error", "ID harus antara 1-127")
                return
            
            if not user_name:
                messagebox.showerror("Error", "Nama tidak boleh kosong")
                return
            
            # Cek apakah ID sudah ada
            self.cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
            if self.cursor.fetchone():
                if not messagebox.askyesno("Konfirmasi", 
                    f"ID {user_id} sudah terdaftar. Timpa data yang lama?"):
                    return
            
            # Simpan ke database (template akan diupdate saat diterima dari ESP32)
            self.cursor.execute('''
                INSERT OR REPLACE INTO users (id, name, email, position) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, user_name, user_email, user_position))
            self.conn.commit()
            self.users[user_id] = user_name
            
            # Kirim perintah enroll ke ESP32
            if self.publish_command({"cmd": "ENROLL", "id": user_id, "name": user_name}):
                self.log(f"📝 Memulai pendaftaran: {user_name} (ID: {user_id})")
                self.log("⏳ Ikuti instruksi di LCD ESP32...")
                
                # Clear form
                self.clear_form()
                
                # Refresh user list
                self.refresh_user_list()
        
        except ValueError:
            messagebox.showerror("Error", "ID harus berupa angka")
    
    def clear_form(self):
        """Clear form pendaftaran"""
        self.entry_id.delete(0, tk.END)
        self.entry_name.delete(0, tk.END)
        self.entry_email.delete(0, tk.END)
        self.entry_position.delete(0, tk.END)
    
    def sync_users_to_esp(self):
        """Sinkronisasi daftar users ke ESP32"""
        users_dict = {str(k): v for k, v in self.users.items()}
        self.publish_command({"cmd": "UPDATE_USERS", "users": users_dict})
        self.log(f"🔄 Sinkronisasi {len(self.users)} users ke ESP32")
    
    def refresh_user_list(self):
        """Refresh treeview users"""
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        self.cursor.execute('''
            SELECT id, name, email, position, fingerprint_template, created_at 
            FROM users ORDER BY id
        ''')
        
        count = 0
        for user_id, name, email, position, template, created_at in self.cursor.fetchall():
            has_template = "✅ Ada" if template else "❌ Tidak"
            email_display = email or "-"
            position_display = position or "-"
            
            # Alternating row colors
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.user_tree.insert("", "end", values=(
                user_id, name, email_display, position_display, has_template, created_at
            ), tags=(tag,))
            count += 1
        
        self.user_count_label.config(text=f"Total: {count} users")
    
    def edit_user(self):
        """Edit data user"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning("Peringatan", "Pilih user yang akan diedit")
            return
        
        item = self.user_tree.item(selection[0])
        user_id = int(item['values'][0])
        
        # Ambil data dari database
        self.cursor.execute('SELECT name, email, position FROM users WHERE id = ?', (user_id,))
        result = self.cursor.fetchone()
        if not result:
            return
        
        name, email, position = result
        
        # Dialog edit
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit User ID: {user_id}")
        edit_window.geometry("400x250")
        edit_window.resizable(False, False)
        
        ttk.Label(edit_window, text=f"Edit User ID: {user_id}", font=("Arial", 12, "bold")).pack(pady=10)
        
        form = ttk.Frame(edit_window, padding=20)
        form.pack(fill="both", expand=True)
        
        ttk.Label(form, text="Nama:").grid(row=0, column=0, sticky="w", pady=5)
        entry_name = ttk.Entry(form, width=30)
        entry_name.grid(row=0, column=1, pady=5, padx=10)
        entry_name.insert(0, name)
        
        ttk.Label(form, text="Email:").grid(row=1, column=0, sticky="w", pady=5)
        entry_email = ttk.Entry(form, width=30)
        entry_email.grid(row=1, column=1, pady=5, padx=10)
        entry_email.insert(0, email or "")
        
        ttk.Label(form, text="Jabatan:").grid(row=2, column=0, sticky="w", pady=5)
        entry_position = ttk.Entry(form, width=30)
        entry_position.grid(row=2, column=1, pady=5, padx=10)
        entry_position.insert(0, position or "")
        
        def save_edit():
            new_name = entry_name.get().strip()
            new_email = entry_email.get().strip() or None
            new_position = entry_position.get().strip() or None
            
            if not new_name:
                messagebox.showerror("Error", "Nama tidak boleh kosong")
                return
            
            self.cursor.execute('''
                UPDATE users SET name = ?, email = ?, position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_name, new_email, new_position, user_id))
            self.conn.commit()
            
            self.users[user_id] = new_name
            self.sync_users_to_esp()
            self.refresh_user_list()
            self.log(f"✏️ User ID {user_id} berhasil diupdate")
            edit_window.destroy()
        
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="💾 Simpan", command=save_edit).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Batal", command=edit_window.destroy).pack(side="left", padx=5)
    
    def delete_user(self):
        """Hapus user terpilih"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning("Peringatan", "Pilih user yang akan dihapus")
            return
        
        item = self.user_tree.item(selection[0])
        user_id = int(item['values'][0])
        user_name = item['values'][1]
        
        if messagebox.askyesno("Konfirmasi", 
            f"Hapus user {user_name} (ID: {user_id})?\n\nIni akan menghapus:\n- Data user\n- Template fingerprint\n- Semua log presensi"):
            
            # Hapus dari database
            self.cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            self.conn.commit()
            
            # Hapus dari dict
            if user_id in self.users:
                del self.users[user_id]
            
            # Kirim perintah delete ke ESP32
            self.publish_command({"cmd": "DELETE", "id": user_id})
            
            self.log(f"🗑️ User {user_name} (ID: {user_id}) dihapus")
            self.refresh_user_list()
    
    def export_users(self):
        """Export daftar user ke CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            self.cursor.execute('''
                SELECT id, name, email, position, 
                       CASE WHEN fingerprint_template IS NOT NULL THEN 'Ada' ELSE 'Tidak' END as template,
                       created_at
                FROM users ORDER BY id
            ''')
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Nama', 'Email', 'Jabatan', 'Template', 'Tanggal Daftar'])
                writer.writerows(self.cursor.fetchall())
            
            messagebox.showinfo("Sukses", f"Data user berhasil diexport ke:\n{filename}")
            self.log(f"📤 Data user diexport ke {filename}")
    
    def refresh_attendance_logs(self):
        """Refresh log presensi"""
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        self.cursor.execute('''
            SELECT log_id, user_id, user_name, check_in_time, match_score, location
            FROM attendance_logs 
            ORDER BY check_in_time DESC 
            LIMIT 1000
        ''')
        
        count = 0
        for log_id, user_id, user_name, timestamp, score, location in self.cursor.fetchall():
            # Alternating row colors
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.log_tree.insert("", "end", values=(
                log_id, user_id, user_name, timestamp, score or "-", location
            ), tags=(tag,))
            count += 1
        
        self.log_count_label.config(text=f"Total: {count} logs")
    
    def filter_logs(self):
        """Filter log berdasarkan keyword"""
        keyword = self.filter_var.get().strip().lower()
        
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        if keyword:
            self.cursor.execute('''
                SELECT log_id, user_id, user_name, check_in_time, match_score, location
                FROM attendance_logs 
                WHERE LOWER(user_name) LIKE ? OR CAST(user_id AS TEXT) LIKE ?
                ORDER BY check_in_time DESC 
                LIMIT 1000
            ''', (f'%{keyword}%', f'%{keyword}%'))
        else:
            self.cursor.execute('''
                SELECT log_id, user_id, user_name, check_in_time, match_score, location
                FROM attendance_logs 
                ORDER BY check_in_time DESC 
                LIMIT 1000
            ''')
        
        count = 0
        for log_id, user_id, user_name, timestamp, score, location in self.cursor.fetchall():
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.log_tree.insert("", "end", values=(
                count + 1, user_id, user_name, timestamp, score or "-", location
            ), tags=(tag,))
            count += 1
        
        self.log_count_label.config(text=f"Total: {count} logs (filtered)")
    
    def filter_logs_by_date(self):
        """Filter log berdasarkan tanggal, bulan, dan tahun"""
        day = self.filter_day.get()
        month = self.filter_month.get()
        year = self.filter_year.get()
        
        # Clear treeview
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        # Mapping bulan ke angka
        month_map = {
            'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4,
            'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8,
            'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
        }
        
        # Build query berdasarkan filter
        query = '''
            SELECT log_id, user_id, user_name, check_in_time, match_score, location
            FROM attendance_logs 
            WHERE 1=1
        '''
        params = []
        
        # Filter tahun
        if year != 'Semua':
            query += " AND strftime('%Y', check_in_time) = ?"
            params.append(year)
        
        # Filter bulan
        if month != 'Semua':
            month_num = month_map.get(month)
            if month_num:
                query += " AND strftime('%m', check_in_time) = ?"
                params.append(f'{month_num:02d}')
        
        # Filter tanggal
        if day != 'Semua':
            query += " AND strftime('%d', check_in_time) = ?"
            params.append(f'{int(day):02d}')
        
        query += " ORDER BY check_in_time DESC LIMIT 1000"
        
        self.cursor.execute(query, params)
        
        count = 0
        for log_id, user_id, user_name, timestamp, score, location in self.cursor.fetchall():
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.log_tree.insert("", "end", values=(
                count + 1, user_id, user_name, timestamp, score or "-", location
            ), tags=(tag,))
            count += 1
        
        # Update label dengan info filter
        filter_info = []
        if day != 'Semua':
            filter_info.append(f"Tgl: {day}")
        if month != 'Semua':
            filter_info.append(f"Bulan: {month}")
        if year != 'Semua':
            filter_info.append(f"Tahun: {year}")
        
        filter_text = f" ({', '.join(filter_info)})" if filter_info else ""
        self.log_count_label.config(text=f"Total: {count} logs{filter_text}")
    
    def reset_date_filter(self):
        """Reset filter tanggal ke default"""
        self.filter_day.set('Semua')
        self.filter_month.set('Semua')
        self.filter_year.set('Semua')
        self.filter_var.set('')
        self.refresh_attendance_logs()
    
    def clear_logs(self):
        """Hapus semua log presensi"""
        if messagebox.askyesno("Konfirmasi", "Hapus SEMUA log presensi?"):
            self.cursor.execute('DELETE FROM attendance_logs')
            self.conn.commit()
            self.refresh_attendance_logs()
            self.log("🗑️ Semua log presensi dihapus")
    
    def export_logs(self):
        """Export log presensi ke CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"attendance_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['No', 'User ID', 'Nama', 'Waktu Presensi', 'Score', 'Lokasi'])
                    
                    self.cursor.execute('''
                        SELECT log_id, user_id, user_name, check_in_time, match_score, location
                        FROM attendance_logs 
                        ORDER BY check_in_time DESC
                    ''')
                    
                    for idx, (log_id, user_id, user_name, timestamp, score, location) in enumerate(self.cursor.fetchall(), 1):
                        writer.writerow([idx, user_id, user_name, timestamp, score or "-", location])
                
                messagebox.showinfo("Sukses", f"Log berhasil diekspor ke:\n{filename}")
                self.log(f"📤 Log diekspor ke {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export: {str(e)}")
    
    def backup_database(self):
        """Backup seluruh database"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialfile=f"attendance_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        
        if filename:
            import shutil
            try:
                # Close current connection
                self.conn.close()
                
                # Copy database file
                shutil.copy2('attendance.db', filename)
                
                # Reopen connection
                self.conn = sqlite3.connect('attendance.db', check_same_thread=False)
                self.cursor = self.conn.cursor()
                
                messagebox.showinfo("Sukses", f"Database berhasil dibackup ke:\n{filename}")
                self.backup_log.insert("end", f"✅ [{datetime.now().strftime('%H:%M:%S')}] Database dibackup ke {filename}\n")
                self.backup_log.see("end")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal backup database:\n{str(e)}")
                self.backup_log.insert("end", f"❌ [{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}\n")
                self.backup_log.see("end")
    
    def restore_all_templates(self):
        """Restore semua template fingerprint ke sensor"""
        if not self.is_connected:
            messagebox.showwarning("Peringatan", "Belum terkoneksi ke MQTT Broker!")
            return
        
        self.cursor.execute('SELECT id, name, fingerprint_template FROM users WHERE fingerprint_template IS NOT NULL')
        users = self.cursor.fetchall()
        
        if not users:
            messagebox.showinfo("Info", "Tidak ada template yang tersimpan di database")
            return
        
        if messagebox.askyesno("Konfirmasi", 
            f"Restore {len(users)} template fingerprint ke sensor?\n\nProses ini akan memakan waktu beberapa menit."):
            
            self.backup_log.insert("end", f"\n{'='*50}\n")
            self.backup_log.insert("end", f"Memulai restore {len(users)} templates...\n")
            self.backup_log.insert("end", f"{'='*50}\n")
            
            for user_id, name, template in users:
                template_b64 = base64.b64encode(template).decode()
                
                self.publish_command({
                    "cmd": "RESTORE_TEMPLATE",
                    "id": user_id,
                    "template": template_b64
                })
                
                self.backup_log.insert("end", f"⏳ Mengirim template {name} (ID: {user_id})...\n")
                self.backup_log.see("end")
                self.root.update()
                
                time.sleep(2)  # Delay untuk processing
            
            self.backup_log.insert("end", f"\n✅ Proses restore selesai!\n")
            self.backup_log.see("end")
    
    def restore_single_template(self):
        """Restore template user tertentu"""
        if not self.is_connected:
            messagebox.showwarning("Peringatan", "Belum terkoneksi ke MQTT Broker!")
            return
        
        # Dialog untuk memilih user
        restore_window = tk.Toplevel(self.root)
        restore_window.title("Restore Template User")
        restore_window.geometry("400x300")
        
        ttk.Label(restore_window, text="Pilih User untuk Restore", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Listbox untuk user
        frame = ttk.Frame(restore_window)
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Load users dengan template
        self.cursor.execute('SELECT id, name FROM users WHERE fingerprint_template IS NOT NULL ORDER BY id')
        users = self.cursor.fetchall()
        
        if not users:
            ttk.Label(restore_window, text="Tidak ada template tersedia", foreground="red").pack()
            return
        
        user_dict = {}
        for user_id, name in users:
            display = f"ID: {user_id} - {name}"
            listbox.insert("end", display)
            user_dict[display] = user_id
        
        def do_restore():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Peringatan", "Pilih user terlebih dahulu")
                return
            
            selected = listbox.get(selection[0])
            user_id = user_dict[selected]
            
            self.cursor.execute('SELECT name, fingerprint_template FROM users WHERE id = ?', (user_id,))
            result = self.cursor.fetchone()
            
            if result:
                name, template = result
                template_b64 = base64.b64encode(template).decode()
                
                self.publish_command({
                    "cmd": "RESTORE_TEMPLATE",
                    "id": user_id,
                    "template": template_b64
                })
                
                self.backup_log.insert("end", f"⏳ Mengirim template {name} (ID: {user_id})...\n")
                self.backup_log.see("end")
                
                restore_window.destroy()
        
        btn_frame = ttk.Frame(restore_window)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="♻️ Restore", command=do_restore).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Batal", command=restore_window.destroy).pack(side="left", padx=5)
    
    def log(self, message):
        """Tambahkan log ke text widget"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
    
    def on_closing(self):
        """Handler saat aplikasi ditutup"""
        if self.is_connected:
            self.disconnect_mqtt()
        self.conn.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()