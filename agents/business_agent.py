"""
============================================================
 Genesis AI — Business Agent (agents/business_agent.py)
 Generates the financial plan, Business Model Canvas, and
 relevant government funding schemes for a solution variant.
============================================================
"""

import json
import logging

try:
    from ibm_watsonx_ai.foundation_models import ModelInference
except ImportError:
    from ibm_watson_machine_learning.foundation_models import Model as ModelInference

logger = logging.getLogger(__name__)


class BusinessAgent:
    """
    Calls IBM Granite to produce a structured business plan.

    Output schema (returned as a Python dict):
      {
        "budget_estimate":  str   — e.g. "$120,000 over 18 months"
        "cost_breakdown":   dict  — {phase: amount}
        "bmc": {
            "value_proposition": str,
            "customer_segments": list[str],
            "revenue_streams":   list[str],
            "key_resources":     list[str],
            "key_activities":    list[str],
            "cost_structure":    str,
            "channels":          list[str],
            "partnerships":      list[str],
            "unfair_advantage":  str
        },
        "government_schemes": list[{name, eligibility, funding_amount, url}],
        "roi_timeline":       str,
        "risk_summary":       str
      }
    """

    SYSTEM_PROMPT = (
        "You are a senior business strategist and financial analyst. "
        "Your response must be a single valid JSON object. "
        "Start your response with { and end with }. "
        "Do not include any explanation, markdown, or text outside the JSON."
    )

    def __init__(self, llm: ModelInference):
        self._llm = llm

    def generate(
        self, enriched_prompt: str, variant: dict, architecture: dict
    ) -> dict:
        """
        Generate a business plan aligned to the architecture and variant.

        Args:
            enriched_prompt: Combined problem + RAG context string.
            variant:         Solution variant dict {id, label, focus}.
            architecture:    Output from ArchitectAgent.generate().

        Returns:
            Business plan dict.
        """
        prompt = self._build_prompt(enriched_prompt, variant, architecture)
        logger.debug("BusinessAgent prompt length: %d chars", len(prompt))

        try:
            response = self._llm.generate_text(prompt=prompt)
            return self._parse_response(response, variant)
        except Exception as exc:
            logger.error("BusinessAgent LLM call failed: %s", exc)
            return self._fallback_business(variant, str(exc))

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self, enriched_prompt: str, variant: dict, architecture: dict
    ) -> str:
        arch_summary = json.dumps(
            {
                "system_overview": architecture.get("system_overview", ""),
                "tech_stack":      architecture.get("tech_stack", {}),
            }
        )

        schema = json.dumps(
            {
                "budget_estimate":  "<total cost string>",
                "cost_breakdown":   {"<phase>": "<amount>"},
                "bmc": {
                    "value_proposition": "<str>",
                    "customer_segments": ["<str>"],
                    "revenue_streams":   ["<str>"],
                    "key_resources":     ["<str>"],
                    "key_activities":    ["<str>"],
                    "cost_structure":    "<str>",
                    "channels":          ["<str>"],
                    "partnerships":      ["<str>"],
                    "unfair_advantage":  "<str>",
                },
                "government_schemes": [
                    {"name": "<str>", "eligibility": "<str>", "funding_amount": "<str>", "url": "<str>"}
                ],
                "roi_timeline": "<str>",
                "risk_summary": "<str>",
            },
            indent=2,
        )

        return (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Problem context:\n{enriched_prompt}\n\n"
            f"Solution variant: {variant['label']} — {variant['focus']}\n\n"
            f"Architecture overview:\n{arch_summary}\n\n"
            f"Produce a complete business plan JSON matching this schema:\n{schema}"
        )

    def _parse_response(self, raw: str, variant: dict) -> dict:
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object in LLM response.")

        parsed = json.loads(raw[start:end])

        defaults = {
            "budget_estimate":  "Estimate not available.",
            "cost_breakdown":   {},
            "bmc":              {},
            "government_schemes": [],
            "roi_timeline":     "18-24 months.",
            "risk_summary":     "Moderate risk profile.",
        }
        for key, default in defaults.items():
            parsed.setdefault(key, default)

        return parsed

    def _fallback_business(self, variant: dict, error: str) -> dict:
        return {
            "budget_estimate":    "$80,000 – $150,000",
            "cost_breakdown":     {"Phase 1 – Discovery": "$15k", "Phase 2 – Build": "$80k", "Phase 3 – Launch": "$30k"},
            "bmc": {
                "value_proposition": f"{variant['label']} AI-powered platform",
                "customer_segments": ["Enterprise", "SMB", "Government"],
                "revenue_streams":   ["SaaS Subscription", "Professional Services"],
                "key_resources":     ["Engineering Team", "Cloud Infrastructure"],
                "key_activities":    ["Product Development", "Customer Onboarding"],
                "cost_structure":    "Cloud hosting + engineering salaries",
                "channels":          ["Direct Sales", "Partner Network"],
                "partnerships":      ["IBM", "AWS", "System Integrators"],
                "unfair_advantage":  "Proprietary AI models + deep domain expertise",
            },
            "government_schemes": [
                {
                    "name":           "SBIR/STTR (USA)",
                    "eligibility":    "US small businesses engaged in R&D",
                    "funding_amount": "Up to $2M",
                    "url":            "https://www.sbir.gov",
                },
            ],
            "roi_timeline": "Break-even at month 18; 3× ROI by month 36.",
            "risk_summary": "Key risks: talent acquisition, regulatory compliance, market adoption.",
            "_error":        error,
        }
