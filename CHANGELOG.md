# Changelog

Todas las modificaciones importantes de este proyecto se documentarán en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-06-10

### Añadido
- Integración completa con Azure OpenAI para procesamiento de lenguaje natural
- Implementación del sistema de búsqueda vectorial con FAISS
- Soporte para carga y procesamiento de documentos PDF, DOCX y TXT
- Panel de administración de archivos para usuarios
- Modo oscuro/claro en la interfaz de usuario

### Cambiado
- Mejora en la interfaz de chat para mostrar el contexto de las respuestas
- Optimización del proceso de generación de embeddings

### Corregido
- Solución al problema de memoria durante el procesamiento de documentos grandes
- Corrección de errores en la autenticación de usuarios

## [0.4.0] - 2025-05-15

### Añadido
- Sistema de autenticación de usuarios (registro, inicio de sesión, cierre de sesión)
- Almacenamiento persistente de conversaciones
- Primera versión del chat con IA

### Cambiado
- Rediseño de la interfaz de usuario principal
- Mejora en la estructura de la base de datos

## [0.3.0] - 2025-04-20

### Añadido
- Implementación inicial de la carga de documentos
- Procesamiento básico de texto extraído de documentos

### Cambiado
- Arquitectura base de la aplicación Flask

## [0.2.0] - 2025-03-15

### Añadido
- Configuración de integración con Azure OpenAI
- Estructura base del proyecto

## [0.1.0] - 2025-02-28

### Añadido
- Inicialización del proyecto
- Configuración básica de Flask
- Documentación inicial