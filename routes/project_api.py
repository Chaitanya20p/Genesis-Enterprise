"""
============================================================
 Genesis AI — Project API Blueprint (routes/project_api.py)
 Exposes the core multi-agent workflow over HTTP.

 Endpoints:
   POST /api/orchestrate     → Starts the full agent pipeline
   POST /api/upload_rag      → Ingests a PDF into ChromaDB
   GET  /api/debate_stream   → Returns the debate transcript
   GET  /api/projects        → Lists all saved projects
   GET  /api/projects/<id>   → Retrieves a single project
============================================================
"""

import json
import os
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

project_bp = Blueprint("project", __name__)

# ------------------------------------------------------------------
#  File upload helper
# ------------------------------------------------------------------

ALLOWED_EXTENSIONS = {"pdf"}


def _allowed_file(filename: str) -> bool:
    """Return True only if the filename has a permitted extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================================================================
#  POST /api/orchestrate
# ==================================================================

@project_bp.route("/orchestrate", methods=["POST"])
def orchestrate():
    """
    Starts the Genesis AI multi-agent orchestration pipeline.

    Request Body (JSON):
        {
          "problem_statement": "Describe your innovation challenge here",
          "project_title":     "Optional project name"
        }

    Response (JSON):
        Full orchestration result including three solutions,
        debate transcript, and Chart.js-ready radar data.

    HTTP Codes:
        200 — Success
        400 — Missing required fields
        500 — Agent pipeline error
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    problem_statement = data.get("problem_statement", "").strip()
    project_title     = data.get("project_title", "Untitled Project").strip()

    if not problem_statement:
        return jsonify({"error": "Field 'problem_statement' is required."}), 400

    if len(problem_statement) > 4000:
        return jsonify({"error": "Problem statement exceeds 4000 character limit."}), 400

    # --- Step 1: Run the agent pipeline ---
    try:
        from agents.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        result = orchestrator.orchestrate(
            problem_statement=problem_statement,
            project_title=project_title,
        )
    except EnvironmentError as env_err:
        logger.error("Credentials error: %s", env_err)
        return jsonify({"error": str(env_err)}), 503
    except Exception as exc:
        logger.exception("Orchestration pipeline failed.")
        return jsonify({"error": f"Orchestration failed: {str(exc)}"}), 500

    # --- Step 2: Persist results inside app context ---
    try:
        from app import db
        from models import Project, DebateLog

        project = Project(
            title        = project_title,
            problem_stmt = problem_statement,
            result_json  = json.dumps(result),
        )
        db.session.add(project)
        db.session.flush()

        for turn in result.get("debate_transcript", []):
            log = DebateLog(
                project_id = project.id,
                speaker    = turn.get("speaker", "Unknown"),
                message    = turn.get("message", ""),
                round_num  = turn.get("round", 0),
            )
            db.session.add(log)

        db.session.commit()
        logger.info("Project '%s' saved with ID %d.", project_title, project.id)
        project_id_saved = project.id

    except Exception as db_exc:
        logger.exception("DB save failed — returning result without persistence.")
        db.session.rollback()
        project_id_saved = 0

    return jsonify({
        "project_id": project_id_saved,
        "result":     result,
    }), 200


# ==================================================================
#  POST /api/upload_rag
# ==================================================================

@project_bp.route("/upload_rag", methods=["POST"])
def upload_rag():
    """
    Upload a PDF document into the ChromaDB knowledge base.

    Request: multipart/form-data with a 'file' field containing a PDF.

    Response (JSON):
        {
          "message":     "File ingested successfully.",
          "filename":    "<original filename>",
          "chunks_added": <int>,
          "total_docs":   <int>
        }

    HTTP Codes:
        200 — Successfully ingested
        400 — No file / wrong file type
        500 — Ingestion error
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in request. Use multipart/form-data with key 'file'."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    try:
        filename   = secure_filename(file.filename)
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        filepath   = os.path.join(upload_dir, filename)
        file.save(filepath)

        from agents.rag_researcher import RAGResearcher
        rag    = RAGResearcher()
        result = rag.ingest_pdf(filepath)

        logger.info("Ingested PDF '%s' — %d chunks added.", filename, result["chunks_added"])

        return jsonify({
            "message":     "File ingested successfully.",
            "filename":    result["filename"],
            "chunks_added": result["chunks_added"],
            "total_docs":   result["total_docs"],
        }), 200

    except Exception as exc:
        logger.exception("RAG ingestion failed.")
        return jsonify({"error": f"Ingestion failed: {str(exc)}"}), 500


# ==================================================================
#  GET /api/debate_stream?project_id=<id>
# ==================================================================

@project_bp.route("/debate_stream", methods=["GET"])
def debate_stream():
    """
    Return the stored debate transcript for a given project.

    Query Parameters:
        project_id (int, required): The project whose transcript to retrieve.

    Response (JSON):
        { "project_id": <int>, "transcript": [ {speaker, round, message, timestamp} ] }

    HTTP Codes:
        200 — Transcript returned
        400 — Missing project_id
        404 — Project not found
    """
    from app import db
    from models import Project

    project_id = request.args.get("project_id", type=int)

    if not project_id:
        return jsonify({"error": "Query parameter 'project_id' is required."}), 400

    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": f"Project {project_id} not found."}), 404

    transcript = [log.to_dict() for log in project.debate_logs]

    return jsonify({
        "project_id": project_id,
        "transcript": transcript,
    }), 200


# ==================================================================
#  GET /api/projects
# ==================================================================

@project_bp.route("/projects", methods=["GET"])
def list_projects():
    """List all projects ordered by most recent first."""
    from app import db
    from models import Project
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify({"projects": [p.to_dict() for p in projects]}), 200


# ==================================================================
#  GET /api/projects/<int:project_id>
# ==================================================================

@project_bp.route("/projects/<int:project_id>", methods=["GET"])
def get_project(project_id: int):
    """Retrieve a single project by ID, including its full result JSON."""
    from app import db
    from models import Project
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": f"Project {project_id} not found."}), 404
    return jsonify(project.to_dict()), 200
