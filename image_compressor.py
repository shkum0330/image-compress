import tkinter as tk
from tkinter import filedialog, messagebox, Listbox
from PIL import Image, ImageTk, ImageOps
import os
import platform
import subprocess
import json
import time
import threading

# Watchdog 라이브러리
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    messagebox.showerror("라이브러리 오류", "watchdog 라이브러리가 필요합니다.\npip install watchdog")
    exit()

# TkinterDnD2 라이브러리
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    messagebox.showerror("라이브러리 오류", "tkinterdnd2 라이브러리가 필요합니다.\npip install tkinterdnd2")
    exit()

# --- 전역 변수 ---
CONFIG_FILE = 'compressor_config.json'
file_list = []
save_directory = os.path.join(os.path.expanduser('~'), 'Downloads')

# 10MB 기준 설정
SIZE_THRESHOLD = 10 * 1024 * 1024

# 자동 감시 관련 변수
observer = None
watch_directory = ""
target_filename = ""
is_watching = False


# --- 경로 저장/로드 함수 ---
def save_config():
    config = {'save_directory': save_directory}
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Config 저장 오류: {e}")


def load_config():
    global save_directory
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            path = config.get('save_directory')
            if path and os.path.isdir(path):
                save_directory = path
            else:
                save_directory = os.path.join(os.path.expanduser('~'), 'Downloads')
                save_config()
    except (FileNotFoundError, json.JSONDecodeError):
        save_directory = os.path.join(os.path.expanduser('~'), 'Downloads')
        save_config()


# --- 메인 기능 함수 (조건부 압축) ---
def compress_image(input_path, output_dir):
    try:
        # 파일이 완전히 저장될 때까지 잠시 대기 (파일 잠금 방지)
        time.sleep(0.5)

        # 1. 파일 크기 확인
        file_size = os.path.getsize(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)

        # 2. 용량에 따른 분기 처리
        if file_size > SIZE_THRESHOLD:
            # [Case A] 10MB 초과 -> 압축 수행
            img = Image.open(input_path)

            new_filename = f"{name}_compressed.jpg"
            output_path = os.path.join(output_dir, new_filename)

            if img.mode == 'RGBA':
                img = img.convert('RGB')

            img.save(output_path, "JPEG", quality=85, optimize=True)
            return f"{new_filename} (압축됨)"

        else:
            # [Case B] 10MB 이하 -> 아무것도 하지 않음 (Skip)
            return f"{filename} (10MB이하-건너뜀)"

    except Exception as e:
        return f"오류 ({os.path.basename(input_path)}): {e}"


def open_save_folder():
    if not os.path.isdir(save_directory):
        messagebox.showerror("오류", f"저장 폴더를 찾을 수 없습니다:\n{save_directory}")
        return
    try:
        if platform.system() == "Windows":
            os.startfile(save_directory)
        elif platform.system() == "Darwin":
            subprocess.run(["open", save_directory])
        else:
            subprocess.run(["xdg-open", save_directory])
    except Exception as e:
        messagebox.showwarning("폴더 열기 실패", f"폴더를 여는 데 실패했습니다: {e}")


# --- Watchdog 이벤트 핸들러 ---
class ImageHandler(FileSystemEventHandler):
    def __init__(self):
        # 마지막 처리 시간을 기록하여 중복 실행 방지 (쿨타임)
        self.last_processed_time = 0

    def on_created(self, event):
        self.process(event)

    # 덮어쓰기 감지
    def on_modified(self, event):
        self.process(event)

    def process(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)

        # 타겟 파일명이 일치하는지 확인
        if filename == target_filename:
            # 쿨타임 로직 (1초 이내 재실행 방지)
            current_time = time.time()
            if current_time - self.last_processed_time < 1.0:
                return  # 1초가 안 지났으면 무시

            self.last_processed_time = current_time
            print(f"감지됨(덮어쓰기 포함): {filename}")

            # 압축 수행
            result_msg = compress_image(event.src_path, save_directory)

            # GUI 업데이트
            root.after(0, lambda: update_status_from_thread(f"[자동] {result_msg}"))


def update_status_from_thread(msg):
    listbox.insert(tk.END, msg)
    listbox.see(tk.END)


# --- 자동 감시 제어 함수 ---
def select_watch_folder():
    global watch_directory
    path = filedialog.askdirectory(title="감시할 폴더 선택")
    if path:
        watch_directory = path
        watch_dir_label.config(text=f"...{path[-30:]}" if len(path) > 30 else path)


def toggle_watch():
    global observer, is_watching, target_filename

    if is_watching:
        if observer:
            observer.stop()
            observer.join()
        is_watching = False
        btn_watch_toggle.config(text="감시 시작", bg="lightgray", fg="black")
        status_label.config(text="자동 감시가 중지되었습니다.")
        entry_filename.config(state="normal")
        btn_watch_dir.config(state="normal")
    else:
        target_filename = entry_filename.get().strip()
        if not watch_directory or not os.path.isdir(watch_directory):
            messagebox.showwarning("경고", "먼저 감시할 폴더를 선택해주세요.")
            return
        if not target_filename:
            messagebox.showwarning("경고", "감지할 파일명을 입력해주세요.")
            return

        # 핸들러 생성 시 쿨타임 변수 초기화됨
        event_handler = ImageHandler()
        observer = Observer()
        observer.schedule(event_handler, watch_directory, recursive=False)

        try:
            observer.start()
            is_watching = True
            btn_watch_toggle.config(text="감시 중지 (작동 중)", bg="red", fg="white")
            status_label.config(text=f"'{target_filename}' (덮어쓰기 감지 중) 감시 중...")
            entry_filename.config(state="disabled")
            btn_watch_dir.config(state="disabled")
        except Exception as e:
            messagebox.showerror("오류", f"감시 시작 실패: {e}")


# --- GUI 이벤트 핸들러 (수동) ---
def add_files_to_list(files_to_add):
    for f in files_to_add:
        f_cleaned = f.strip('{}')
        if f_cleaned not in file_list:
            if f_cleaned.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_list.append(f_cleaned)
                listbox.insert(tk.END, os.path.basename(f_cleaned))
            else:
                listbox.insert(tk.END, f"[지원안함] {os.path.basename(f_cleaned)}")


def select_files():
    selected_files = filedialog.askopenfilenames(
        title="압축할 이미지 선택",
        filetypes=(("이미지 파일", "*.jpg *.jpeg *.png"), ("모든 파일", "*.*"))
    )
    if selected_files:
        add_files_to_list(selected_files)


def drop_handler(event):
    files = root.tk.splitlist(event.data)
    add_files_to_list(files)


def select_save_directory():
    global save_directory
    path = filedialog.askdirectory(title="압축된 파일을 저장할 폴더 선택")
    if path:
        save_directory = path
        update_save_dir_label()
        save_config()


def update_save_dir_label():
    display_path = save_directory
    if len(display_path) > 35:
        display_path = "..." + display_path[-32:]
    save_dir_label.config(text=f"저장 위치: {display_path}")


def start_compression():
    if not file_list:
        messagebox.showwarning("경고", "먼저 파일을 선택하거나 드래그해주세요.")
        return
    if not os.path.exists(save_directory):
        messagebox.showerror("오류", f"저장 위치를 찾을 수 없습니다: {save_directory}\n"
                                   "'저장 폴더 변경' 버튼으로 위치를 다시 설정해주세요.")
        return

    status_label.config(text="수동 작업 진행 중...")
    compressed_count = 0
    listbox.delete(0, tk.END)

    for i, file_path in enumerate(file_list):
        listbox.insert(tk.END, f"[처리 중...] {os.path.basename(file_path)}")
        root.update_idletasks()

        result_msg = compress_image(file_path, save_directory)

        listbox.delete(i)
        listbox.insert(i, f"[결과] {result_msg}")

        if "압축됨" in result_msg:
            compressed_count += 1

    status_label.config(text=f"작업 완료! (총 {compressed_count}개 파일 압축됨)")
    messagebox.showinfo("완료", f"작업이 완료되었습니다.\n"
                              f"실제 압축된 파일: {compressed_count}개\n"
                              f"저장 폴더: {save_directory}")
    file_list.clear()


# --- GUI 생성 ---
load_config()

root = TkinterDnD.Tk()
root.title("이미지 용량 축소기 v6.3 (덮어쓰기 감지)")
root.minsize(420, 600)

root.drop_target_register(DND_FILES)
root.dnd_bind('<<Drop>>', drop_handler)

# --- 프레임 설정 ---
top_frame = tk.Frame(root, pady=10)
top_frame.pack()

save_frame = tk.Frame(root, pady=5)
save_frame.pack(fill="x", padx=20)

middle_frame = tk.Frame(root, pady=5)
middle_frame.pack(fill="x")

separator = tk.Frame(root, height=2, bd=1, relief="sunken")
separator.pack(fill="x", padx=10, pady=10)

auto_frame = tk.LabelFrame(root, text=" 자동 감시 설정 (10MB 이상 & 덮어쓰기 포함) ", padx=10, pady=10)
auto_frame.pack(fill="x", padx=20, pady=5)

bottom_frame = tk.Frame(root, pady=10)
bottom_frame.pack(fill="x")

# --- 위젯 생성 ---
btn_select = tk.Button(top_frame, text="파일 선택 (수동)", width=15, command=select_files)
btn_select.pack()

save_dir_label = tk.Label(save_frame, text="", anchor="w")
save_dir_label.pack(side="left", fill="x", expand=True, padx=5)

btn_save_dir = tk.Button(save_frame, text="저장 폴더 변경", width=12, command=select_save_directory)
btn_save_dir.pack(side="right")
update_save_dir_label()

list_label = tk.Label(middle_frame, text="--- 상태 로그 / 드래그 드롭 ---")
list_label.pack()

listbox = tk.Listbox(middle_frame, height=8)
listbox.pack(pady=5, padx=20, fill="x")

# 자동 감시 UI
watch_frame_inner = tk.Frame(auto_frame)
watch_frame_inner.pack(fill="x", pady=2)
tk.Label(watch_frame_inner, text="감시 폴더:").pack(side="left")
watch_dir_label = tk.Label(watch_frame_inner, text="(선택 없음)", fg="blue")
watch_dir_label.pack(side="left", padx=5)
btn_watch_dir = tk.Button(watch_frame_inner, text="폴더 찾기", command=select_watch_folder)
btn_watch_dir.pack(side="right")

filename_frame = tk.Frame(auto_frame)
filename_frame.pack(fill="x", pady=5)
tk.Label(filename_frame, text="파일명(확장자포함):").pack(side="left")
entry_filename = tk.Entry(filename_frame)
entry_filename.pack(side="left", padx=5, fill="x", expand=True)
entry_filename.insert(0, "screenshot.png")

btn_watch_toggle = tk.Button(auto_frame, text="감시 시작", bg="lightgray", command=toggle_watch)
btn_watch_toggle.pack(fill="x", pady=5)

status_label = tk.Label(bottom_frame, text="준비 완료")
status_label.pack(pady=5)

btn_start = tk.Button(bottom_frame, text="선택 파일 처리 시작", width=20, command=start_compression, bg="lightblue")
btn_start.pack(pady=5)

btn_open_folder = tk.Button(bottom_frame, text="저장 폴더 열기", width=20, command=open_save_folder)
btn_open_folder.pack(pady=5)

root.mainloop()