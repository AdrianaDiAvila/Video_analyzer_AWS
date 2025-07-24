# Análisis Inteligente de Videos con AWS

Este proyecto es una aplicación web que utiliza Flask y Docker para analizar videos de YouTube. La aplicación descarga el video, procesa el audio para generar una transcripción, crea resúmenes en español e inglés, y detecta los capítulos principales del video.

## Características

- **Carga de Videos**: Permite a los usuarios enviar la URL de un video de YouTube para su análisis.
- **Procesamiento en AWS**: Utiliza un bucket de S3 para almacenar los videos y los resultados del análisis.
- **Análisis con IA**: Genera automáticamente:
  - Transcripción completa del audio.
  - Resúmenes en español e inglés.
  - Detección y listado de capítulos.
- **Interfaz Web**: Muestra los resultados del análisis de forma clara, incluyendo un reproductor de video embebido para una fácil navegación por los capítulos.

## Prerrequisitos

Antes de empezar, asegúrate de tener instalado lo siguiente:

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)
- Una cuenta de AWS con permisos para acceder a S3.

## Configuración del Entorno

1.  **Clonar el Repositorio (si aplica)**:
    ```bash
    git clone <url-del-repositorio>
    cd <nombre-del-directorio>
    ```

2.  **Crear el Archivo de Entorno**:
    Crea un archivo llamado `.env` en la raíz del proyecto. Este archivo contendrá las variables necesarias para la conexión con AWS.

3.  **Configurar Variables de Entorno**:
    Añade las siguientes variables al archivo `.env`, reemplazando los valores de ejemplo con tus propias credenciales y configuración de AWS:

    ```env
    # Nombre de tu bucket de S3 donde se almacenarán los videos
    VIDEO_BUCKET=tu-bucket-de-s3

    # Región de AWS donde se encuentra tu bucket
    AWS_REGION=tu-region-de-aws
    ```
    **Nota**: La autenticación con AWS (Access Key y Secret Key) debe estar configurada en tu sistema, ya que `boto3` (el SDK de AWS para Python) las buscará en las ubicaciones estándar (ej. `~/.aws/credentials`) o en variables de entorno del sistema.

## Ejecución con Docker

Una vez que hayas configurado tu archivo `.env`, puedes construir y ejecutar la aplicación usando Docker Compose.

1.  **Construir y Levantar el Contenedor**:
    Abre una terminal en el directorio raíz del proyecto y ejecuta el siguiente comando. La opción `--build` reconstruirá la imagen si ha habido cambios y `-d` la ejecutará en segundo plano (detached mode).

    ```bash
    docker-compose up --build -d
    ```

2.  **Verificar los Logs (Opcional)**:
    Si quieres ver los registros de la aplicación en tiempo real para asegurarte de que todo funciona correctamente, puedes usar:

    ```bash
    docker-compose logs -f
    ```

3.  **Detener la Aplicación**:
    Para detener y eliminar los contenedores, redes y volúmenes creados por `docker-compose`, ejecuta:

    ```bash
    docker-compose down
    ```

## Acceso a la Aplicación

Cuando el contenedor esté en ejecución, abre tu navegador web y navega a la siguiente dirección:

[**http://localhost:3000**](http://localhost:3000)

Desde ahí, podrás pegar una URL de YouTube y comenzar el análisis.
