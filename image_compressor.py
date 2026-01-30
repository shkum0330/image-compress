import tkinter as tk
from tkinter import filedialog, messagebox, Listbox
from PIL import Image, ImageTk, ImageOps
import os
import platform
import subprocess
import json
import time
import shutil

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

# 전역 변수
CONFIG_FILE = 'compressor_config.json'
file_list = []

# 용량(여기선 10MB) 기준 설정
SIZE_THRESHOLD = 10 * 1024 * 1024

# 설정값 기본 초기화
watch_directory = ""
target_filename_input = "screenshot.png"

# 자동 감시 관련 변수
observer = None
target_filename = ""
is_watching = False

# 설정 저장/로드 함수 (저장 경로 제거됨)
def save_config():
    """ 현재 설정(감시폴더, 파일명)을 JSON에 저장 """
    current_filename = "screenshot.png"
    try:
        if 'entry_filename' in globals():
            current_filename = entry_filename.get()
    except:
        pass

    config = {
        'watch_directory': watch_directory,
        'target_filename': current_filename
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Config 저장 오류: {e}")

def load_config():
    """ JSON에서 설정 불러오기 """
    global watch_directory, target_filename_input
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

            # 감시 폴더 로드
            w_path = config.get('watch_directory')
            if w_path and os.path.isdir(w_path):
                watch_directory = w_path

            # 타겟 파일명 로드
            t_name = config.get('target_filename')
            if t_name:
                target_filename_input = t_name

    except (FileNotFoundError, json.JSONDecodeError):
        save_config()

# 핵심 기능 함수
def compress_image(input_path):
    """
    입력된 파일의 경로(input_path)와 동일한 폴더에 결과물을 저장
    """
    try:
        time.sleep(0.5)  # 파일 잠금 방지

        # 저장 경로는 원본 파일이 있는 폴더
        output_dir = os.path.dirname(input_path)

        file_size = os.path.getsize(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)

        if file_size > SIZE_THRESHOLD:
            # 10MB 초과 -> 압축
            img = Image.open(input_path)
            new_filename = f"{name}_compressed.jpg"
            output_path = os.path.join(output_dir, new_filename)

            if img.mode == 'RGBA':
                img = img.convert('RGB')

            img.save(output_path, "JPEG", quality=85, optimize=True)
            return f"{new_filename} (압축됨)"
        else:
            # 10MB 이하 -> 원본 복사
            new_filename = f"{name}_original{ext}"
            output_path = os.path.join(output_dir, new_filename)

            # 원본과 대상 경로가 같으면 생략
            if os.path.abspath(input_path) == os.path.abspath(output_path):
                return f"{filename} (변경없음)"

            shutil.copy2(input_path, output_path)
            return f"{new_filename} (원본복사)"

    except Exception as e:
        return f"오류 ({os.path.basename(input_path)}): {e}"

def open_watch_folder():
    """ 감시 폴더 열기 (저장 폴더 대신 사용) """
    target_dir = watch_directory

    if not target_dir or not os.path.isdir(target_dir):
        messagebox.showwarning("알림", "설정된 감시 폴더가 없습니다.")
        return

    try:
        if platform.system() == "Windows":
            os.startfile(target_dir)
        elif platform.system() == "Darwin":
            subprocess.run(["open", target_dir])
        else:
            subprocess.run(["xdg-open", target_dir])
    except Exception as e:
        messagebox.showwarning("폴더 열기 실패", f"폴더를 여는 데 실패했습니다: {e}")


# Watchdog 핸들러
class ImageHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_processed_time = 0

    def on_created(self, event):
        self.process(event)

    def on_modified(self, event):
        self.process(event)

    def process(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)

        if filename == target_filename:
            current_time = time.time()
            if current_time - self.last_processed_time < 1.0:
                return

            self.last_processed_time = current_time
            print(f"감지됨: {filename}")

            # 압축 수행 (경로 전달 불필요, 내부에서 처리)
            result_msg = compress_image(event.src_path)
            root.after(0, lambda: update_status_from_thread(f"[자동] {result_msg}"))


def update_status_from_thread(msg):
    listbox.insert(tk.END, msg)
    listbox.see(tk.END)


# 제어 함수
def select_watch_folder():
    global watch_directory
    path = filedialog.askdirectory(title="감시할 폴더 선택")
    if path:
        watch_directory = path
        update_watch_dir_label()
        save_config()

def update_watch_dir_label():
    """ 감시 폴더 레이블 업데이트 """
    if watch_directory:
        text = f"...{watch_directory[-30:]}" if len(watch_directory) > 30 else watch_directory
        watch_dir_label.config(text=text)
    else:
        watch_dir_label.config(text="(선택 없음)")

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
        save_config()

        if not watch_directory or not os.path.isdir(watch_directory):
            messagebox.showwarning("경고", "먼저 감시할 폴더를 선택해주세요.")
            return
        if not target_filename:
            messagebox.showwarning("경고", "감지할 파일명을 입력해주세요.")
            return

        event_handler = ImageHandler()
        observer = Observer()
        observer.schedule(event_handler, watch_directory, recursive=False)

        try:
            observer.start()
            is_watching = True
            btn_watch_toggle.config(text="감시 중지 (작동 중)", bg="red", fg="white")
            status_label.config(text=f"'{target_filename}' 감시 중...")
            entry_filename.config(state="disabled")
            btn_watch_dir.config(state="disabled")
        except Exception as e:
            messagebox.showerror("오류", f"감시 시작 실패: {e}")


# GUI 이벤트 핸들러
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


def start_compression():
    if not file_list:
        messagebox.showwarning("경고", "먼저 파일을 선택하거나 드래그해주세요.")
        return

    status_label.config(text="수동 작업 진행 중...")
    compressed_count = 0
    listbox.delete(0, tk.END)

    for i, file_path in enumerate(file_list):
        listbox.insert(tk.END, f"[처리 중...] {os.path.basename(file_path)}")
        root.update_idletasks()

        # 수동 압축 시에도 원본 폴더에 저장
        result_msg = compress_image(file_path)

        listbox.delete(i)
        listbox.insert(i, f"[결과] {result_msg}")

        if "오류" not in result_msg:
            compressed_count += 1

    status_label.config(text=f"작업 완료! (총 {compressed_count}개 파일 처리됨)")
    messagebox.showinfo("완료", f"작업이 완료되었습니다.\n"
                              f"총 처리 파일: {compressed_count}개\n"
                              f"결과물 위치: 원본 파일과 동일 폴더")
    file_list.clear()


# GUI 생성
load_config()

root = TkinterDnD.Tk()
root.title("이미지 용량 축소기 v7.0 (In-Place)")
root.minsize(420, 550)

root.drop_target_register(DND_FILES)
root.dnd_bind('<<Drop>>', drop_handler)

# 프레임 설정
top_frame = tk.Frame(root, pady=10)
top_frame.pack()

middle_frame = tk.Frame(root, pady=5)
middle_frame.pack(fill="x")

separator = tk.Frame(root, height=2, bd=1, relief="sunken")
separator.pack(fill="x", padx=10, pady=10)

auto_frame = tk.LabelFrame(root, text=" 자동 감시 설정 (10MB 이상 & 덮어쓰기) ", padx=10, pady=10)
auto_frame.pack(fill="x", padx=20, pady=5)

bottom_frame = tk.Frame(root, pady=10)
bottom_frame.pack(fill="x")

# 위젯 생성
btn_select = tk.Button(top_frame, text="파일 선택 (수동)", width=15, command=select_files)
btn_select.pack()

# 안내 라벨 (저장 위치 설명)
tk.Label(top_frame, text="※ 결과물은 원본 폴더에 저장됩니다.", fg="gray").pack(pady=2)

list_label = tk.Label(middle_frame, text="--- 상태 로그 / 드래그 드롭 ---")
list_label.pack()

listbox = tk.Listbox(middle_frame, height=10)
listbox.pack(pady=5, padx=20, fill="x")

# 자동 감시 UI
watch_frame_inner = tk.Frame(auto_frame)
watch_frame_inner.pack(fill="x", pady=2)
tk.Label(watch_frame_inner, text="감시 폴더:").pack(side="left")
watch_dir_label = tk.Label(watch_frame_inner, text="(선택 없음)", fg="blue")
watch_dir_label.pack(side="left", padx=5)
update_watch_dir_label()

btn_watch_dir = tk.Button(watch_frame_inner, text="폴더 찾기", command=select_watch_folder)
btn_watch_dir.pack(side="right")

filename_frame = tk.Frame(auto_frame)
filename_frame.pack(fill="x", pady=5)
tk.Label(filename_frame, text="파일명(확장자포함):").pack(side="left")
entry_filename = tk.Entry(filename_frame)
entry_filename.pack(side="left", padx=5, fill="x", expand=True)
entry_filename.insert(0, target_filename_input)

btn_watch_toggle = tk.Button(auto_frame, text="감시 시작", bg="lightgray", command=toggle_watch)
btn_watch_toggle.pack(fill="x", pady=5)

status_label = tk.Label(bottom_frame, text="준비 완료")
status_label.pack(pady=5)

btn_start = tk.Button(bottom_frame, text="선택 파일 처리 시작", width=20, command=start_compression, bg="lightblue")
btn_start.pack(pady=5)

# 하단 버튼 변경: 감시 폴더 열기
btn_open_folder = tk.Button(bottom_frame, text="감시 폴더 열기", width=20, command=open_watch_folder)
btn_open_folder.pack(pady=5)

root.mainloop()