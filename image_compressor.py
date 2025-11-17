import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk  # 썸네일
import os
import platform
import subprocess
import json  # 경로 저장을 위해 json 추가

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    messagebox.showerror("라이브러리 오류",
                         "tkinterdnd2 라이브러리가 필요합니다.\n\n"
                         "터미널에서 'pip install tkinterdnd2'를 실행해주세요.")
    exit()

CONFIG_FILE = 'compressor_config.json'
file_list = []
save_directory = os.path.join(os.path.expanduser('~'), 'Downloads')


# --- 경로 저장/로드 함수 ---
def save_config():
    # 현재 save_directory를 config.json에 저장
    config = {'save_directory': save_directory}
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Config 저장 오류: {e}")


def load_config():
    # config.json에서 save_directory를 불러옴
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


# --- 메인 기능 ---
def compress_image(input_path, output_dir):
    try:
        img = Image.open(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        new_filename = f"{name}_compressed.jpg"
        output_path = os.path.join(output_dir, new_filename)

        if img.mode == 'RGBA':
            img = img.convert('RGB')

        img.save(output_path, "JPEG", quality=90, optimize=True)
        return output_path
    except Exception as e:
        return f"오류 발생 ({filename}): {e}"


def open_save_folder():
    if not os.path.isdir(save_directory):
        messagebox.showerror("오류", f"저장 폴더를 찾을 수 없습니다:\n{save_directory}")
        return
    try:
        if platform.system() == "Windows":
            os.startfile(save_directory)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", save_directory])
        else:  # Linux
            subprocess.run(["xdg-open", save_directory])
    except Exception as e:
        messagebox.showwarning("폴더 열기 실패", f"폴더를 여는 데 실패했습니다: {e}")


# --- GUI 이벤트 핸들러 ---
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
        save_config()  # 변경된 경로 저장

def update_save_dir_label():
    display_path = save_directory
    if len(display_path) > 35:  # 레이블 공간에 맞게 길이 조절
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

    status_label.config(text="압축 진행 중...")
    compressed_count = 0
    listbox.delete(0, tk.END)

    for i, file_path in enumerate(file_list):
        listbox.insert(tk.END, f"[압축 중...] {os.path.basename(file_path)}")
        listbox.update_idletasks()

        result = compress_image(file_path, save_directory)

        listbox.delete(i)
        if "오류" in str(result):
            listbox.insert(i, f"[실패] {os.path.basename(file_path)}")
        else:
            listbox.insert(i, f"[완료] {os.path.basename(result)}")
            compressed_count += 1

            # 썸네일 생성
            try:
                pil_img = Image.open(result)
                pil_img.thumbnail((100, 100))  # 썸네일 크기 100x100
                new_thumb_tk = ImageTk.PhotoImage(pil_img)
                thumbnail_label.config(image=new_thumb_tk)
                thumbnail_label.image = new_thumb_tk
            except Exception as e:
                print(f"썸네일 생성 오류: {e}")
                thumbnail_label.config(text="썸네일 오류")

    status_label.config(text=f"압축 완료! (총 {compressed_count}개 파일)")
    messagebox.showinfo("완료", f"총 {compressed_count}개의 파일 압축을 완료했습니다.\n"
                              f"저장 폴더: {save_directory}")
    file_list.clear()


# --- GUI 생성 ---

# 프로그램 시작 시 설정 불러오기
load_config()

root = TkinterDnD.Tk()
root.title("이미지 용량 축소기 v4.1")
root.minsize(300, 300)

# 항상 화면에 띄우기
root.wm_attributes("-topmost", 1)

# --- 프레임 설정 ---
top_frame = tk.Frame(root, pady=10)
top_frame.pack()

save_frame = tk.Frame(root, pady=5)
save_frame.pack(fill="x", padx=20)

# ★★★ 썸네일 프레임 (높이 조절) ★★★
thumbnail_frame = tk.Frame(root, height=110, pady=5)
thumbnail_frame.pack()
thumbnail_frame.pack_propagate(False)

middle_frame = tk.Frame(root, pady=5)
middle_frame.pack(fill="x")

bottom_frame = tk.Frame(root, pady=10)
bottom_frame.pack(fill="x")

# --- 위젯 생성 ---
# 상단 프레임: 버튼들 (저장 폴더 변경 버튼 제거)
btn_select = tk.Button(top_frame, text="파일 선택", width=12, command=select_files)
btn_select.pack(side="left", padx=5)

btn_start = tk.Button(top_frame, text="압축 시작", width=12, command=start_compression, bg="lightblue")
btn_start.pack(side="left", padx=5)

# 저장 폴더 프레임
# 레이블이 왼쪽에, 버튼이 오른쪽에 오도록 배치
save_dir_label = tk.Label(save_frame, text="", anchor="w")  # 텍스트는 update 함수로 설정
save_dir_label.pack(side="left", fill="x", expand=True, padx=5)

btn_save_dir = tk.Button(save_frame, text="저장 폴더 변경", width=12, command=select_save_directory)
btn_save_dir.pack(side="right")


update_save_dir_label()

# 썸네일 프레임
thumbnail_label = tk.Label(thumbnail_frame, text="압축 썸네일",
                           borderwidth=1, relief="solid",
                           width=100, height=100)  # 썸네일 크기 100x100
thumbnail_label.pack(pady=5)

# 중간 프레임: 파일 목록
list_label = tk.Label(middle_frame, text="--- 여기에 파일을 드래그하세요 ---")
list_label.pack()

listbox = tk.Listbox(middle_frame, height=10)
listbox.pack(pady=5, padx=20, fill="x")

listbox.drop_target_register(DND_FILES)
listbox.dnd_bind('<<Drop>>', drop_handler)

# 하단 프레임: 상태 표시줄 및 폴더 열기 버튼
status_label = tk.Label(bottom_frame, text="압축할 파일을 선택하거나 드래그하세요.")
status_label.pack(pady=5)

btn_open_folder = tk.Button(bottom_frame, text="압축 폴더 열기", width=20, command=open_save_folder)
btn_open_folder.pack(pady=5)

# --- 메인 루프 시작 ---
root.mainloop()