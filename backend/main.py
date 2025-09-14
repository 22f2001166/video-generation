from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
import requests
import os
import uuid
import subprocess
from dotenv import load_dotenv
from pathlib import Path
import tempfile
import shlex

# Load env vars
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
ASSETS_DIR = BASE_DIR / "assets"

# Ensure folders exist
AUDIO_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.post("/generate")
async def generate(prompt: str = Form(...)):
    try:
        if not API_KEY:
            script = (
                "This is a fallback script because OPENROUTER_API_KEY is not set. "
                "Please set OPENROUTER_API_KEY in .env to use the real model."
            )
        else:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek/deepseek-chat-v3.1:free",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            data = response.json()
            if "choices" not in data or not data["choices"]:
                return JSONResponse({"error": data}, status_code=500)
            script = data["choices"][0]["message"]["content"]

        # Generate audio (gTTS)
        filename = f"{uuid.uuid4()}.mp3"
        file_path = AUDIO_DIR / filename
        tts_text = script if script.strip() else "Hello world."
        tts = gTTS(text=tts_text, lang="en")
        tts.save(str(file_path))

        return JSONResponse({"script": script, "audio_url": f"/audio/{filename}"})

    except Exception as e:
        print("Error in /generate:", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/export")
async def export(request: Request):
    """
    Expects JSON body:
    {
      "script": "...",
      "image": "/assets/1.jpg",
      "video": "/assets/v1.mp4",
      "audio_url": "/audio/<filename>.mp3",
      "useVideo": true
    }
    """
    try:
        body = await request.json()
        script = body.get("script", "")
        image = body.get("image")
        video = body.get("video")
        audio_url = body.get("audio_url")
        use_video = bool(body.get("useVideo", True))

        if not audio_url:
            return JSONResponse({"error": "audio_url required"}, status_code=400)

        # Resolve audio path inside AUDIO_DIR
        audio_path = (AUDIO_DIR / Path(audio_url).name).resolve()
        if not audio_path.exists():
            return JSONResponse(
                {"error": f"audio file not found: {audio_path}"}, status_code=404
            )

        out_filename = f"output_{uuid.uuid4().hex}.mp4"
        out_path = BASE_DIR / out_filename

        def get_audio_duration(path: Path) -> float:
            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True)
                return float(res.stdout.strip())
            except Exception:
                return 10.0

        duration_seconds = get_audio_duration(audio_path)

        # ---- SUBTITLES ----
        # Split into sentences (keeps ., ?, ! endings)
        import re

        sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", script) if s.strip()]
        per_sentence = duration_seconds / max(1, len(sentences))

        def sec_to_srt(t: float) -> str:
            hrs = int(t // 3600)
            mins = int((t % 3600) // 60)
            secs = int(t % 60)
            ms = int((t * 1000) % 1000)
            return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

        srt_content = ""
        for i, sentence in enumerate(sentences, start=1):
            start_t = sec_to_srt((i - 1) * per_sentence)
            end_t = sec_to_srt(min(duration_seconds, i * per_sentence))
            # sanitize sentence to avoid problematic chars? keep as-is for now
            srt_content += f"{i}\n{start_t} --> {end_t}\n{sentence}\n\n"

        tmp_srt = tempfile.NamedTemporaryFile(delete=False, suffix=".srt")
        tmp_srt.write(srt_content.encode("utf-8"))
        tmp_srt.flush()
        tmp_srt.close()
        srt_path = tmp_srt.name

        # Escape backslashes for ffmpeg (especially on Windows)
        srt_path_escaped = srt_path.replace("\\", "\\\\")

        # Build subtitles filter string (don't shlex.quote the whole thing; ffmpeg expects raw path here)
        subtitle_filter = (
            f"subtitles={srt_path_escaped}:force_style='FontName=Arial,FontSize=22,"
            "PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=1'"
        )

        # ---- FFmpeg ----
        if use_video and video:
            input_video_path = (ASSETS_DIR / Path(video).name).resolve()
            if not input_video_path.exists():
                return JSONResponse(
                    {"error": f"video not found: {input_video_path}"}, status_code=404
                )

            cmd = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(input_video_path),
                "-i",
                str(audio_path),
                # map video from input 0 and audio from input 1
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                # set frames-per-second
                "-r",
                "30",
                # apply subtitles filter
                "-vf",
                subtitle_filter,
                # codecs and format
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                # stop when shortest stream ends (audio)
                "-shortest",
                str(out_path),
            ]
        else:
            input_image_path = (
                (ASSETS_DIR / Path(image).name).resolve() if image else None
            )
            if not input_image_path or not input_image_path.exists():
                return JSONResponse(
                    {"error": f"image not found: {input_image_path}"}, status_code=404
                )

            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(input_image_path),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-r",
                "30",
                "-vf",
                subtitle_filter,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                str(out_path),
            ]

        # Run ffmpeg and capture logs
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            print("ffmpeg failed:")
            print(proc.stdout)
            print(proc.stderr)
            return JSONResponse(
                {"error": "ffmpeg failed", "details": proc.stderr}, status_code=500
            )

        # Optionally remove tmp_srt file:
        # os.unlink(srt_path)

        return FileResponse(
            path=str(out_path),
            filename="storyshort_output.mp4",
            media_type="video/mp4",
        )

    except Exception as e:
        print("Error in /export:", e)
        return JSONResponse({"error": str(e)}, status_code=500)
