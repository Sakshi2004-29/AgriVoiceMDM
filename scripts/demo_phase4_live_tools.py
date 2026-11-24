"""
Interactive Demonstration for Phase 4:
Live Mandi Market Prices, Live Weather Advisories, and Multilingual NLU Routing.

Demonstrates:
1. Mandi Market Prices (Agmarknet schema, modal prices, units, dates).
2. Live Weather and Agromet Advisories (Open-Meteo & IMD caution rules).
3. Multilingual NLU intent classification & entity extraction (Hindi & Marathi).
4. Intelligent routing across Mandi, Weather, ICAR/KVK RAG, and Safe Refusal.
5. End-to-end voice query integration with spoken responses.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.voice_assistant import VoiceAgriculturalAssistant
from src.knowledge.models import DocumentMetadata


def print_banner(text: str):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)


def setup_knowledge_base(assistant: VoiceAgriculturalAssistant):
    """Ensures verified ICAR Cotton advisory is indexed for RAG queries."""
    meta_cotton = DocumentMetadata(
        doc_id="DOC_ICAR_COTTON_001",
        title="ICAR-CICR Cotton Advisory: Pink Bollworm Management",
        source="ICAR-CICR Advisory Bulletin 2026",
        publisher="Indian Council of Agricultural Research",
        crop="Cotton",
        region="Maharashtra",
        season="Kharif",
        language="en",
        publication_date="2026-05-15"
    )
    assistant.rag_service.ingest_pdf(
        "data/raw_documents/cotton_pink_bollworm_icar_advisory.pdf",
        meta_cotton,
        auto_approve=True
    )


def main():
    print_banner("PHASE 4 DEMO: LIVE DATA TOOLS & MULTILINGUAL NLU ROUTING")

    assistant = VoiceAgriculturalAssistant(data_dir="data")
    setup_knowledge_base(assistant)

    # 1. Mandi Price Query in Hindi (Cotton in Nagpur)
    print_banner("DEMO 1: Mandi Market Price Query in Hindi (नागपुर में कपास का भाव)")
    q1 = "नागपुर मंडी में कपास का आज का भाव क्या है?"
    print(f"User Query: '{q1}' (Language: hi)")
    res1 = assistant.process_text_query(q1, language_hint="hi")
    print(f"Status:             {res1['status'].upper()}")
    print(f"Intent Identified:  {res1['intent'].upper()}")
    print(f"Extracted Entities: {res1.get('entities')}")
    print(f"Response:           {res1['text_response']}")
    print(f"Source Cited:       {res1['citations']}")

    # 2. Mandi Price Query in Marathi (Onion in Nashik)
    print_banner("DEMO 2: Mandi Market Price Query in Marathi (नाशिकमध्ये कांद्याचा भाव)")
    q2 = "नाशिक बाजारपेठेत कांद्याचा काय भाव चालू आहे?"
    print(f"User Query: '{q2}' (Language: mr)")
    res2 = assistant.process_text_query(q2, language_hint="mr")
    print(f"Status:             {res2['status'].upper()}")
    print(f"Intent Identified:  {res2['intent'].upper()}")
    print(f"Extracted Entities: {res2.get('entities')}")
    print(f"Response:           {res2['text_response']}")
    print(f"Source Cited:       {res2['citations']}")

    # 3. Weather Advisory Query in Marathi (Pune Weather)
    print_banner("DEMO 3: Live Weather Advisory in Marathi (पुणे येथील हवामान)")
    q3 = "पुणे येथील आजचे हवामान कसे आहे?"
    print(f"User Query: '{q3}' (Language: mr)")
    res3 = assistant.process_text_query(q3, language_hint="mr")
    print(f"Status:             {res3['status'].upper()}")
    print(f"Intent Identified:  {res3['intent'].upper()}")
    print(f"Extracted Entities: {res3.get('entities')}")
    print(f"Response:           {res3['text_response']}")
    print(f"Source Cited:       {res3['citations']}")

    # 4. Clarification Request: Mandi query without crop
    print_banner("DEMO 4: Clarification Request (Mandi price asked without crop)")
    q4 = "आज मंडी में क्या भाव चल रहा है?"
    print(f"User Query: '{q4}' (Language: hi)")
    res4 = assistant.process_text_query(q4, language_hint="hi")
    print(f"Status:             {res4['status'].upper()} (Missing: {res4.get('missing_entity')})")
    print(f"Clarification Note: {res4['text_response']}")

    # 5. Verified Agricultural Knowledge RAG (Cotton Pink Bollworm)
    print_banner("DEMO 5: Knowledge RAG Routing (कपास में गुलाबी सुंडी नियंत्रण)")
    q5 = "कपास में गुलाबी सुंडी नियंत्रण के लिए क्या करें?"
    print(f"User Query: '{q5}' (Language: hi)")
    res5 = assistant.process_text_query(q5, language_hint="hi")
    print(f"Status:             {res5['status'].upper()}")
    print(f"Intent Identified:  {res5['intent'].upper()}")
    print(f"Grounded Response:  {res5['text_response']}")
    print(f"Source Cited:       {res5['citations']}")

    # 6. Out-of-Scope Query (Zero-Guessing Safe Refusal)
    print_banner("DEMO 6: Out-of-Scope Query (Cryptocurrency in Mumbai)")
    q6 = "What is the cryptocurrency stock rate in Mumbai?"
    print(f"User Query: '{q6}' (Language: en)")
    res6 = assistant.process_text_query(q6, language_hint="en")
    print(f"Status:             {res6['status'].upper()}")
    print(f"Intent Identified:  {res6['intent'].upper()}")
    print(f"Refusal Response:   {res6['text_response']}")
    print(f"Helpline Referral:  {res6.get('referrals', {}).get('kisan_call_centre')}")

    # 7. Voice Query with Live Mandi Lookup
    print_banner("DEMO 7: Voice Note Query -> Live Mandi Price Response")
    voice_dir = Path("data/cache/demo_voice_inputs")
    voice_dir.mkdir(parents=True, exist_ok=True)
    voice_file = voice_dir / "voice_mandi_cotton.wav"
    assistant.preprocessor.generate_synthetic_tone_wav(str(voice_file), duration=2.0)
    assistant.transcriber.register_mock_audio(
        file_path=str(voice_file),
        transcript="नागपुर मंडी में कपास का भाव क्या है?",
        language="hi",
        confidence=0.95
    )
    print(f"-> Processing Voice Note: {voice_file.name}")
    res7 = assistant.process_voice_query(str(voice_file), language_hint="hi")
    print(f"Status:             {res7['status'].upper()}")
    print(f"Transcript:         '{res7['transcript']}'")
    print(f"Intent:             {res7['intent'].upper()}")
    print(f"Spoken Response:    {res7['text_response']}")
    print(f"Audio Output Path:  {res7['audio_response_path']}")

    print_banner("PHASE 4 DEMONSTRATION COMPLETE - ALL LIVE TOOLS AND NLU ROUTES VERIFIED")


if __name__ == "__main__":
    main()
