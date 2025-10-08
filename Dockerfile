FROM python:3.10-slim

WORKDIR /app
# Set version based on build date
RUN date +"%Y%m%d%H%M" >/app/version.txt
# Install Apache and mod_wsgi along with other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    apache2 \
    apache2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install mod_wsgi

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p vector_db uploads data

# Configure Apache with mod_wsgi
# Command to run Apache in foreground


# Expose the Apache port
RUN mod_wsgi-express install-module
RUN ln -s /usr/lib/apache2/modules/mod_wsgi-py310.cpython-310-x86_64-linux-gnu.so /usr/lib/apache2/modules/mod_wsgi.so
RUN echo "LoadModule wsgi_module /usr/lib/apache2/modules/mod_wsgi.so" > /etc/apache2/mods-available/wsgi.load
RUN a2enmod wsgi

# Create WSGI configuration file
RUN echo '<VirtualHost *:80>\n\
    ServerName localhost\n\
    DocumentRoot /app\n\
    WSGIDaemonProcess mariajose python-path=/app\n\
    WSGIProcessGroup mariajose\n\
    WSGIScriptAlias / /app/wsgi.py\n\
    <Directory /app>\n\
        Require all granted\n\
    </Directory>\n\
</VirtualHost>' > /etc/apache2/sites-available/000-default.conf

# Create WSGI entry point
RUN echo 'import sys\n\
sys.path.insert(0, "/app")\n\
from app import app as application' > /app/wsgi.py

# Expose the Apache port
EXPOSE 80

# Command to run Apache in foreground
CMD ["apache2ctl", "-D", "FOREGROUND"]
#CMD ["python", "app.py"]