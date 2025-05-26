import os
import sys
import time
from datetime import datetime

# Niveles de log
LEVEL_DEBUG = 10
LEVEL_INFO = 20
LEVEL_WARNING = 30
LEVEL_ERROR = 40
LEVEL_CRITICAL = 50

# Nombres de los niveles
LEVEL_NAMES = {
    LEVEL_DEBUG: 'DEBUG',
    LEVEL_INFO: 'INFO',
    LEVEL_WARNING: 'WARNING',
    LEVEL_ERROR: 'ERROR',
    LEVEL_CRITICAL: 'CRITICAL'
}

# Colores para los niveles (para consola)
LEVEL_COLORS = {
    LEVEL_DEBUG: '\033[36m',     # Cyan
    LEVEL_INFO: '\033[32m',      # Verde
    LEVEL_WARNING: '\033[33m',   # Amarillo
    LEVEL_ERROR: '\033[31m',     # Rojo
    LEVEL_WARNING: '\033[35m',   # Magenta
    'RESET': '\033[0m'           # Reset
}

# Nivel de log actual (por defecto INFO)
CURRENT_LEVEL = LEVEL_INFO

# Verificar si estamos en producción (Azure)
def is_production():
    return os.environ.get('WEBSITE_SITE_NAME') is not None

# Función para establecer el nivel de log
def set_level(level):
    global CURRENT_LEVEL
    CURRENT_LEVEL = level
    debug(f"Nivel de log establecido a {LEVEL_NAMES.get(level, 'DESCONOCIDO')}")

# Función base de log
def log(level, message, module=None, use_color=True):
    if level < CURRENT_LEVEL:
        return
    
    # Obtener timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    
    # Obtener nombre del módulo si no se proporciona
    if module is None:
        frame = sys._getframe(2)  # Obtener el frame del llamador
        module = frame.f_globals.get('__name__', 'unknown')
    
    # Formatear mensaje
    level_name = LEVEL_NAMES.get(level, 'UNKNOWN')
    
    # Determinar si usar colores (no usar en producción o si se especifica)
    use_color = use_color and not is_production()
    
    if use_color:
        color = LEVEL_COLORS.get(level, LEVEL_COLORS['RESET'])
        formatted_message = f"{timestamp} {color}[{level_name}]{LEVEL_COLORS['RESET']} [{module}] {message}"
    else:
        formatted_message = f"{timestamp} [{level_name}] [{module}] {message}"
    
    # Imprimir mensaje usando print()
    print(formatted_message)
    
    # Asegurar que el mensaje se muestre inmediatamente
    sys.stdout.flush()

# Funciones específicas para cada nivel
def debug(message, module=None):
    log(LEVEL_DEBUG, message, module)

def info(message, module=None):
    log(LEVEL_INFO, message, module)

def warning(message, module=None):
    log(LEVEL_WARNING, message, module)

def error(message, module=None):
    log(LEVEL_ERROR, message, module)

def critical(message, module=None):
    log(LEVEL_CRITICAL, message, module)

# Configuración inicial
def configure():
    # Configurar nivel basado en variable de entorno
    env_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level_map = {
        'DEBUG': LEVEL_DEBUG,
        'INFO': LEVEL_INFO,
        'WARNING': LEVEL_WARNING,
        'ERROR': LEVEL_ERROR,
        'CRITICAL': LEVEL_CRITICAL
    }
    set_level(level_map.get(env_level, LEVEL_INFO))
    
    # Log inicial
    if is_production():
        info("Iniciando aplicación en entorno de producción (Azure)")
    else:
        info("Iniciando aplicación en entorno de desarrollo")

# Configurar al importar
configure()