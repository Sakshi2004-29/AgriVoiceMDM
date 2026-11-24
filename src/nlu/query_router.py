"""
Multilingual Query Router (Phase 5 Enhanced).
Enforces:
1. Pre-execution Prompt Injection Guardrails
2. Banned / Hazardous Chemical Safety Filters
3. Multi-Signal Confidence Gating
4. Grounded Output Chemical Verification and Safety Disclaimers
Routes across Mandi Prices, Weather, Institutional RAG, and Safe Refusals.
"""
from typing import Dict, Any, Optional

from src.nlu.intent_classifier import IntentClassifier
from src.nlu.entity_extractor import EntityExtractor
from src.tools.mandi_price_tool import MandiPriceTool
from src.tools.weather_tool import WeatherTool
from src.knowledge.rag_service import AgriculturalRAGService
from src.guardrails.fallback_handler import FallbackHandler
from src.guardrails.chemical_safety import ChemicalSafetyGuardrail, PromptInjectionGuardrail
from src.guardrails.confidence_gate import MultiSignalConfidenceGate


class QueryRouter:
    """
    Intelligent query router with multi-signal confidence gating and safety guardrails.
    """

    CLARIFICATION_PROMPTS = {
        "mandi_crop_missing": {
            "hi": "कृपया बताएं कि आप किस फसल का मंडी भाव जानना चाहते हैं? (जैसे कपास, गेहूं, सोयाबीन, प्याज)।",
            "mr": "कृपया सांगा आपण कोणत्या पिकाचा बाजारभाव जाणून घेऊ इच्छिता? (उदा. कपाशी, गहू, सोयाबीन, कांदा).",
            "en": "Please tell me which crop's mandi price you want to check (e.g., Cotton, Wheat, Soybean, Onion)."
        },
        "weather_location_missing": {
            "hi": "कृपया जिले या स्थान का नाम बताएं जहां का मौसम आप जानना चाहते हैं (जैसे नागपुर, पुणे, लुधियाना)।",
            "mr": "कृपया जिल्ह्याचे किंवा ठिकाणाचे नाव सांगा जेथील हवामान आपण जाणून घेऊ इच्छिता (उदा. नागपूर, पुणे, अकोला).",
            "en": "Please specify the district name for the weather report (e.g., Nagpur, Pune, Ludhiana)."
        }
    }

    def __init__(
        self,
        rag_service: Optional[AgriculturalRAGService] = None,
        mandi_tool: Optional[MandiPriceTool] = None,
        weather_tool: Optional[WeatherTool] = None
    ):
        self.classifier = IntentClassifier()
        self.extractor = EntityExtractor()
        self.rag_service = rag_service or AgriculturalRAGService()
        self.mandi_tool = mandi_tool or MandiPriceTool()
        self.weather_tool = weather_tool or WeatherTool()
        self.fallback = FallbackHandler()
        self.confidence_gate = MultiSignalConfidenceGate()

    def route_query(
        self,
        query: str,
        language: str = "hi",
        default_district: Optional[str] = None,
        asr_confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Analyzes query intent, entities, safety risks, and confidence scores,
        then routes to the designated tool or knowledge engine.
        """
        lang = language if language in ["hi", "mr", "en"] else "hi"

        # 1. Safety Guardrail: Prompt Injection & Adversarial Bypass
        is_safe, injection_reason = PromptInjectionGuardrail.check_for_injection(query)
        if not is_safe:
            refusal = self.fallback.generate_refusal(language=lang, reason_code="PROMPT_INJECTION_BLOCKED")
            return {
                "status": "refused",
                "intent": "adversarial",
                "decision": "REFUSE",
                "text_response": refusal["spoken_text"],
                "spoken_text": refusal["spoken_text"],
                "citations": ["Kisan Call Centre Advisory Directorate"],
                "referrals": refusal.get("referrals", {}),
                "gate_signals": {"safety": 0.0, "reason": injection_reason}
            }

        # 2. Safety Guardrail: Banned / Hazardous Agricultural Chemicals
        chem_check = ChemicalSafetyGuardrail.analyze_chemical_request(query)
        if chem_check["is_dangerous"]:
            refusal = self.fallback.generate_refusal(language=lang, reason_code="BANNED_CHEMICAL_REFUSED")
            warning_msg = (
                f"सुरक्षा चेतावनी: यह रसायन भारत सरकार द्वारा प्रतिबंधित या अत्यधिक विषैला है। "
                f"फसल व स्वास्थ्य सुरक्षा के लिए प्रमाणित कृषि विशेषज्ञ या किसान कॉल सेंटर 1800-180-1551 से संपर्क करें।"
                if lang == "hi" else
                f"सुरक्षा इशारा: हे रसायन शासनाने प्रतिबंधित किंवा अत्यंत घातक घोषित केले आहे. "
                f"सुरक्षिततेसाठी कृषी तज्ज्ञ किंवा किसान कॉल सेंटर 1800-180-1551 वर संपर्क साधावा."
            )
            return {
                "status": "refused",
                "intent": "unsafe_chemical",
                "decision": "REFUSE",
                "text_response": warning_msg,
                "spoken_text": warning_msg,
                "citations": ["Central Insecticides Board & Registration Committee (CIBRC)"],
                "referrals": refusal.get("referrals", {}),
                "gate_signals": {"safety": 0.0, "reason": chem_check["reason"]}
            }

        # 3. Intent Classification & Entity Extraction
        intent, intent_conf = self.classifier.classify_intent(query)
        entities = self.extractor.extract_entities(query)
        crop = entities.get("crop")
        district = entities.get("district") or default_district

        # 4. Routing Logic

        # A. Mandi Market Prices
        if intent == "mandi_price":
            if not crop:
                prompt = self.CLARIFICATION_PROMPTS["mandi_crop_missing"][lang]
                return {
                    "status": "clarification_required",
                    "intent": "mandi_price",
                    "decision": "CLARIFY",
                    "missing_entity": "crop",
                    "text_response": prompt,
                    "spoken_text": prompt,
                    "citations": [MandiPriceTool.OFFICIAL_SOURCE]
                }

            mandi_res = self.mandi_tool.get_mandi_prices(commodity=crop, district=district)
            spoken_key = f"spoken_text_{lang}"
            text_response = (
                mandi_res.get(spoken_key) or
                mandi_res.get("spoken_text_en") or
                mandi_res.get("message") or
                "मंडी भाव की आधिकारिक जानकारी उपलब्ध नहीं हो सकी।"
            )

            gate_eval = self.confidence_gate.evaluate_gate(
                query=query,
                asr_confidence=asr_confidence,
                language=lang,
                intent="mandi_price",
                tool_status=mandi_res["status"]
            )

            final_decision = "REFUSE" if mandi_res["status"] == "not_found" else gate_eval["decision"]

            return {
                "status": mandi_res["status"],
                "intent": "mandi_price",
                "decision": final_decision,
                "entities": entities,
                "text_response": text_response,
                "spoken_text": text_response,
                "citations": [mandi_res.get("source", MandiPriceTool.OFFICIAL_SOURCE)],
                "tool_data": mandi_res,
                "gate_signals": gate_eval
            }

        # B. Live Weather Advisory
        elif intent == "weather":
            if not district:
                prompt = self.CLARIFICATION_PROMPTS["weather_location_missing"][lang]
                return {
                    "status": "clarification_required",
                    "intent": "weather",
                    "decision": "CLARIFY",
                    "missing_entity": "district",
                    "text_response": prompt,
                    "spoken_text": prompt,
                    "citations": [WeatherTool.OFFICIAL_SOURCE]
                }

            weather_res = self.weather_tool.get_weather(location_name=district)
            spoken_key = f"spoken_text_{lang}"
            text_response = (
                weather_res.get(spoken_key) or
                weather_res.get("spoken_text_en") or
                weather_res.get("message") or
                "हवामान माहिती उपलब्ध होऊ शकली नाही."
            )

            gate_eval = self.confidence_gate.evaluate_gate(
                query=query,
                asr_confidence=asr_confidence,
                language=lang,
                intent="weather",
                tool_status=weather_res["status"]
            )

            return {
                "status": weather_res["status"],
                "intent": "weather",
                "decision": gate_eval["decision"],
                "entities": entities,
                "text_response": text_response,
                "spoken_text": text_response,
                "citations": [weather_res.get("source", WeatherTool.OFFICIAL_SOURCE)],
                "tool_data": weather_res,
                "gate_signals": gate_eval
            }

        # C. Out-of-Scope Queries (Safe Refusal)
        elif intent == "out_of_scope":
            refusal_res = self.fallback.generate_refusal(language=lang, reason_code="OUT_OF_SCOPE")
            return {
                "status": "refused",
                "intent": "out_of_scope",
                "decision": "REFUSE",
                "entities": entities,
                "text_response": refusal_res["spoken_text"],
                "spoken_text": refusal_res["spoken_text"],
                "citations": ["Kisan Call Centre Advisory Directorate"],
                "referrals": refusal_res.get("referrals", {})
            }

        # D. Verified Agricultural Knowledge RAG (Crop Advice, Pests, Diseases, Schemes)
        else:
            rag_res = self.rag_service.query(
                question=query,
                language=lang,
                crop_filter=crop
            )

            # Evaluate Multi-Signal Confidence Gate
            gate_eval = self.confidence_gate.evaluate_gate(
                query=query,
                asr_confidence=asr_confidence,
                language=lang,
                intent=intent,
                intent_confidence=intent_conf,
                retrieval_results=rag_res.get("evidence_passages", [])
            )

            if gate_eval["decision"] == "REFUSE":
                refusal_res = self.fallback.generate_refusal(language=lang, reason_code=gate_eval["reason_code"])
                return {
                    "status": "refused",
                    "intent": intent,
                    "decision": "REFUSE",
                    "entities": entities,
                    "text_response": refusal_res["spoken_text"],
                    "spoken_text": refusal_res["spoken_text"],
                    "citations": ["Kisan Call Centre Advisory Directorate"],
                    "referrals": refusal_res.get("referrals", {}),
                    "gate_signals": gate_eval
                }

            spoken = rag_res.get("answer_text") or rag_res.get("spoken_text") or ""

            # Post-generation Chemical Safety Check: Verify dosages against retrieved chunks
            retrieved_contexts = [ep["text"] for ep in rag_res.get("evidence_passages", [])]
            verified_chem = ChemicalSafetyGuardrail.verify_and_safeguard_answer(
                answer_text=spoken,
                retrieved_contexts=retrieved_contexts,
                language=lang
            )
            final_text = verified_chem["safe_answer"]

            final_decision = "REFUSE" if rag_res["status"] == "refused" else gate_eval["decision"]

            return {
                "status": rag_res["status"],
                "intent": intent,
                "decision": final_decision,
                "entities": entities,
                "text_response": final_text,
                "spoken_text": final_text,
                "citations": rag_res.get("citations", []),
                "evidence_passages": rag_res.get("evidence_passages", []),
                "referrals": rag_res.get("referrals", {}),
                "gate_signals": gate_eval
            }
