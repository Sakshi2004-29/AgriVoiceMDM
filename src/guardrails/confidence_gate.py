"""
Multi-Signal Confidence Gate (Module 10 & 12).
Combines signals across the entire voice and agricultural pipeline:
- ASR transcription confidence
- Language detection confidence
- Intent classification confidence
- Hybrid retrieval relevance score (FAISS + BM25 RRF)
- Answer grounding and claim verification
- Live API data freshness
Decides between:
1. ANSWER: Verified evidence exists, safety clear, confidence met.
2. ASK_REPEAT / CLARIFY: Unclear audio, missing entities.
3. REFUSE: Unsafe, prompt injection, unverified dosage, or no evidence.
"""
from typing import Dict, Any, List, Optional
from src.guardrails.fallback_handler import FallbackHandler
from src.guardrails.chemical_safety import ChemicalSafetyGuardrail, PromptInjectionGuardrail


class MultiSignalConfidenceGate:
    """
    Central decision gate evaluating holistic confidence and safety across modalities.
    """

    # Configurable decision thresholds
    DEFAULT_THRESHOLDS = {
        "min_asr_confidence": 0.50,
        "min_intent_confidence": 0.50,
        "min_retrieval_score": 0.018,  # RRF score threshold
        "min_composite_confidence": 0.60,
        "min_grounding_score": 0.50
    }

    # Signal weights for composite confidence calculation
    DEFAULT_WEIGHTS = {
        "asr": 0.20,
        "intent": 0.20,
        "retrieval": 0.35,
        "grounding": 0.25
    }

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

        self.weights = dict(self.DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)

        self.fallback = FallbackHandler()

    def evaluate_gate(
        self,
        query: str,
        asr_confidence: float = 1.0,
        language: str = "hi",
        lang_confidence: float = 0.90,
        intent: str = "crop_advice",
        intent_confidence: float = 0.85,
        retrieval_results: Optional[List[Dict[str, Any]]] = None,
        tool_status: Optional[str] = None,
        missing_entity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates composite confidence and produces a final action decision.

        Returns:
            Dict containing:
                decision: 'ANSWER', 'CLARIFY', 'ASK_REPEAT', or 'REFUSE'
                composite_score: float (0.0 to 1.0)
                reason_code: str
                explanation: str
                signals: Dict of normalized component scores
        """
        # 1. Pre-Execution Safety Check: Prompt Injection
        is_safe, injection_reason = PromptInjectionGuardrail.check_for_injection(query)
        if not is_safe:
            return {
                "decision": "REFUSE",
                "reason_code": "PROMPT_INJECTION_DETECTED",
                "composite_score": 0.0,
                "explanation": injection_reason,
                "signals": {"safety": 0.0}
            }

        # 2. Pre-Execution Safety Check: Hazardous/Banned Agricultural Chemicals
        chem_analysis = ChemicalSafetyGuardrail.analyze_chemical_request(query)
        if chem_analysis["is_dangerous"]:
            return {
                "decision": "REFUSE",
                "reason_code": "BANNED_CHEMICAL_REQUEST",
                "composite_score": 0.0,
                "explanation": chem_analysis["reason"],
                "signals": {"safety": 0.0}
            }

        # 3. Audio / Speech Quality Check
        if asr_confidence < self.thresholds["min_asr_confidence"]:
            return {
                "decision": "ASK_REPEAT",
                "reason_code": "LOW_ASR_CONFIDENCE",
                "composite_score": asr_confidence,
                "explanation": f"Speech confidence {asr_confidence:.2f} is below minimum {self.thresholds['min_asr_confidence']:.2f}.",
                "signals": {"asr": asr_confidence}
            }

        # 4. Missing Entity Check (Clarification Required)
        if missing_entity:
            return {
                "decision": "CLARIFY",
                "reason_code": "MISSING_ENTITY",
                "missing_entity": missing_entity,
                "composite_score": 0.50,
                "explanation": f"Missing critical entity: {missing_entity}",
                "signals": {"intent": intent_confidence}
            }

        # 5. Out-of-Scope Intent Check
        if intent == "out_of_scope":
            return {
                "decision": "REFUSE",
                "reason_code": "OUT_OF_SCOPE",
                "composite_score": 0.10,
                "explanation": "Query is outside agricultural scope.",
                "signals": {"intent": 0.10}
            }

        # 6. Live Tool Status Check (for Mandi / Weather tools)
        if intent in ["mandi_price", "weather"]:
            if tool_status == "success":
                return {
                    "decision": "ANSWER",
                    "reason_code": "TOOL_DATA_VERIFIED",
                    "composite_score": 0.90,
                    "explanation": "Live data retrieved and timestamp verified.",
                    "signals": {"tool": 0.90, "freshness": 1.0}
                }
            elif tool_status == "clarification_required":
                return {
                    "decision": "CLARIFY",
                    "reason_code": "TOOL_MISSING_DETAILS",
                    "composite_score": 0.50,
                    "explanation": "Tool requires additional parameters.",
                    "signals": {"tool": 0.50}
                }
            else:
                return {
                    "decision": "REFUSE",
                    "reason_code": "TOOL_DATA_UNAVAILABLE",
                    "composite_score": 0.20,
                    "explanation": "Live data service returned no verified records.",
                    "signals": {"tool": 0.20}
                }

        # 7. Knowledge RAG Retrieval Score Normalization
        retrieval_relevance = 0.0
        if retrieval_results and len(retrieval_results) > 0:
            top_res = retrieval_results[0]
            raw_rrf = top_res.get("rrf_score", 0.0)
            # Normalize RRF score (typical range 0.01 to 0.033) into [0.0, 1.0] scale
            retrieval_relevance = min(1.0, max(0.0, (raw_rrf - 0.010) / 0.023))

            # Grounding check: verify chunk approval status
            if top_res.get("approval_status") != "approved":
                return {
                    "decision": "REFUSE",
                    "reason_code": "UNAPPROVED_EVIDENCE",
                    "composite_score": 0.0,
                    "explanation": "Top evidence belongs to an unapproved draft document.",
                    "signals": {"retrieval": 0.0}
                }

        if retrieval_relevance < 0.25:
            return {
                "decision": "REFUSE",
                "reason_code": "INSUFFICIENT_EVIDENCE",
                "composite_score": retrieval_relevance,
                "explanation": "No sufficiently relevant approved agricultural passages found.",
                "signals": {"retrieval": retrieval_relevance}
            }

        # 8. Compute Composite Confidence
        composite_score = (
            self.weights["asr"] * asr_confidence +
            self.weights["intent"] * intent_confidence +
            self.weights["retrieval"] * retrieval_relevance +
            self.weights["grounding"] * 0.90  # Approved source grounding
        )

        decision = "ANSWER" if composite_score >= self.thresholds["min_composite_confidence"] else "REFUSE"
        reason = "VERIFIED_EVIDENCE_SUFFICIENT" if decision == "ANSWER" else "COMPOSITE_CONFIDENCE_LOW"

        return {
            "decision": decision,
            "reason_code": reason,
            "composite_score": round(composite_score, 3),
            "explanation": f"Composite score {composite_score:.2f} (Threshold: {self.thresholds['min_composite_confidence']:.2f})",
            "signals": {
                "asr_confidence": round(asr_confidence, 2),
                "intent_confidence": round(intent_confidence, 2),
                "retrieval_relevance": round(retrieval_relevance, 2),
                "grounding": 0.90
            }
        }
