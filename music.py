import tkinter as tk
from tkinter import filedialog
import pygame
import threading
import time
import os
import json
from googletrans import Translator

class AudioPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Player with LRC")
        self.root.geometry("400x400")

        self.label = tk.Label(self.root, text="Select an audio file to play", wraplength=300)
        self.label.pack(pady=5)

        self.music_listbox = tk.Listbox(self.root, width=50)
        self.music_listbox.pack()
        self.music_listbox.bind("<<ListboxSelect>>", self.on_music_select)

        self.play_stop_button = tk.Button(self.root, text="Play", command=self.play_stop_audio)
        self.play_stop_button.pack()

        self.progress = tk.Scale(self.root, from_=0, to=100, orient="horizontal", length=300, showvalue=False)
        self.progress.bind("<ButtonRelease-1>", self.on_progress_change)
        self.progress.pack(pady=5)

        self.time_label = tk.Label(self.root, text="0:00 / 0:00")
        self.time_label.pack()

        self.prev_lyric_label = tk.Label(self.root, text="", wraplength=300, fg="gray")
        self.prev_lyric_label.pack()

        self.current_lyric_label = tk.Label(self.root, text="", wraplength=300, fg="black", font=("Helvetica", 14))
        self.current_lyric_label.pack(pady=5)

        self.next_lyric_label = tk.Label(self.root, text="", wraplength=300, fg="gray")
        self.next_lyric_label.pack()

        pygame.mixer.init()
        self.is_playing = False
        self.is_paused = False
        self.lrc_data = None
        self.audio_start_time = None
        self.paused_position = 0
        self.drag_data = {"x": 0, "y": 0}
        self.translator = Translator()
        self.translated_lyrics = {}  # 用於緩存翻譯結果
        self.music_files = []  # 用於存儲音樂文件的路徑

        self.init_lrc_window()
        self.load_music_files("musiclist")  # 加載 "musiclist" 文件夾中的音樂文件

    def load_music_files(self, folder):
        for file in os.listdir(folder):
            if file.endswith((".wav", ".mp3")):  # 支持多種音樂文件類型
                audio_file_path = os.path.join(folder, file)
                lrc_file_path = os.path.splitext(audio_file_path)[0] + ".lrc"
                if os.path.exists(lrc_file_path):
                    self.music_files.append((audio_file_path, lrc_file_path))
                    self.music_listbox.insert(tk.END, file)
        if self.music_files:
            self.open_file(self.music_files[0][0], self.music_files[0][1])

    def on_music_select(self, event):
        selected_index = self.music_listbox.curselection()
        if selected_index:
            audio_file, lrc_file = self.music_files[selected_index[0]]
            self.open_file(audio_file, lrc_file)

    def open_file(self, audio_file, lrc_file):
        self.audio_file = audio_file
        self.lrc_file = lrc_file
        self.load_lrc(self.lrc_file)
        self.label.config(text=f"Selected File: {self.audio_file}")
        self.audio_length = pygame.mixer.Sound(self.audio_file).get_length()
        self.progress.config(to=self.audio_length)

        # 加載翻譯記錄
        self.load_translation_cache()

        # 開始預翻譯歌詞
        threading.Thread(target=self.pre_translate_lyrics).start()

    def load_lrc(self, lrc_path):
        self.lrc_data = []
        try:
            with open(lrc_path, "r", encoding="utf-8") as file:
                for line in file:
                    if line.strip().startswith('[') and ']' in line:
                        time_str, lyric = line.strip().split(']', 1)
                        try:
                            minute, second = map(float, time_str[1:].split(':'))
                            self.lrc_data.append((minute * 60 + second, lyric))
                        except ValueError:
                            continue
        except FileNotFoundError:
            self.lrc_window_label.config(text="No LRC file found.")

    def load_translation_cache(self):
        translation_cache_file = os.path.splitext(self.audio_file)[0] + ".json"
        if os.path.exists(translation_cache_file):
            with open(translation_cache_file, "r", encoding="utf-8") as file:
                self.translated_lyrics = json.load(file)
        # 檢查翻譯記錄是否有空字符串或"no wifi"
        for lyric, translation in self.translated_lyrics.items():
            if translation in ["", "no wifi"]:
                self.translated_lyrics[lyric] = self.translate_lyric(lyric)
                self.save_translation_cache()

    def save_translation_cache(self):
        translation_cache_file = os.path.splitext(self.audio_file)[0] + ".json"
        with open(translation_cache_file, "w", encoding="utf-8") as file:
            json.dump(self.translated_lyrics, file, ensure_ascii=False, indent=4)

    def pre_translate_lyrics(self):
        updated = False
        for i, (_, lyric) in enumerate(self.lrc_data):
            if lyric not in self.translated_lyrics or self.translated_lyrics[lyric] in ["", "no wifi"]:
                translated_lyric = self.translate_lyric(lyric)
                self.translated_lyrics[lyric] = translated_lyric
                updated = True
            if i >= len(self.lrc_data) - 1:
                break
            next_lyric = self.lrc_data[i + 1][1]
            if next_lyric not in self.translated_lyrics or self.translated_lyrics[next_lyric] in ["", "no wifi"]:
                translated_lyric = self.translate_lyric(next_lyric)
                self.translated_lyrics[next_lyric] = translated_lyric
                updated = True
        if updated:
            self.save_translation_cache()

    def play_audio(self, start_pos=0):
        if self.audio_file:
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.play(start=start_pos)
            self.is_playing = True
            self.is_paused = False
            self.audio_start_time = time.time() - start_pos
            threading.Thread(target=self.update_progress).start()
            threading.Thread(target=self.update_lrc).start()
            self.play_stop_button.config(text="Stop")

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.play_stop_button.config(text="Play")

    def play_stop_audio(self):
        if self.is_playing:
            self.stop_audio()
        else:
            self.play_audio(start_pos=self.paused_position)

    def on_progress_change(self, event):
        new_pos = self.progress.get()
        self.paused_position = new_pos
        self.play_audio(start_pos=new_pos)

    def update_progress(self):
        while self.is_playing and pygame.mixer.music.get_busy():
            if not self.is_paused:
                current_pos = (time.time() - self.audio_start_time)
                self.progress.set(current_pos)
                self.update_time_label(current_pos)
            time.sleep(0.5)

    def update_time_label(self, current_pos):
        current_minutes = int(current_pos // 60)
        current_seconds = int(current_pos % 60)
        total_minutes = int(self.audio_length // 60)
        total_seconds = int(self.audio_length % 60)
        self.time_label.config(text=f"{current_minutes}:{current_seconds:02d} / {total_minutes}:{total_seconds:02d}")

    def update_lrc(self):
        while self.is_playing and pygame.mixer.music.get_busy():
            if not self.is_paused:
                elapsed_time = time.time() - self.audio_start_time
                prev_lyric = ""
                current_lyric = ""
                next_lyric = ""
                for i, (t, lyric) in enumerate(self.lrc_data):
                    if elapsed_time > t:
                        current_lyric = lyric
                        prev_lyric = self.lrc_data[i - 1][1] if i > 0 else ""
                        next_lyric = self.lrc_data[i + 1][1] if i < len(self.lrc_data) - 1 else ""
                self.prev_lyric_label.config(text=prev_lyric)
                self.current_lyric_label.config(text=current_lyric)
                self.next_lyric_label.config(text=next_lyric)
                translated_lyric = self.translated_lyrics.get(current_lyric, "")
                self.lrc_window_label.config(text=f"{current_lyric}\n{translated_lyric}")
                self.adjust_lrc_window_size()
            time.sleep(0.5)

    def init_lrc_window(self):
        self.lrc_window = tk.Toplevel(self.root)
        self.lrc_window.overrideredirect(True)
        self.lrc_window.attributes("-topmost", True)

        # 設置淺灰色且透明50%的背景
        self.lrc_window.attributes("-alpha", 0.5)
        self.lrc_window.configure(bg="#D3D3D3")

        self.lrc_window.geometry("300x50+100+100")
        self.lrc_window.bind("<B1-Motion>", self.on_drag_window)
        self.lrc_window.bind("<Button-1>", self.on_click_window)

        self.lrc_window_label = tk.Label(self.lrc_window, text="", font=("Helvetica", 14), fg="black", bg="#D3D3D3", wraplength=500)
        self.lrc_window_label.pack(pady=5)

    def adjust_lrc_window_size(self):
        self.lrc_window.update_idletasks()
        width = self.lrc_window_label.winfo_reqwidth() + 20
        height = self.lrc_window_label.winfo_reqheight() + 10
        self.lrc_window.geometry(f"{width}x{height}")

    def on_drag_window(self, event):
        x = self.lrc_window.winfo_pointerx() - self.drag_data["x"]
        y = self.lrc_window.winfo_pointery() - self.drag_data["y"]
        self.lrc_window.geometry(f"+{x}+{y}")

    def on_click_window(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def translate_lyric(self, text):
        try:
            result = self.translator.translate(text, dest='zh-cn')
            return result.text
        except Exception as e:
            return "no wifi"

if __name__ == "__main__":
    root = tk.Tk()
    player = AudioPlayer(root)
    root.mainloop()
