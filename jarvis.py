# wake word 
import pvporcupine
# for input capture
import pyaudio
import struct
import speech_recognition as sr
import time # Added for potential sleeps
import whisper # Added for Whisper
import numpy as np # Added for Whisper audio processing
import io # Added for in-memory audio file
import requests
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

# Replace '/path/to/jarvis.ppn' with the actual path to your custom keyword file.
keyword_paths = ['jarvis_wake_word.ppn']

# Initialize Porcupine with your custom keyword.
porcupine = pvporcupine.create(keyword_paths=keyword_paths, access_key="R/OeswFKU3HGjqIM/PHstMUn4Lwm3nZY5I7HO9zL1EgP/abRZi6qBA==")

# Set up audio stream using PyAudio.
pa = pyaudio.PyAudio()
audio_stream = pa.open(
    rate=porcupine.sample_rate, # Use Porcupine's sample rate
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

# Initialize Recognizer
r = sr.Recognizer()
# Increase pause threshold to be more tolerant of pauses in speech
r.pause_threshold = 1.5  # Default is 0.8, increase to allow longer pauses

# Load Whisper model (using .en for English-only, faster)
# Models: tiny.en, base.en, small.en, medium.en
print("Loading Whisper model...")
whisper_model = whisper.load_model("base.en")
print("Whisper model loaded.")

def listen_for_query():
    """Listens for a command after the wake word is detected using Whisper."""
    global audio_stream # Need to modify the global stream object
    # Close Porcupine audio stream completely
    if audio_stream is not None:
        audio_stream.close()
        audio_stream = None # Set to None after closing

    query = None
    try:
        # Use the same sample rate Porcupine uses for consistency
        with sr.Microphone(sample_rate=porcupine.sample_rate) as source:
            # Adjust for ambient noise dynamically
            r.adjust_for_ambient_noise(source, duration=0.1)

            # Listen for audio with increased timeout and phrase limit
            print("Listening for command...")
            audio = r.listen(source, timeout=7, phrase_time_limit=15) 

            # Get audio data in WAV format
            wav_data = audio.get_wav_data()
            audio_data = io.BytesIO(wav_data)
            audio_data.name = "speech.wav" # Whisper needs a filename hint

            # Convert audio data to numpy array expected by Whisper
            # Need to ensure the sample rate matches what the model expects if different
            # For PyAudio paInt16 format, scale to float between -1 and 1
            audio_np = np.frombuffer(audio.get_raw_data(), dtype=np.int16).astype(np.float32) / 32768.0

            # Transcribe using Whisper
            # Use fp16=False if you don't have a GPU or encounter issues
            result = whisper_model.transcribe(audio_np, fp16=False) # Set fp16=False for CPU
            query = result['text'].strip()

    except sr.WaitTimeoutError:
        print("No speech detected within timeout.")
    except Exception as e:
        print(f"An error occurred during listening or transcription: {e}")

    # Reopen Porcupine audio stream
    if audio_stream is None: # Make sure it's closed before reopening
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )
    # Add a small delay after reopening to allow stabilization
    time.sleep(0.1)
    print("Listening for wake word 'Jarvis'...") # Re-prompt after listening attempt
    return query

def initialize_audio_stream():
    """Initialize a new PyAudio stream for wake word detection."""
    global audio_stream
    if audio_stream is not None and hasattr(audio_stream, 'is_active') and audio_stream.is_active():
        audio_stream.stop_stream()
        audio_stream.close()
        
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )
    return audio_stream

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
            # Call function that starts listening for command
            query = listen_for_query()
            if query:
                # Process the query (add your logic here)
                print(f"Processing query: {query}")
                # hit n8n endpoint
                response = requests.post(
                    "http://localhost:5678/webhook/jarvis",
                    json={"query": query}
                )
                print(f"N8N response: {response.json()}")

                # text to speech - use a different variable for the speech stream
                tts_stream = client.text_to_speech.convert_as_stream(
                    text=response.json()['output'],
                    voice_id="RwsRBpO5E3SozIPdOsTc",
                    model_id="eleven_flash_v2_5",
                    optimize_streaming_latency=4
                )

                # Make sure audio_stream is closed before playing speech
                if audio_stream is not None and hasattr(audio_stream, 'is_active') and audio_stream.is_active():
                    audio_stream.stop_stream()
                    audio_stream.close()
                    audio_stream = None

                # Play the speech
                stream(tts_stream)
                
                # After speech playback, reinitialize audio stream for wake word detection
                audio_stream = initialize_audio_stream()
                print("Listening for wake word 'Jarvis'...")

        # Optional: Add a small sleep to reduce CPU usage slightly
        # time.sleep(0.01)

except KeyboardInterrupt:
    print("Stopping wake word detection.")

finally:
    # Clean up resources.
    if audio_stream is not None and hasattr(audio_stream, 'is_active') and audio_stream.is_active():
        audio_stream.stop_stream()
    if audio_stream is not None and hasattr(audio_stream, 'close'):
        audio_stream.close()
    if pa is not None:
        pa.terminate()
    if porcupine is not None:
        porcupine.delete()
    print("Resources cleaned up.")
