import time
import os
import json
import subprocess
import webbrowser
import pyttsx3
import queue
import threading
import sounddevice as sd
import soundfile as sf
import tempfile
from rapidfuzz import process
from fuzzywuzzy import fuzz
import sounddevice as sd
import queue
import json
import pvporcupine
import struct
import threading
from faster_whisper import WhisperModel
from textblob import TextBlob
import re

wake_detected = threading.Event()

q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print("Mic error:", status)
    q.put(bytes(indata))

def porcupine_wake_listener():
    ACCESS_KEY = "q4++4wxo7NYc2kKudZ1iq7DzuNgW0D8N1l4lzRsUVwPmZXFhytNHPg=="
    PPN_PATH = r"C:\Users\bhard\AppData\Local\Programs\Python\Python310\Alen Siri\hey-alen_en_windows_v3_0_0\hey-alen_en_windows_v3_0_0.ppn"

    if not os.path.exists(PPN_PATH):
        print(f"❌ Wake word model not found at {PPN_PATH}")
        return

    porcupine = pvporcupine.create(
        access_key=ACCESS_KEY,
        keyword_paths=[PPN_PATH]
    )

    def callback(indata, frames, time, status):
        if status:
            print("Mic error:", status)
        pcm = struct.unpack_from("h" * porcupine.frame_length, indata)
        if porcupine.process(pcm) >= 0:
            print("🎤 Wake word detected.")
            wake_detected.set()

    with sd.RawInputStream(
        samplerate=porcupine.sample_rate,
        blocksize=porcupine.frame_length,
        dtype='int16',
        channels=1,
        callback=callback
    ):
        print("✅ Listening for 'Hey Alen'...")
        while not wake_detected.is_set():
            sd.sleep(100)

    porcupine.delete()
    wake_detected.clear()


# === Files ===
MEMORY_FILE = "memory.json"
APP_INDEX_FILE = "app_index.json"
FOLDER_INDEX_FILE = "folder_index.json"
STORE_APP_INDEX_FILE = "store_app_index.json"


# === Voice Engine ===
speech_queue = queue.Queue()

def speak(text):
    speech_queue.put(text)
    if speech_queue.qsize() == 1:
        threading.Thread(target=_speak_loop).start()

_speak_lock = threading.Lock()

def _speak_loop():
    with _speak_lock:
        engine = pyttsx3.init()
        engine.setProperty('rate', 180)
        while not speech_queue.empty():
            text = speech_queue.get()
            try:
                engine.say(text)
                engine.runAndWait()
            except RuntimeError as e:
                print("Speech error:", e)


# === Memory ===
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)

def memory_response(command, threshold=85):
    command = command.lower().strip()
    memory = load_memory()
    best_match = None
    best_score = 0
    for key in memory:
        score = fuzz.ratio(command, key)
        if score > best_score and score >= threshold:
            best_match = key
            best_score = score
    return memory.get(best_match) if best_match else None

def teach_memory(command, answer):
    memory = load_memory()
    memory[command.lower()] = answer
    save_memory(memory)

# === App and Folder Indexing ===
def build_app_index():
    apps = {}
    search_paths = [
        os.path.expandvars(r"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs"),
        r"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs",
        r"C:\\Program Files",
        r"C:\\Program Files (x86)",
    ]
    for path in search_paths:
        for root, _, files in os.walk(path):
            if "WindowsApps" in root:
                continue  # ⛔ skip UWP/Store app binaries

            for file in files:
                if file.lower().endswith(('.lnk', '.exe')):
                    name = os.path.splitext(file)[0].lower()
                    apps[name] = os.path.join(root, file)
    with open(APP_INDEX_FILE, 'w') as f:
        json.dump(apps, f, indent=4)
    return apps

def load_app_index():
    if os.path.exists(APP_INDEX_FILE):
        with open(APP_INDEX_FILE, 'r') as f:
            return json.load(f)
    return build_app_index()

def open_app_by_name(name):
    apps = load_app_index()
    match = process.extractOne(name.lower(), apps.keys(), score_cutoff=75)
    if match:
        try:
            os.startfile(apps[match[0]])
            return f"Opening {match[0].title()}"
        except PermissionError:
            return f"Permission denied for app {match[0]}. Trying store app..."
        except Exception as e:
            return f"Error launching app {match[0]}: {str(e)}. Trying store app..."
    return f"Sorry, couldn't find the app {name}"


def build_folder_index():
    folders = {}

    # Add common user folders like Downloads, Desktop, Documents
    user_profile = os.environ["USERPROFILE"]
    common_dirs = ["Downloads", "Desktop", "Documents", "Pictures", "Music", "Videos"]

    for folder in common_dirs:
        path = os.path.join(user_profile, folder)
        if os.path.exists(path):
            folders[folder.lower()] = path

    # Scan top-level folders from drives (as in your current logic)
    drives = ["C:\\", "D:\\", "E:\\"]
    for drive in drives:
        for root, dirs, _ in os.walk(drive):
            for d in dirs:
                folders[d.lower()] = os.path.join(root, d)
            break  # prevent deep scan

    with open(FOLDER_INDEX_FILE, 'w') as f:
        json.dump(folders, f, indent=4)

    return folders


def load_folder_index():
    if os.path.exists(FOLDER_INDEX_FILE):
        with open(FOLDER_INDEX_FILE, 'r') as f:
            return json.load(f)
    return build_folder_index()

def load_store_app_index():
    if os.path.exists(STORE_APP_INDEX_FILE):
        with open(STORE_APP_INDEX_FILE, "r") as f:
            return json.load(f)
    else:
        return detect_store_apps()  # auto-create with PowerShell


def save_store_app_index(data):
    with open(STORE_APP_INDEX_FILE, "w") as f:
        json.dump(data, f, indent=4)


def open_folder_by_name(name):
    folders = load_folder_index()
    match = process.extractOne(name.lower(), folders.keys(), score_cutoff=75)
    if match:
        os.startfile(folders[match[0]])
        return f"Opening folder {match[0].title()}"
    return f"Sorry, couldn't find the folder {name}"

def open_store_app_by_name(name):
    store_apps = load_store_app_index()
    name = name.lower()
    match = process.extractOne(name, store_apps.keys(), score_cutoff=75)

    if match:
        os.system(store_apps[match[0]])
        return f"Opening store app {match[0].title()}"

def detect_store_apps():
    command = r'powershell "Get-StartApps | Select-Object Name,AppID"'
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stdout.splitlines()

    apps = {}
    for line in output[3:]:  # Skip header
        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) == 2:
            name, app_id = parts
            apps[name.lower()] = f'start {app_id}'

    with open(STORE_APP_INDEX_FILE, 'w') as f:
        json.dump(apps, f, indent=4)

    return apps


# === Command Handler ===
def handle_command(command):
    command = command.lower()
    if command.startswith("open") or command.startswith("launch"):
        target = command.split(" ", 1)[1]
        folder_result = open_folder_by_name(target)
        if "couldn't" not in folder_result:
            return folder_result
        result = open_app_by_name(target)
        if "couldn't" not in result.lower():
            return result

        result = open_folder_by_name(target)
        if "couldn't" not in result.lower():
            return result

# 🔁 Try store app last
        result = open_store_app_by_name(target)
        return result

    return None

# === Voice Input ===
def listen(duration=4, model=None):
    samplerate = 16000
    audio = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1, dtype='float32')
    sd.wait()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio, samplerate)

        segments, _ = model.transcribe(
            f.name,
            beam_size=3,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300}
        )

        command = " ".join([seg.text for seg in segments]).strip()
        print("🧠 You said (raw):", command)

# Skip correction if command contains known app or entity keywords
        known_keywords = ["chrome", "modi", "youtube", "notepad", "calculator", "music", "alarm", "folder", "weather"]

        lower_cmd = command.lower()
        if any(word in lower_cmd for word in known_keywords):
            print("🧠 Using raw command (contains known keyword):", command)
            return command

        # Fallback correction if input seems vague or unclear
        if len(command.strip().split()) < 2 or not command.replace(" ", "").isalpha():
            corrected = str(TextBlob(command).correct())
            print("🧠 You said (corrected):", corrected)
            return corrected

        print("🧠 Using raw command (confident):", command)
        return command

def add_to_startup():
    import sys
    import os
    import pythoncom
    from win32com.client import Dispatch

    startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft\\Windows\\Start Menu\\Programs\\Startup")
    exe_path = sys.executable  # points to .exe when frozen

    shortcut_path = os.path.join(startup_dir, "ALEN.lnk")
    if os.path.exists(shortcut_path):
        return  # Already added

    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = exe_path
    shortcut.WorkingDirectory = os.path.dirname(exe_path)
    shortcut.IconLocation = exe_path
    shortcut.save()

        

# === Main ===
def main():
    add_to_startup()
    build_folder_index()
    detect_store_apps()  # refresh UWP store app index
    print("✅ ALEN is running. Say 'Hey Alen' to wake me up.")

    whisper_model = WhisperModel("small", device="cpu")   




    while True:
        porcupine_wake_listener()

        print("🎤 Wake word detected.")
        speak("yes")
        while speech_queue.qsize() > 0:
            time.sleep(0.18)  # ⏳ Wait until speaking finishes

        time.sleep(0.5)  # optional delay to avoid capturing its own voice

        print("🤖 Waiting for your command...")
        


        command = listen(duration=4, model=whisper_model).strip()
        print("You:", command)

        if not command or len(command) < 3:
            print("⏳ No valid command. Back to sleep.")
            continue

        mem = memory_response(command)
        if mem:
            print("ALEN:", mem)
            speak(mem)
            continue

        sys = handle_command(command)
        if sys:
            print("ALEN:", sys)
            speak(sys)
            continue

        print("ALEN: Redirecting to web search...")
        webbrowser.open(f"https://www.google.com/search?q={command}")

        print("🤖 Waiting for your explanation...")
        






if __name__ == "__main__":
    main()
