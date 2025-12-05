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

class RoundedButton(tk.Canvas):
    """Custom rounded button"""
    def __init__(self, parent, text, command=None, radius=10, padding=(20, 10), 
                 bg_color='#9B7EDE', fg_color='white', hover_color='#8B6FD9', 
                 font=('Segoe UI', 10, 'bold'), **kwargs):
        tk.Canvas.__init__(self, parent, **kwargs)
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg_color = fg_color
        self.text = text
        self.font = font
        self.radius = radius
        self.padding = padding
        self.enabled = True  # Button state
        
        # Calculate size
        temp_label = tk.Label(self, text=text, font=font)
        temp_label.update_idletasks()
        text_width = temp_label.winfo_reqwidth()
        text_height = temp_label.winfo_reqheight()
        temp_label.destroy()
        
        width = text_width + padding[0] * 2
        height = text_height + padding[1] * 2
        
        self.config(width=width, height=height, highlightthickness=0, bg=parent['bg'])
        
        # Draw rounded rectangle
        self.bg_rect = self._round_rectangle(0, 0, width, height, radius, fill=bg_color, outline='')
        self.text_id = self.create_text(width/2, height/2, text=text, fill=fg_color, font=font)
        
        # Bind events
        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.config(cursor='hand2')
    
    def _round_rectangle(self, x1, y1, x2, y2, radius=25, **kwargs):
        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _on_click(self, event):
        if self.command and self.enabled:
            self.command()
    
    def _on_enter(self, event):
        if self.enabled:
            self.itemconfig(self.bg_rect, fill=self.hover_color)
    
    def _on_leave(self, event):
        self.itemconfig(self.bg_rect, fill=self.bg_color)
    
    def config_text(self, text):
        self.itemconfig(self.text_id, text=text)
    
    def config_color(self, bg_color):
        self.bg_color = bg_color
        self.itemconfig(self.bg_rect, fill=bg_color)
    
    def config(self, **kwargs):
        """Override config to handle state and cursor"""
        if 'state' in kwargs:
            state = kwargs.pop('state')
            self.enabled = (state != 'disabled')
            if not self.enabled:
                # Disabled appearance
                self.itemconfig(self.bg_rect, fill='#D0D0D0')
                self.itemconfig(self.text_id, fill='#888888')
            else:
                # Enabled appearance
                self.itemconfig(self.bg_rect, fill=self.bg_color)
                self.itemconfig(self.text_id, fill=self.fg_color)
        
        if 'cursor' in kwargs:
            cursor = kwargs.pop('cursor')
            super().config(cursor=cursor)
        
        # Pass remaining kwargs to parent
        if kwargs:
            super().config(**kwargs)

class RoundedEntry(tk.Frame):
    """Custom rounded entry"""
    def __init__(self, parent, width=20, **kwargs):
        tk.Frame.__init__(self, parent, bg=parent['bg'])
        
        self.entry = tk.Entry(self, width=width, font=('Segoe UI', 10),
                             relief='flat', bd=0, bg='white', 
                             highlightthickness=1, highlightbackground='#D0D0D0',
                             highlightcolor='#9B7EDE', **kwargs)
        self.entry.pack(padx=2, pady=2, ipady=6)
    
    def get(self):
        return self.entry.get()
    
    def insert(self, index, string):
        return self.entry.insert(index, string)
    
    def delete(self, first, last=None):
        return self.entry.delete(first, last)

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VeriFynger - Sistem Presensi Fingerprint")
        # Set fullscreen
        self.root.state('zoomed')  # For Windows - maximized window
        self.root.resizable(True, True)
        
        # Setup tema dan styling
        self.setup_theme()
        
        # MQTT Configuration
        self.mqtt_broker = "test.mosquitto.org"  # Public MQTT broker untuk testing
        self.mqtt_port = 1883
        self.mqtt_client = None
        self.is_connected = False
        
        # MQTT Topics
        # MQTT Topics - Must match ESP32 Config.h
        self.TOPIC_CMD_MODE = "verifynger/command/mode"
        self.TOPIC_CMD_ENROLL = "verifynger/command/enroll"
        self.TOPIC_CMD_SENSOR = "verifynger/command/sensor"
        self.TOPIC_CMD_RELAY = "verifynger/command/relay"
        
        self.TOPIC_RES_TEMPLATE = "verifynger/response/template"
        self.TOPIC_RES_STATUS = "verifynger/response/status"
        self.TOPIC_RES_ERROR = "verifynger/response/error"
        
        self.TOPIC_VERIFY_REQUEST = "verifynger/verify/request"
        self.TOPIC_VERIFY_RESPONSE = "verifynger/verify/response"
        
        self.TOPIC_SYS_HEALTH = "verifynger/system/health"
        self.TOPIC_SYS_CONFIG = "verifynger/system/config"
        self.TOPIC_SENSOR_METRICS = "verifynger/sensor/metrics"
        
        self.users = {}
        
        # Sensor tracking
        self.active_sensor = "FPM10A"  # Default sensor
        self.sensor_list = ["FPM10A", "AS608", "ZW101"]
        
        # Sensor metrics tracking
        self.sensor_metrics = {
            "FPM10A": {
                "capacity": 100,
                "used": 0,
                "response_time": [],
                "success_count": 0,
                "fail_count": 0,
                "avg_confidence": 0,
                "total_scans": 0,
                "last_update": None
            },
            "AS608": {
                "capacity": 200,
                "used": 0,
                "response_time": [],
                "success_count": 0,
                "fail_count": 0,
                "avg_confidence": 0,
                "total_scans": 0,
                "last_update": None
            },
            "ZW101": {
                "capacity": 50,
                "used": 0,
                "response_time": [],
                "success_count": 0,
                "fail_count": 0,
                "avg_confidence": 0,
                "total_scans": 0,
                "last_update": None
            }
        }
        
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
        style.configure('TNotebook', background=self.colors['bg_main'], borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure('TNotebook.Tab',
                       background=self.colors['secondary'],
                       foreground=self.colors['text_dark'],
                       padding=[25, 12],
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=0,
                       focuscolor='')
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['primary'])],
                 foreground=[('selected', self.colors['text_light'])],
                 padding=[('selected', [25, 12])])
        
        # Configure Treeview
        style.configure('Treeview',
                       background='white',
                       foreground=self.colors['text_dark'],
                       fieldbackground='white',
                       borderwidth=0,
                       font=('Segoe UI', 11),
                       rowheight=30)
        style.configure('Treeview.Heading',
                       background=self.colors['primary'],
                       foreground=self.colors['text_light'],
                       borderwidth=0,
                       font=('Segoe UI', 12, 'bold'))
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
        
        # Check if users table migration is needed (old schema with 'id' column)
        self.cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in self.cursor.fetchall()]
        
        needs_migration = False
        old_users = []
        if columns and 'id' in columns and 'id_user' not in columns:
            needs_migration = True
            print("⚠️ Old database schema detected. Migrating to new schema...")
            
            # Backup old data
            self.cursor.execute('SELECT * FROM users')
            old_users = self.cursor.fetchall()
            
            # Drop old table
            self.cursor.execute('DROP TABLE IF EXISTS users')
            self.conn.commit()
            
            print(f"✓ Backed up {len(old_users)} users")
        
        # Tabel users - template berisi hash dari (fingerprint_id + sensor_name)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id_user INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                position TEXT,
                fingerprint_template TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Restore data if migration happened
        if needs_migration and old_users:
            print("✓ Restoring user data with new schema...")
            for user in old_users:
                # old_users columns: id, name, email, position, fingerprint_template, created_at, updated_at
                # OR: id, name, email, position, fingerprint_template, sensor_type, fingerprint_id, created_at, updated_at
                # Generate hash from old data
                try:
                    sensor_type = user[5] if len(user) > 5 and user[5] else None
                    fingerprint_id = user[6] if len(user) > 6 and user[6] is not None else None
                    
                    # Create hash: "SENSOR_ID" (e.g., "AS608_1")
                    if sensor_type and fingerprint_id is not None:
                        fingerprint_hash = f"{sensor_type}_{fingerprint_id}"
                    else:
                        fingerprint_hash = "UNKNOWN_0"  # Fallback for old data
                    
                    self.cursor.execute('''
                        INSERT INTO users (id_user, name, email, position, fingerprint_template, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (user[0], user[1], user[2], user[3], fingerprint_hash, 
                         user[5] if len(user) > 5 else None, user[6] if len(user) > 6 else None))
                except Exception as e:
                    print(f"⚠️ Error restoring user {user[1]}: {e}")
            self.conn.commit()
            print(f"✓ Migration completed. {len(old_users)} users restored.")
        
        # Check if attendance_logs table needs migration (has 'location' column)
        self.cursor.execute("PRAGMA table_info(attendance_logs)")
        log_columns = [col[1] for col in self.cursor.fetchall()]
        
        needs_log_migration = False
        old_logs = []
        if log_columns and 'location' in log_columns and 'fingerprint_hash' not in log_columns:
            needs_log_migration = True
            print("⚠️ Old attendance_logs schema detected. Migrating...")
            
            # Backup old logs
            self.cursor.execute('SELECT * FROM attendance_logs')
            old_logs = self.cursor.fetchall()
            
            # Drop old table
            self.cursor.execute('DROP TABLE IF EXISTS attendance_logs')
            self.conn.commit()
            
            print(f"✓ Backed up {len(old_logs)} attendance logs")
        
        # Tabel attendance logs
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                match_score INTEGER,
                fingerprint_hash TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id_user) ON DELETE CASCADE
            )
        ''')
        
        # Restore attendance logs if migration happened
        if needs_log_migration and old_logs:
            print("✓ Restoring attendance logs with new schema...")
            for log in old_logs:
                # old_logs columns: log_id, user_id, user_name, check_in_time, match_score, location
                try:
                    # Map old location to fingerprint_hash (use placeholder if needed)
                    fp_hash = log[5] if len(log) > 5 else "MIGRATED_UNKNOWN"
                    
                    self.cursor.execute('''
                        INSERT INTO attendance_logs (log_id, user_id, user_name, check_in_time, match_score, fingerprint_hash)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (log[0], log[1], log[2], log[3], log[4], fp_hash))
                except Exception as e:
                    print(f"⚠️ Error restoring log {log[0]}: {e}")
            self.conn.commit()
            print(f"✓ Attendance logs migration completed. {len(old_logs)} logs restored.")
        
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
        self.cursor.execute('SELECT id_user, name FROM users')
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
        
        # Input container untuk alignment yang lebih baik
        input_frame = tk.Frame(conn_frame, bg=self.colors['bg_frame'])
        input_frame.grid(row=1, column=0, columnspan=6, padx=15, pady=(5, 15))
        
        tk.Label(input_frame, text="Broker Address:", bg=self.colors['bg_frame'], 
                fg=self.colors['text_dark'], font=('Segoe UI', 10)).pack(side="left", padx=(0, 8))
        
        self.entry_broker = RoundedEntry(input_frame, width=20)
        self.entry_broker.pack(side="left", padx=(0, 15))
        self.entry_broker.insert(0, self.mqtt_broker)
        
        tk.Label(input_frame, text="Port:", bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'], font=('Segoe UI', 10)).pack(side="left", padx=(0, 8))
        
        self.entry_port = RoundedEntry(input_frame, width=8)
        self.entry_port.pack(side="left", padx=(0, 15))
        self.entry_port.insert(0, str(self.mqtt_port))
        
        self.btn_connect = RoundedButton(input_frame, text="🔗 Connect",
                                        command=self.toggle_connection,
                                        bg_color=self.colors['primary'],
                                        fg_color=self.colors['text_light'],
                                        hover_color=self.colors['hover'],
                                        font=('Segoe UI', 10, 'bold'),
                                        padding=(25, 10),
                                        radius=10)
        self.btn_connect.pack(side="left", padx=(0, 15))
        
        self.status_label = tk.Label(input_frame, text="● Disconnected", 
                                     bg=self.colors['bg_frame'],
                                     foreground=self.colors['error'], 
                                     font=('Segoe UI', 10, 'bold'))
        self.status_label.pack(side="left", padx=(0, 15))
        
        # Sensor status and control
        tk.Label(input_frame, text="📟 Sensor:", bg=self.colors['bg_frame'],
                fg=self.colors['text_dark'], font=('Segoe UI', 10, 'bold')).pack(side="left", padx=(0, 5))
        
        self.sensor_status = tk.Label(input_frame, text=self.active_sensor,
                                      bg=self.colors['bg_frame'],
                                      foreground=self.colors['accent'],
                                      font=('Segoe UI', 10, 'bold'))
        self.sensor_status.pack(side="left", padx=(0, 10))
        
        self.btn_cycle_sensor = RoundedButton(input_frame, text="🔄 Cycle Sensor",
                                             command=self.cycle_sensor,
                                             bg_color=self.colors['accent'],
                                             fg_color=self.colors['text_light'],
                                             hover_color=self.colors['hover'],
                                             font=('Segoe UI', 9, 'bold'),
                                             padding=(15, 8),
                                             radius=8)
        self.btn_cycle_sensor.pack(side="left", padx=(0, 5))
        
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
        
        # Tab 4: Analisa Sensor
        tab_analysis = ttk.Frame(notebook)
        notebook.add(tab_analysis, text="📈 Analisa Sensor")
        self.setup_analysis_tab(tab_analysis)
    
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
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=canvas.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas width to scrollable_frame width
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        # Bind mouse wheel to canvas - only when mouse is over canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        
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
        
        # Custom styled buttons (instead of radiobuttons)
        self.btn_mode_presensi = RoundedButton(mode_info, text="🕐 Mode Presensi",
                                              command=lambda: self.switch_to_mode("PRESENSI"),
                                              bg_color=self.colors['primary'],
                                              fg_color=self.colors['text_light'],
                                              hover_color=self.colors['hover'],
                                              font=('Segoe UI', 11, 'bold'),
                                              padding=(25, 12),
                                              radius=10)
        self.btn_mode_presensi.pack(side="left", padx=10)
        
        self.btn_mode_daftar = RoundedButton(mode_info, text="✍️ Mode Daftar",
                                            command=lambda: self.switch_to_mode("DAFTAR"),
                                            bg_color=self.colors['secondary'],
                                            fg_color=self.colors['text_dark'],
                                            hover_color=self.colors['primary'],
                                            font=('Segoe UI', 11, 'bold'),
                                            padding=(25, 12),
                                            radius=10)
        self.btn_mode_daftar.pack(side="left", padx=10)
        
        # Set initial button state (presensi is active by default)
        self.btn_mode_presensi.config(state='disabled', cursor='arrow')
        
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
        
        # Frame Pendaftaran dengan card design - akan di-switch sesuai mode
        self.register_container = ttk.Frame(scrollable_frame)
        self.register_container.pack(fill="both", expand=True, padx=10, pady=(5, 5))
        
        register_frame = tk.Frame(self.register_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        register_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Shadow effect
        shadow = tk.Frame(self.register_container, bg='#E0E0E0')
        shadow.place(in_=register_frame, x=3, y=3, relwidth=1, relheight=1)
        register_frame.lift()
        
        # Title yang akan berubah sesuai mode
        self.reg_title = tk.Label(register_frame,
                            text="📝 Pendaftaran User Baru",
                            bg=self.colors['bg_frame'],
                            fg=self.colors['primary'],
                            font=('Segoe UI', 12, 'bold'))
        self.reg_title.pack(anchor="w", padx=20, pady=(20, 15))
        
        # Form frame - untuk mode DAFTAR (input form)
        self.form_frame_daftar = tk.Frame(register_frame, bg=self.colors['bg_frame'])
        self.form_frame_daftar.pack(fill="x", padx=20, pady=10)
        
        tk.Label(self.form_frame_daftar, text="ID User:", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=0, column=0, sticky="w", pady=12, padx=5)
        self.entry_id = RoundedEntry(self.form_frame_daftar, width=22)
        self.entry_id.grid(row=0, column=1, pady=12, padx=10, sticky="w")
        # Bind event untuk validasi ID user saat input berubah
        self.entry_id.entry.bind('<KeyRelease>', self.validate_user_id)
        
        tk.Label(self.form_frame_daftar, text="Nama User:", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=1, column=0, sticky="w", pady=12, padx=5)
        self.entry_name = RoundedEntry(self.form_frame_daftar, width=40)
        self.entry_name.grid(row=1, column=1, pady=12, padx=10, sticky="w")
        
        tk.Label(self.form_frame_daftar, text="Email:", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=2, column=0, sticky="w", pady=12, padx=5)
        self.entry_email = RoundedEntry(self.form_frame_daftar, width=40)
        self.entry_email.grid(row=2, column=1, pady=12, padx=10, sticky="w")
        
        tk.Label(self.form_frame_daftar, text="Jabatan:", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=3, column=0, sticky="w", pady=12, padx=5)
        self.entry_position = RoundedEntry(self.form_frame_daftar, width=40)
        self.entry_position.grid(row=3, column=1, pady=12, padx=10, sticky="w")
        
        # Fingerprint Template Display (readonly)
        tk.Label(self.form_frame_daftar, text="Fingerprint Template:", 
                bg=self.colors['bg_frame'], fg=self.colors['text_dark'],
                font=('Segoe UI', 10)).grid(row=4, column=0, sticky="w", pady=12, padx=5)
        
        self.template_display_frame = tk.Frame(self.form_frame_daftar, bg=self.colors['bg_frame'])
        self.template_display_frame.grid(row=4, column=1, pady=12, padx=10, sticky="w")
        
        self.template_display = tk.Entry(self.template_display_frame, width=40, 
                                         font=('Segoe UI', 10, 'bold'),
                                         relief='flat', bd=1, bg='#F5F3FF',
                                         state='readonly',
                                         fg=self.colors['accent'],
                                         readonlybackground='#F5F3FF')
        self.template_display.pack(ipady=6)
        
        # Variable untuk menyimpan hash sementara
        self.pending_fingerprint_hash = None
        
        # Button frame
        self.btn_frame_daftar = tk.Frame(register_frame, bg=self.colors['bg_frame'])
        self.btn_frame_daftar.pack(pady=20)
        
        # Button "Add Fingerprint Template" - hanya enrollment
        add_template_btn = RoundedButton(self.btn_frame_daftar, 
                                         text="🖐️ Add Fingerprint Template",
                                         command=self.add_fingerprint_template,
                                         bg_color=self.colors['accent'],
                                         fg_color=self.colors['text_light'],
                                         hover_color=self.colors['hover'],
                                         font=('Segoe UI', 11, 'bold'),
                                         padding=(30, 12),
                                         radius=12)
        add_template_btn.pack(side="left", padx=8)
        
        # Button "Save User" - simpan ke database (initially disabled)
        self.save_user_btn = RoundedButton(self.btn_frame_daftar, 
                                      text="💾 Save User",
                                      command=self.save_user_to_database,
                                      bg_color=self.colors['success'],
                                      fg_color=self.colors['text_light'],
                                      hover_color='#689F38',
                                      font=('Segoe UI', 11, 'bold'),
                                      padding=(30, 12),
                                      radius=12)
        self.save_user_btn.pack(side="left", padx=8)
        # Set initial state to disabled (akan di-enable setelah dapat fingerprint hash)
        self.save_user_btn.config(state='disabled', cursor='arrow')
        
        # Button "Clear Form"
        clear_btn = RoundedButton(self.btn_frame_daftar, text="🗑️ Clear Form",
                                 command=self.clear_form,
                                 bg_color=self.colors['secondary'],
                                 fg_color=self.colors['text_dark'],
                                 hover_color=self.colors['primary'],
                                 font=('Segoe UI', 10, 'bold'),
                                 padding=(25, 12),
                                 radius=12)
        clear_btn.pack(side="left", padx=8)
        
        # Form frame - untuk mode PRESENSI (display only)
        self.form_frame_presensi = tk.Frame(register_frame, bg=self.colors['bg_frame'])
        
        # Info text
        info_text = tk.Label(self.form_frame_presensi, 
                            text="Silakan scan fingerprint untuk melakukan presensi.\nInformasi user akan ditampilkan di bawah setelah scan berhasil.",
                            bg=self.colors['bg_frame'],
                            fg=self.colors['text_dark'],
                            font=('Segoe UI', 10),
                            justify="center")
        info_text.pack(pady=(10, 20))
        
        # Display frame with larger font and better styling
        display_frame = tk.Frame(self.form_frame_presensi, bg=self.colors['bg_frame'])
        display_frame.pack(fill="x", padx=20, pady=10)
        
        # ID User
        id_container = tk.Frame(display_frame, bg='#F5F3FF', relief='flat', bd=0)
        id_container.grid(row=0, column=0, columnspan=2, sticky="ew", pady=8, padx=5)
        tk.Label(id_container, text="🆔 ID User:", 
                bg='#F5F3FF', fg=self.colors['text_dark'],
                font=('Segoe UI', 10, 'bold')).pack(side="left", padx=(15, 10), pady=12)
        self.display_id = tk.Label(id_container, text="-",
                                   bg='#F5F3FF', fg=self.colors['accent'],
                                   font=('Segoe UI', 14, 'bold'))
        self.display_id.pack(side="left", padx=10, pady=12)
        
        # Nama
        nama_container = tk.Frame(display_frame, bg='#F5F3FF', relief='flat', bd=0)
        nama_container.grid(row=1, column=0, columnspan=2, sticky="ew", pady=8, padx=5)
        tk.Label(nama_container, text="👤 Nama:", 
                bg='#F5F3FF', fg=self.colors['text_dark'],
                font=('Segoe UI', 10, 'bold')).pack(side="left", padx=(15, 10), pady=12)
        self.display_name = tk.Label(nama_container, text="-",
                                     bg='#F5F3FF', fg=self.colors['text_dark'],
                                     font=('Segoe UI', 13, 'bold'))
        self.display_name.pack(side="left", padx=10, pady=12)
        
        # Email
        email_container = tk.Frame(display_frame, bg='#F5F3FF', relief='flat', bd=0)
        email_container.grid(row=2, column=0, columnspan=2, sticky="ew", pady=8, padx=5)
        tk.Label(email_container, text="📧 Email:", 
                bg='#F5F3FF', fg=self.colors['text_dark'],
                font=('Segoe UI', 10, 'bold')).pack(side="left", padx=(15, 10), pady=12)
        self.display_email = tk.Label(email_container, text="-",
                                      bg='#F5F3FF', fg=self.colors['text_dark'],
                                      font=('Segoe UI', 12))
        self.display_email.pack(side="left", padx=10, pady=12)
        
        # Jabatan
        jabatan_container = tk.Frame(display_frame, bg='#F5F3FF', relief='flat', bd=0)
        jabatan_container.grid(row=3, column=0, columnspan=2, sticky="ew", pady=8, padx=5)
        tk.Label(jabatan_container, text="💼 Jabatan:", 
                bg='#F5F3FF', fg=self.colors['text_dark'],
                font=('Segoe UI', 10, 'bold')).pack(side="left", padx=(15, 10), pady=12)
        self.display_position = tk.Label(jabatan_container, text="-",
                                        bg='#F5F3FF', fg=self.colors['text_dark'],
                                        font=('Segoe UI', 12))
        self.display_position.pack(side="left", padx=10, pady=12)
        
        display_frame.columnconfigure(0, weight=1)
        
        # Show PRESENSI form by default (matches default mode)
        self.form_frame_daftar.pack_forget()
        self.btn_frame_daftar.pack_forget()
        self.form_frame_presensi.pack(fill="x", padx=20, pady=10)
        
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
        
        # Frame toolbar dengan styling modern
        toolbar_container = ttk.Frame(parent)
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
        refresh_btn = RoundedButton(btn_container, text="🔄 Refresh",
                                   command=self.refresh_user_list,
                                   bg_color=self.colors['primary'],
                                   fg_color=self.colors['text_light'],
                                   hover_color=self.colors['hover'],
                                   font=('Segoe UI', 9, 'bold'),
                                   padding=(18, 10),
                                   radius=10)
        refresh_btn.pack(side="left", padx=5)
        
        edit_btn = RoundedButton(btn_container, text="✏️ Edit User",
                                command=self.edit_user,
                                bg_color=self.colors['secondary'],
                                fg_color=self.colors['text_dark'],
                                hover_color=self.colors['primary'],
                                font=('Segoe UI', 9, 'bold'),
                                padding=(18, 10),
                                radius=10)
        edit_btn.pack(side="left", padx=5)
        
        delete_btn = RoundedButton(btn_container, text="🗑️ Hapus User",
                                  command=self.delete_user,
                                  bg_color=self.colors['error'],
                                  fg_color=self.colors['text_light'],
                                  hover_color='#E53935',
                                  font=('Segoe UI', 9, 'bold'),
                                  padding=(18, 10),
                                  radius=10)
        delete_btn.pack(side="left", padx=5)
        
        export_btn = RoundedButton(btn_container, text="📤 Export CSV",
                                  command=self.export_users,
                                  bg_color=self.colors['success'],
                                  fg_color=self.colors['text_light'],
                                  hover_color='#689F38',
                                  font=('Segoe UI', 9, 'bold'),
                                  padding=(18, 10),
                                  radius=10)
        export_btn.pack(side="left", padx=5)
        
        # Info label
        self.user_count_label = tk.Label(btn_container, text="Total: 0 users", 
                                         bg=self.colors['bg_frame'],
                                         fg=self.colors['primary'],
                                         font=('Segoe UI', 13, 'bold'))
        self.user_count_label.pack(side="right", padx=15)
        
        # Treeview untuk daftar user dengan card design
        tree_container = ttk.Frame(parent)
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
                             font=('Segoe UI', 13, 'bold'))
        tree_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Treeview wrapper
        tree_wrapper = tk.Frame(tree_frame, bg=self.colors['bg_frame'])
        tree_wrapper.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        scrollbar_y = ttk.Scrollbar(tree_wrapper)
        scrollbar_y.pack(side="right", fill="y")
        
        scrollbar_x = ttk.Scrollbar(tree_wrapper, orient="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")
        
        self.user_tree = ttk.Treeview(tree_wrapper, 
                                      columns=("ID", "Nama", "Email", "Jabatan", "Hash", "Tanggal"), 
                                      show="headings", 
                                      yscrollcommand=scrollbar_y.set,
                                      xscrollcommand=scrollbar_x.set,
                                      height=15)
        scrollbar_y.config(command=self.user_tree.yview)
        scrollbar_x.config(command=self.user_tree.xview)
        
        self.user_tree.heading("ID", text="User ID")
        self.user_tree.heading("Nama", text="Nama")
        self.user_tree.heading("Email", text="Email")
        self.user_tree.heading("Jabatan", text="Jabatan")
        self.user_tree.heading("Hash", text="Fingerprint Hash")
        self.user_tree.heading("Tanggal", text="Tanggal Daftar")
        
        self.user_tree.column("ID", width=70, anchor="center")
        self.user_tree.column("Nama", width=180)
        self.user_tree.column("Email", width=200)
        self.user_tree.column("Jabatan", width=150)
        self.user_tree.column("Hash", width=150, anchor="center")
        self.user_tree.column("Tanggal", width=150, anchor="center")
        
        # Alternating row colors
        self.user_tree.tag_configure('oddrow', background='white')
        self.user_tree.tag_configure('evenrow', background='#F9F9FF')
        
        self.user_tree.pack(fill="both", expand=True)
        
        self.refresh_user_list()
    
    def setup_logs_tab(self, parent):
        """Tab untuk log presensi"""
        parent.configure(style='TFrame')
        
        # Frame toolbar dengan styling modern
        toolbar_container = ttk.Frame(parent)
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
        refresh_btn = RoundedButton(btn_container, text="🔄 Refresh",
                                   command=self.refresh_attendance_logs,
                                   bg_color=self.colors['primary'],
                                   fg_color=self.colors['text_light'],
                                   hover_color=self.colors['hover'],
                                   font=('Segoe UI', 9, 'bold'),
                                   padding=(18, 10),
                                   radius=10)
        refresh_btn.pack(side="left", padx=5)
        
        clear_btn = RoundedButton(btn_container, text="🗑️ Hapus Semua Log",
                                 command=self.clear_logs,
                                 bg_color=self.colors['error'],
                                 fg_color=self.colors['text_light'],
                                 hover_color='#E53935',
                                 font=('Segoe UI', 9, 'bold'),
                                 padding=(18, 10),
                                 radius=10)
        clear_btn.pack(side="left", padx=5)
        
        export_btn = RoundedButton(btn_container, text="📤 Export CSV",
                                  command=self.export_logs,
                                  bg_color=self.colors['success'],
                                  fg_color=self.colors['text_light'],
                                  hover_color='#689F38',
                                  font=('Segoe UI', 9, 'bold'),
                                  padding=(18, 10),
                                  radius=10)
        export_btn.pack(side="left", padx=5)
        
        # Filter section
        tk.Label(btn_container, text="🔍", 
                bg=self.colors['bg_frame'],
                font=('Segoe UI', 11)).pack(side="left", padx=(20, 5))
        
        self.filter_var = tk.StringVar()
        self.filter_entry = RoundedEntry(btn_container, width=25)
        self.filter_entry.pack(side="left", padx=5)
        self.filter_entry.entry.config(textvariable=self.filter_var)
        self.filter_entry.entry.bind('<Return>', lambda e: self.filter_logs())
        
        search_btn = RoundedButton(btn_container, text="Cari Nama",
                                  command=self.filter_logs,
                                  bg_color=self.colors['accent'],
                                  fg_color=self.colors['text_light'],
                                  hover_color=self.colors['hover'],
                                  font=('Segoe UI', 9, 'bold'),
                                  padding=(18, 10),
                                  radius=10)
        search_btn.pack(side="left", padx=5)
        
        # Info label
        self.log_count_label = tk.Label(btn_container, text="Total: 0 logs", 
                                        bg=self.colors['bg_frame'],
                                        fg=self.colors['primary'],
                                        font=('Segoe UI', 13, 'bold'))
        self.log_count_label.pack(side="right", padx=15)
        
        # Filter tanggal dengan card design
        filter_date_container = ttk.Frame(parent)
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
                               font=('Segoe UI', 13, 'bold'))
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
        filter_date_btn = RoundedButton(date_filter_controls, text="🔍 Filter Tanggal",
                                        command=self.filter_logs_by_date,
                                        bg_color=self.colors['success'],
                                        fg_color=self.colors['text_light'],
                                        hover_color='#689F38',
                                        font=('Segoe UI', 9, 'bold'),
                                        padding=(18, 10),
                                        radius=10)
        filter_date_btn.pack(side="left", padx=10)
        
        reset_filter_btn = RoundedButton(date_filter_controls, text="↺ Reset",
                                         command=self.reset_date_filter,
                                         bg_color=self.colors['secondary'],
                                         fg_color=self.colors['text_dark'],
                                         hover_color=self.colors['primary'],
                                         font=('Segoe UI', 9, 'bold'),
                                         padding=(18, 10),
                                         radius=10)
        reset_filter_btn.pack(side="left", padx=5)
        
        # Treeview untuk log dengan card design
        tree_container = ttk.Frame(parent)
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
                             font=('Segoe UI', 13, 'bold'))
        tree_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Treeview wrapper
        tree_wrapper = tk.Frame(tree_frame, bg=self.colors['bg_frame'])
        tree_wrapper.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(tree_wrapper)
        scrollbar.pack(side="right", fill="y")
        
        self.log_tree = ttk.Treeview(tree_wrapper, 
                                     columns=("No", "ID", "Nama", "Waktu", "Score", "Hash"), 
                                     show="headings", 
                                     yscrollcommand=scrollbar.set,
                                     height=12)
        scrollbar.config(command=self.log_tree.yview)
        
        self.log_tree.heading("No", text="No")
        self.log_tree.heading("ID", text="ID User")
        self.log_tree.heading("Nama", text="Nama")
        self.log_tree.heading("Waktu", text="Waktu Presensi")
        self.log_tree.heading("Score", text="Score")
        self.log_tree.heading("Hash", text="Fingerprint Hash")
        
        self.log_tree.column("No", width=50, anchor="center")
        self.log_tree.column("ID", width=80, anchor="center")
        self.log_tree.column("Nama", width=200)
        self.log_tree.column("Waktu", width=180, anchor="center")
        self.log_tree.column("Score", width=80, anchor="center")
        self.log_tree.column("Hash", width=150, anchor="center")
        
        # Alternating row colors
        self.log_tree.tag_configure('oddrow', background='white')
        self.log_tree.tag_configure('evenrow', background='#F9F9FF')
        
        self.log_tree.pack(fill="both", expand=True)
        
        self.refresh_attendance_logs()
    
    def setup_analysis_tab(self, parent):
        """Tab untuk analisa perbandingan sensor"""
        parent.configure(style='TFrame')
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(parent, bg=self.colors['bg_main'], highlightthickness=0)
        scrollbar_main = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=canvas.winfo_width())
        canvas.configure(yscrollcommand=scrollbar_main.set)
        
        # Bind canvas width to scrollable_frame width
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        # Bind mouse wheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_main.pack(side="right", fill="y")
        
        # Header frame
        header_container = ttk.Frame(scrollable_frame)
        header_container.pack(fill="x", padx=10, pady=(10, 5))
        
        header_frame = tk.Frame(header_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        header_frame.pack(fill="x", padx=0, pady=0)
        
        shadow = tk.Frame(header_container, bg='#E0E0E0')
        shadow.place(in_=header_frame, x=3, y=3, relwidth=1, relheight=1)
        header_frame.lift()
        
        # Header content with title and refresh button in same row
        header_content = tk.Frame(header_frame, bg=self.colors['bg_frame'])
        header_content.pack(fill="x", padx=20, pady=15)
        
        # Left side - Title and subtitle
        title_frame = tk.Frame(header_content, bg=self.colors['bg_frame'])
        title_frame.pack(side="left", fill="x", expand=True)
        
        title = tk.Label(title_frame,
                        text="📊 Analisa Perbandingan Sensor Fingerprint",
                        bg=self.colors['bg_frame'],
                        fg=self.colors['primary'],
                        font=('Segoe UI', 16, 'bold'))
        title.pack(anchor="w")
        
        subtitle = tk.Label(title_frame,
                           text="Performa dan karakteristik sensor FPM10A, AS608, dan HLK-ZW101",
                           bg=self.colors['bg_frame'],
                           fg=self.colors['text_dark'],
                           font=('Segoe UI', 11))
        subtitle.pack(anchor="w", pady=(3, 0))
        
        # Right side - Refresh button
        refresh_btn = RoundedButton(header_content, text="🔄 Refresh Data",
                                    command=self.refresh_sensor_analysis,
                                    bg_color=self.colors['primary'],
                                    fg_color=self.colors['text_light'],
                                    hover_color=self.colors['hover'],
                                    font=('Segoe UI', 9, 'bold'),
                                    padding=(18, 10),
                                    radius=10)
        refresh_btn.pack(side="right", padx=(10, 0))
        
        # Sensor cards container - display in grid layout
        cards_container = ttk.Frame(scrollable_frame)
        cards_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Configure grid to have 3 equal columns
        cards_container.columnconfigure(0, weight=1)
        cards_container.columnconfigure(1, weight=1)
        cards_container.columnconfigure(2, weight=1)
        
        # FPM10A Card
        self.create_sensor_card(cards_container, "FPM10A", "📟 FPM10A Sensor", 0)
        
        # AS608 Card
        self.create_sensor_card(cards_container, "AS608", "📟 AS608 Sensor", 1)
        
        # ZW101 Card
        self.create_sensor_card(cards_container, "ZW101", "📟 HLK-ZW101 Sensor", 2)
        
        # Load initial data
        self.refresh_sensor_analysis()
    
    def create_sensor_card(self, parent, sensor_name, title, column):
        """Create individual sensor detail card with comprehensive parameters"""
        card_container = ttk.Frame(parent)
        card_container.grid(row=0, column=column, padx=8, pady=5, sticky="nsew")
        
        card = tk.Frame(card_container, bg=self.colors['bg_frame'], relief='flat', bd=0)
        card.pack(fill="both", expand=True)
        
        shadow = tk.Frame(card_container, bg='#E0E0E0')
        shadow.place(in_=card, x=3, y=3, relwidth=1, relheight=1)
        card.lift()
        
        # Title with colored background
        title_bg = tk.Frame(card, bg=self.colors['primary'], height=50)
        title_bg.pack(fill="x")
        title_bg.pack_propagate(False)
        
        card_title = tk.Label(title_bg,
                             text=title,
                             bg=self.colors['primary'],
                             fg=self.colors['text_light'],
                             font=('Segoe UI', 14, 'bold'))
        card_title.pack(anchor="center", expand=True)
        
        # Content area
        content = tk.Frame(card, bg=self.colors['bg_frame'])
        content.pack(fill="both", expand=True, padx=18, pady=15)
        
        # Status indicator with larger font
        status_frame = tk.Frame(content, bg='#F5F3FF', relief='flat', bd=0)
        status_frame.pack(fill="x", pady=(0, 12))
        
        tk.Label(status_frame, text="Status:", bg='#F5F3FF',
                fg=self.colors['text_dark'], font=('Segoe UI', 12, 'bold')).pack(side="left", padx=(12, 8), pady=10)
        
        status_label = tk.Label(status_frame, 
                               text="● Aktif" if sensor_name == self.active_sensor else "○ Tidak Aktif",
                               bg='#F5F3FF',
                               fg=self.colors['success'] if sensor_name == self.active_sensor else self.colors['text_dark'],
                               font=('Segoe UI', 12, 'bold'))
        status_label.pack(side="left", pady=10)
        
        # Store reference for updates
        setattr(self, f"status_label_{sensor_name}", status_label)
        
        # Separator
        sep = tk.Frame(content, bg=self.colors['secondary'], height=1)
        sep.pack(fill="x", pady=(0, 12))
        
        # Metrics with improved layout
        metrics_frame = tk.Frame(content, bg=self.colors['bg_frame'])
        metrics_frame.pack(fill="both", expand=True)
        
        # Create metric items with icons and better spacing
        metrics = [
            ("📦", "Kapasitas", f"capacity_label_{sensor_name}", "Storage capacity"),
            ("⚡", "Responsivitas", f"response_label_{sensor_name}", "Average response time"),
            ("🎯", "Rata-rata Confidence", f"confidence_label_{sensor_name}", "Match confidence"),
            ("📊", "Total Scan", f"total_scans_label_{sensor_name}", "Total scans performed"),
            ("⏱️", "Update Terakhir", f"last_update_label_{sensor_name}", "Last activity")
        ]
        
        for i, (icon, label_text, attr_name, tooltip) in enumerate(metrics):
            # Container for each metric
            metric_container = tk.Frame(metrics_frame, bg='#FAFAFA' if i % 2 == 0 else self.colors['bg_frame'])
            metric_container.pack(fill="x", pady=3)
            
            # Label row
            label_frame = tk.Frame(metric_container, bg='#FAFAFA' if i % 2 == 0 else self.colors['bg_frame'])
            label_frame.pack(fill="x", padx=8, pady=6)
            
            tk.Label(label_frame, text=f"{icon} {label_text}:", 
                    bg='#FAFAFA' if i % 2 == 0 else self.colors['bg_frame'],
                    fg=self.colors['text_dark'], 
                    font=('Segoe UI', 11, 'bold')).pack(side="left")
            
            value_label = tk.Label(label_frame, text="N/A", 
                                  bg='#FAFAFA' if i % 2 == 0 else self.colors['bg_frame'],
                                  fg=self.colors['accent'], 
                                  font=('Segoe UI', 11, 'bold'))
            value_label.pack(side="right")
            
            setattr(self, attr_name, value_label)
    
    def refresh_sensor_analysis(self):
        """Refresh sensor analysis cards with latest data"""
        # Count used capacity per sensor by reading database
        self.cursor.execute('SELECT fingerprint_template FROM users')
        templates = self.cursor.fetchall()
        
        # Reset used counts
        for sensor in self.sensor_metrics:
            self.sensor_metrics[sensor]['used'] = 0
        
        # Count templates per sensor
        for (template,) in templates:
            if template:
                # Template format: "SENSOR_ID" (e.g., "AS608_5")
                sensor_name = template.split('_')[0] if '_' in template else None
                if sensor_name in self.sensor_metrics:
                    self.sensor_metrics[sensor_name]['used'] += 1
        
        # Update sensor cards with latest data
        self.update_sensor_cards()
        
        self.log("📊 Data analisa sensor berhasil di-refresh")
    
    def calculate_avg_response_time(self, sensor_name):
        """Calculate average response time for sensor"""
        times = self.sensor_metrics[sensor_name]['response_time']
        if not times:
            return "N/A"
        avg = sum(times) / len(times)
        return f"{avg:.2f} ms"
    
    def update_sensor_cards(self):
        """Update individual sensor card displays"""
        for sensor in ["FPM10A", "AS608", "ZW101"]:
            # Update status
            status_label = getattr(self, f"status_label_{sensor}", None)
            if status_label:
                if sensor == self.active_sensor:
                    status_label.config(text="● Aktif", fg=self.colors['success'])
                else:
                    status_label.config(text="○ Tidak Aktif", fg=self.colors['text_dark'])
            
            # Update capacity
            capacity_label = getattr(self, f"capacity_label_{sensor}", None)
            if capacity_label:
                used = self.sensor_metrics[sensor]['used']
                total = self.sensor_metrics[sensor]['capacity']
                capacity_label.config(text=f"{used} / {total} ({(used/total*100):.1f}%)")
            
            # Update responsiveness
            response_label = getattr(self, f"response_label_{sensor}", None)
            if response_label:
                response_label.config(text=self.calculate_avg_response_time(sensor))
            
            # Update confidence
            confidence_label = getattr(self, f"confidence_label_{sensor}", None)
            if confidence_label:
                conf = self.sensor_metrics[sensor]['avg_confidence']
                confidence_label.config(text=f"{conf:.1f}%")
            
            # Update total scans
            total_scans_label = getattr(self, f"total_scans_label_{sensor}", None)
            if total_scans_label:
                total = self.sensor_metrics[sensor]['total_scans']
                total_scans_label.config(text=f"{total} kali")
            
            # Update last update
            last_update_label = getattr(self, f"last_update_label_{sensor}", None)
            if last_update_label:
                last_update = self.sensor_metrics[sensor]['last_update']
                if last_update:
                    last_update_label.config(text=last_update)
                else:
                    last_update_label.config(text="Belum ada aktivitas")
    
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
            self.btn_connect.config_text("🔌 Disconnect")
            self.btn_connect.config_color(self.colors['error'])
            self.log(f"✅ Terhubung ke MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")
            
            # Subscribe ke topics
            # Subscribe to all ESP32 response topics
            self.mqtt_client.subscribe(self.TOPIC_RES_TEMPLATE)
            self.mqtt_client.subscribe(self.TOPIC_RES_STATUS)
            self.mqtt_client.subscribe(self.TOPIC_RES_ERROR)
            self.mqtt_client.subscribe(self.TOPIC_VERIFY_REQUEST)
            self.mqtt_client.subscribe(self.TOPIC_VERIFY_RESPONSE)
            self.mqtt_client.subscribe(self.TOPIC_SYS_HEALTH)
            self.mqtt_client.subscribe(self.TOPIC_SENSOR_METRICS)
            
            self.log(f"📡 Subscribed to topics: template, status, error, verify_request, verify_response, health, metrics")
            
            # Save settings
            self.save_settings()
            
            # Publish current selected mode from radiobutton
            current_mode = self.current_mode.get().lower()
            self.publish_command({"mode": current_mode}, topic=self.TOPIC_CMD_MODE)
            self.mode_status.config(text=current_mode.upper())
            self.log(f"📡 Mode synchronized to ESP32: {current_mode.upper()}")
            
            # Update sensor cards di tab Analysis dengan data terbaru
            self.root.after(100, self.update_sensor_cards)
            
            # Note: ESP32 does not store user list locally
            # All verification is done via MQTT template matching
            # self.sync_users_to_esp()  # Not needed
        else:
            self.log(f"❌ Gagal koneksi: RC={rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback saat disconnect dari MQTT"""
        self.is_connected = False
        self.status_label.config(text="● Disconnected", foreground=self.colors['error'])
        self.btn_connect.config_text("🔗 Connect")
        self.btn_connect.config_color(self.colors['primary'])
        self.log("⚠️ Terputus dari MQTT Broker (Mode: Idle)")
    
    def disconnect_mqtt(self):
        """Disconnect dari MQTT Broker"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
    
    def on_mqtt_message(self, client, userdata, msg):
        """Callback saat menerima pesan MQTT"""
        try:
            # Decode payload with error handling for binary data
            try:
                payload_str = msg.payload.decode('utf-8')
            except UnicodeDecodeError:
                # If UTF-8 decode fails, try with latin-1 (accepts all byte values)
                payload_str = msg.payload.decode('latin-1')
                self.log(f"⚠️ Warning: Message contains non-UTF8 data, using latin-1 decode")
            
            data = json.loads(payload_str)
            
            # Handle sensor metrics update (without logging to avoid spam)
            if msg.topic == self.TOPIC_SENSOR_METRICS:
                try:
                    # Update sensor metrics from ESP32
                    for sensor_name in ["FPM10A", "AS608", "ZW101"]:
                        if sensor_name in data:
                            sensor_data = data[sensor_name]
                            if sensor_name in self.sensor_metrics:
                                # Update metrics dari ESP32
                                self.sensor_metrics[sensor_name]['total_scans'] = sensor_data.get('total_scans', 0)
                                self.sensor_metrics[sensor_name]['success_count'] = sensor_data.get('success_count', 0)
                                self.sensor_metrics[sensor_name]['fail_count'] = sensor_data.get('fail_count', 0)
                                self.sensor_metrics[sensor_name]['avg_confidence'] = sensor_data.get('avg_confidence', 0)
                                
                                # Update response time
                                avg_resp_time = sensor_data.get('avg_response_time', 0)
                                if avg_resp_time > 0:
                                    self.sensor_metrics[sensor_name]['response_time'] = [avg_resp_time]
                                
                                # Update last scan time
                                last_scan = sensor_data.get('last_scan_time', 0)
                                if last_scan > 0:
                                    self.sensor_metrics[sensor_name]['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Update card display
                    self.root.after(0, self.update_sensor_cards)
                except Exception as e:
                    self.log(f"⚠️ Error parsing sensor metrics: {e}")
                return
            
            # Debug log untuk tracking (skip untuk metrics to avoid spam)
            self.log(f"📨 MQTT [{msg.topic}]: {json.dumps(data, indent=2)}")
            
            # Handle response/template topic - enrollment confirmation from ESP32
            if msg.topic == self.TOPIC_RES_TEMPLATE:
                # ESP32 mengirim hash setelah enrollment berhasil (TANPA user_id)
                fingerprint_hash = data.get("fingerprint_hash")  # e.g., "AS608_5"
                sensor_type = data.get("sensor")
                fingerprint_id = data.get("fingerprint_id")
                user_name = data.get("name")
                
                if fingerprint_hash:
                    # Simpan hash ke pending variable (TIDAK LANGSUNG SIMPAN KE DATABASE)
                    self.pending_fingerprint_hash = fingerprint_hash
                    
                    # Update textbox display
                    self.template_display.config(state='normal')
                    self.template_display.delete(0, tk.END)
                    self.template_display.insert(0, fingerprint_hash)
                    self.template_display.config(state='readonly', fg=self.colors['success'])
                    
                    # ✅ ENABLE button Save User setelah dapat fingerprint hash
                    self.save_user_btn.config(state='normal', cursor='hand2')
                    
                    self.log(f"✅ Fingerprint template berhasil ditambahkan!")
                    self.log(f"   Hash: {fingerprint_hash}")
                    self.log(f"   Sensor: {sensor_type}, ID: {fingerprint_id}")
                    self.log(f"ℹ️ Klik 'Save User' untuk menyimpan ke database")
                    
                    # Update sensor metrics
                    if sensor_type in self.sensor_metrics:
                        self.sensor_metrics[sensor_type]['success_count'] += 1
                        self.sensor_metrics[sensor_type]['total_scans'] += 1
                        self.sensor_metrics[sensor_type]['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Show success message
                    messagebox.showinfo("Sukses", 
                        f"Fingerprint template berhasil ditambahkan!\n\n" +
                        f"Hash: {fingerprint_hash}\n" +
                        f"Sensor: {sensor_type}\n" +
                        f"ID di sensor: {fingerprint_id}\n\n" +
                        f"Silakan klik 'Save User' untuk menyimpan data.")
                else:
                    self.log(f"❌ Enrollment failed - No hash received")
                    self.template_display.config(state='normal')
                    self.template_display.delete(0, tk.END)
                    self.template_display.insert(0, "❌ Enrollment failed")
                    self.template_display.config(state='readonly', fg=self.colors['error'])
                    
                    # ✅ DISABLE button Save User jika enrollment gagal
                    self.save_user_btn.config(state='disabled', cursor='arrow')
                    
                    # Track failure
                    if sensor_type in self.sensor_metrics:
                        self.sensor_metrics[sensor_type]['fail_count'] += 1
                        self.sensor_metrics[sensor_type]['total_scans'] += 1
            
            # Handle response/status topic - general status messages
            elif msg.topic == self.TOPIC_RES_STATUS:
                status = data.get("status")
                details = data.get("details", "")
                mode = data.get("mode")
                sensor = data.get("sensor")
                
                self.log(f"📡 Status dari ESP32: {status} - {details}")
                
                # Update UI based on ESP32 status
                if status == "mode_changed" and mode:
                    # Sync mode from ESP32
                    mode_upper = mode.upper()
                    
                    # Update internal state
                    self.current_mode.set(mode_upper)
                    self.mode_status.config(text=mode_upper)
                    
                    # Update button states and form display
                    if mode_upper == "PRESENSI":
                        self.btn_mode_presensi.config_color(self.colors['primary'])
                        self.btn_mode_presensi.config(state='disabled', cursor='arrow')
                        self.btn_mode_daftar.config_color(self.colors['secondary'])
                        self.btn_mode_daftar.config(state='normal', cursor='hand2')
                        
                        # Switch form display
                        self.reg_title.config(text="✅ Form Presensi")
                        self.form_frame_daftar.pack_forget()
                        self.btn_frame_daftar.pack_forget()
                        self.form_frame_presensi.pack(fill="x", padx=20, pady=10)
                        
                        # Reset display fields
                        self.display_id.config(text="-", fg=self.colors['accent'])
                        self.display_name.config(text="-", fg=self.colors['text_dark'])
                        self.display_email.config(text="-")
                        self.display_position.config(text="-")
                    else:  # ENROLL/DAFTAR
                        self.btn_mode_presensi.config_color(self.colors['secondary'])
                        self.btn_mode_presensi.config(state='normal', cursor='hand2')
                        self.btn_mode_daftar.config_color(self.colors['primary'])
                        self.btn_mode_daftar.config(state='disabled', cursor='arrow')
                        
                        # Switch form display
                        self.reg_title.config(text="📝 Pendaftaran User Baru")
                        self.form_frame_presensi.pack_forget()
                        self.form_frame_daftar.pack(fill="x", padx=20, pady=10)
                        self.btn_frame_daftar.pack(pady=20)
                    
                    self.log(f"✅ Mode berhasil disinkronkan: {mode_upper}")
                
                elif status == "sensor_changed" and sensor:
                    # Sync active sensor from ESP32
                    if sensor in self.sensor_list:
                        self.active_sensor = sensor
                        self.sensor_status.config(text=sensor)
                        self.log(f"✅ Sensor berhasil disinkronkan: {sensor}")
                        
                        # Update sensor cards di tab Analysis untuk reflect sensor aktif
                        self.root.after(0, self.update_sensor_cards)
                
                elif status == "enroll_complete":
                    # Enrollment completed successfully
                    self.log(f"🎉 Enrollment selesai: {details}")
                    # Refresh user list to show new user
                    self.root.after(0, self.refresh_user_list)
                
                elif status == "enroll_started":
                    # Enrollment started
                    self.log(f"▶️ Enrollment dimulai: {details}")
            
            # Handle response/error topic - error messages from ESP32
            elif msg.topic == self.TOPIC_RES_ERROR:
                error_code = data.get("error_code")
                error_msg = data.get("error_message")
                self.log(f"❌ ESP32 Error [{error_code}]: {error_msg}")
            
            # Handle verify/request topic - verification result from ESP32 (already matched)
            elif msg.topic == self.TOPIC_VERIFY_REQUEST:
                # ESP32 sends verification request with fingerprint hash
                fingerprint_hash = data.get("fingerprint_hash")  # Hash: "SENSOR_ID" (e.g., "AS608_42")
                match_score = data.get("match_score", 95)  # Confidence score dari sensor
                sensor = data.get("sensor", self.active_sensor)
                fingerprint_id = data.get("fingerprint_id")  # Raw ID (for logging)
                
                if fingerprint_hash:
                    # Find user by fingerprint hash (direct match)
                    self.cursor.execute(
                        'SELECT id_user, name, email, position FROM users WHERE fingerprint_template = ?',
                        (fingerprint_hash,)
                    )
                    result = self.cursor.fetchone()
                    
                    if result:
                        user_id, name, email, position = result
                        
                        # Send verification response to ESP32
                        response = {
                            "status": "MATCH",
                            "user_id": user_id,
                            "user_name": name,
                            "match_score": match_score
                        }
                        self.mqtt_client.publish(self.TOPIC_VERIFY_RESPONSE, json.dumps(response))
                        
                        # Log attendance with local time and hash
                        try:
                            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            self.cursor.execute(
                                'INSERT INTO attendance_logs (user_id, user_name, check_in_time, match_score, fingerprint_hash) VALUES (?, ?, ?, ?, ?)',
                                (user_id, name, current_time, match_score, fingerprint_hash)
                            )
                            self.conn.commit()
                            
                            self.log(f"✅ Presensi berhasil: {name} (User ID: {user_id}, Hash: {fingerprint_hash}, Score: {match_score})")
                            self.log(f"📝 Log presensi tersimpan di database: {current_time}")
                        except Exception as db_error:
                            self.log(f"❌ Error menyimpan log presensi: {str(db_error)}")
                            import traceback
                            self.log(f"   Traceback: {traceback.format_exc()}")
                        
                        # Update sensor metrics for successful verification
                        if sensor in self.sensor_metrics:
                            self.sensor_metrics[sensor]['success_count'] += 1
                            self.sensor_metrics[sensor]['total_scans'] += 1
                            self.sensor_metrics[sensor]['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Track confidence score
                            if self.sensor_metrics[sensor]['avg_confidence'] == 0:
                                self.sensor_metrics[sensor]['avg_confidence'] = match_score
                            else:
                                # Running average
                                current_avg = self.sensor_metrics[sensor]['avg_confidence']
                                total = self.sensor_metrics[sensor]['success_count']
                                self.sensor_metrics[sensor]['avg_confidence'] = ((current_avg * (total - 1)) + match_score) / total
                        
                        # Update display form if in PRESENSI mode
                        if self.current_mode.get() == "PRESENSI":
                            self.root.after(0, lambda: self.update_presensi_display(user_id, name, email if email else "-", position if position else "-"))
                        
                        self.root.after(0, self.refresh_attendance_logs)
                    else:
                        # User not found in database
                        response = {
                            "status": "NO_MATCH",
                            "user_id": 0,
                            "user_name": "Unknown",
                            "match_score": 0
                        }
                        self.mqtt_client.publish(self.TOPIC_VERIFY_RESPONSE, json.dumps(response))
                        self.log(f"❌ Presensi gagal: Hash {fingerprint_hash} tidak ditemukan di database")
                        
                        # Track failed verification
                        if sensor in self.sensor_metrics:
                            self.sensor_metrics[sensor]['fail_count'] += 1
                            self.sensor_metrics[sensor]['total_scans'] += 1
                            self.sensor_metrics[sensor]['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    self.log(f"⚠️ Verification request without fingerprint_hash")
            
            # Handle verify/response topic - verification result from ESP32
            elif msg.topic == self.TOPIC_VERIFY_RESPONSE:
                status = data.get("status", "")
                
                if status == "success":
                    # ESP32 successfully verified fingerprint
                    user_id = data.get("user_id")
                    sensor = data.get("sensor", self.active_sensor)
                    
                    # Get user info from database
                    self.cursor.execute('SELECT name FROM users WHERE id_user = ?', (user_id,))
                    result = self.cursor.fetchone()
                    
                    if result:
                        user_name = result[0]
                        
                        # Save attendance log with local time
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        match_score = 95  # Default confidence score for ESP32 internal match
                        
                        self.cursor.execute(
                            'INSERT INTO attendance_logs (user_id, user_name, check_in_time, match_score, location) VALUES (?, ?, ?, ?, ?)',
                            (user_id, user_name, current_time, match_score, f"Sensor {sensor}")
                        )
                        self.conn.commit()
                        
                        self.log(f"✅ Presensi berhasil: {user_name} (ID: {user_id}) - Sensor: {sensor}")
                        
                        # Update sensor metrics
                        if sensor in self.sensor_metrics:
                            self.sensor_metrics[sensor]['success_count'] += 1
                            self.sensor_metrics[sensor]['total_scans'] += 1
                            self.sensor_metrics[sensor]['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Update confidence
                            if self.sensor_metrics[sensor]['avg_confidence'] == 0:
                                self.sensor_metrics[sensor]['avg_confidence'] = match_score
                            else:
                                current_avg = self.sensor_metrics[sensor]['avg_confidence']
                                total = self.sensor_metrics[sensor]['success_count']
                                self.sensor_metrics[sensor]['avg_confidence'] = ((current_avg * (total - 1)) + match_score) / total
                        
                        # Refresh attendance logs display
                        self.root.after(0, self.refresh_attendance_logs)
                    else:
                        self.log(f"⚠️ User ID {user_id} tidak ditemukan di database")
                
                elif status == "no_match":
                    # No match found
                    sensor = data.get("sensor", self.active_sensor)
                    self.log(f"❌ Verifikasi gagal: Sidik jari tidak dikenali - Sensor: {sensor}")
                    
                    # Track failed verification
                    if sensor in self.sensor_metrics:
                        self.sensor_metrics[sensor]['fail_count'] += 1
                        self.sensor_metrics[sensor]['total_scans'] += 1
                        self.sensor_metrics[sensor]['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Handle system/health topic - system health status
            elif msg.topic == self.TOPIC_SYS_HEALTH:
                state = data.get("state", "unknown")
                mode = data.get("mode", "unknown")
                sensor = data.get("sensor", "unknown")
                wifi_rssi = data.get("wifi_rssi", 0)
                free_heap = data.get("free_heap", 0)
                uptime_ms = data.get("uptime_ms", 0)
                relay_state = data.get("relay_state", "closed")
                battery = data.get("battery_voltage", 0)
                
                # Update sensor status display
                if sensor != "unknown":
                    self.active_sensor = sensor
                    self.sensor_status.config(text=sensor)
                
                # Update mode status display from ESP32 health message
                if mode != "unknown":
                    # Update the mode_status label to reflect ESP32's current mode
                    self.mode_status.config(text=mode.upper())
                    self.log(f"📡 Mode synchronized from ESP32: {mode.upper()}")
                
                # Format uptime
                uptime_sec = uptime_ms // 1000
                uptime_str = f"{uptime_sec//3600}h{(uptime_sec%3600)//60}m{uptime_sec%60}s"
                
                self.log(f"💓 Health: State={state}, Mode={mode}, Sensor={sensor}, WiFi={wifi_rssi}dBm, Heap={free_heap}B, Uptime={uptime_str}, Relay={relay_state}, Battery={battery}V")
        
        except Exception as e:
            import traceback
            self.log(f"❌ Error processing MQTT message from topic '{msg.topic}': {str(e)}")
            self.log(f"   Payload length: {len(msg.payload)} bytes")
            # Log traceback for debugging (optional)
            # self.log(f"   Traceback: {traceback.format_exc()}")
    
    def publish_command(self, command, topic=None):
        """Publish command ke ESP32"""
        if not self.is_connected:
            messagebox.showwarning("Peringatan", "Belum terkoneksi ke MQTT Broker!")
            return False
        
        try:
            # Determine topic based on command type if not specified
            if topic is None:
                cmd_type = command.get("command", "")
                if cmd_type == "mode":
                    topic = self.TOPIC_CMD_MODE
                elif cmd_type in ["enroll", "enroll_start"]:
                    topic = self.TOPIC_CMD_ENROLL
                elif cmd_type in ["switch_sensor", "sensor"]:
                    topic = self.TOPIC_CMD_SENSOR
                elif cmd_type in ["relay", "open_door"]:
                    topic = self.TOPIC_CMD_RELAY
                else:
                    topic = self.TOPIC_CMD_MODE  # Default
            
            payload = json.dumps(command)
            self.log(f"📡 MQTT Publish -> Topic: {topic}, Payload: {payload}")
            self.mqtt_client.publish(topic, payload)
            return True
        except Exception as e:
            self.log(f"❌ Error publish: {str(e)}")
            return False
    
    # ============= UI Functions =============
    def switch_to_mode(self, mode):
        """Switch to specified mode and update buttons"""
        if self.current_mode.get() == mode:
            # Already in this mode
            self.log(f"ℹ️ Sudah dalam mode {mode}")
            return
        
        if not self.is_connected:
            self.log("⚠️ Tidak terhubung ke MQTT. Mode tidak dapat diubah (tetap idle)")
            messagebox.showwarning("MQTT Disconnected", "Harap connect ke MQTT terlebih dahulu!")
            return
        
        mode_lower = mode.lower()
        
        # Debug log
        self.log(f"📤 Mengirim perintah mode ke ESP32: {mode_lower}")
        
        # Publish mode ke ESP32 via MQTT - UI akan diupdate otomatis via TOPIC_RES_STATUS
        if self.publish_command({"mode": mode_lower}, topic=self.TOPIC_CMD_MODE):
            self.log(f"⏳ Menunggu konfirmasi dari ESP32...")
            # UI update akan dilakukan di on_mqtt_message() handler saat menerima TOPIC_RES_STATUS
    
    def cycle_sensor(self):
        """Cycle through available sensors: FPM10A -> AS608 -> ZW101 -> FPM10A"""
        if not self.is_connected:
            self.log("⚠️ Tidak terhubung ke MQTT. Sensor tidak dapat diubah")
            messagebox.showwarning("MQTT Disconnected", "Harap connect ke MQTT terlebih dahulu!")
            return
        
        # Get current sensor index
        try:
            current_idx = self.sensor_list.index(self.active_sensor)
        except ValueError:
            current_idx = 0
        
        # Cycle to next sensor
        next_idx = (current_idx + 1) % len(self.sensor_list)
        next_sensor = self.sensor_list[next_idx]
        
        # Map sensor name to ID
        sensor_id_map = {"FPM10A": 0, "AS608": 1, "ZW101": 2}
        sensor_id = sensor_id_map.get(next_sensor, 0)
        
        self.log(f"📤 Mengirim perintah ganti sensor ke ESP32: {next_sensor}")
        
        # Publish sensor switch command - UI akan diupdate otomatis via TOPIC_RES_STATUS
        if self.publish_command({"sensor_id": sensor_id}, topic=self.TOPIC_CMD_SENSOR):
            self.log(f"⏳ Menunggu konfirmasi dari ESP32...")
            
            # Update local state immediately (will be synced again when ESP32 confirms)
            self.active_sensor = next_sensor
            self.sensor_status.config(text=next_sensor)
            
            # Update sensor cards di tab Analysis
            self.update_sensor_cards()
    
    def update_presensi_display(self, user_id, name, email, position):
        """Update display form presensi dengan data user yang melakukan presensi"""
        try:
            self.display_id.config(text=str(user_id), fg=self.colors['success'])
            self.display_name.config(text=name, fg=self.colors['success'])
            self.display_email.config(text=email)
            self.display_position.config(text=position)
            
            # Reset after 5 seconds
            self.root.after(5000, self.reset_presensi_display)
        except Exception as e:
            self.log(f"❌ Error update display: {str(e)}")
    
    def reset_presensi_display(self):
        """Reset display form presensi"""
        try:
            self.display_id.config(text="-", fg=self.colors['accent'])
            self.display_name.config(text="-", fg=self.colors['text_dark'])
            self.display_email.config(text="-")
            self.display_position.config(text="-")
        except Exception as e:
            # Ignore error if widgets don't exist
            pass
    
    def add_fingerprint_template(self):
        """Trigger enrollment tanpa save ke database - hanya dapatkan fingerprint hash"""
        try:
            user_name = self.entry_name.get().strip()
            
            if not user_name:
                messagebox.showerror("Error", "Nama harus diisi terlebih dahulu!")
                return
            
            if not self.is_connected:
                messagebox.showwarning("Peringatan", "Belum terkoneksi ke MQTT Broker!")
                return
            
            # Reset pending hash
            self.pending_fingerprint_hash = None
            
            # Update textbox
            self.template_display.config(state='normal')
            self.template_display.delete(0, tk.END)
            self.template_display.insert(0, "⏳ Scanning fingerprint...")
            self.template_display.config(state='readonly')
            
            # Kirim command ke ESP32 untuk start enrollment (TANPA user_id)
            enroll_data = {
                "action": "start",
                "name": user_name,
                "email": self.entry_email.get().strip() or "",
                "position": self.entry_position.get().strip() or "",
                "timestamp": int(datetime.now().timestamp())
            }
            
            if self.publish_command(enroll_data, topic=self.TOPIC_CMD_ENROLL):
                self.log(f"📝 Memulai scan fingerprint untuk: {user_name}")
                self.log("⏳ Ikuti instruksi di LCD ESP32...")
                self.log("ℹ️ Hash fingerprint akan ditampilkan setelah scan berhasil")
        
        except Exception as e:
            messagebox.showerror("Error", f"Terjadi error: {str(e)}")
    
    def save_user_to_database(self):
        """Simpan user ke database setelah mendapatkan fingerprint hash"""
        try:
            user_id = int(self.entry_id.get())
            user_name = self.entry_name.get().strip()
            user_email = self.entry_email.get().strip() or None
            user_position = self.entry_position.get().strip() or None
            
            if not (1 <= user_id <= 200):
                messagebox.showerror("Error", "ID User harus antara 1-200")
                return
            
            if not user_name:
                messagebox.showerror("Error", "Nama tidak boleh kosong")
                return
            
            # Cek apakah fingerprint hash sudah ada
            if not self.pending_fingerprint_hash:
                messagebox.showwarning("Peringatan", 
                    "Fingerprint template belum ditambahkan!\n\nKlik 'Add Fingerprint Template' terlebih dahulu.")
                return
            
            # Cek apakah ID sudah ada (TIDAK BOLEH DUPLIKAT)
            self.cursor.execute('SELECT id_user, name FROM users WHERE id_user = ?', (user_id,))
            existing_user = self.cursor.fetchone()
            if existing_user:
                messagebox.showerror("Error", 
                    f"ID User {user_id} sudah digunakan oleh '{existing_user[1]}'!\n\n" +
                    f"Silakan gunakan ID User yang berbeda.\n" +
                    f"ID yang tersedia: 1-200 (kecuali yang sudah terdaftar)")
                return
            
            # Simpan ke database dengan hash yang sudah didapat
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute('''
                INSERT INTO users (id_user, name, email, position, fingerprint_template, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, user_name, user_email, user_position, 
                  self.pending_fingerprint_hash, current_time, current_time))
            self.conn.commit()
            
            self.log(f"✅ User berhasil disimpan: {user_name} (ID: {user_id}, Hash: {self.pending_fingerprint_hash})")
            
            # Update sensor metrics
            sensor_name = self.pending_fingerprint_hash.split("_")[0]
            if sensor_name in self.sensor_metrics:
                self.sensor_metrics[sensor_name]['used'] += 1
            
            # Clear form dan pending hash
            self.clear_form()
            self.pending_fingerprint_hash = None
            
            # Refresh user list
            self.refresh_user_list()
            
            messagebox.showinfo("Sukses", f"User {user_name} berhasil didaftarkan!")
        
        except ValueError:
            messagebox.showerror("Error", "ID harus berupa angka")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan user: {str(e)}")
    
    def validate_user_id(self, event=None):
        """Validasi ID User saat input berubah - cek apakah ID sudah digunakan"""
        try:
            user_id_str = self.entry_id.get().strip()
            if not user_id_str:
                return
            
            user_id = int(user_id_str)
            
            # Cek apakah ID sudah ada di database
            self.cursor.execute('SELECT name FROM users WHERE id_user = ?', (user_id,))
            existing_user = self.cursor.fetchone()
            
            if existing_user:
                # ID sudah digunakan - tampilkan warning di log
                self.log(f"⚠️ ID User {user_id} sudah digunakan oleh '{existing_user[0]}'")
                # Ubah warna entry menjadi merah
                self.entry_id.entry.config(bg='#FFE5E5')
            else:
                # ID tersedia - reset warna
                self.entry_id.entry.config(bg='white')
        except ValueError:
            # Bukan angka, abaikan
            pass
    
    def clear_form(self):
        """Clear form pendaftaran"""
        self.entry_id.delete(0, tk.END)
        self.entry_name.delete(0, tk.END)
        self.entry_email.delete(0, tk.END)
        self.entry_position.delete(0, tk.END)
        
        # Reset warna entry ID
        self.entry_id.entry.config(bg='white')
        
        # Clear template display
        self.template_display.config(state='normal')
        self.template_display.delete(0, tk.END)
        self.template_display.insert(0, "")
        self.template_display.config(state='readonly')
        
        # Reset pending hash
        self.pending_fingerprint_hash = None
        
        # Disable button save user
        self.save_user_btn.config(state='disabled', cursor='arrow')
    
    def sync_users_to_esp(self):
        """Sinkronisasi daftar users ke ESP32 - NOT USED
        
        ESP32 does not store user list locally.
        System uses template-based verification via MQTT:
        1. ESP32 scans fingerprint
        2. Sends template to desktop via MQTT
        3. Desktop matches against database
        4. Sends result back to ESP32
        """
        # This function is kept for compatibility but does nothing
        self.log("📌 Note: ESP32 uses MQTT-based verification (no local user storage)")
    
    def refresh_user_list(self):
        """Refresh treeview users"""
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        self.cursor.execute('''
            SELECT id_user, name, email, position, fingerprint_template, created_at 
            FROM users ORDER BY id_user
        ''')
        
        count = 0
        sensor_counts = {"FPM10A": 0, "AS608": 0, "ZW101": 0}
        
        for user_id, name, email, position, fp_hash, created_at in self.cursor.fetchall():
            email_display = email or "-"
            position_display = position or "-"
            hash_display = fp_hash if fp_hash else "-"
            
            # Count per sensor berdasarkan hash (format: "SENSOR_ID")
            if fp_hash and "_" in fp_hash:
                sensor_name = fp_hash.split("_")[0]
                if sensor_name in sensor_counts:
                    sensor_counts[sensor_name] += 1
            
            # Alternating row colors
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.user_tree.insert("", "end", values=(
                user_id, name, email_display, position_display, hash_display, created_at
            ), tags=(tag,))
            count += 1
        
        self.user_count_label.config(text=f"Total: {count} users")
        
        # Update sensor metrics used count per sensor
        for sensor in self.sensor_list:
            self.sensor_metrics[sensor]['used'] = sensor_counts.get(sensor, 0)
    
    def edit_user(self):
        """Edit data user"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning("Peringatan", "Pilih user yang akan diedit")
            return
        
        item = self.user_tree.item(selection[0])
        user_id = int(item['values'][0])
        
        # Ambil data dari database
        self.cursor.execute('SELECT name, email, position FROM users WHERE id_user = ?', (user_id,))
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
            
            # Update dengan waktu lokal
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute('''
                UPDATE users SET name = ?, email = ?, position = ?, updated_at = ?
                WHERE id_user = ?
            ''', (new_name, new_email, new_position, current_time, user_id))
            self.conn.commit()
            
            self.users[user_id] = new_name
            # self.sync_users_to_esp()  # Not needed - ESP32 uses MQTT verification
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
            self.cursor.execute('DELETE FROM users WHERE id_user = ?', (user_id,))
            self.conn.commit()
            
            # Hapus dari dict
            if user_id in self.users:
                del self.users[user_id]
            
            # Note: No need to send delete to ESP32 (no local storage)
            # ESP32 uses MQTT verification - desktop database is the source of truth
            
            self.log(f"🗑️ User {user_name} (ID: {user_id}) dihapus dari database")
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
            SELECT log_id, user_id, user_name, check_in_time, match_score, fingerprint_hash
            FROM attendance_logs 
            ORDER BY check_in_time DESC 
            LIMIT 1000
        ''')
        
        count = 0
        for log_id, user_id, user_name, timestamp, score, fp_hash in self.cursor.fetchall():
            # Alternating row colors
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.log_tree.insert("", "end", values=(
                log_id, user_id, user_name, timestamp, score or "-", fp_hash or "-"
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
                SELECT log_id, user_id, user_name, check_in_time, match_score, fingerprint_hash
                FROM attendance_logs 
                WHERE LOWER(user_name) LIKE ? OR CAST(user_id AS TEXT) LIKE ?
                ORDER BY check_in_time DESC 
                LIMIT 1000
            ''', (f'%{keyword}%', f'%{keyword}%'))
        else:
            self.cursor.execute('''
                SELECT log_id, user_id, user_name, check_in_time, match_score, fingerprint_hash
                FROM attendance_logs 
                ORDER BY check_in_time DESC 
                LIMIT 1000
            ''')
        
        count = 0
        for log_id, user_id, user_name, timestamp, score, fp_hash in self.cursor.fetchall():
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.log_tree.insert("", "end", values=(
                count + 1, user_id, user_name, timestamp, score or "-", fp_hash or "-"
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
            SELECT log_id, user_id, user_name, check_in_time, match_score, fingerprint_hash
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
        for log_id, user_id, user_name, timestamp, score, fp_hash in self.cursor.fetchall():
            tag = 'evenrow' if count % 2 == 0 else 'oddrow'
            self.log_tree.insert("", "end", values=(
                count + 1, user_id, user_name, timestamp, score or "-", fp_hash or "-"
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
