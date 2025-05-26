# Mar-IA-Jose

## Descripción
Mar-IA-Jose es una aplicación web construida con Flask que integra Azure OpenAI para el procesamiento de lenguaje natural. La aplicación permite a los usuarios cargar diferentes tipos de documentos (PDF, DOCX, TXT), procesarlos mediante embeddings vectoriales y realizar búsquedas contextuales utilizando FAISS. Los usuarios pueden interactuar con sus documentos a través de un chat con IA que proporciona respuestas basadas en el contenido de los documentos cargados.

## Características principales

- **Integración con Azure OpenAI**: Procesamiento avanzado de lenguaje natural
- **Autenticación de usuarios**: Sistema completo de registro, inicio de sesión y cierre de sesión
- **Chat con IA**: Interfaz conversacional con respuestas contextuales
- **Gestión de documentos**:
  - Carga de múltiples formatos (PDF, DOCX, TXT)
  - Procesamiento automático y generación de embeddings
  - Búsqueda contextual mediante FAISS
- **Interfaz de usuario adaptable**: Diseño responsive con modo oscuro/claro
- **Panel de gestión de archivos**: Control y organización de los documentos cargados
- **Cola de procesamiento**: Manejo eficiente de documentos grandes

## Requisitos previos

- Python 3.12
- Azure OpenAI Service configurado
- Docker (opcional, para contenerización)

## Instalación

### Configuración local

1. Clone el repositorio:
   ```
   git clone https://github.com/yourusername/mar-IA-Jose.git
   cd mar-IA-Jose
   ```

2. Cree un entorno virtual e instale las dependencias:
   ```
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure las variables de entorno (cree un archivo `.env`):
   ```
   FLASK_APP=app
   FLASK_ENV=development
   SECRET_KEY=your_secret_key
   AZURE_OPENAI_API_KEY=your_azure_openai_api_key
   AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
   ```

4. Inicie la aplicación:
   ```
   flask run
   ```

### Usando Docker

1. Construya la imagen:
   ```
   docker build -t maria-jose .
   ```

2. Ejecute el contenedor:
   ```
   docker run -p 5000:5000 --env-file .env maria-jose
   ```

## Despliegue en Azure

El proyecto incluye scripts de despliegue para:

- Azure Web App
- Azure Container Apps

Consulte la carpeta `/scripts/deployment` para obtener más información sobre el proceso de despliegue.

## Uso

1. Regístrese o inicie sesión en la aplicación
2. Cargue los documentos que desee procesar
3. Una vez procesados, utilice el chat con IA para realizar preguntas sobre el contenido
4. Administre sus documentos a través del panel de control

## Estructura del proyecto

```
mar-IA-Jose/
├── app/                 # Código principal de la aplicación Flask
├── scripts/             # Scripts de utilidad y despliegue
├── templates/           # Plantillas HTML
├── static/              # Recursos estáticos (CSS, JS, imágenes)
├── tests/               # Pruebas unitarias y de integración
├── Dockerfile           # Configuración para contenerización
├── requirements.txt     # Dependencias del proyecto
├── CHANGELOG.md         # Registro de cambios
└── README.md            # Este archivo
```

## Estado del desarrollo

Actualmente en la versión 0.5.0. Consulte el [CHANGELOG.md](CHANGELOG.md) para obtener información detallada sobre las versiones y las funcionalidades planificadas.

## Licencia

[Especificar licencia]

## Contacto

Creado y mantenido por Luise López (luise92@gmail.com)