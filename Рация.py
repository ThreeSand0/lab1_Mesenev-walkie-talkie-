import socket
import threading
import tkinter as tk
from datetime import datetime
import pyaudio

# НАСТРОЙКИ СЕТИ
BROADCAST_IP = "255.255.255.255"
TEXT_PORT = 55555
AUDIO_PORT = 55556  # Отдельный порт для аудио, чтобы не смешивать с текстом

# НАСТРОЙКИ АУДИОПОТОКА
FORMAT = pyaudio.paInt16  # 16-битный звук
CHANNELS = 1  # Моно
RATE = 11025  # Частота дискретизации (оптимально для раций в локальной сети)
CHUNK = 512  # Размер буфера данных

# Инициализация звукового движка
audio_engine = pyaudio.PyAudio()

# Глобальный флаг для контроля записи голоса
is_recording = False


# === МОДУЛЬ ЗВУКА И СЕТЕВОЙ ГОЛОСОВОЙ ПЕРЕДАЧИ ===


def voice_transmitter():
    """Поток, который считывает звук с микрофона и шлет в сеть, пока зажата кнопка."""
    global is_recording
    try:
        # Открываем поток записи с микрофона
        input_stream = audio_engine.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        print("🎙️ Микрофон активен, передача голоса...")

        while is_recording:
            # Читаем байты звука с микрофона и отправляем их по UDP бродкастом
            try:
                audio_data = input_stream.read(CHUNK, exception_on_overflow=False)
                audio_socket.sendto(audio_data, (BROADCAST_IP, AUDIO_PORT))
            except IOError:
                pass  # Игнорируем переполнение буфера микрофона

        input_stream.stop_stream()
        input_stream.close()
        audio_socket.close()
        print("🤫 Микрофон отключен.")
    except Exception as e:
        print(f"Ошибка аудио-передатчика: {e}")


def voice_receiver():
    """Фоновый поток, который слушает аудио-порт и воспроизводит звук в динамики."""
    try:
        output_stream = audio_engine.open(
            format=FORMAT, channels=CHANNELS, rate=RATE, output=True
        )

        audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        audio_socket.bind(("0.0.0.0", AUDIO_PORT))

        print(f"🔊 Динамики слушают аудио-эфир на порту {AUDIO_PORT}...")

        while True:
            audio_data, addr = audio_socket.recvfrom(2048)
            # Если мы сами отправляем бродкаст на одном ПК, звук может зациклиться.
            # Для полноценного теста на разных ПК это воспроизведет чистый звук соседа.
            output_stream.write(audio_data)

    except Exception as e:
        print(f"Ошибка аудио-приемника: {e}")


# === МОДУЛЬ ТЕКСТА (UDP) ===


def send_text_broadcast(message_type, content=""):
    """Отправка текстовых команд и сообщений."""
    try:
        sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        packet = f"{message_type}||{content}"
        sender_socket.sendto(packet.encode("utf-8"), (BROADCAST_IP, TEXT_PORT))
        sender_socket.close()
    except Exception as e:
        print(f"Ошибка текста: {e}")


def text_receiver():
    """Слушатель текстового эфира."""
    receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver_socket.bind(("0.0.0.0", TEXT_PORT))

    while True:
        try:
            data, addr = receiver_socket.recvfrom(1024)
            raw_message = data.decode("utf-8")
            if "||" in raw_message:
                msg_type, content = raw_message.split("||", 1)
                if msg_type == "MSG":
                    root.after(
                        0, lambda: log_event(f"[{addr[0]}] Сообщение: {content}")
                    )
                elif msg_type == "PING":
                    root.after(0, lambda: log_event(f"📡 В сети рация: {addr[0]}"))
        except Exception as e:
            print(f"Ошибка текста: {e}")
            break


# === ЛОГИКА УПРАВЛЕНИЯ И ИНТЕРФЕЙСА ===


def start_voice_transmission(event):
    """Срабатывает при зажатии кнопки голоса."""
    global is_recording
    if not is_recording:
        is_recording = True
        lbl_status.config(text="🎙️ ЭФИР ОТКРЫТ: ГОВОРИТЕ", fg="red")
        # Запускаем поток отправки звука
        threading.Thread(target=voice_transmitter, daemon=True).start()


def stop_voice_transmission(event):
    """Срабатывает при отпускании кнопки голоса."""
    global is_recording
    is_recording = False
    lbl_status.config(text="💤 Режим ожидания", fg="black")


def log_event(text):
    current_time = datetime.now().strftime("%H:%M:%S")
    chat_box.insert(tk.END, f"[{current_time}] {text}\n")
    chat_box.see(tk.END)


def transmit_text():
    text = entry_msg.get().strip()
    if text:
        send_text_broadcast("MSG", text)
        entry_msg.delete(0, tk.END)


# === ИНТЕРФЕЙС ПРИЛОЖЕНИЯ ===

root = tk.Tk()
root.title("Мультимедийная Рация (Голос + Текст)")
root.geometry("450x550")

# Блок голосовой связи (Push-to-Talk)
frame_voice = tk.LabelFrame(root, text="Голосовая рация PTT", padx=10, pady=10)
frame_voice.pack(fill=tk.X, padx=10, pady=5)

btn_voice = tk.Button(
    frame_voice,
    text="🎤 НАЖМИ И ГОВОРИ",
    font=("Arial", 12, "bold"),
    bg="#d9534f",
    fg="white",
    height=2,
)
btn_voice.pack(fill=tk.X)

# Привязываем события зажатия и отпускания кнопки мыши
btn_voice.bind("<ButtonPress-1>", start_voice_transmission)
btn_voice.bind("<ButtonRelease-1>", stop_voice_transmission)

lbl_status = tk.Label(
    frame_voice, text="💤 Режим ожидания", font=("Arial", 10, "italic")
)
lbl_status.pack(pady=5)

# Блок текстового чата
frame_chat = tk.LabelFrame(root, text="Текстовый лог эфира", padx=10, pady=5)
frame_chat.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

chat_box = tk.Text(frame_chat, height=12, width=40, font=("Courier", 10))
chat_box.pack(fill=tk.BOTH, expand=True, pady=5)

frame_input = tk.Frame(root, padx=10, pady=10)
frame_input.pack(fill=tk.X)

entry_msg = tk.Entry(frame_input, font=("Arial", 12))
entry_msg.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
entry_msg.bind("<Return>", lambda event: transmit_text())

btn_send = tk.Button(frame_input, text="📢 Текст", command=transmit_text)
btn_send.pack(side=tk.RIGHT, padx=5)

# Дополнительные инструменты
btn_ping = tk.Button(
    root, text="📡 Проверить устройства в сети", command=lambda: send_text_broadcast("PING")
)
btn_ping.pack(fill=tk.X, padx=15, pady=5)

# ЗАПУСК ФОНОВЫХ ПОТОКОВ ПРИЕМА
threading.Thread(target=text_receiver, daemon=True).start()
threading.Thread(target=voice_receiver, daemon=True).start()

root.mainloop()
