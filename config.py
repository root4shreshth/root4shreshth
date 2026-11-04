"""
Everything personal lives here. Edit this file, push, and the GitHub Action
re-renders every SVG in /assets. Nothing in generate.py needs touching.
"""

LOGIN = "root4shreshth"
NAME = "SHRESHTH"
ROLE = "AI Product Engineer"
LOCATION = "India"
TIMEZONE_OFFSET_MIN = 330          # IST, used for the "synced" timestamp
TIMEZONE_LABEL = "IST"

# The hero "prompt" and the answer that streams out token by token.
PROMPT = 'shreshth.run(prompt="who are you?")'
ANSWER = (
    "I build AI products end to end: from a blank Figma frame to a model "
    "serving real users. LLMs, agentic systems and real-time voice, "
    "shipped production-grade."
)

# 02 / ATTENTION ------------------------------------------------------------
# Rows are what you work on (queries); columns are what you reach for (keys).
# Weights are 0..1 and are yours to tune; each row does not need to sum to 1.
ATTN_ROWS = ["LLM products", "Agentic systems", "Voice AI",
             "Backend & APIs", "Frontend & UX", "Ship & operate"]
ATTN_COLS = ["Python", "TypeScript", "FastAPI", "Next.js", "React",
             "PyTorch", "Supabase", "n8n", "Vercel", "AWS"]
ATTN = [
    # Py   TS   Fast  Next  React Torch Supa  n8n  Vercel AWS
    [0.95, 0.70, 0.85, 0.60, 0.45, 0.55, 0.40, 0.35, 0.40, 0.50],  # LLM products
    [0.90, 0.55, 0.75, 0.30, 0.20, 0.35, 0.30, 0.85, 0.25, 0.45],  # Agentic systems
    [0.85, 0.50, 0.80, 0.35, 0.40, 0.60, 0.20, 0.30, 0.25, 0.55],  # Voice AI
    [0.80, 0.65, 0.95, 0.45, 0.15, 0.10, 0.80, 0.40, 0.35, 0.70],  # Backend & APIs
    [0.15, 0.90, 0.20, 0.95, 0.95, 0.05, 0.45, 0.10, 0.75, 0.15],  # Frontend & UX
    [0.50, 0.55, 0.60, 0.65, 0.35, 0.10, 0.55, 0.45, 0.90, 0.85],  # Ship & operate
]

# 03 / TOOL CALLS -----------------------------------------------------------
TOOLS = [
    ("languages.load",   ["python", "typescript", "javascript", "c"]),
    ("frontend.render",  ["next.js", "react", "tailwind", "gsap", "three.js"]),
    ("backend.serve",    ["fastapi", "supabase", "firebase", "mysql"]),
    ("model.infer",      ["pytorch", "numpy", "pandas", "llm-apis"]),
    ("agents.orchestrate", ["n8n", "tool-use", "webhooks"]),
    ("infra.deploy",     ["vercel", "aws", "netlify", "git"]),
    ("design.craft",     ["figma", "blender", "photoshop", "lightroom"]),
]

# 04 / OUTPUTS --------------------------------------------------------------
# Leave empty to use your pinned repos (falls back to top repos by stars).
# Or list repo names to force a specific order, e.g. ["repo-a", "repo-b"].
FEATURED_REPOS = []
MAX_CARDS = 4
