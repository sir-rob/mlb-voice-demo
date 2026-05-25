import streamlit as st
import json
import io
import os
import wave
from google import genai
from google.genai import types

# Setup page layout
st.set_page_config(page_title="MLB AI Voice Broadcast Demo", page_icon="⚾", layout="wide")

# Determine project setup
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
REGION = "global"  # Gemini-TTS uses global endpoints for enterprise rendering

# Initialize the new Google Gen AI SDK Client
if PROJECT_ID:
    client = genai.Client(
        enterprise=True,
        project=PROJECT_ID,
        location=REGION
    )
else:
    st.warning("⚠️ GOOGLE_CLOUD_PROJECT environment variable not set.")

def generate_broadcast_script(game_json_str: str) -> list:
    """
    Sends simulated MLB data to Gemini 3.5 Flash to write the draft script.
    Optimized with bracketed emotion tags for Gemini-TTS.
    """
    prompt = f"""
    You are an award-winning, highly energetic Major League Baseball radio broadcasting team.
    Analyze the following live MLB game data and write an incredibly exciting, 3-to-4 turn radio broadcast dialogue.
    
    Roles:
    - 'announcer' (Play-by-Play): High energy, screaming with excitement on big plays. Uses rapid speech and dramatic pauses.
    - 'commentator' (Color Analyst): Deeper, more analytical, but matching the announcer's hype with professional weight.

    CRITICAL INSTRUCTION FOR NATURAL EXPRESSION (AUDIO TAGS):
    Do not use SSML tags (like <speak> or <prosody>). Instead, guide the voice engine using bracketed "Stage Directions" / Audio Tags directly in the sentences.
    - Use '[screaming]' before highly excited home run calls (e.g. "[screaming] SWUNG ON AND CRUSHED!").
    - Use '[excited]' for building high energy (e.g. "[excited] That ball is deep!").
    - Use '[short pause]' or '[gasp]' for building athletic tension.
    - Use '[thoughtful]' or '[analytical]' for the commentator's tactical review.

    Game State Data:
    {game_json_str}
    """

    # Structured JSON Schema
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "turns": {
                "type": "ARRAY",
                "description": "List of turns in the broadcast script.",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "speaker": {
                            "type": "STRING", 
                            "enum": ["announcer", "commentator"],
                            "description": "The person currently speaking."
                        },
                        "text": {
                            "type": "STRING",
                            "description": "The dialogue script turn containing bracketed audio tags."
                        }
                    },
                    "required": ["speaker", "text"]
                }
            }
        },
        "required": ["turns"]
    }

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=0.7,
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=config
    )
    
    data = json.loads(response.text)
    return data.get("turns", [])


def convert_pcm_to_wav(pcm_bytes: bytes, channels=1, rate=24000, sample_width=2) -> bytes:
    """
    Wraps raw 24kHz 16-bit mono PCM bytes into a standard WAV container 
    so standard web browsers can natively play the stream.
    """
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    wav_io.seek(0)
    return wav_io.read()


def synthesize_broadcast_native(script_turns: list) -> bytes:
    """
    Uses Gemini-TTS (gemini-3.1-flash-tts-preview) to synthesize highly emotional,
    excited voices directly from the model, then stitches the resulting audio streams.
    """
    # Create an in-memory buffer to collect raw PCM bytes
    pcm_buffer = io.BytesIO()

    # Highly expressive native Gemini-TTS voices
    voice_map = {
        "announcer": {
            "voice_name": "Puck",  # Upbeat, lively, perfect for sports shouting
            "style_prompt": "You are a professional radio play-by-play announcer. Perform this script turn with maximum authentic sportscast energy: "
        },
        "commentator": {
            "voice_name": "Kore",  # Warm, professional, conversational podcast voice
            "style_prompt": "You are a professional sports color commentator. Perform this strategic analyst turn naturally and clearly: "
        }
    }

    for turn in script_turns:
        speaker = turn["speaker"]
        dialogue_text = turn["text"]
        
        cfg = voice_map.get(speaker, voice_map["announcer"])
        
        # Build the natural language vocal instruction prompt
        generation_prompt = f"{cfg['style_prompt']}\n\"{dialogue_text}\""
        
        # Call the dedicated gemini-3.1-flash-tts-preview model
        response = client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=generation_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=cfg["voice_name"]
                        )
                    )
                ),
            )
        )
        
        # Extract and append the raw PCM audio bytes
        try:
            audio_part = response.candidates[0].content.parts[0]
            if audio_part.inline_data:
                pcm_buffer.write(audio_part.inline_data.data)
        except (IndexError, AttributeError):
            continue

    raw_pcm_data = pcm_buffer.getvalue()
    
    if not raw_pcm_data:
        raise ValueError("No audio content returned by the Gemini-TTS model.")

    # Wrap raw 24kHz 16-bit mono PCM into a standard WAV stream
    wav_output = convert_pcm_to_wav(raw_pcm_data)
    return wav_output


# --- Streamlit UI Render ---

st.title("⚾ MLB Live Game AI Broadcast Engine")
st.markdown("### Powered by **Gemini 3.5 Flash** (Script) & **Gemini 3.1 Flash TTS** (Performance Voice) 🎙️")

# Create the columns list as a single variable first to bypass the formatter macro
layout_columns = [1, 1]
cols = st.columns(layout_columns)

col1 = cols[0]
col2 = cols[1]

with col1:
    st.header("1. Live Game Data Feed (Simulated)")
    st.caption("Change values within the JSON box (e.g., pitch_type, score, outcome, or description) to simulate real-time game shifts.")
    
    json_input = st.text_area(
        "Raw Game Event JSON", 
        value=json.dumps({
          "game_state": {
            "inning": 9,
            "half_inning": "bottom",
            "outs": 2,
            "score": {
              "away_team": "Boston Red Sox",
              "home_team": "New York Yankees",
              "away_score": 4,
              "home_score": 3
            },
            "runners": {
              "first_base": "Aaron Judge",
              "second_base": None,
              "third_base": "Juan Soto"
            },
            "count": {
              "balls": 3,
              "strikes": 2
            }
          },
          "current_play": {
            "pitcher": "Kenley Jansen",
            "batter": "Giancarlo Stanton",
            "pitch_velocity_mph": 98,
            "pitch_type": "Cutter",
            "outcome": "Home Run",
            "description": "Stanton crushes a 98mph cutter deep into the left-field bleachers! A walk-off two-run home run!"
          }
        }, indent=2), 
        height=450
    )

with col2:
    st.header("2. AI Broadcast Output")
    
    if st.button("Generate Live Broadcast Audio 🎙️", use_container_width=True):
        try:
            parsed_data = json.loads(json_input)
            
            with st.spinner("Gemini 3.5 Flash writing script with Audio Tags..."):
                script = generate_broadcast_script(json.dumps(parsed_data))
                
            st.write("### Generated Broadcast Script")
            for turn in script:
                speaker_label = "🎙️ Play-by-Play (Announcer - Puck)" if turn['speaker'] == 'announcer' else "🧠 Color Commentator (Analyst - Kore)"
                st.markdown(f"**{speaker_label}**")
                st.info(turn['text'])
                
            with st.spinner("Executing Multimodal Performance Audio Generation..."):
                audio_bytes = synthesize_broadcast_native(script)
                
            st.write("### Play Native Audio Broadcast")
            st.audio(audio_bytes, format="audio/wav")
            st.success("Audio synthesized successfully using Native Gemini-TTS Modalities!")
            
        except json.JSONDecodeError:
            st.error("Invalid JSON format. Please correct your data syntax.")
        except Exception as e:
            st.error(f"Error executing pipeline: {e}")