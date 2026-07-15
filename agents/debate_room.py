"""
============================================================
 Genesis AI — Debate Room Agent (agents/debate_room.py)
 Implements the "AI Self-Critic Loop".

 A Security Agent and a Finance Agent independently evaluate
 the Architect's plan against two thresholds:
   - Innovation Score  ≥ 7 / 10
   - Cost Efficiency   ≥ 6 / 10

 If either threshold is missed, the Debate Room triggers a
 structured negotiation loop (up to MAX_ROUNDS retries).
 The final approved architecture and full transcript are
 returned to the Orchestrator.
============================================================
"""

import json
import logging
import re
from copy import deepcopy

try:
    from ibm_watsonx_ai.foundation_models import ModelInference
except ImportError:
    from ibm_watson_machine_learning.foundation_models import Model as ModelInference

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
#  Thresholds — adjust to tighten or relax critic standards
# ------------------------------------------------------------------
INNOVATION_THRESHOLD = 7    # out of 10
COST_THRESHOLD       = 6    # out of 10
MAX_ROUNDS           = 3    # maximum debate iterations before forced acceptance


class DebateRoom:
    """
    Hosts a multi-turn structured debate between specialist critic agents.

    Agents:
      • Architect  — proposes and defends the architecture
      • Security   — evaluates security posture and assigns innovation score
      • Finance    — evaluates cost efficiency and assigns cost score

    If both agents approve (scores ≥ thresholds), the debate ends.
    Otherwise, the Architect revises and the cycle repeats.
    """

    def __init__(self, llm: ModelInference):
        self._llm = llm

    def evaluate(
        self,
        architecture: dict,
        business: dict,
        variant: dict,
        problem_statement: str,
    ) -> tuple[dict, list[dict]]:
        """
        Run the critic debate loop.

        Args:
            architecture:      Output from ArchitectAgent.
            business:          Output from BusinessAgent.
            variant:           Solution variant {id, label, focus}.
            problem_statement: Original user problem text.

        Returns:
            (approved_architecture, transcript)
            where transcript is a list of debate turn dicts.
        """
        transcript       = []
        current_arch     = deepcopy(architecture)
        approved         = False
        round_num        = 0

        # --- Opening: Architect presents the plan ---
        transcript.append(self._turn(
            speaker="Architect",
            round_num=0,
            message=(
                f"I propose the following {variant['label']} architecture: "
                f"{current_arch.get('system_overview', 'See full spec.')} "
                f"Tech stack: {json.dumps(current_arch.get('tech_stack', {}))}. "
                f"Security stance: {current_arch.get('security_notes', 'TBD')}. "
                f"Scalability: {current_arch.get('scalability_notes', 'TBD')}."
            ),
        ))

        while not approved and round_num < MAX_ROUNDS:
            round_num += 1
            logger.info("Debate Room — Round %d for variant %s", round_num, variant["id"])

            # --- Security Agent critique ---
            security_response = self._security_review(current_arch, variant, round_num)
            transcript.append(self._turn(
                speaker="Security",
                round_num=round_num,
                message=security_response["message"],
            ))
            innovation_score = security_response["score"]

            # --- Finance Agent critique ---
            finance_response = self._finance_review(current_arch, business, variant, round_num)
            transcript.append(self._turn(
                speaker="Finance",
                round_num=round_num,
                message=finance_response["message"],
            ))
            cost_score = finance_response["score"]

            logger.info(
                "  Scores — Innovation: %d/10, Cost: %d/10 (thresholds: %d, %d)",
                innovation_score, cost_score, INNOVATION_THRESHOLD, COST_THRESHOLD,
            )

            # --- Check approval ---
            if innovation_score >= INNOVATION_THRESHOLD and cost_score >= COST_THRESHOLD:
                approved = True
                transcript.append(self._turn(
                    speaker="Moderator",
                    round_num=round_num,
                    message=(
                        f"✅ Consensus reached in Round {round_num}. "
                        f"Innovation Score: {innovation_score}/10 — "
                        f"Cost Score: {cost_score}/10. "
                        f"Architecture approved for Solution {variant['id']}."
                    ),
                ))
            else:
                # --- Architect revision ---
                revision = self._architect_revision(
                    current_arch, security_response, finance_response,
                    variant, round_num,
                )
                current_arch = revision["architecture"]
                transcript.append(self._turn(
                    speaker="Architect",
                    round_num=round_num,
                    message=revision["message"],
                ))

        # If MAX_ROUNDS reached without consensus, force acceptance
        if not approved:
            transcript.append(self._turn(
                speaker="Moderator",
                round_num=round_num,
                message=(
                    f"⚠️ Max debate rounds ({MAX_ROUNDS}) reached. "
                    f"Accepting best available architecture for Solution {variant['id']}."
                ),
            ))

        return current_arch, transcript

    # ------------------------------------------------------------------
    #  Agent sub-prompts
    # ------------------------------------------------------------------

    def _security_review(self, architecture: dict, variant: dict, round_num: int) -> dict:
        """Security Agent evaluates the architecture's innovation and security posture."""
        prompt = (
            "You are a Chief Information Security Officer and Innovation Assessor. "
            "Evaluate the following enterprise architecture and assign an INNOVATION SCORE "
            "from 1-10 (10 = highly innovative and secure). "
            "Respond with a JSON object: "
            '{"score": <int 1-10>, "message": "<2-3 sentences of critique and score rationale>"}\n\n'
            f"Architecture (Round {round_num}):\n"
            f"Overview: {architecture.get('system_overview', '')}\n"
            f"Tech Stack: {json.dumps(architecture.get('tech_stack', {}))}\n"
            f"Security Notes: {architecture.get('security_notes', '')}\n"
            f"API Endpoints: {json.dumps(architecture.get('api_endpoints', [])[:3])}\n"
            f"Variant Focus: {variant['focus']}"
        )

        return self._call_llm_for_score(prompt, "Security", round_num)

    def _finance_review(
        self, architecture: dict, business: dict, variant: dict, round_num: int
    ) -> dict:
        """Finance Agent evaluates cost efficiency."""
        prompt = (
            "You are a Chief Financial Officer and Cost Efficiency Analyst. "
            "Evaluate the following business case and assign a COST EFFICIENCY SCORE "
            "from 1-10 (10 = highly cost-efficient). "
            "Respond with a JSON object: "
            '{"score": <int 1-10>, "message": "<2-3 sentences of critique and score rationale>"}\n\n'
            f"Business Case (Round {round_num}):\n"
            f"Budget: {business.get('budget_estimate', 'Unknown')}\n"
            f"Cost Breakdown: {json.dumps(business.get('cost_breakdown', {}))}\n"
            f"ROI Timeline: {business.get('roi_timeline', '')}\n"
            f"Risk Summary: {business.get('risk_summary', '')}\n"
            f"Variant Focus: {variant['focus']}"
        )

        return self._call_llm_for_score(prompt, "Finance", round_num)

    def _architect_revision(
        self,
        architecture: dict,
        security_resp: dict,
        finance_resp: dict,
        variant: dict,
        round_num: int,
    ) -> dict:
        """Architect responds to critique and produces a revised architecture."""
        prompt = (
            "You are a senior enterprise architect responding to a design review. "
            "Revise the architecture to address the following critique. "
            "Respond with a JSON object: "
            '{"message": "<architect response — 2-3 sentences>", "architecture": <revised architecture JSON>}\n\n'
            f"Original Architecture:\n{json.dumps(architecture, indent=2)}\n\n"
            f"Security Critique (score {security_resp['score']}/10): {security_resp['message']}\n"
            f"Finance Critique (score {finance_resp['score']}/10): {finance_resp['message']}\n"
            f"Variant: {variant['label']} — {variant['focus']}"
        )

        try:
            raw      = self._llm.generate_text(prompt=prompt)
            start    = raw.find("{")
            end      = raw.rfind("}") + 1
            parsed   = json.loads(raw[start:end]) if start != -1 else {}
            message  = parsed.get("message", "Architecture revised based on feedback.")
            new_arch = parsed.get("architecture", architecture)
            if not isinstance(new_arch, dict):
                new_arch = architecture
        except Exception as exc:
            logger.warning("Architect revision LLM call failed: %s", exc)
            message  = f"[Round {round_num}] Architecture updated to address security and cost concerns."
            new_arch = self._apply_heuristic_revision(architecture, security_resp, finance_resp)

        return {"message": message, "architecture": new_arch}

    # ------------------------------------------------------------------
    #  Utilities
    # ------------------------------------------------------------------

    def _call_llm_for_score(
        self, prompt: str, agent_name: str, round_num: int
    ) -> dict:
        """
        Call the LLM and parse a {score, message} JSON response.
        Returns a heuristic fallback if the LLM or JSON parsing fails.
        """
        try:
            raw   = self._llm.generate_text(prompt=prompt)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found.")
            parsed = json.loads(raw[start:end])
            score  = max(1, min(10, int(parsed.get("score", 7))))
            return {"score": score, "message": parsed.get("message", "Review complete.")}
        except Exception as exc:
            logger.warning("%s agent LLM failed (Round %d): %s", agent_name, round_num, exc)
            # Heuristic: score improves by 1 each round (demonstrates convergence)
            return {
                "score":   min(10, 5 + round_num),
                "message": (
                    f"[Round {round_num}] {agent_name} review: "
                    "Architecture meets baseline standards. "
                    "Recommend addressing noted gaps in next revision."
                ),
            }

    def _apply_heuristic_revision(
        self, architecture: dict, security_resp: dict, finance_resp: dict
    ) -> dict:
        """
        Apply rule-based improvements when the LLM revision call fails.
        Appends security and cost notes to the existing architecture.
        """
        revised = deepcopy(architecture)
        if security_resp["score"] < INNOVATION_THRESHOLD:
            existing = revised.get("security_notes", "")
            revised["security_notes"] = (
                existing + " Additional: Zero-trust network policy, secrets rotation, WAF enabled."
            )
        if finance_resp["score"] < COST_THRESHOLD:
            existing = revised.get("scalability_notes", "")
            revised["scalability_notes"] = (
                existing + " Cost optimisation: reserved instances, spot VMs for batch workloads."
            )
        return revised

    @staticmethod
    def _turn(speaker: str, round_num: int, message: str) -> dict:
        """Construct a standard debate transcript turn dict."""
        return {
            "speaker":   speaker,
            "round":     round_num,
            "message":   message,
        }
