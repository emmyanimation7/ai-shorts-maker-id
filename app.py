import os, json, uuid, shutil, subprocess, asyncio
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()
BASE = Path(__file__).resolve().parent
WORK = BASE / "work"
WORK.mkdir(exist_ok=True)
app = FastAPI(title="AI Shorts Maker V2")

def has_ffmpeg():
    return shutil.which("ffmpeg") is not None

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse((BASE/"index.html").read_text(encoding="utf-8"))

@app.get("/api/status")
async def status():
    return {"ffmpeg": has_ffmpeg(), "gemini_configured": bool(os.getenv("GEMINI_API_KEY"))}

@app.post("/api/analyze")
async def analyze(video: UploadFile = File(...), duration: int = Form(20), style: str = Form("dokumenter"), language: str = Form("id")):
    if duration not in (20,30): raise HTTPException(400, "Durasi harus 20 atau 30 detik.")
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(400, "GEMINI_API_KEY belum diatur. Isi file .env terlebih dahulu. Pemotongan manual tetap dapat digunakan.")
    job = uuid.uuid4().hex
    folder = WORK/job; folder.mkdir(parents=True)
    ext = Path(video.filename or "video.mp4").suffix.lower()
    if ext not in (".mp4",".mov",".m4v",".webm",".mkv"): ext=".mp4"
    input_path=folder/("source"+ext)
    data=await video.read()
    if not data: raise HTTPException(400,"File video kosong.")
    if len(data)>500*1024*1024: raise HTTPException(413,"Ukuran video maksimum 500 MB untuk MVP ini.")
    input_path.write_bytes(data)
    try:
        result = await analyze_with_gemini(input_path, duration, style, language)
        result["job_id"]=job
        result["duration"]=duration
        result["style"]=style
        (folder/"analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return result
    except Exception as e:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(500, f"Analisis gagal: {str(e)[:500]}")

async def analyze_with_gemini(path: Path, duration: int, style: str, language: str):
    # Google GenAI SDK uploads the source video and asks for a scene-aware edit plan.
    from google import genai
    from google.genai import types
    client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    uploaded=client.files.upload(file=str(path))
    prompt=f"""
Kamu adalah editor video pendek. Analisis isi video yang diunggah. Buat rencana klip untuk video vertikal sosial.
Durasi target setiap klip {duration} detik. Gaya narasi: {style}. Bahasa: Indonesia.
Pilih momen yang punya awal-tengah-akhir, jangan membuat klaim tentang hal yang tidak terlihat.
Buat JSON valid saja dengan skema:
{{"summary":"ringkasan visual singkat","clips":[{{"start":0.0,"end":{duration}.0,"hook":"hook pembuka","narration":"narasi voice-over yang sesuai visual, 35-65 kata untuk 20 detik atau 50-90 kata untuk 30 detik","caption":"judul pendek"}}]}}
Buat maksimal 8 klip, waktu start/end dalam detik, start >= 0, end > start, rentang klip tidak melebihi durasi video jika durasi diketahui.
Jika video tidak dapat dianalisis, jelaskan melalui JSON {"summary":"...","clips":[]}.
"""
    response=client.models.generate_content(
        model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),
        contents=[uploaded, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.5)
    )
    raw=response.text or "{}"
    try: obj=json.loads(raw)
    except Exception: raise RuntimeError("AI mengembalikan format yang tidak valid.")
    # Probe duration and clamp suggested ranges.
    dur=probe_duration(path)
    clips=[]
    for c in obj.get("clips",[])[:8]:
        try:
            start=max(0,float(c.get("start",0))); end=min(dur,float(c.get("end",duration)))
            if end-start < 2: continue
            c["start"]=start; c["end"]=end
            c["narration"]=str(c.get("narration","")).strip()
            clips.append(c)
        except Exception: pass
    obj["clips"]=clips
    obj["video_duration"]=dur
    return obj

def probe_duration(path: Path) -> float:
    if not has_ffmpeg(): raise RuntimeError("FFmpeg tidak ditemukan. Instal FFmpeg dan pastikan perintah ffmpeg tersedia.")
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,text=True)
    if p.returncode!=0: raise RuntimeError("Tidak dapat membaca durasi video.")
    return float(p.stdout.strip())

@app.post("/api/render/{job_id}")
async def render(job_id: str, clip_index: int = Form(...), narration: str = Form(...), style: str = Form("dokumenter"), ratio: str = Form("vertical")):
    folder=WORK/job_id
    if not folder.exists(): raise HTTPException(404,"Pekerjaan tidak ditemukan atau sudah dibersihkan.")
    plan_path=folder/"analysis.json"
    if not plan_path.exists(): raise HTTPException(400,"Rencana klip tidak ditemukan.")
    plan=json.loads(plan_path.read_text(encoding="utf-8"))
    clips=plan.get("clips",[])
    if clip_index<0 or clip_index>=len(clips): raise HTTPException(400,"Pilihan klip tidak valid.")
    clip=clips[clip_index]
    source=next((p for p in folder.iterdir() if p.name.startswith("source")),None)
    if not source: raise HTTPException(404,"Video sumber tidak ditemukan.")
    if not has_ffmpeg(): raise HTTPException(500,"FFmpeg tidak terpasang.")
    start=float(clip["start"]); end=float(clip["end"]); length=end-start
    out=folder/f"short_{clip_index+1}.mp4"
    audio=folder/f"voice_{clip_index+1}.mp3"
    # TTS: edge-tts is a free community package; requires internet. Voice is Indonesian female by default.
    voice=os.getenv("TTS_VOICE","id-ID-GadisNeural")
    try:
        import edge_tts
        communicate=edge_tts.Communicate(narration, voice)
        await communicate.save(str(audio))
    except Exception as e:
        raise HTTPException(500, f"Gagal membuat audio narasi. Periksa koneksi internet atau instal edge-tts. Detail: {str(e)[:200]}")
    vf = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" if ratio=="vertical" else "scale='min(1280,iw)':-2"
    # Narration is mixed over original audio at reduced volume; if no source audio, ffmpeg's amix may fail, so use optional map.
    cmd=["ffmpeg","-y","-ss",str(start),"-i",str(source),"-i",str(audio),"-t",str(length),"-vf",vf,
         "-filter_complex","[0:a]volume=0.18[bg];[bg][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]",
         "-map","0:v:0","-map","[aout]","-c:v","libx264","-preset","veryfast","-crf","25","-c:a","aac","-b:a","160k","-movflags","+faststart",str(out)]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode!=0:
        # Retry for silent source videos without an audio stream.
        cmd2=["ffmpeg","-y","-ss",str(start),"-i",str(source),"-i",str(audio),"-t",str(length),"-vf",vf,
              "-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","veryfast","-crf","25","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(out)]
        p=subprocess.run(cmd2,capture_output=True,text=True)
        if p.returncode!=0: raise HTTPException(500,"Render gagal. Pastikan FFmpeg mendukung codec video. "+p.stderr[-350:])
    return {"download_url":f"/api/download/{job_id}/{out.name}","filename":out.name,"narration":narration}

@app.get("/api/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    if "/" in filename or "\\" in filename: raise HTTPException(400,"Nama file tidak valid.")
    path=WORK/job_id/filename
    if not path.exists(): raise HTTPException(404,"File belum ada.")
    return FileResponse(path, media_type="video/mp4", filename=filename)
