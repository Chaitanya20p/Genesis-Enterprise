"""
============================================================
 Genesis AI — Export API Blueprint (routes/export_api.py)
 Generates a professional PDF report from a project's
 orchestration results using pdfkit + wkhtmltopdf.

 Endpoints:
   POST /api/export_pdf   → Returns a downloadable PDF report
============================================================
"""

import os
import json
import logging
import tempfile
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file, current_app

logger = logging.getLogger(__name__)

export_bp = Blueprint("export", __name__)


# ==================================================================
#  POST /api/export_pdf
# ==================================================================

@export_bp.route("/export_pdf", methods=["POST"])
def export_pdf():
    """
    Generate a multi-section PDF report for a completed project.

    Request Body (JSON):
        { "project_id": <int> }

    Response:
        Binary PDF file download (application/pdf).

    HTTP Codes:
        200 — PDF returned as download
        400 — Missing project_id
        404 — Project not found
        500 — PDF generation error
    """
    data = request.get_json(silent=True)

    if not data or "project_id" not in data:
        return jsonify({"error": "Field 'project_id' is required."}), 400

    project_id = int(data["project_id"])
    project    = db.session.get(Project, project_id)

    if not project:
        return jsonify({"error": f"Project {project_id} not found."}), 404

    try:
        result_data = json.loads(project.result_json) if project.result_json else {}
        html_report = _build_html_report(project, result_data)

        # Write HTML to a temp file, then convert to PDF via pdfkit
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, dir=tempfile.gettempdir()
        ) as tmp_pdf:
            pdf_path = tmp_pdf.name

        import pdfkit

        # Read wkhtmltopdf binary path from environment
        wk_path = os.environ.get("WKHTMLTOPDF_PATH", "/usr/bin/wkhtmltopdf")
        config  = pdfkit.configuration(wkhtmltopdf=wk_path)
        options = {
            "page-size":        "A4",
            "margin-top":       "20mm",
            "margin-right":     "20mm",
            "margin-bottom":    "20mm",
            "margin-left":      "20mm",
            "encoding":         "UTF-8",
            "enable-local-file-access": "",
        }

        pdfkit.from_string(html_report, pdf_path, configuration=config, options=options)

        safe_title = "".join(c for c in project.title if c.isalnum() or c in " _-")[:40]
        filename   = f"Genesis_Report_{safe_title}_{project.id}.pdf"

        logger.info("PDF report generated: %s (%s)", filename, pdf_path)

        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as exc:
        logger.exception("PDF generation failed for project %d.", project_id)
        return jsonify({"error": f"PDF generation failed: {str(exc)}"}), 500


# ==================================================================
#  HTML Report Builder
# ==================================================================

def _build_html_report(project: "Project", result: dict) -> str:
    """
    Render a full-page HTML document suitable for PDF export.
    Uses inline styles only — no external assets required.
    """
    solutions = result.get("solutions", [])
    debate    = result.get("debate_transcript", [])
    now       = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    solutions_html = ""
    for sol in solutions:
        arch  = sol.get("architecture", {})
        biz   = sol.get("business", {})
        score = sol.get("scores", {})
        bmc   = biz.get("bmc", {})

        # Tech stack table rows
        stack_rows = "".join(
            f"<tr><td><b>{k.title()}</b></td><td>{v}</td></tr>"
            for k, v in arch.get("tech_stack", {}).items()
        )

        # BMC rows
        bmc_rows = "".join(
            f"<tr><td><b>{k.replace('_', ' ').title()}</b></td>"
            f"<td>{', '.join(v) if isinstance(v, list) else v}</td></tr>"
            for k, v in bmc.items()
        )

        # API endpoints list
        api_items = "".join(
            f"<li><code>{ep.get('method','GET')} {ep.get('path','')}</code> — {ep.get('description','')}</li>"
            for ep in arch.get("api_endpoints", [])
        )

        # Government schemes
        schemes_items = "".join(
            f"<li><b>{s.get('name','')}</b> — {s.get('funding_amount','')} — "
            f"{s.get('eligibility','')}</li>"
            for s in biz.get("government_schemes", [])
        )

        solutions_html += f"""
        <div style="page-break-before:always;">
          <h2 style="color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:6px;">
            Solution {sol.get('id','?')}: {sol.get('label','—')}
          </h2>

          <h3 style="color:#2d6a9f;">System Overview</h3>
          <p>{arch.get('system_overview','—')}</p>

          <h3 style="color:#2d6a9f;">Tech Stack</h3>
          <table style="width:100%;border-collapse:collapse;">
            <tr style="background:#e8f0fb;"><th>Layer</th><th>Technology</th></tr>
            {stack_rows}
          </table>

          <h3 style="color:#2d6a9f;">API Endpoints</h3>
          <ul style="font-size:12px;">{api_items or '<li>None specified.</li>'}</ul>

          <h3 style="color:#2d6a9f;">Security &amp; Scalability</h3>
          <p><b>Security:</b> {arch.get('security_notes','—')}</p>
          <p><b>Scalability:</b> {arch.get('scalability_notes','—')}</p>

          <h3 style="color:#2d6a9f;">Business Model Canvas</h3>
          <table style="width:100%;border-collapse:collapse;">
            {bmc_rows}
          </table>

          <h3 style="color:#2d6a9f;">Financial Summary</h3>
          <p><b>Budget Estimate:</b> {biz.get('budget_estimate','—')}</p>
          <p><b>ROI Timeline:</b> {biz.get('roi_timeline','—')}</p>
          <p><b>Risk Summary:</b> {biz.get('risk_summary','—')}</p>

          <h3 style="color:#2d6a9f;">Government Funding Schemes</h3>
          <ul>{schemes_items or '<li>None identified.</li>'}</ul>

          <h3 style="color:#2d6a9f;">Innovation Scores</h3>
          <table style="width:60%;border-collapse:collapse;">
            <tr style="background:#e8f0fb;"><th>Dimension</th><th>Score / 10</th></tr>
            <tr><td>Cost Efficiency</td><td>{score.get('cost','—')}</td></tr>
            <tr><td>Feasibility</td><td>{score.get('feasibility','—')}</td></tr>
            <tr><td>Sustainability</td><td>{score.get('sustainability','—')}</td></tr>
            <tr><td>Scalability</td><td>{score.get('scalability','—')}</td></tr>
          </table>
        </div>
        """

    # Debate transcript section
    debate_rows = "".join(
        f"<tr><td><b style='color:{_speaker_colour(t['speaker'])};'>{t['speaker']}</b></td>"
        f"<td>R{t.get('round',0)}</td><td>{t.get('message','')}</td></tr>"
        for t in debate
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Genesis AI Report — {project.title}</title>
  <style>
    body  {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
             font-size: 13px; color: #1a1a2e; margin: 0; padding: 0; }}
    h1    {{ color: #1e3a5f; font-size: 24px; }}
    h2    {{ font-size: 18px; margin-top: 30px; }}
    h3    {{ font-size: 14px; margin-top: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
    th, td{{ border: 1px solid #cdd5e0; padding: 6px 10px; text-align: left; }}
    th    {{ background: #e8f0fb; }}
    code  {{ background: #f0f4f8; padding: 1px 4px; border-radius: 3px; }}
    .cover{{ background:#1e3a5f; color:#fff; padding:40px; }}
    .cover h1{{ color:#fff; font-size:32px; margin-bottom:8px; }}
    .cover p {{ color:#afc8e8; margin:4px 0; }}
  </style>
</head>
<body>
  <div class="cover">
    <h1>Genesis AI — Enterprise Innovation Report</h1>
    <p><b>Project:</b> {project.title}</p>
    <p><b>Generated:</b> {now}</p>
    <p><b>Problem Statement:</b> {project.problem_stmt}</p>
  </div>

  <div style="padding:20px;">
    <h2 style="color:#1e3a5f;">Executive Summary</h2>
    <p>
      This report presents <b>three distinct innovation solutions</b> generated by
      the Genesis AI multi-agent platform, each evaluated through an automated
      Debate Room critic loop involving Security and Finance agents.
    </p>

    {solutions_html}

    <div style="page-break-before:always;">
      <h2 style="color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:6px;">
        AI Debate Room Transcript
      </h2>
      <table>
        <tr style="background:#e8f0fb;"><th>Agent</th><th>Round</th><th>Message</th></tr>
        {debate_rows or '<tr><td colspan="3">No debate transcript available.</td></tr>'}
      </table>
    </div>

    <div style="margin-top:40px;padding-top:16px;border-top:1px solid #cdd5e0;
                text-align:center;color:#888;font-size:11px;">
      Generated by Genesis AI Enterprise Platform &nbsp;|&nbsp; Powered by IBM Watsonx.ai (Granite)
    </div>
  </div>
</body>
</html>"""


def _speaker_colour(speaker: str) -> str:
    """Map a speaker name to a highlight colour for the debate transcript."""
    colours = {
        "Architect": "#1e3a5f",
        "Security":  "#c0392b",
        "Finance":   "#1a7a4a",
        "Moderator": "#7b2d8b",
    }
    return colours.get(speaker, "#333333")
