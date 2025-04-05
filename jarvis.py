import pvporcupine
import pyaudio
import struct

# Replace '/path/to/jarvis.ppn' with the actual path to your custom keyword file.
# wake word
keyword_paths = ['jarvis_wake_word.ppn']

# Initialize Porcupine with your custom keyword.
porcupine = pvporcupine.create(keyword_paths=keyword_paths, access_key="HcnZSWZjMrd3zWYFYK5W4leD2ki82wH1F/5iRefSUa+rbmTEqUlrQQ==")

# Set up audio stream using PyAudio.
pa = pyaudio.PyAudio()
audio_stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

print("Listening for wake word 'Jarvis'...")

try:
    while True:
        # Read a frame of audio.
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

        # Process the audio frame with Porcupine.
        result = porcupine.process(pcm)
        if result >= 0:
            print("Wake word 'Jarvis' detected!")
            # You can now trigger your recording or further processing here.
            # Call function that starts listening for command
            
            break

except KeyboardInterrupt:
    print("Stopping wake word detection.")

finally:
    # Clean up resources.
    audio_stream.stop_stream()
    audio_stream.close()
    pa.terminate()
    porcupine.delete()
