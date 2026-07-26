#!/usr/bin/env python3
"""
AI Mentor OS — a terminal AI project mentor (single-file version).

Enter a project abstract and get a complete, step-by-step build guide:
tech stack, architecture, file structure, implementation steps, testing,
deployment, pitfalls, learning resources, and a timeline. You can also
ask follow-up questions about any saved guide.

Backend: NVIDIA NIM (https://build.nvidia.com), a free, OpenAI-compatible
inference API.

Setup:
    pip install openai rich
    export NVIDIA_API_KEY=nvapi-your-key-here   (or you'll be prompted for it)
    Get a free key at https://build.nvidia.com

Run:
    python main.py
"""

import os
import re
import sys
import json
import datetime
from pathlib import Path
import time
import webbrowser
import threading
from flask import Flask, render_template, request, jsonify, Response

try:
    from openai import OpenAI
except ImportError:
    print("Missing dependency 'openai'. Install it with:\n  pip install openai")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.markdown import Markdown
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://integrate.api.nvidia.com/v1"
# Browse more free models at https://build.nvidia.com/models and swap this.
MODEL = "meta/llama-3.1-8b-instruct"
MAX_TOKENS = 4096

PROJECTS_DIR = Path(__file__).resolve().parent / "projects"
INDEX_FILE = PROJECTS_DIR / "index.json"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert software architect and mentor who helps learners turn a short project abstract into a complete, actionable build guide.

NON-NEGOTIABLE RULES — apply to the entire document:
1. Every step in Section 6 must be written in FULL detail using the exact 5-part structure defined below (title, paragraph, sub-actions, time, complexity). A single sentence or one-line summary for a step is a failure — this applies to every step in every phase, from the first step to the very last one. Do not shorten, compress, or summarize steps later in the document even if the guide is getting long.
2. Every fact, command, tool name, library, or instruction must be technically accurate and something that actually works in real-world development. Never invent a command, flag, library, or step just to fill space. If you are not fully certain of an exact command or syntax, describe the goal and general approach in plain language instead of fabricating specific syntax.
3. Do not skip, merge, or abbreviate any of the 12 sections below.

Given a project abstract, produce a thorough Markdown document with these exact sections, in this order:

## 1. Project Overview
A clear restatement of what the project does and why it's useful (3-5 sentences).

## 2. Objectives & Scope
Bullet list of concrete goals, and what is explicitly OUT of scope for a first version.

## 3. Recommended Tech Stack
For every language, framework, library, or service, include on its own line:
- Name — one-line reason it's the right choice for this specific project
- Learning curve: Easy, Moderate, or Hard

## 4. System Architecture
A text-based architecture description (components and how they talk to each other).
Include a simple ASCII diagram if it helps.

## 5. Project Folder Structure
A realistic file/folder tree for the project.

## 6. Step-by-Step Build Guide
Numbered, sequential steps from environment setup to a working first version. Group steps into phases using ### headings (e.g. "### Phase 1: Setup").

Every step MUST follow this exact structure, with nothing skipped:

1. A numbered title line (e.g. "1. Install and configure Python").
2. A blank line, then a full paragraph of 4-6 sentences that explains: what exactly to do, how to do it step by step, what needs to be decided or configured along the way, what commonly goes wrong at this stage, and what the finished result should look like before moving on.
3. A bullet list of 3-5 specific, checkable sub-actions for that step.
4. A line reading "Time required: X" (in minutes or hours).
5. A line reading "Complexity: Easy / Moderate / Hard" (pick exactly one).

Do not include any code blocks or inline code in this section — describe everything in plain language, as this section is meant to be a narrative checklist, not a coding tutorial. A short one-line description is not acceptable for any step — always write the full paragraph.

Example of one correctly formatted step:

1. Set up the Python virtual environment

   Create a dedicated virtual environment for this project to isolate its dependencies from your system Python. This prevents version conflicts with other projects and keeps the project portable across machines. Work from the project's root folder and use Python's built-in venv module to create the environment, then activate it before installing anything. You'll know it's active when the environment name appears in your terminal prompt, and you should re-activate it every time you return to work on the project. If activation doesn't seem to take effect, close and reopen your terminal and try again before troubleshooting further.

   - Create the environment folder using the venv module
   - Activate it with the correct script for your operating system
   - Confirm activation by checking that pip resolves to the local environment
   - Install one test package to confirm isolation is working

   Time required: 30 minutes
   Complexity: Easy

## 7. Core Logic Explained
Explain the trickiest 2-4 algorithms or modules in more depth, focusing on the logic and data flow in plain language — no code.

## 8. Testing Strategy
What to test and how (unit/integration/manual), with test cases described in detail rather than written as code.

## 9. Deployment & Usage
How to run the project locally and, if relevant, how to deploy or share it.

## 10. Common Pitfalls & Troubleshooting
Mistakes beginners make on this kind of project, and how to avoid or fix them.

## 11. Learning Resources
3-6 specific topics or technologies worth reading up on, each described in a sentence (not linked, since live URLs can't be verified).

## 12. Suggested Timeline
A milestone breakdown (e.g. Week 1, Week 2...) sized to the project's apparent complexity, consistent with the per-step time estimates in Section 6.

Be specific to the abstract given — avoid generic advice that could apply to any project. Assume the reader can code but has not built this exact kind of project before. Use proper Markdown headers and bullet points throughout. Do not use code blocks anywhere in the document."""


# ---------------------------------------------------------------------------
# NVIDIA NIM API (OpenAI-compatible)
# ---------------------------------------------------------------------------

def get_client() -> OpenAI:
    """Build an OpenAI-compatible client pointed at NVIDIA NIM."""
    api_key = os.environ.get("NVIDIA_API_KEY", "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")
    if not api_key:
        print("NVIDIA_API_KEY is not set in your environment.")
        api_key = input("Paste your NVIDIA API key (starts with nvapi-): ").strip()
    return OpenAI(base_url=BASE_URL, api_key=api_key)


def _stream_chat(client: OpenAI, system_prompt: str, messages: list, on_chunk=None) -> str:
    """Shared streaming helper: sends a chat request and yields text as it arrives."""
    full_text = []
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        max_tokens=MAX_TOKENS,
        temperature=0.4,
        top_p=0.9,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            full_text.append(content)
            if on_chunk:
                on_chunk(content)
    return "".join(full_text)


def generate_guide(client: OpenAI, abstract: str, on_chunk=None) -> str:
    """Generate a full build guide from a project abstract. Streams if on_chunk given."""
    messages = [{"role": "user", "content": f"Project abstract:\n\n{abstract}"}]
    return _stream_chat(client, SYSTEM_PROMPT, messages, on_chunk)


def ask_followup(client: OpenAI, history: list, question: str, on_chunk=None) -> str:
    """Ask a follow-up question, given prior conversation history."""
    messages = history + [{"role": "user", "content": question}]
    return _stream_chat(client, FOLLOWUP_SYSTEM_PROMPT, messages, on_chunk)


# ---------------------------------------------------------------------------
# Storage — save/load guides as Markdown, tracked in a JSON index
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _load_index() -> list:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return []


def _save_index(index: list) -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")


def save_project(name: str, abstract: str, guide_markdown: str) -> Path:
    """Write the guide to a Markdown file and record it in the index."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = f"{_slugify(name)}-{timestamp}"
    filepath = PROJECTS_DIR / f"{slug}.md"

    header = (
        f"# {name}\n\n"
        f"*Generated {datetime.datetime.now():%Y-%m-%d %H:%M}*\n\n"
        f"**Abstract:** {abstract}\n\n---\n\n"
    )
    filepath.write_text(header + guide_markdown, encoding="utf-8")

    index = _load_index()
    index.append({
        "name": name,
        "slug": slug,
        "file": filepath.name,
        "abstract": abstract,
        "created": timestamp,
    })
    _save_index(index)
    return filepath


def list_projects() -> list:
    return _load_index()


def load_project(slug: str) -> str:
    filepath = PROJECTS_DIR / f"{slug}.md"
    return filepath.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Terminal UI helpers
# ---------------------------------------------------------------------------

BANNER = r"""
   _    ___   __  __            _              ___  ____
  / \  |_ _| |  \/  | ___ _ __ | |_ ___  _ __  / _ \/ ___|
 / _ \  | |  | |\/| |/ _ \ '_ \| __/ _ \| '__|| | | \___ \
/ ___ \ | |  | |  | |  __/ | | | || (_) | |   | |_| |___) |
/_/   \_\___| |_|  |_|\___|_| |_|\__\___/|_|    \___/|____/

   Turn a project abstract into a complete, step-by-step build guide.
"""


def show_banner():
    print(BANNER)


def show_menu() -> str:
    print("\n1) Start Web UI (Recommended)")
    print("2) New project guide (Terminal)")
    print("3) View a saved project (Terminal)")
    print("4) Ask a follow-up question about a saved project (Terminal)")
    print("5) Exit")
    return input("\nChoose an option: ").strip()


def get_multiline_input(prompt_text: str) -> str:
    print(f"\n{prompt_text}")
    print("(Type or paste your text. Finish with an empty line or press Enter twice to finish.)")
    lines = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def stream_print(chunk: str):
    print(chunk, end="", flush=True)


def render_markdown(md_text: str):
    if RICH:
        console.print(Markdown(md_text))
    else:
        print(md_text)


def info(msg: str):
    print(f"\n[i] {msg}")


def error(msg: str):
    print(f"\n[!] {msg}")


def success(msg: str):
    print(f"\n[OK] {msg}")


# ---------------------------------------------------------------------------
# App flows
# ---------------------------------------------------------------------------

def new_project_flow(client: OpenAI):
    name = input("\nProject name: ").strip() or "untitled-project"
    abstract = get_multiline_input("Paste your project abstract:")
    if not abstract:
        error("No abstract provided, aborting.")
        return

    info(f"Generating build guide for '{name}'... this can take a minute.\n")
    try:
        guide = generate_guide(client, abstract, on_chunk=stream_print)
        print()
        filepath = save_project(name, abstract, guide)
        success(f"Saved to {filepath}")
    except Exception as e:
        error(f"Failed to generate guide: {e}")


def view_project_flow():
    projects = list_projects()
    if not projects:
        info("No saved projects yet.")
        return None
    print("\nSaved projects:")
    for i, p in enumerate(projects, 1):
        print(f"  {i}) {p['name']}  ({p['created']})")
    choice = input("\nOpen which one? (number, or Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(projects)):
        return None
    project = projects[int(choice) - 1]
    content = load_project(project["slug"])
    render_markdown(content)
    return project


def followup_flow(client: OpenAI):
    project = view_project_flow()
    if not project:
        return
    guide_text = load_project(project["slug"])
    history = [
        {"role": "user", "content": f"Project abstract:\n\n{project['abstract']}"},
        {"role": "assistant", "content": guide_text},
    ]
    question = input("\nYour follow-up question: ").strip()
    if not question:
        return
    try:
        ask_followup(client, history, question, on_chunk=stream_print)
        print()
    except Exception as e:
        error(f"Failed to get response: {e}")


# Flask App Setup
app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/projects', methods=['GET'])
def api_projects():
    try:
        return jsonify(_load_index())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<slug>', methods=['GET'])
def api_get_project(slug):
    try:
        content = load_project(slug)
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def api_generate():
    data = request.json or {}
    name = data.get('name', '').strip() or 'untitled-project'
    abstract = data.get('abstract', '').strip()
    if not abstract:
        return jsonify({'error': 'No abstract provided'}), 400

    def generate():
        client = get_client()
        full_text = []
        try:
            messages = [{"role": "user", "content": f"Project abstract:\n\n{abstract}"}]
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
                max_tokens=MAX_TOKENS,
                temperature=0.4,
                top_p=0.9,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    full_text.append(content)
                    yield f"data: {json.dumps({'chunk': content})}\n\n"
            
            guide = "".join(full_text)
            filepath = save_project(name, abstract, guide)
            yield f"data: {json.dumps({'done': True, 'slug': filepath.stem})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/followup', methods=['POST'])
def api_followup():
    data = request.json or {}
    slug = data.get('slug', '').strip()
    question = data.get('question', '').strip()
    if not slug or not question:
        return jsonify({'error': 'Missing slug or question'}), 400

    try:
        projects = _load_index()
        project = next((p for p in projects if p['slug'] == slug), None)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        guide_text = load_project(slug)
        history = [
            {"role": "user", "content": f"Project abstract:\n\n{project['abstract']}"},
            {"role": "assistant", "content": guide_text},
        ]

        def generate():
            client = get_client()
            full_text = []
            try:
                messages = history + [{"role": "user", "content": question}]
                stream = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT}, *messages],
                    max_tokens=MAX_TOKENS,
                    temperature=0.4,
                    top_p=0.9,
                    stream=True,
                )
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", None)
                    if content:
                        full_text.append(content)
                        yield f"data: {json.dumps({'chunk': content})}\n\n"
                
                qa_text = f"\n\n### Follow-up Question\n**Q:** {question}\n\n**A:** " + "".join(full_text)
                filepath = PROJECTS_DIR / f"{slug}.md"
                if filepath.exists():
                    current_content = filepath.read_text(encoding="utf-8")
                    filepath.write_text(current_content + qa_text, encoding="utf-8")
                    
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_web_server():
    print("\nStarting Flask web server...")
    print("Open http://127.0.0.1:5000 in your browser.")
    threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open("http://127.0.0.1:5000")), daemon=True).start()
    app.run(port=5000)


if __name__ == "__main__":
    try:
        start_web_server()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")