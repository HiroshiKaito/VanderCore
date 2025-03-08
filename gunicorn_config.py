# Gunicorn Konfiguration für optimale Leistung und Stabilität
import multiprocessing

# Server Socket
bind = "0.0.0.0:5000"
backlog = 2048

# Ensure application is properly accessible
forwarded_allow_ips = '*'
secure_scheme_headers = {'X-Forwarded-Proto': 'https'}

# Worker Prozesse
workers = multiprocessing.cpu_count() * 2 + 1  # Optimale Worker-Anzahl
worker_class = "sync"
worker_connections = 1000
timeout = 120  # Erhöhtes Timeout für lange Verbindungen
keepalive = 65  # Längerer Keepalive für stabilere Verbindungen

# Logging
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True

# Server Mechaniken
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Reload und Debug Einstellungen
reload = False  # Deaktiviert für Produktionsumgebung
spew = False
check_config = False

# Worker Neustart
max_requests = 1000  # Worker-Neustarts nach X Anfragen
max_requests_jitter = 50  # Zufällige Verzögerung beim Neustart
graceful_timeout = 120  # Zeit für Worker-Neustarts

# Fehlerbehandlung
retry_policy = {
    'max_retries': 3,
    'retry_delay': 5
}

# Prozess Benennung
proc_name = "telegram_bot"

# SSL Konfiguration
keyfile = None
certfile = None