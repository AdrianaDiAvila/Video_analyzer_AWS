# Usa la imagen oficial de Python 3.10 slim como base
FROM python:3.10-slim

# Variables de entorno para que Python no bufee stdout/stderr
ENV PYTHONUNBUFFERED=1

# Instala ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Directorio de trabajo en el contenedor
WORKDIR /app

# Copia e instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto de tu código
COPY . .

# Expone el puerto 3000 de la aplicación
EXPOSE 3000

# Comando por defecto al arrancar el contenedor
CMD ["python", "app.py"]