"""
ui/app_ui.py — AI Frontend Generation Agent Web UI Server

Serves a dark glassmorphism UI for:
  - Uploading a reference image
  - Providing user stories JSON
  - Configuring project settings
  - Watching the live pipeline with per-stage timers (via SSE)
  - Viewing the generated file tree

Run with:
    python ui/app_ui.py
"""
from __future__ import annotations

import io
import json
import os
import queue
import shutil
import sys
import threading
import time
import zipfile
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
    stream_with_context,
)
from werkzeug.utils import secure_filename

from config import settings

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB max upload

# Allowed image extensions
ALLOWED_IMAGES = {".png", ".jpg", ".jpeg", ".webp"}

# Active generation sessions: session_id → queue of SSE messages
_sessions: dict[str, queue.Queue] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_IMAGES


def sse_message(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", settings=settings)

# ---------------------------------------------------------------------------
# Project-Centric SQLite Database APIs
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))

db_list_projects = None
db_create_project = None
db_get_project_details = None
db_add_story = None
db_delete_project = None

try:
    from services.project_manager import (
        list_projects as db_list_projects,
        create_project as db_create_project,
        get_project_details as db_get_project_details,
        add_user_story_to_project as db_add_story,
        delete_project as db_delete_project
    )
    from models.project_model import ProjectCreatePayload, AddStoryPayload
except Exception as err:
    print(f"[Database Import Warning]: {err}")

@app.route("/api/v1/projects", methods=["GET"])
def get_projects():
    """List projects directly from local SQLite Database (code_gene.db)."""
    if db_list_projects:
        return jsonify({"projects": db_list_projects()})
    return jsonify({"projects": []})

@app.route("/api/v1/projects", methods=["POST"])
def create_project():
    """Create a new project record in local SQLite Database."""
    data = request.get_json() or {}
    if db_create_project:
        payload = ProjectCreatePayload(
            projectName=data.get("projectName", "New Project"),
            framework=data.get("framework", "React"),
            language=data.get("language", "TypeScript"),
            cssStrategy=data.get("cssStrategy", "Separate"),
            folderStructure=data.get("folderStructure", "Feature-based")
        )
        res = db_create_project(payload)
        return jsonify(res)
    return jsonify({"error": "DB engine not ready"}), 500

@app.route("/api/v1/projects/<project_id>", methods=["GET"])
def get_project_by_id(project_id):
    """Retrieve details for a project from SQLite DB."""
    if db_get_project_details:
        details = db_get_project_details(project_id)
        if details:
            return jsonify(details)
    return jsonify({"error": "Project not found"}), 404

@app.route("/api/v1/projects/<project_id>", methods=["DELETE"])
def delete_project_by_id(project_id):
    """Delete a project from SQLite DB."""
    if db_delete_project:
        success = db_delete_project(project_id)
        if success:
            return jsonify({"status": "deleted"})
        return jsonify({"error": "Project not found"}), 404
    return jsonify({"error": "DB engine not ready"}), 500

@app.route("/api/v1/projects/<project_id>/stories", methods=["POST"])
def add_story_to_project(project_id):
    """Add a new user story incrementally to SQLite DB."""
    story_text = request.form.get("userStory", "").strip()
    wireframe_file = request.files.get("wireframe")

    if not story_text:
        return jsonify({"error": "User story is required"}), 400
        
    if not wireframe_file:
        return jsonify({"error": "Wireframe image is mandatory"}), 400

    if db_add_story:
        try:
            payload = AddStoryPayload(userStory=story_text)
            res = db_add_story(project_id, payload)
            return jsonify(res)
        except ValueError as err:
            return jsonify({"error": str(err)}), 404

    return jsonify({"error": "DB engine not ready"}), 500


@app.route("/generate", methods=["POST"])
def generate():
    """Start a generation job and return a session_id for SSE streaming."""
    import uuid

    # --- Validate inputs ---
    if "image" not in request.files or request.files["image"].filename == "":
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image"]
    stories_text = request.form.get("stories", "").strip()
    project_name = request.form.get("project", "generated-app").strip() or "generated-app"
    output_lang = request.form.get("lang", settings.output_language)
    if output_lang not in ("tsx", "jsx"):
        output_lang = "tsx"

    if not stories_text:
        return jsonify({"error": "No user stories provided"}), 400

    # Parse stories JSON early to give fast feedback
    try:
        stories_data = json.loads(stories_text)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Invalid JSON in user stories: {exc}"}), 400

    # Validate image
    orig_name = secure_filename(image_file.filename or "image.png")
    if not allowed_image(orig_name):
        return jsonify({"error": f"Unsupported image type. Allowed: {ALLOWED_IMAGES}"}), 400

    # Save inputs to input/ directory
    image_path = settings.input_dir / "images" / orig_name
    image_file.save(str(image_path))

    stories_path = settings.input_dir / "user_stories" / "stories.json"
    stories_path.write_text(json.dumps(stories_data, indent=2), encoding="utf-8")

    # Create SSE session
    session_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    _sessions[session_id] = q

    # Override language setting for this run
    settings.output_language = output_lang

    # Launch pipeline in background thread
    def run_pipeline():
        import importlib
        import config
        importlib.reload(config)
        if hasattr(config.settings, "reload"):
            config.settings.reload()
        import models.story_mapping
        import models.ui_spec
        import agent.code_generator
        import agent.story_mapper
        import agent.image_analyzer
        importlib.reload(models.story_mapping)
        importlib.reload(models.ui_spec)
        importlib.reload(agent.code_generator)
        importlib.reload(agent.story_mapper)
        importlib.reload(agent.image_analyzer)
        from agent import ImageAnalyzer, StoryMapper, CodeGenerator
        from utils.groq_client import GroqClient
        from utils.file_manager import FileManager

        def emit(event: str, **kwargs):
            q.put(sse_message(event, kwargs))

        try:
            groq_client = GroqClient()
            fm = FileManager(project_name)
            fm.clean_project()
            analyzer = ImageAnalyzer(groq_client)
            mapper = StoryMapper(groq_client)
            generator = CodeGenerator(groq_client)

            # --- Stage 1 ---
            emit("stage_start", stage=1, name="Image Analysis")
            t1 = time.monotonic()

            ui_spec_path = fm.metadata_dir / "ui_spec.json"
            ui_spec = analyzer.analyze(
                image_path=image_path,
                output_path=ui_spec_path,
                progress_cb=lambda msg: emit("log", stage=1, message=msg),
            )

            elapsed1 = int(time.monotonic() - t1)
            if ui_spec is None:
                emit("stage_fail", stage=1, name="Image Analysis", elapsed=elapsed1, error="Failed to analyze image")
                emit("done", success=False)
                return

            emit("stage_done", stage=1, name="Image Analysis", elapsed=elapsed1,
                 elements=len(ui_spec.all_element_ids()), pages=len(ui_spec.pages))

            # --- Stage 2 ---
            emit("stage_start", stage=2, name="Story Mapping")
            t2 = time.monotonic()

            mapping_path = fm.metadata_dir / "story_ui_mapping.json"
            mapping_doc = mapper.map(
                ui_spec=ui_spec,
                ui_spec_path=ui_spec_path,
                stories_path=stories_path,
                output_path=mapping_path,
                progress_cb=lambda msg: emit("log", stage=2, message=msg),
            )

            elapsed2 = int(time.monotonic() - t2)
            if mapping_doc is None:
                emit("stage_fail", stage=2, name="Story Mapping", elapsed=elapsed2, error="Failed to map stories")
                emit("done", success=False)
                return

            emit("stage_done", stage=2, name="Story Mapping", elapsed=elapsed2,
                 mappings=len(mapping_doc.mappings))

            # --- Stage 3 ---
            emit("stage_start", stage=3, name="Code Generation")
            t3 = time.monotonic()

            report = generator.generate(
                image_path=image_path,
                ui_spec=ui_spec,
                ui_spec_path=ui_spec_path,
                mapping_doc=mapping_doc,
                mapping_path=mapping_path,
                file_manager=fm,
                project_name=project_name,
                progress_cb=lambda msg: emit("log", stage=3, message=msg),
            )

            elapsed3 = int(time.monotonic() - t3)
            emit("stage_done", stage=3, name="Code Generation", elapsed=elapsed3,
                 coverage=report.coverage_percent if report else 0)

            # --- Stage 4: UI Validation & Refinement ---
            emit("stage_start", stage=4, name="UI Validation & Refinement")
            t4 = time.monotonic()
            val_report = {}
            try:
                from agent import UIValidator
                validator = UIValidator(groq_client)
                val_path = fm.metadata_dir / "validation_report.json"
                val_report = validator.validate(
                    ground_truth_image=image_path,
                    output_path=val_path,
                    ui_spec_path=ui_spec_path,
                    react_src_dir=fm.react_src_dir,
                    progress_cb=lambda msg: emit("log", stage=4, message=msg),
                ) or {}

                score = val_report.get("similarity_score", 95)
                emit("log", stage=4, message=f"UI Visual Similarity Score: {score}%")

                if score < 98:
                    emit("log", stage=4, message="Visual similarity below threshold (<98%). Triggering UI Regeneration Agent...")
                    from agent import UIRegenerator
                    regenerator = UIRegenerator(groq_client)
                    regenerated = regenerator.regenerate(
                        file_manager=fm,
                        validation_report=val_report,
                        project_name=project_name,
                        progress_cb=lambda msg: emit("log", stage=4, message=msg),
                    )
                    if regenerated:
                        emit("log", stage=4, message="✓ React UI Regeneration Agent refined component & CSS files.")
                else:
                    emit("log", stage=4, message="✓ UI visual match verified (≥98%). No regeneration needed.")

            except Exception as val_exc:
                emit("log", stage=4, message=f"[WARN] UI Validation step: {val_exc}")

            elapsed4 = int(time.monotonic() - t4)
            emit("stage_done", stage=4, name="UI Validation & Refinement", elapsed=elapsed4)

            # File tree
            file_tree = fm.file_tree()
            react_path = str(fm.react_app_dir)
            emit("done", success=True, project=project_name,
                 react_path=react_path, file_tree=file_tree,
                 coverage=report.coverage_percent if report else 0,
                 total_elapsed=int(time.monotonic() - t1))

        except Exception as exc:
            import traceback
            emit("error", message=str(exc), traceback=traceback.format_exc())
            emit("done", success=False)
        finally:
            # Clean up session after 5 minutes
            def cleanup():
                time.sleep(300)
                _sessions.pop(session_id, None)
            threading.Thread(target=cleanup, daemon=True).start()

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return jsonify({"session_id": session_id})


@app.route("/stream/<session_id>")
def stream(session_id: str):
    """SSE endpoint — streams pipeline progress events."""
    q = _sessions.get(session_id)
    if q is None:
        return jsonify({"error": "Session not found"}), 404

    def event_stream():
        yield sse_message("connected", {"session_id": session_id})
        while True:
            try:
                msg = q.get(timeout=2)
                yield msg
                if '"event": "done"' in msg or 'event: done' in msg:
                    break
            except queue.Empty:
                yield sse_message("ping", {})

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/download/<project_name>")
def download_project(project_name: str):
    """Package the generated project directory into a ZIP and download it."""
    proj_dir = settings.output_dir / secure_filename(project_name)
    if not proj_dir.exists() or not proj_dir.is_dir():
        return jsonify({"error": f"Project '{project_name}' not found"}), 404

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in proj_dir.rglob("*"):
            if file.is_file():
                # Avoid zipping node_modules if present to keep download fast
                if "node_modules" in file.parts:
                    continue
                arcname = file.relative_to(proj_dir)
                zf.write(file, arcname)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{project_name}.zip",
    )


@app.route("/delete/<project_name>", methods=["POST", "DELETE"])
def delete_project(project_name: str):
    """Erase a generated project directory."""
    proj_dir = settings.output_dir / secure_filename(project_name)
    if not proj_dir.exists():
        return jsonify({"error": f"Project '{project_name}' not found"}), 404

    try:
        shutil.rmtree(proj_dir, ignore_errors=True)
        return jsonify({"success": True, "message": f"Project '{project_name}' deleted successfully."})
    except Exception as exc:
        return jsonify({"error": f"Failed to delete project: {exc}"}), 500


@app.route("/projects", methods=["GET"])
def list_projects():
    """List all generated project folders."""
    if not settings.output_dir.exists():
        return jsonify({"projects": []})

    projects = [
        p.name for p in settings.output_dir.iterdir() if p.is_dir()
    ]
    return jsonify({"projects": sorted(projects)})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "1.0"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  AI Frontend Generation Agent — Web UI")
    print(f"  http://{settings.ui_host}:{settings.ui_port}")
    print(f"{'='*55}\n")
    app.run(
        host=settings.ui_host,
        port=settings.ui_port,
        debug=settings.ui_debug,
        threaded=True,
    )
