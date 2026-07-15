"""
============================================================
 Genesis AI — Orchestrator Agent (agents/orchestrator.py)
 The central "brain" of the multi-agent pipeline.

 Responsibilities:
   1. Accept the user's problem statement.
   2. Optionally enrich the context with RAG research.
   3. Fan out to the Architect and Business agents in parallel.
   4. Route all outputs through the Debate Room critic loop.
   5. Return exactly THREE distinct solutions:
        A) Low Cost   B) High Performance   C) Eco-Friendly
============================================================
"""

import os
import json
import logging
from typing import Optional

# ---------------------------------------------------------------------------
# IBM SDK compatibility shim.
# ibm-watsonx-ai >= 1.x (Python >=3.10) uses ibm_watsonx_ai.*
# ibm-watsonx-ai == 0.0.5 (Python 3.9)  wraps ibm_watson_machine_learning.*
# ---------------------------------------------------------------------------
try:
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    _SDK_VERSION = "new"
except ImportError:
    _SDK_VERSION = "rest"   # Fall back to direct REST API — no SDK version lock-in

    # Stub GenParams so _build_watsonx_client can reference the same keys
    class GenParams:
        MAX_NEW_TOKENS      = "max_new_tokens"
        TEMPERATURE         = "temperature"
        TOP_P               = "top_p"
        REPETITION_PENALTY  = "repetition_penalty"


class _LegacyModelAdapter:
    """
    Direct REST adapter for IBM Watsonx.ai inference.
    Bypasses ibm-watson-machine-learning SDK URL validation issues
    by calling the inference REST API directly via requests + IAM token.

    Works with any region (us-south, eu-de, au-syd, etc.) and
    any Python version.
    """

    IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"

    def __init__(self, api_key: str, project_id: str, url: str, model_id: str, params: dict):
        self._api_key    = api_key
        self._project_id = project_id
        self._base_url   = url.rstrip("/")
        self._model_id   = model_id
        self._params     = params
        self._token      = None
        self._token_expiry = 0

    def _get_iam_token(self) -> str:
        """Fetch a fresh IAM bearer token, caching it until expiry."""
        import time
        if self._token and time.time() < self._token_expiry - 30:
            return self._token

        import requests as _requests
        resp = _requests.post(
            self.IAM_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type":    "urn:ibm:params:oauth:grant-type:apikey",
                "apikey":        self._api_key,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token        = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def generate_text(self, prompt: str) -> str:
        """Call the Watsonx.ai text generation REST endpoint directly."""
        import requests as _requests

        token    = self._get_iam_token()
        endpoint = (
            f"{self._base_url}/ml/v1/text/generation"
            f"?version=2023-05-29"
        )
        payload = {
            "model_id":   self._model_id,
            "project_id": self._project_id,
            "input":      prompt,
            "parameters": {
                "max_new_tokens":      self._params.get("max_new_tokens", 1024),
                "temperature":         self._params.get("temperature", 0.7),
                "top_p":               self._params.get("top_p", 0.9),
                "repetition_penalty":  self._params.get("repetition_penalty", 1.1),
            },
        }
        resp = _requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["results"][0]["generated_text"]
        except (KeyError, IndexError, TypeError):
            return str(data)


logger = logging.getLogger(__name__)

from agents.rag_researcher  import RAGResearcher
from agents.architect_agent import ArchitectAgent
from agents.business_agent  import BusinessAgent
from agents.debate_room     import DebateRoom


# ---------------------------------------------------------------------------
#  Helper — build authenticated Watsonx.ai model inference client
# ---------------------------------------------------------------------------

def _build_watsonx_client(model_id: str = "ibm/granite-8b-code-instruct"):
    """
    Construct a Watsonx.ai model inference client using credentials
    pulled from environment variables.

    Supports both SDK generations:
      - ibm-watsonx-ai >= 1.x  (Python >=3.10) → returns ModelInference
      - ibm-watsonx-ai == 0.0.5 (Python 3.9)   → returns ibm_watson_machine_learning.Model

    Raises EnvironmentError when any required credential is missing.
    """
    api_key    = os.environ.get("IBM_CLOUD_API_KEY")
    project_id = os.environ.get("PROJECT_ID")
    url        = os.environ.get("IBM_CLOUD_URL", "https://us-south.ml.cloud.ibm.com")

    if not api_key or not project_id:
        raise EnvironmentError(
            "IBM_CLOUD_API_KEY and PROJECT_ID must be set in your .env file."
        )

    params = {
        GenParams.MAX_NEW_TOKENS: 1024,
        GenParams.TEMPERATURE:    0.7,
        GenParams.TOP_P:          0.9,
        GenParams.REPETITION_PENALTY: 1.1,
    }

    if _SDK_VERSION == "new":
        # Modern SDK path (Python >=3.10)
        credentials = Credentials(url=url, api_key=api_key)
        return ModelInference(
            model_id=model_id,
            credentials=credentials,
            project_id=project_id,
            params=params,
        )
    else:
        # REST adapter path — works on Python 3.9, any region, no SDK lock-in
        return _LegacyModelAdapter(
            api_key=api_key,
            project_id=project_id,
            url=url,
            model_id=model_id,
            params={
                "max_new_tokens":     params[GenParams.MAX_NEW_TOKENS],
                "temperature":        params[GenParams.TEMPERATURE],
                "top_p":              params[GenParams.TOP_P],
                "repetition_penalty": params[GenParams.REPETITION_PENALTY],
            },
        )


# ---------------------------------------------------------------------------
#  Orchestrator Class
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Coordinates the full Genesis AI multi-agent workflow.

    Workflow:
        User problem
            ↓
        RAGResearcher   → context snippets
            ↓
        ArchitectAgent  → architecture plan per solution variant
            ↓
        BusinessAgent   → budget / BMC / schemes per variant
            ↓
        DebateRoom      → critic loop (Security + Finance agents)
            ↓
        Final JSON with 3 validated solutions + debate transcript
    """

    SOLUTION_VARIANTS = [
        {
            "id":    "A",
            "label": "Low Cost",
            "focus": (
                "Minimise total cost of ownership. Prefer open-source tooling, "
                "shared cloud resources, and phased delivery milestones."
            ),
        },
        {
            "id":    "B",
            "label": "High Performance",
            "focus": (
                "Maximise throughput and reliability. Use managed cloud services, "
                "dedicated compute, auto-scaling, and enterprise SLAs."
            ),
        },
        {
            "id":    "C",
            "label": "Eco-Friendly",
            "focus": (
                "Minimise carbon footprint. Prefer green cloud regions, serverless "
                "architectures, energy-efficient hardware, and sustainability reporting."
            ),
        },
    ]

    def __init__(self):
        self.llm         = _build_watsonx_client()
        self.rag         = RAGResearcher()
        self.architect   = ArchitectAgent(self.llm)
        self.business    = BusinessAgent(self.llm)
        self.debate_room = DebateRoom(self.llm)

    # ------------------------------------------------------------------
    #  Public entry point
    # ------------------------------------------------------------------

    def orchestrate(
        self,
        problem_statement: str,
        project_title: str = "Untitled Project",
        rag_query: Optional[str] = None,
    ) -> dict:
        """
        Run the full multi-agent pipeline.

        Args:
            problem_statement: Free-text description of the innovation challenge.
            project_title:     Human-readable name for this project.
            rag_query:         Optional override query for ChromaDB retrieval;
                               defaults to the first 120 chars of problem_statement.

        Returns:
            A dict with keys:
              - solutions:        list of 3 solution dicts (A, B, C)
              - debate_transcript: list of debate turn dicts
              - rag_context:       snippets retrieved from ChromaDB
              - scores:           radar-chart data for Chart.js
        """
        logger.info("Orchestrator starting for project: '%s'", project_title)

        # Step 1 — Knowledge enrichment via RAG
        rag_context = self._fetch_rag_context(
            rag_query or problem_statement[:120]
        )

        solutions        = []
        debate_transcript = []

        # Step 2 — For each solution variant, run the full sub-pipeline
        for variant in self.SOLUTION_VARIANTS:
            logger.info("Processing solution variant %s: %s", variant["id"], variant["label"])

            enriched_prompt = self._build_enriched_prompt(
                problem_statement, variant, rag_context
            )

            # Sub-step 2a: Architecture
            architecture = self.architect.generate(enriched_prompt, variant)

            # Sub-step 2b: Business plan
            business = self.business.generate(enriched_prompt, variant, architecture)

            # Sub-step 2c: Debate Room — critics review and possibly retry
            debated_architecture, turns = self.debate_room.evaluate(
                architecture, business, variant, problem_statement
            )
            debate_transcript.extend(turns)

            # Compute innovation scores for radar chart
            scores = self._compute_scores(debated_architecture, business, variant)

            solutions.append({
                "id":           variant["id"],
                "label":        variant["label"],
                "architecture": debated_architecture,
                "business":     business,
                "scores":       scores,
            })

        logger.info("Orchestration complete — %d solutions generated.", len(solutions))

        return {
            "project_title":    project_title,
            "solutions":        solutions,
            "debate_transcript": debate_transcript,
            "rag_context":      rag_context,
            "scores":           self._aggregate_radar_data(solutions),
        }

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _fetch_rag_context(self, query: str) -> list[dict]:
        """
        Query ChromaDB for relevant document snippets.
        Returns an empty list gracefully when the DB has no documents yet.
        """
        try:
            return self.rag.query(query, n_results=5)
        except Exception as exc:
            logger.warning("RAG retrieval skipped — %s", exc)
            return []

    def _build_enriched_prompt(
        self, problem: str, variant: dict, rag_context: list[dict]
    ) -> str:
        """Combine the user problem, solution focus, and RAG snippets into one prompt."""
        context_block = ""
        if rag_context:
            snippets = "\n".join(
                f"[Doc {i+1}] {item.get('text','')[:400]}"
                for i, item in enumerate(rag_context)
            )
            context_block = f"\n\nRelevant knowledge from internal documents:\n{snippets}"

        return (
            f"Project Challenge: {problem}\n"
            f"Solution Focus ({variant['label']}): {variant['focus']}"
            f"{context_block}"
        )

    def _compute_scores(
        self, architecture: dict, business: dict, variant: dict
    ) -> dict:
        """
        Derive normalised radar-chart scores (0-10) for four dimensions.
        Scores are partially derived from agent outputs and partially
        from heuristic adjustments based on the variant type.
        """
        base = {
            "A": {"cost": 9, "feasibility": 7, "sustainability": 5, "scalability": 5},
            "B": {"cost": 4, "feasibility": 8, "sustainability": 5, "scalability": 10},
            "C": {"cost": 6, "feasibility": 6, "sustainability": 10, "scalability": 7},
        }.get(variant["id"], {"cost": 5, "feasibility": 5, "sustainability": 5, "scalability": 5})

        # Apply a small modifier from the business agent's budget estimate
        budget_str = str(business.get("budget_estimate", "0"))
        digits     = "".join(filter(str.isdigit, budget_str))
        budget_val = int(digits[:6]) if digits else 50000
        cost_mod   = max(-2, min(2, (100000 - budget_val) // 25000))

        return {
            "cost":           min(10, base["cost"] + cost_mod),
            "feasibility":    base["feasibility"],
            "sustainability": base["sustainability"],
            "scalability":    base["scalability"],
        }

    def _aggregate_radar_data(self, solutions: list[dict]) -> dict:
        """Format all solution scores for direct Chart.js radar consumption."""
        labels     = ["Cost Efficiency", "Feasibility", "Sustainability", "Scalability"]
        datasets   = []
        colours    = ["#3b82f6", "#a855f7", "#22c55e"]

        for sol, colour in zip(solutions, colours):
            s = sol["scores"]
            datasets.append({
                "label": f"Solution {sol['id']}: {sol['label']}",
                "data":  [s["cost"], s["feasibility"], s["sustainability"], s["scalability"]],
                "borderColor": colour,
                "backgroundColor": colour + "33",  # 20% opacity fill
            })

        return {"labels": labels, "datasets": datasets}
