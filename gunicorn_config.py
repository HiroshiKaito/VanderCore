
# Gunicorn Konfiguration für optimale Leistung und Stabilität
import multiprocessing

# Server Socket
bind = "0.0.0.0:5000"
backlog = 2048

# Ensure application is properly accessible
forwarded_allow_ips = '*'
secure_scheme_headers = {'X-Forwarded-Proto': 'https'}

# Worker Prozesse
workers = 4  # Feste Anzahl von 4 Workern
worker_class = "sync"
worker_connections = 1000
timeout = 120  # Erhöhtes Timeout für lange Verbindungen
keepalive = 65  # Längerer Keepalive für stabilere Verbindungen

# Logging
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"  # Normales Log-Level für Produktion
capture_output = True
enable_stdio_inheritance = True

# Server Mechaniken
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Prozess Benennung
proc_name = "solana_trading_bot"

# SSL Konfiguration (falls benötigt)
keyfile = None
certfile = None
