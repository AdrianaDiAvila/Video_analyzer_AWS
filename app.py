# app.py

import os
from dotenv import load_dotenv

load_dotenv()
import json
import tempfile
import threading
import webbrowser

from flask import Flask, render_template_string, request, redirect, url_for, jsonify, abort
import boto3
from yt_dlp import YoutubeDL
from botocore.exceptions import BotoCoreError, ClientError

app = Flask(__name__)

# — Configuración S3 desde entorno —
BUCKET = os.getenv ("VIDEO_BUCKET")
REGION = os.getenv("AWS_REGION")
if not BUCKET or not REGION:
    raise RuntimeError("Define VIDEO_BUCKET y AWS_REGION en tu entorno")
s3 = boto3.client("s3", region_name=REGION)

# — Helpers de análisis —

def get_text(key):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8")

def find_latest(prefix, contains, suffix):
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET, Prefix=prefix)
    candidates = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            lm  = obj["LastModified"]
            if contains in key and key.endswith(suffix):
                candidates.append((lm, key))
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]

# — Verifica si los resultados están listos —

@app.route("/results_ready")
def results_ready():
    es_key        = find_latest("outputs/",        "resumen-es-transcripcion",             ".txt")
    en_key        = find_latest("outputs/",        "resumen-en-transcripcion",             ".txt")
    chapters_key  = find_latest("Chapters/",       "capitulos-transcripcion-raw-videos",   ".json")
    transcript_key= find_latest("transcriptions/","transcripcion-raw-videos",             ".json")
    if all([es_key, en_key, chapters_key, transcript_key]):
        return jsonify(ready=True), 200
    return jsonify(ready=False), 202

# — Página de resultados final —

@app.route("/results")
def results():
    video_url = request.args.get("video_url", "")

    # Busca artefactos
    es_key        = find_latest("outputs/",        "resumen-es-transcripcion",             ".txt")
    en_key        = find_latest("outputs/",        "resumen-en-transcripcion",             ".txt")
    chapters_key  = find_latest("Chapters/",       "capitulos-transcripcion-raw-videos",   ".json")
    transcript_key= find_latest("transcriptions/","transcripcion-raw-videos",             ".json")

    if not all([es_key, en_key, chapters_key, transcript_key]):
        return abort(503, "Artefactos aún no listos")

    # Descarga resúmenes
    summary_es = get_text(es_key)
    summary_en = get_text(en_key)

    # Descarga y parsea capítulos
    raw = get_text(chapters_key)
    if not raw or not raw.strip():
        chapters = []
    else:
        s = raw.strip()
        if s.startswith("```"):
            lines = s.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines)
        try:
            data = json.loads(s)
            chapters = data if isinstance(data, list) else data.get("chapters", [])
        except json.JSONDecodeError:
            chapters = []

    # Descarga transcript
    raw_t = get_text(transcript_key)
    try:
        jt = json.loads(raw_t)
        transcript_text = jt["results"]["transcripts"][0]["transcript"]
    except:
        transcript_text = raw_t

    # Renderiza la plantilla con YouTube embebido, skeleton, pasos e interactividad
    return render_template_string("""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Análisis</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body { margin:0; min-height:100vh;
      background:linear-gradient(135deg,#5B21B6,#DB2777);
      font-family:'Segoe UI',sans-serif; color:#F3F4F6;
    }
    .steps {
      display:flex; justify-content:center; gap:1.5rem; margin:1rem 0;
    }
    .step {
      padding:.5rem 1rem; border-radius:1rem;
      background:rgba(255,255,255,0.1); color:#EEE;
    }
    .step.active {
      background:#FCD34D; color:#111;
    }
    .container {
      max-width:900px; margin:0 auto; padding:1rem;
    }
    .card {
      background:rgba(30,41,59,0.9); border-radius:12px;
      padding:2rem; box-shadow:0 8px 24px rgba(0,0,0,0.2);
    }
    /* Skeleton loading */
    .skeleton {
      width:100%; height:400px;
      background:linear-gradient(90deg, rgba(255,255,255,0.1) 25%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.1) 75%);
      background-size:400% 100%;
      animation:shimmer 1.5s infinite ease-out;
    }
    @keyframes shimmer {
      0% { background-position:200% 0 }
      100% { background-position:-200% 0 }
    }
    /* YouTube player container */
    #player { width:100%; height:400px; display:none; margin-bottom:1.5rem; }
    /* Scroll interno para <pre> de resumen y transcript */
    pre {
      background: rgba(55,65,81,0.8);
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      overflow-y: auto;     /* scroll vertical */
      max-height: 250px;    /* ajusta altura según necesites */
      line-height: 1.5;
    }
    /* Capítulos */
    ul { list-style:none; padding:0; margin:0; }
    li {
      display:flex; align-items:center; justify-content:space-between;
      margin:.75rem 0; padding:.75rem;
      background:rgba(55,65,81,0.8); border-radius:6px;
    }
    .chap-info { flex:1; }
    .chap-link {
      color:#FBBF24; text-decoration:none; font-weight:bold;
    }
    .chap-link:hover { text-decoration:underline; }
    li em { font-style:italic; color:#A78BFA; margin-left:.5rem; }
    button.seek-btn {
      background:none; border:none; color:#FCD34D;
      font-size:1.25rem; cursor:pointer;
    }
  </style>
</head>
<body>

  <div class="steps">
    <div class="step">1. Subir</div>
    <div class="step active">2. Analisis de video con AI </div>
  </div>

  <div class="container">
    <div class="card">
      <div id="skeleton" class="skeleton"></div>
      <div id="player"></div>

      <h2>Resumen (ES)</h2>
      <pre>{{ summary_es }}</pre>

      <h2>Summary (EN)</h2>
      <pre>{{ summary_en }}</pre>

      <h2>Chapters ({{ chapters|length }})</h2>
      {% if chapters %}
        <ul>
        {% for chap in chapters %}
          {% set parts = chap['inicio'].split(':') %}
          {% set secs  = (parts[0]|int)*3600 + (parts[1]|int)*60 + (parts[2]|int) %}
          <li>
            <div class="chap-info">
              <a href="#" data-secs="{{ secs }}" class="chap-link">{{ chap['inicio'] }}</a>
              : <em>{{ chap['capitulo'] }}</em><br>
              {{ chap['descripcion'] }}
            </div>
            <button class="seek-btn" data-secs="{{ secs }}">▶️</button>
          </li>
        {% endfor %}
        </ul>
      {% else %}
        <p>No se encontraron capítulos.</p>
      {% endif %}

      <h2>Transcript</h2>
      <pre>{{ transcript_text }}</pre>
    </div>
  </div>

  <!-- YouTube IFrame API -->
  <script src="https://www.youtube.com/iframe_api"></script>
  <script>
    let player;
    function getYouTubeID(url) {
      // Robust function to extract video ID from various YouTube URL formats
      let videoId = null;
      try {
        const urlObj = new URL(url);
        if (urlObj.hostname === 'youtu.be') {
          videoId = urlObj.pathname.slice(1);
        } else if (urlObj.hostname.includes('youtube.com')) {
          videoId = urlObj.searchParams.get('v');
        }
        // Clean up potential extra params from youtu.be links
        if (videoId) {
          return videoId.split(/[?&]/)[0];
        }
      } catch (e) {
        console.error("Error parsing URL:", url, e);
      }
      // Fallback for URLs that are not full URLs
      const match = url.match(/[?&]v=([^&]+)/);
      if (match) return match[1];
      
      return null;
    }

    function onYouTubeIframeAPIReady() {
      const videoUrl = new URLSearchParams(location.search).get('video_url');
      const videoId = getYouTubeID(videoUrl);

      if (videoId) {
        player = new YT.Player('player', {
          videoId: videoId,
          playerVars: { 'autoplay': 0, 'controls': 1 },
          events: {
            'onReady': onPlayerReady
          }
        });
      } else {
        console.error("Could not extract YouTube Video ID from URL:", videoUrl);
        document.getElementById('skeleton').style.display = 'none';
        const playerDiv = document.getElementById('player');
        playerDiv.innerHTML = '<p style="color: red; text-align: center;">Error: No se pudo cargar el video. ID no válido.</p>';
        playerDiv.style.display = 'block';
      }
    }
    function onPlayerReady() {
      document.getElementById('skeleton').style.display = 'none';
      const p = document.getElementById('player');
      p.style.display = 'block';
    }
    function seek(sec) {
      if (player && player.seekTo) {
        player.seekTo(sec, true);
        player.playVideo();
      }
    }
    document.addEventListener('click', e => {
      if (e.target.matches('.chap-link') || e.target.matches('.seek-btn')) {
        e.preventDefault();
        const sec = parseInt(e.target.dataset.secs, 10);
        seek(sec);
      }
    });
  </script>

</body>
</html>
    """,
    summary_es=summary_es,
    summary_en=summary_en,
    chapters=chapters,
    transcript_text=transcript_text,
    video_url=video_url
    )

# — Página de carga de YouTube —

@app.route("/")
def index():
    return redirect(url_for("upload_youtube"))

@app.route("/upload", methods=["GET", "POST"])
def upload_youtube():
    msg = None
    youtube_url = request.form.get("youtube_url", "")
    if request.method == "POST":
        url = youtube_url.strip()
        if not url:
            msg = "URL inválida."
        else:
            opts = {
              "format": "bestvideo+bestaudio",
              "merge_output_format": "mp4",
              "outtmpl": os.path.join("downloads", "%(id)s.%(ext)s"), # Cambiado a un subdirectorio dentro de /app
              "quiet": True,
            }
            # Asegurarse de que el directorio de descargas exista
            download_dir = "downloads"
            os.makedirs(download_dir, exist_ok=True)
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    vid = info["id"]
                    fn  = f"{vid}.mp4"
                    lp  = os.path.join(download_dir, fn) # Usar el nuevo directorio
                key = f"raw-videos/{fn}"
                s3.upload_file(lp, BUCKET, key)
                os.remove(lp)
                return redirect(url_for("loading", video_url=youtube_url))
            except Exception as e:
                msg = f"❌ {e}"

    return render_template_string("""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Análisis Inteligente de Videos</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin:0; min-height:100vh;
      background:linear-gradient(135deg,#5B21B6,#DB2777);
      font-family:'Segoe UI',sans-serif; display:flex;
      align-items:center; justify-content:center; padding:2rem;
    }
    .card {
      background:rgba(30,41,59,0.9); border-radius:1rem;
      padding:2rem; max-width:600px; width:100%;
      box-shadow:0 8px 24px rgba(0,0,0,0.3);
    }
    h1 { color:#FFF; text-align:center;
      font-size:2.25rem; margin-bottom:1.5rem;
    }
    form { display:flex; gap:.5rem; }
    input {
      flex:1; padding:.75rem 1rem; border:none;
      border-radius:.75rem; font-size:1rem;
    }
    button {
      background:#FCD34D; border:none;
      padding:.75rem 1.5rem; border-radius:.75rem;
      font-size:1rem; font-weight:bold;
      cursor:pointer; transition:background .2s;
    }
    button:hover { background:#FBBF24; }
    .msg {
      margin-top:1rem; padding:1rem;
      border-radius:.5rem; background:rgba(254,226,226,0.9);
      color:#991B1B; text-align:center;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Análisis Inteligente de Videos</h1>
    {% if msg %}
      <div class="msg">{{ msg }}</div>
    {% endif %}
    <form method="post">
      <input
        type="text"
        name="youtube_url"
        placeholder="https://www.youtube.com/watch?v=..."
        value="{{ youtube_url }}"
        required
      >
      <button type="submit">Subir</button>
    </form>
  </div>
</body>
</html>
""", msg=msg, youtube_url=youtube_url)

# — Página de “Loading” con spinner y polling —

@app.route("/loading")
def loading():
    video_url = request.args.get("video_url", "")
    return render_template_string("""
<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Procesando…</title>
<style>
  body{margin:0;min-height:100vh;
    background:linear-gradient(135deg,#5B21B6,#DB2777);
    display:flex;align-items:center;justify-content:center;
    font-family:'Segoe UI',sans-serif;color:white}
  .spinner {
    width:80px;height:80px;
    border:8px solid rgba(255,255,255,0.3);
    border-top-color:#fff;border-radius:50%;
    animation:spin 1s linear infinite;
  }
  @keyframes spin{to{transform:rotate(360deg)}}
  h2{margin-top:1rem;font-size:1.5rem}
</style>
</head><body>
  <div style="text-align:center">
    <div class="spinner"></div>
    <h2>Procesando, por favor espera…</h2>
  </div>
  <script>
    const videoUrl = "{{ video_url }}";
    (function poll(){
      fetch("/results_ready")
        .then(r => {
          if(r.status === 200) {
            window.location = `/results?video_url=${encodeURIComponent(videoUrl)}`;
          } else {
            setTimeout(poll, 3000);
          }
        });
    })();
  </script>
</body></html>
    """, video_url=video_url)

if __name__ == "__main__":
    def open_browser():
        webbrowser.open("http://127.0.0.1:5000/upload")
    threading.Timer(1, open_browser).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
