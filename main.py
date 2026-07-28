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
<<<<<<< HEAD
import csv
from flask import Flask, render_template, request, jsonify, Response
import scraper
=======
from flask import Flask, render_template, request, jsonify, Response
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082

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
<<<<<<< HEAD
4. For large, complex, or hard projects, you must scale the build guide accordingly. Do not write a simple minimal set of tasks. Break down the project into a comprehensive list of 10 to 20 individual steps, ordered chronologically. Every phase must contain all intermediate steps (such as environment bootstrap, schema designs, helper creation, component builds, state integration, testing, etc.) without skipping, combining, or glossing over them.
5. In Section 6 (Step-by-Step Build Guide), focus heavily on the logic, execution, code setup, coding steps, testing, and practical implementation details of the task itself. Do NOT focus on explaining or describing the project folder structure or file layout details in Section 6, as the folder structure is already fully covered in Section 5.
=======
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082

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

<<<<<<< HEAD
FOLLOWUP_SYSTEM_PROMPT = """You are an expert software architect and mentor. The user has generated a project build guide and is asking follow-up questions about it.
Answer their questions accurately, clearly, and constructively, focusing on helping them implement the project steps. Keep your answers detailed and practical, but do not use code blocks unless specifically requested. Use markdown styling."""

=======
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082

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
<<<<<<< HEAD
# YouTube Dataset & Classification
# ---------------------------------------------------------------------------

def load_youtube_dataset() -> dict:
    dataset_path = Path(__file__).resolve().parent / "Dataset" / "CS_Areas_YouTube_Dataset.xlsx"
    if not dataset_path.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_excel(dataset_path)
        df['Area'] = df['Area'].ffill()
        data = {}
        for area, group in df.groupby('Area'):
            videos = []
            for _, row in group.iterrows():
                if not pd.isna(row['Links']) and str(row['Links']).strip():
                    videos.append({
                        "details": str(row['Details']) if not pd.isna(row['Details']) else '',
                        "link": str(row['Links']).strip()
                    })
            data[area] = videos
        return data
    except Exception as e:
        print(f"Error loading YouTube dataset: {e}")
        return {}


def classify_project_area_keyword(name: str, abstract: str, areas_list: list) -> str:
    name_abs = (name + " " + abstract).lower()
    
    # Define keywords for each area
    keywords = {
        "Artificial Intelligence (AI)": ["ai", "artificial intelligence", "chatbot", "machine learning", "deep learning", "neural", "nlp", "computer vision", "vision", "image recognition", "face recognition", "speech recognition", "generative", "llm", "gpt", "claude", "gemini", "llama", "chat", "bot"],
        "Bioinformatics": ["bioinformatics", "biological", "dna", "rna", "protein", "genome", "genomic", "gene", "sequencing", "ncbi", "blast"],
        "Cloud Computing": ["cloud", "aws", "azure", "gcp", "serverless", "hosting", "deployment", "docker", "kubernetes", "devops"],
        "Computer Graphics": ["graphics", "rendering", "opengl", "webgl", "3d", "blender", "ray tracing", "shading", "directx", "wayfinding", "ar", "augmented reality"],
        "Computer Networks": ["network", "routing", "switch", "protocol", "tcp", "ip", "ethernet", "wi-fi", "dns", "socket"],
        "Cybersecurity": ["cybersecurity", "security", "hacking", "penetration", "encryption", "decryption", "firewall", "auth", "vulnerability", "exploit", "malware", "phishing", "login", "password"],
        "Data Science & Big Data": ["data science", "big data", "data analysis", "statistics", "pandas", "numpy", "matplotlib", "dataframe", "visualisation", "analytics", "gdp", "visualization"],
        "Database Systems": ["database", "sql", "mysql", "postgresql", "mongodb", "nosql", "sqlite", "orm", "queries", "indexing"],
        "Distributed Systems": ["distributed", "gfs", "raft", "consensus", "microservices", "mapreduce", "p2p", "blockchain"],
        "Embedded Systems & IoT": ["iot", "embedded", "arduino", "raspberry pi", "sensor", "actuator", "microcontroller", "firmware"],
        "Game Development": ["game", "unity", "unreal", "godot", "2d game", "3d game", "physics engine", "sprite"],
        "Human-Computer Interaction (HCI)": ["hci", "interaction", "user interface", "ui", "ux", "accessibility", "wireframe", "prototype"],
        "Operating Systems": ["operating system", "kernel", "process scheduling", "memory management", "file system", "drivers", "threads"],
        "Programming Languages": ["programming language", "compiler", "interpreter", "python", "java", "c++", "rust", "javascript", "typescript", "go lang", "syntax"],
        "Quantum Computing": ["quantum", "qubit", "superposition", "entanglement", "qiskit", "quantum computer"],
        "Robotics": ["robotics", "robot", "kinematics", "manipulator", "control system", "autonomous vehicle"],
        "Software Engineering": ["software engineering", "software testing", "agile", "scrum", "design patterns", "refactoring", "testing", "selenium", "git", "github"],
        "Theory of Computation": ["theory of computation", "automata", "turing machine", "formal languages", "cfg", "dfa", "nfa", "complexity theory"]
    }
    
    scores = {}
    for area in areas_list:
        score = 0
        area_keywords = keywords.get(area, [])
        for kw in area_keywords:
            if kw in name_abs:
                score += name_abs.count(kw)
        scores[area] = score
        
    best_area = max(scores, key=scores.get)
    if scores[best_area] > 0:
        return best_area
        
    return "Software Engineering"  # Default fallback


def classify_project_area(client: OpenAI, name: str, abstract: str, areas_list: list) -> str:
    prompt = f"""Given the project name: "{name}" and abstract: "{abstract}".
Classify this project into exactly one of the following Computer Science areas:
{', '.join(areas_list)}

Respond with ONLY the exact name of the area from the list. Do not write any other text, explanation, or punctuation."""
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": "You are a helpful assistant that classifies project ideas into CS categories."},
                      {"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.0,
            timeout=5.0
        )
        classified_area = response.choices[0].message.content.strip()
        classified_area = classified_area.replace('"', '').replace("'", "").strip()
        if classified_area in areas_list:
            return classified_area
        for area in areas_list:
            if area.lower() in classified_area.lower() or classified_area.lower() in area.lower():
                return area
    except Exception as e:
        print(f"Error classifying area via LLM: {e}")
    
    # Fallback to keyword matching
    return classify_project_area_keyword(name, abstract, areas_list)


def generate_search_topic(client: OpenAI, name: str, abstract: str) -> str:
    prompt = f"""Given the project name: "{name}" and description: "{abstract}".
Generate a concise, search-engine-friendly topic query (3 to 6 words) that can be used to search for related academic/scientific papers on Google Scholar, IEEE, or arXiv.
Do NOT include punctuation, do NOT use quotes, just return the raw search query words.
Example name: "Hand Gesture Recognition for Deaf People"
Example query: "hand gesture recognition deaf communication"
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": "You are a research assistant that generates search queries for academic papers."},
                      {"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.3,
            timeout=5.0
        )
        query = response.choices[0].message.content.strip()
        query = re.sub(r'["\'\-\.]', '', query).strip()
        if query:
            return query
    except Exception as e:
        print(f"Error generating search topic: {e}")
    return name


# ---------------------------------------------------------------------------
=======
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082
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
<<<<<<< HEAD
    
    # Classify the project domain using YouTube dataset areas
    youtube_data = load_youtube_dataset()
    areas_list = list(youtube_data.keys())
    area = ""
    client = get_client()
    if areas_list:
        area = classify_project_area(client, name, abstract, areas_list)

    # Run the paper scraper based on project name and description
    all_papers_path = PROJECTS_DIR / f"{slug}_all_papers.csv"
    ieee_papers_path = PROJECTS_DIR / f"{slug}_ieee_papers.csv"
    try:
        topic = generate_search_topic(client, name, abstract)
        print(f"Scraping papers for search topic: {topic}")
        scraper.search_and_save_papers(topic, str(all_papers_path), str(ieee_papers_path))
    except Exception as e:
        print(f"Error running paper scraper during project save: {e}")

=======
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082
    index.append({
        "name": name,
        "slug": slug,
        "file": filepath.name,
        "abstract": abstract,
        "created": timestamp,
<<<<<<< HEAD
        "area": area
=======
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082
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
<<<<<<< HEAD
        projects = _load_index()
        project = next((p for p in projects if p['slug'] == slug), None)
        
        area = ""
        videos = []
        
        if project:
            if 'area' not in project:
                youtube_data = load_youtube_dataset()
                areas_list = list(youtube_data.keys())
                if areas_list:
                    client = get_client()
                    project['area'] = classify_project_area(client, project['name'], project['abstract'], areas_list)
                    _save_index(projects)
            
            area = project.get('area', '')
            youtube_data = load_youtube_dataset()
            videos = youtube_data.get(area, [])
            
        return jsonify({
            'content': content,
            'area': area,
            'videos': videos
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<slug>/papers', methods=['GET'])
def api_get_project_papers(slug):
    try:
        projects = _load_index()
        project = next((p for p in projects if p['slug'] == slug), None)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        all_papers_path = PROJECTS_DIR / f"{slug}_all_papers.csv"
        ieee_papers_path = PROJECTS_DIR / f"{slug}_ieee_papers.csv"
        
        # On-demand generation if missing (e.g. for pre-existing projects)
        if not all_papers_path.exists() or not ieee_papers_path.exists():
            client = get_client()
            topic = generate_search_topic(client, project['name'], project['abstract'])
            try:
                scraper.search_and_save_papers(topic, str(all_papers_path), str(ieee_papers_path))
            except Exception as e:
                print(f"Error generating papers on-demand for {slug}: {e}")
        
        def parse_csv(path):
            if not path.exists():
                return []
            results = []
            try:
                with open(path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get("url", "").strip()
                        # Only return accurate, non-empty paper reference links
                        if url.startswith("http://") or url.startswith("https://"):
                            results.append({
                                "source": row.get("source", ""),
                                "title": row.get("title", ""),
                                "authors": row.get("authors", ""),
                                "year": row.get("year", ""),
                                "venue": row.get("venue", ""),
                                "doi": row.get("doi", ""),
                                "url": url
                            })
            except Exception as e:
                print(f"Error parsing CSV {path}: {e}")
            return results
        
        all_papers = parse_csv(all_papers_path)
        ieee_papers = parse_csv(ieee_papers_path)
        
        return jsonify({
            'all_papers': all_papers,
            'ieee_papers': ieee_papers
        })
=======
        return jsonify({'content': content})
>>>>>>> 8ba20ef3734c5c876a1c63a3896609a88770e082
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