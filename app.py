import streamlit as st
import json
import io
import os
from google import genai
from google.genai import types
from google.cloud import texttospeech

# Setup page layout
st.set_page_config(page_title="MLB AI Voice Broadcast Demo", page_icon="⚾", layout="wide")

# Determine project setup
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")

# Initialize the new Google Gen AI SDK Client
if PROJECT_ID:
    client = genai.Client(
        enterprise=True,
        project=PROJECT_ID,
        location="global"
    )
else:
    st.warning("⚠️ GOOGLE_CLOUD_PROJECT environment variable not set. Running locally might require setting active gcloud credentials.")

def generate_broadcast_script(game_json_str: str) -> list:
    """
    Sends simulated MLB data to Gemini 3.5 Flash using the brand new Google Gen AI SDK.
    Outputs a natural, sports-radio dialog script complete with Studio-compatible SSML.
    """
    # Using the brand new Gemini 3.5 Flash model!
    # model = GenerativeModel("gemini-3.5-flash")
    
    prompt = f"""
    You are an award-winning, highly energetic Major League Baseball radio broadcasting team.
    Analyze the following live MLB game data and write an incredibly exciting, 3-to-4 turn radio broadcast dialogue.
    
    Roles:
    - 'announcer' (Play-by-Play): High energy, screaming with excitement on big plays. Uses rapid speech, dramatic pauses, and vocal shifts.
    - 'commentator' (Color Analyst): Deeper, more analytical, but matching the announcer's hype with professional weight.

    CRITICAL INSTRUCTION FOR NATURAL EXPRESSION (SSML & Studio Voices):
    Studio voices are highly expressive but have specific SSML limits:
    1. DO NOT use `<emphasis>` tags. They are unsupported.
    2. Instead of emphasis tags, use natural textual cues like ALL CAPS (e.g., "CRUSHED", "GONE") or exclamation points to indicate excitement.
    3. Use `<break time="300ms"/>` or `<break time="600ms"/>` for dramatic suspense before big announcements (e.g., "The pitch is on the way... <break time="400ms"/> HE HIT IT!").
    4. Wrap the entire string in `<speak> ... </speak>` tags. Do not write text outside of `<speak>` tags.

    Game State Data:
    {game_json_str}
    """

    # Structured JSON Schema for the new SDK
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
                            "description": "The exact SSML string wrapped in <speak> tags."
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
        temperature=0.45,
    )

    # Calling the gemini-3.5-flash model via the new SDK
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=config
    )
    
    data = json.loads(response.text)
    return data.get("turns", [])


def synthesize_broadcast(script_turns: list) -> bytes:
    """
    Stitches individual turn-by-turn dialogue into a single MP3 stream using Cloud TTS Premium Studio Voices.
    """
    tts_client = texttospeech.TextToSpeechClient()
    combined_audio = io.BytesIO()

    # Premium, high-fidelity Studio voices
    voice_map = {
        "announcer": {
            "language_code": "en-US",
            "name": "en-US-Studio-O",  # Extremely rich, deep, professional male narrator
        },
        "commentator": {
            "language_code": "en-US",
            "name": "en-US-Studio-Q",  # Crisp, highly articulated, analytical female narrator
        }
    }

    for turn in script_turns:
        speaker = turn["speaker"]
        ssml_text = turn["text"]
        
        cfg = voice_map.get(speaker, voice_map["announcer"])
        
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=cfg["language_code"],
            name=cfg["name"]
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        combined_audio.write(response.audio_content)

    combined_audio.seek(0)
    return combined_audio.read()


# --- Streamlit UI Render ---

st.title("⚾ MLB Live Game AI Broadcast Engine")
st.markdown("### Powered by **Gemini 3.5 Flash** & Google Cloud Premium **Studio** Voices")

# Seed sample live game event JSON
DEFAULT_GAME_DATA = {
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
}

col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Live Game Data Feed (Simulated)")
    st.caption("Change values within the JSON box (e.g., pitch_type, score, outcome, or description) to simulate real-time game shifts.")
    
    json_input = st.text_area(
        "Raw Game Event JSON", 
        value=json.dumps(DEFAULT_GAME_DATA, indent=2), 
        height=450
    )

with col2:
    st.header("2. AI Broadcast Output")
    
    if st.button("Generate Live Broadcast Audio 🎙️", use_container_width=True):
        try:
            parsed_data = json.loads(json_input)
            
            with st.spinner("Gemini 3.5 Flash analyzing game data and writing script..."):
                script = generate_broadcast_script(json.dumps(parsed_data))
                
            st.write("### Generated Broadcast Script")
            for turn in script:
                speaker_label = "🎙️ Play-by-Play (Announcer - Studio-O)" if turn['speaker'] == 'announcer' else "🧠 Color Commentator (Analyst - Studio-Q)"
                st.markdown(f"**{speaker_label}**")
                st.info(turn['text'])
                
            with st.spinner("Synthesizing multi-speaker studio-quality audio..."):
                audio_bytes = synthesize_broadcast(script)
                
            st.write("### Play Broadcast Audio")
            st.audio(audio_bytes, format="audio/mp3")
            st.success("Audio synthesized successfully using Premium Google Cloud Studio TTS!")
            
        except json.JSONDecodeError:
            st.error("Invalid JSON format. Please correct your data syntax.")
        except Exception as e:
            st.error(f"Error executing pipeline: {e}")
