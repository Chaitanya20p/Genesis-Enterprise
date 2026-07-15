"""
============================================================
 Genesis AI — Architect Agent (agents/architect_agent.py)
 Generates the System Architecture, Tech Stack, and API
 blueprint for a given solution variant using IBM Granite.
============================================================
"""

import json
import logging
import re

try:
    from ibm_watsonx_ai.foundation_models import ModelInference
except ImportError:
    from ibm_watson_machine_learning.foundation_models import Model as ModelInference

logger = logging.getLogger(__name__)


class ArchitectAgent:
    """
    Calls IBM Granite to produce a structured architecture plan.

    Output schema (returned as a Python dict):
      {
        "system_overview":   str   — 2-3 sentence summary
        "components":        list  — [{name, description, technology}]
        "tech_stack":        dict  — {frontend, backend, database, infra, ai_ml}
        "api_endpoints":     list  — [{method, path, description}]
        "data_flow":         str   — description of data movement
        "security_notes":    str   — security considerations
        "scalability_notes": str   — how the system scales
      }
    """

    SYSTEM_PROMPT = (
        "You are a senior enterprise solutions architect. "
        "Your response must be a single valid JSON object. "
        "Start your response with { and end with }. "
        "Do not include any explanation, markdown, or text outside the JSON."
    )

    def __init__(self, llm: ModelInference):
        self._llm = llm

    def generate(self, enriched_prompt: str, variant: dict) -> dict:
        """
        Generate an architecture plan for the given problem and variant.

        Args:
            enriched_prompt: Combined problem + RAG context string.
            variant:         Solution variant dict {id, label, focus}.

        Returns:
            Architecture dict (parsed from Granite's JSON response).
            Falls back to a structured error dict if parsing fails.
        """
        prompt = self._build_prompt(enriched_prompt, variant)
        logger.debug("ArchitectAgent prompt length: %d chars", len(prompt))

        try:
            response = self._llm.generate_text(prompt=prompt)
            return self._parse_response(response, variant)
        except Exception as exc:
            logger.error("ArchitectAgent LLM call failed: %s", exc)
            return self._fallback_architecture(variant, str(exc))

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, enriched_prompt: str, variant: dict) -> str:
        schema = json.dumps(
            {
                "system_overview":   "<2-3 sentence description>",
                "components": [{"name": "<str>", "description": "<str>", "technology": "<str>"}],
                "tech_stack":        {"frontend": "<str>", "backend": "<str>", "database": "<str>", "infra": "<str>", "ai_ml": "<str>"},
                "api_endpoints":     [{"method": "GET|POST|PUT|DELETE", "path": "/api/...", "description": "<str>"}],
                "data_flow":         "<str>",
                "security_notes":    "<str>",
                "scalability_notes": "<str>",
            },
            indent=2,
        )

        return (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Problem context:\n{enriched_prompt}\n\n"
            f"Solution variant: {variant['label']} — {variant['focus']}\n\n"
            f"Produce a complete enterprise system architecture JSON matching this schema:\n"
            f"{schema}"
        )

    def _parse_response(self, raw: str, variant: dict) -> dict:
        """
        Extract the first valid JSON object from the LLM response string.
        Granite occasionally wraps output in prose — strip it defensively.
        """
        # Find the first '{' and last '}'
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in LLM response.")

        json_str = raw[start:end]
        parsed   = json.loads(json_str)

        # Enforce required keys — inject defaults for any that are missing
        defaults = {
            "system_overview":   f"{variant['label']} architecture overview.",
            "components":        [],
            "tech_stack":        {},
            "api_endpoints":     [],
            "data_flow":         "Not specified.",
            "security_notes":    "Standard OWASP practices apply.",
            "scalability_notes": "Horizontal scaling supported.",
        }
        for key, default in defaults.items():
            parsed.setdefault(key, default)

        return parsed

    def _fallback_architecture(self, variant: dict, error: str) -> dict:
        """Return a minimal valid architecture dict when the LLM call fails."""
        return {
            "system_overview":   f"[LLM unavailable] {variant['label']} solution.",
            "components":        [{"name": "Core Service", "description": "Primary application service", "technology": "Python/Flask"}],
            "tech_stack":        {"frontend": "React", "backend": "Flask", "database": "PostgreSQL", "infra": "Kubernetes", "ai_ml": "IBM Watsonx"},
            "api_endpoints":     [{"method": "POST", "path": "/api/infer", "description": "AI inference endpoint"}],
            "data_flow":         "Client → API Gateway → Inference Service → Database",
            "security_notes":    "TLS 1.3, OAuth 2.0, field-level encryption.",
            "scalability_notes": "Horizontal pod autoscaling on Kubernetes.",
            "_error":            error,
        }
