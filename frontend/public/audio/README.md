# NEX Voice Audio Files

These .mp3 files are generated via ElevenLabs API (voice: Adam, pNInz6obpgDQGcFmaJgB).
Model: eleven_multilingual_v2 | Stability: 0.75 | Similarity: 0.85

## Lines to generate:
1. nex_line1.mp3 - "Hello. I am NEX. I am the core intelligence of your workspace."
2. nex_line2.mp3 - "I read, analyze, and map your documents. Scroll down to ask me anything."

## Generate via curl:
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB" \
  -H "xi-api-key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello. I am NEX.","model_id":"eleven_multilingual_v2","voice_settings":{"stability":0.75,"similarity_boost":0.85}}' \
  --output public/audio/nex_line1.mp3

Note: .mp3 files are gitignored. Add them locally after generation.
