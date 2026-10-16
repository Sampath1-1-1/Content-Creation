"""Starting defaults that CANNOT be measured from metadata.

We never download audio or video, so tempo, voice style and pacing can't be
measured. These are conservative, widely used early-childhood production
practices — clearly labelled "inferred" in the report, and meant to be
tested and adjusted, not treated as facts.
"""

INFERRED_GUIDANCE_2_TO_4 = {
    "label": "INFERRED — common early-childhood practice, not measured from YouTube data",
    "tempo_bpm_range": [90, 120],
    "tempo_note": "Moderate tempo so toddlers can sing and move along; slower for counting sections.",
    "key_and_melody": "Bright major key, small melodic range (about 5–6 notes), simple repeating phrases.",
    "pause_for_answers_s": [1.5, 3.0],
    "repetition": "Say/sing each new number at least 3 times; recap the whole sequence at the end.",
    "one_concept_per_scene": True,
    "voice": "Warm, clear, slightly slower than adult speech; exaggerated but natural intonation.",
    "screen_text": "Large numerals, one at a time, high contrast; minimal other text.",
    "hook": "Show the main character and the 'problem/goal' within the first 5 seconds.",
    "call_and_response": "Ask a question, pause, then confirm the answer (e.g. 'How many? … Three!').",
    "safety": "No flashing (>3 flashes/s), no scary surprises, no unsafe actions children could copy.",
}
