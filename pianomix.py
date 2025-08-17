from gpiozero import Button, LED
from signal import pause
import pygame
from time import time, sleep
from threading import Thread

# Sound setup
pygame.mixer.init()
sound_files = ["C.wav", "D.wav", "E.wav", "F.wav", "G.wav", "A.wav"]  # Must be present in same dir
sounds = [pygame.mixer.Sound(f) for f in sound_files]

# Button and LED setup (example GPIO pins)
button_pins = [5, 6, 13, 19, 26, 21]
led_pins = [12, 16, 20, 25, 8, 7]
buttons = [Button(pin) for pin in button_pins]
leds = [LED(pin) for pin in led_pins]

# Record/Playback button
record_button = Button(18)

# Recording buffer
recording = []
is_recording = False
start_time = None
is_replaying = False

# Store pressed notes with timestamps
def play_note(index):
    if is_replaying:
        return
    leds[index].on()
    sounds[index].play()
    sleep(0.2)
    leds[index].off()
    if is_recording:
        timestamp = time() - start_time
        recording.append((timestamp, index))

# Button press binding
for i, btn in enumerate(buttons):
    btn.when_pressed = lambda i=i: play_note(i)

# Record/playback logic
def handle_record_button():
    global is_recording, recording, start_time, is_replaying

    if not is_recording and not is_replaying:
        print("Recording started.")
        recording = []
        is_recording = True
        start_time = time()
        Thread(target=stop_recording_after_10s).start()
    elif not is_replaying:
        print("Replaying...")
        is_replaying = True
        Thread(target=replay_recording).start()

def stop_recording_after_10s():
    global is_recording
    sleep(10)
    is_recording = False
    print("Recording stopped.")

def replay_recording():
    global is_replaying
    base = time()
    for note_time, note_index in recording:
        while time() - base < note_time:
            sleep(0.01)
        play_note(note_index)
    print("Replay complete.")
    is_replaying = False

# Bind record/playback button
record_button.when_pressed = handle_record_button

# Keep program running
print("Piano ready. Press record to start.")
pause()
