"""Builds the MARG Build Stage presentation (python-pptx).

Run:  python build_presentation.py   ->  MARG_Build_Stage_Presentation.pptx (same folder)
All figures are taken from docs/TESTING.md (runs on 31 Oct 2026). No credentials or real
personal data are included; screenshots show fictional demo data only.
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
OUT = HERE / "MARG_Build_Stage_Presentation.pptx"

NAVY = RGBColor(0x14, 0x2B, 0x4A)
NAVY2 = RGBColor(0x20, 0x3F, 0x65)
TEAL = RGBColor(0x13, 0xA8, 0x9E)
TEAL_D = RGBColor(0x0D, 0x89, 0x82)
BG = RGBColor(0xF5, 0xF7, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TEXT = RGBColor(0x17, 0x2B, 0x4D)
MUTED = RGBColor(0x5A, 0x6B, 0x82)
BORDER = RGBColor(0xDD, 0xE3, 0xEC)
AMBER = RGBColor(0xD5, 0x8A, 0x32)
AMBER_BG = RGBColor(0xFF, 0xF4, 0xE7)
GREEN_BG = RGBColor(0xE7, 0xF7, 0xF0)
GREEN = RGBColor(0x0F, 0x7A, 0x57)
PURPLE = RGBColor(0x6B, 0x3F, 0xA0)
PURPLE_BG = RGBColor(0xF3, 0xED, 0xFA)
BLUE_BG = RGBColor(0xEA, 0xF3, 0xFC)
FONT = "Segoe UI"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
W, H = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]
TOTAL = 15


# --------------------------------------------------------------------------- helpers
def fill(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color


def text(slide, x, y, w, h, s, size=16, bold=False, color=TEXT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
        r.font.color.rgb = color
    return tb


def bullets(slide, x, y, w, h, items, size=16, color=TEXT, gap=6):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        bold = None
        if isinstance(item, tuple):
            bold, item = item
        r0 = p.add_run()
        r0.text = "▪  "
        r0.font.size, r0.font.name = Pt(size - 2), FONT
        r0.font.color.rgb = TEAL
        if bold:
            rb = p.add_run()
            rb.text = bold + " "
            rb.font.size, rb.font.bold, rb.font.name = Pt(size), True, FONT
            rb.font.color.rgb = color
        r = p.add_run()
        r.text = item
        r.font.size, r.font.name = Pt(size), FONT
        r.font.color.rgb = color
    return tb


def box(slide, x, y, w, h, color=WHITE, line=BORDER, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    fill(s, color)
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def card(slide, x, y, w, h, title, body, accent=TEAL, title_size=16, body_size=13, color=WHITE):
    box(slide, x, y, w, h, color=color)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y + Inches(0.18), Inches(0.07), h - Inches(0.36))
    fill(bar, accent)
    bar.line.fill.background()
    text(slide, x + Inches(0.25), y + Inches(0.15), w - Inches(0.4), Inches(0.45), title, size=title_size, bold=True, color=NAVY)
    if isinstance(body, list):
        bullets(slide, x + Inches(0.22), y + Inches(0.62), w - Inches(0.35), h - Inches(0.7), body, size=body_size, gap=3)
    else:
        text(slide, x + Inches(0.25), y + Inches(0.62), w - Inches(0.4), h - Inches(0.7), body, size=body_size, color=MUTED)


def pill(slide, x, y, w, label, bg, fg, size=11):
    s = box(slide, x, y, w, Inches(0.32), color=bg, line=None, radius=0.5)
    tf = s.text_frame
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.name = Pt(size), True, FONT
    r.font.color.rgb = fg
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return s


def node(slide, x, y, w, h, title, sub, color=WHITE, title_color=NAVY, sub_color=MUTED, line=BORDER):
    s = box(slide, x, y, w, h, color=color, line=line)
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = title
    r.font.size, r.font.bold, r.font.name = Pt(15), True, FONT
    r.font.color.rgb = title_color
    for line_text in sub if isinstance(sub, list) else [sub]:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = line_text
        r2.font.size, r2.font.name = Pt(11), FONT
        r2.font.color.rgb = sub_color
    return s


def arrow(slide, x1, y1, x2, y2, label=None, color=NAVY2, label_dx=0, label_dy=-0.3):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(2)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    if label:
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        text(slide, mx - Inches(1.3) + Inches(label_dx), my + Inches(label_dy), Inches(2.6), Inches(0.5), label.split("|"), size=10, color=MUTED, align=PP_ALIGN.CENTER)
    return c


def base_slide(title, kicker=None, n=None):
    s = prs.slides.add_slide(BLANK)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    fill(bg, BG)
    bg.line.fill.background()
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), H)
    fill(band, TEAL)
    band.line.fill.background()
    if kicker:
        text(s, Inches(0.6), Inches(0.35), Inches(10), Inches(0.35), kicker.upper(), size=12, bold=True, color=TEAL_D)
    text(s, Inches(0.6), Inches(0.62), Inches(12.4), Inches(0.8), title, size=26, bold=True, color=NAVY)
    if n:
        text(s, W - Inches(1.6), H - Inches(0.45), Inches(1.3), Inches(0.3), f"MARG  ·  {n}/{TOTAL}", size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    return s


def phone(slide, img, x, y, h):
    """Screenshot in a phone-like frame."""
    from PIL import Image  # pillow ships with python-pptx

    iw, ih = Image.open(img).size
    w = int(h * iw / ih)
    frame = box(slide, x - Inches(0.08), y - Inches(0.08), w + Inches(0.16), h + Inches(0.16), color=NAVY, line=None, radius=0.06)
    frame.shadow.inherit = False
    slide.shapes.add_picture(str(img), x, y, height=h)
    return w


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# =========================================================================== 1 Title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
fill(bg, NAVY)
bg.line.fill.background()
deco = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.6), Inches(-1.8), Inches(7), Inches(7))
fill(deco, NAVY2)
deco.line.fill.background()
text(s, Inches(0.9), Inches(1.5), Inches(8), Inches(1.4), "MARG", size=72, bold=True, color=WHITE)
text(s, Inches(0.95), Inches(2.85), Inches(8), Inches(0.5), "Mentoring · Action · Reflection · Growth", size=22, color=TEAL)
text(s, Inches(0.95), Inches(3.6), Inches(7.6), Inches(1.2),
     "A mentor-focused platform that turns every classroom visit into a tracked improvement cycle — "
     "supported by two independent AI assistants.", size=18, color=RGBColor(0xDC, 0xE6, 0xF2))
pill(s, Inches(0.95), Inches(5.2), Inches(2.6), "Build Stage evaluation", TEAL, WHITE, size=12)
pill(s, Inches(3.7), Inches(5.2), Inches(5.3), "Working prototype · tested locally · not yet deployed", NAVY2, WHITE, size=12)
w = phone(s, ASSETS / "dashboard.png", Inches(9.55), Inches(0.9), Inches(5.7))
notes(s, "Status is stated up front: integrated and tested on the development machine; public deployment awaits approval.")

# =========================================================================== 2 Challenge
s = base_slide("The challenge: classroom insights rarely become improvement", "Problem statement", 2)
bullets(s, Inches(0.6), Inches(1.65), Inches(6.4), Inches(4.6), [
    ("Mentors support many teachers across many schools,", "often with long travel between them."),
    ("Observations live on paper and in chat threads,", "so learning gaps are noticed but rarely tracked to closure."),
    ("Follow-ups depend on memory:", "agreed actions, evidence and teacher responses are easily lost."),
    ("Expert guidance is hard to reach in the moment:", "national frameworks (NCF, NEP, CCE) and mentoring manuals run to thousands of pages."),
    ("Connectivity in schools is unreliable,", "so tools that need a constant connection fail exactly where work happens."),
], size=17, gap=10)
card(s, Inches(7.4), Inches(1.7), Inches(5.3), Inches(2.1), "MARG's answer",
     "One mentor app for the full cycle: visit → observation → learning gap → recommendation → action plan → follow-up with evidence — with AI help that never acts without the mentor.",
     accent=TEAL, body_size=14)
card(s, Inches(7.4), Inches(4.05), Inches(5.3), Inches(2.1), "Outcome we design for",
     "Every identified gap has an owner, a plan, evidence and a closure — visible to the mentor at a glance, online or offline.",
     accent=AMBER, body_size=14)

# =========================================================================== 3 Users
s = base_slide("Built for mentors — not a student-facing app", "Intended users", 3)
card(s, Inches(0.6), Inches(1.7), Inches(4.0), Inches(3.9), "Mentor  (primary user)", [
    "Signs in securely; sees only assigned schools",
    "Plans visits, observes, records findings",
    "Approves AI suggestions and plans",
    "Tracks follow-ups, tasks and reports",
], accent=TEAL, body_size=14)
card(s, Inches(4.75), Inches(1.7), Inches(4.0), Inches(3.9), "Administrator  (system only)", [
    "Assigns mentors to schools",
    "Creates school records",
    "No mentoring workflows",
    "Uses the API; no extra screens added",
], accent=NAVY2, body_size=14)
card(s, Inches(8.9), Inches(1.7), Inches(3.85), Inches(3.9), "Teachers & students", [
    "No accounts, no logins",
    "Teachers: subjects of mentoring; responses recorded by the mentor",
    "Students: appear only as aggregated learning gaps",
    "No student data or chatbot",
], accent=AMBER, body_size=14)
text(s, Inches(0.6), Inches(5.9), Inches(12), Inches(0.6),
     "All demonstration data is fictional (schools, teachers, observations).", size=14, color=MUTED)

# =========================================================================== 4 Architecture
s = base_slide("System architecture: four projects, one controlled entry point", "How it fits together", 4)
fe = node(s, Inches(0.6), Inches(2.75), Inches(2.6), Inches(1.5), "MARG Frontend", ["Expo · React Native + web", "offline outbox & cache"])
be = node(s, Inches(4.1), Inches(2.45), Inches(3.0), Inches(2.1), "MARG Backend", ["FastAPI · PostgreSQL", "auth · school-scoped data", "sync · reports · evidence"], color=NAVY, title_color=WHITE, sub_color=RGBColor(0xC9, 0xD6, 0xE6), line=None)
db = node(s, Inches(4.35), Inches(5.35), Inches(2.5), Inches(1.0), "PostgreSQL", "authoritative business data", color=BLUE_BG)
cc = node(s, Inches(8.2), Inches(1.45), Inches(2.6), Inches(1.45), "Classroom Coach", ["educational intelligence", "RAG Q&A · observation analysis"], color=GREEN_BG)
mi = node(s, Inches(8.2), Inches(4.1), Inches(2.6), Inches(1.45), "Mentor Intelligence", ["workflow intelligence", "10 agents · proposals"], color=PURPLE_BG)
ol = node(s, Inches(11.1), Inches(1.45), Inches(1.95), Inches(1.45), "Qwen 2.5 3B", ["Ollama (local)", "ChromaDB 33,624 chunks"], color=WHITE)
cl = node(s, Inches(11.1), Inches(4.1), Inches(1.95), Inches(1.45), "Claude", ["claude-opus-5", "Anthropic API"], color=WHITE)
arrow(s, Inches(3.2), Inches(3.5), Inches(4.1), Inches(3.5), "HTTPS + JWT")
arrow(s, Inches(5.6), Inches(4.55), Inches(5.6), Inches(5.35))
arrow(s, Inches(7.1), Inches(2.9), Inches(8.2), Inches(2.2), "service key", label_dy=-0.45)
arrow(s, Inches(7.1), Inches(4.1), Inches(8.2), Inches(4.8), "service key +|mentor identity", label_dx=-0.55, label_dy=0.2)
arrow(s, Inches(10.8), Inches(2.17), Inches(11.1), Inches(2.17))
arrow(s, Inches(10.8), Inches(4.82), Inches(11.1), Inches(4.82))
text(s, Inches(0.6), Inches(1.55), Inches(7), Inches(0.8),
     ["The app talks only to the backend. AI keys and service URLs never reach the device.",
      "The two AI systems are independent and never share data stores."], size=13, color=MUTED)
text(s, Inches(7.4), Inches(6.0), Inches(5.6), Inches(0.9),
     "Mentor Intelligence reads a per-mentor snapshot and executes approved actions only through backend APIs — never the database.",
     size=12, color=MUTED)

# =========================================================================== 5 Workflow
s = base_slide("The mentor workflow, end to end", "Core features", 5)
steps = [("Plan visit", "assigned schools,\ntimetables"), ("Observe", "notes, photos,\nevidence"), ("Analyse", "findings &\nlearning gaps"),
         ("Recommend", "mentor approves\nwhat is official"), ("Action plan", "steps with owners\n& dates"), ("Follow up", "teacher response,\nevidence, verify")]
x = Inches(0.6)
for i, (t, sub) in enumerate(steps):
    sh = s.shapes.add_shape(MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, x, Inches(1.8), Inches(2.15), Inches(1.0))
    fill(sh, NAVY if i % 2 == 0 else TEAL_D)
    sh.line.fill.background()
    tf = sh.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = tf.paragraphs[0].add_run()
    r.text = t
    r.font.size, r.font.bold, r.font.name = Pt(15), True, FONT
    r.font.color.rgb = WHITE
    text(s, x + Inches(0.15), Inches(2.9), Inches(1.9), Inches(0.8), sub.split("\n"), size=12, color=MUTED, align=PP_ALIGN.CENTER)
    x += Inches(2.05)
feats = [
    ("Dashboard & reports", "Live counts, activity trends and learning-gap reports computed from records."),
    ("Tasks & schedule", "Priority-scored tasks, visit agenda, time proposals and daily workload."),
    ("Notifications", "Reminders for overdue tasks, upcoming visits, due steps and evidence to verify."),
    ("Evidence", "Photo/PDF evidence on observations and follow-ups, validated and access-controlled."),
]
for i, (t, b) in enumerate(feats):
    card(s, Inches(0.6) + i * Inches(3.13), Inches(4.0), Inches(2.95), Inches(2.3), t, b, accent=TEAL if i % 2 == 0 else AMBER, body_size=13)

# =========================================================================== 6 Classroom Coach
s = base_slide("Classroom Coach: grounded educational intelligence", "AI assistant 1 · local LLM + RAG", 6)
pipeline = [("Question or\nobservation", BLUE_BG), ("Embed\nMiniLM-L6-v2", WHITE), ("Retrieve\nChromaDB", WHITE), ("Filter\nrelevance · dedupe", WHITE), ("Generate\nQwen 2.5 3B", GREEN_BG), ("Answer\n+ sources [S1…]", BLUE_BG)]
x = Inches(0.6)
for i, (t, c) in enumerate(pipeline):
    node(s, x, Inches(1.7), Inches(1.75), Inches(1.15), t.split("\n")[0], t.split("\n")[1], color=c)
    if i < len(pipeline) - 1:
        arrow(s, x + Inches(1.75), Inches(2.27), x + Inches(2.0), Inches(2.27))
    x += Inches(2.0)
bullets(s, Inches(0.6), Inches(3.3), Inches(7.4), Inches(3.4), [
    ("Knowledge base:", "167 educational documents (NCF, NEP, CCE, mentoring and observation manuals) → 33,624 passages."),
    ("Calibrated relevance:", "on-topic queries score 0.18–0.40; off-topic ≥ 0.75; cut-off 0.60. Nothing relevant → it says so and does not answer."),
    ("Honest citations:", "real document titles and pages; citations to sources not retrieved are removed."),
    ("Observation analysis:", "schema-constrained JSON — findings with quoted evidence, gaps, recommendations — saved only as “AI suggested”."),
    ("Privacy:", "only subject, grade, topic and notes are sent — never teacher or student names. Runs locally (Ollama)."),
], size=14, gap=7)
phone(s, ASSETS / "coach-answer.png", Inches(9.4), Inches(3.15), Inches(3.9))
text(s, Inches(8.3), Inches(3.3), Inches(1.1), Inches(1.5), ["Live", "answer", "≈ 7 s"], size=12, color=MUTED, align=PP_ALIGN.CENTER)

# =========================================================================== 7 Mentor Intelligence
s = base_slide("Mentor Intelligence: Claude-powered workflow agents", "AI assistant 2 · claude-opus-5", 7)
agents = ["Daily plan", "Weekly plan", "Task prioritisation", "Workload", "Schedule check", "Visit planning", "Follow-up analysis", "Activity report", "Teacher message draft"]
for i, a in enumerate(agents):
    col, row = i % 3, i // 3
    pill(s, Inches(0.6) + col * Inches(2.3), Inches(1.75) + row * Inches(0.48), Inches(2.15), a, PURPLE_BG, PURPLE, size=12)
text(s, Inches(0.6), Inches(3.25), Inches(7), Inches(0.35), "How every agent run works", size=16, bold=True, color=NAVY)
flow = [("1  Snapshot", "mentor's records via\nbackend service API"), ("2  Compute", "deterministic scores,\nplans, conflicts"), ("3  Claude", "validated JSON insights,\nlabelled as AI"), ("4  Propose", "actions wait for\nmentor approval")]
for i, (t, b) in enumerate(flow):
    node(s, Inches(0.6) + i * Inches(1.78), Inches(3.7), Inches(1.6), Inches(1.35), t, b.split("\n"), color=WHITE)
    if i < 3:
        arrow(s, Inches(0.6) + i * Inches(1.78) + Inches(1.6), Inches(4.37), Inches(0.6) + (i + 1) * Inches(1.78), Inches(4.37))
bullets(s, Inches(0.6), Inches(5.3), Inches(7.3), Inches(1.6), [
    "If Claude is unavailable, the computed analysis is still returned (ai_status).",
    "Teacher names become placeholders before any Claude call; token budgets and per-call usage are recorded.",
    "Refusal fallback enabled: server-side, to claude-opus-4-8 only if a request is declined.",
], size=13, gap=4)
phone(s, ASSETS / "mentor-ai.png", Inches(9.4), Inches(1.6), Inches(5.2))

# =========================================================================== 8 Safeguards
s = base_slide("Safeguards: humans decide, data stays scoped, actions are audited", "Responsible AI & security", 8)
card(s, Inches(0.6), Inches(1.7), Inches(3.95), Inches(4.6), "Human approval", [
    "AI findings & recommendations start as “AI suggested”",
    "Action plans only from mentor-approved recommendations",
    "Mentor AI actions are proposals; only the owning mentor can approve",
    "Teacher messages are drafts the mentor sends personally",
], accent=TEAL, body_size=13)
card(s, Inches(4.7), Inches(1.7), Inches(3.95), Inches(4.6), "Role & school-level access", [
    "Argon2 passwords; JWT + rotating refresh tokens; logout",
    "Login rate limiting; timing-safe sign-in",
    "Every query filtered to the mentor's assigned schools (deny by default)",
    "Admin-only school assignment; service keys between services",
], accent=NAVY2, body_size=13)
card(s, Inches(8.8), Inches(1.7), Inches(3.95), Inches(4.6), "Auditability & data care", [
    "Approval, execution and policy events in an audit log",
    "Every Claude call logged: model, tokens, latency, cost",
    "Versioned records; request IDs in all logs",
    "Uploads checked by file signature; no public file URLs",
], accent=AMBER, body_size=13)
text(s, Inches(0.6), Inches(6.45), Inches(12), Inches(0.5),
     "Verified live: proposals changed nothing until approved · another mentor's approval attempt → 403 · rejection changed nothing.",
     size=13, bold=True, color=GREEN)

# =========================================================================== 9 Offline
s = base_slide("Offline-first: works in the classroom, syncs safely later", "Reliability", 9)
seq = [("Mentor edits offline", "visit status, observation,\ntask, teacher response"), ("Saved on device", "persisted outbox +\ncached screens"),
       ("Reconnect", "automatic push to\n/sync/push"), ("Backend applies", "same business rules &\nschool scope as online"), ("Outcome per change", "synced · conflict ·\nfailed (with reason)")]
for i, (t, b) in enumerate(seq):
    node(s, Inches(0.6) + i * Inches(2.5), Inches(1.75), Inches(2.25), Inches(1.4), t, b.split("\n"), color=WHITE if i % 2 else BLUE_BG)
    if i < 4:
        arrow(s, Inches(0.6) + i * Inches(2.5) + Inches(2.25), Inches(2.45), Inches(0.6) + (i + 1) * Inches(2.5), Inches(2.45))
bullets(s, Inches(0.6), Inches(3.55), Inches(7.6), Inches(3.2), [
    ("No silent overwrites:", "each change carries the version the device saw; if the server moved on, it becomes a conflict for the mentor to resolve."),
    ("No duplicates:", "client-generated IDs and idempotency keys make re-sending safe."),
    ("Partial failure is visible:", "one rejected change never blocks the rest; reasons are shown on the Sync screen."),
    ("Pull sync:", "cursor-paginated changes with tombstones for deleted records."),
], size=14, gap=8)
phone(s, ASSETS / "sync.png", Inches(9.4), Inches(3.4), Inches(3.75))

# =========================================================================== 10 Testing
s = base_slide("Testing evidence (all suites actually run)", "Quality", 10)
rows = [("Suite", "Scope", "Result"),
        ("Backend", "auth, school isolation, workflow, sync, AI integration, storage", "49 passed"),
        ("Classroom Coach", "API contract, grounding, errors (mocked LLM)", "8 passed"),
        ("Mentor Intelligence", "agents, approvals, adapter, gateway auth, fallback", "132 passed"),
        ("Frontend (Jest)", "API layer, offline outbox, login → dashboard screen", "9 passed"),
        ("Browser E2E (Playwright)", "14 screens, task persistence, live Coach answer", "4 passed"),
        ("Total automated", "", "202 passed")]
tbl = s.shapes.add_table(len(rows), 3, Inches(0.6), Inches(1.65), Inches(7.6), Inches(3.9)).table
tbl.columns[0].width, tbl.columns[1].width, tbl.columns[2].width = Inches(2.2), Inches(4.0), Inches(1.4)
for r, row in enumerate(rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = val or " "
        run = cell.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.name = Pt(12), FONT
        run.font.bold = r in (0, len(rows) - 1) or c == 2
        run.font.color.rgb = WHITE if r == 0 else (GREEN if c == 2 else TEXT)
        fill(cell, NAVY if r == 0 else (GREEN_BG if r == len(rows) - 1 else (WHITE if r % 2 else BG)))
card(s, Inches(8.5), Inches(1.65), Inches(4.25), Inches(2.45), "Live Claude workflow test", [
    "5 agents on demo data via backend → claude-opus-5",
    "All structured outputs valid; 5–26 s each",
    "15,541 tokens · ≈ US$0.19 · no errors",
], accent=PURPLE, body_size=13)
card(s, Inches(8.5), Inches(4.3), Inches(4.25), Inches(2.25), "Live Classroom Coach", [
    "Grounded answer with sources ≈ 7 s",
    "Observation analysis ≈ 18 s on local GPU",
    "Off-topic question → “no relevant knowledge”",
], accent=TEAL, body_size=13)
text(s, Inches(0.6), Inches(5.75), Inches(7.6), Inches(0.9),
     ["Plus 2 live Coach tests against the real model and knowledge base, and a live",
      "refusal-fallback check (served by claude-opus-5). Run on 31 Oct 2026."], size=12, color=MUTED)

# =========================================================================== 11 Demo scenarios
s = base_slide("Demo scenarios for evaluators", "Try it", 11)
scen = [
    ("1  The mentor's day", "Sign in → live dashboard → reminders → school, teachers and timetable. Only assigned schools are visible."),
    ("2  Observation to plan", "Analyse a Science observation with the Coach → keep suggestions → approve → create and approve an action plan."),
    ("3  Follow-up with evidence", "Record the teacher's response, upload a photo, verify and close the follow-up."),
    ("4  Ask the Coach", "A teaching question returns cited sources; an off-topic question is declined honestly."),
    ("5  Mentor AI + approval", "Daily plan and visit planning → approve a proposed visit → it appears in Visits; a rejected one changes nothing."),
]
for i, (t, b) in enumerate(scen):
    col, row = i % 2, i // 2
    if i == 4:
        col, row = 0, 2
    card(s, Inches(0.6) + col * Inches(4.25), Inches(1.65) + row * Inches(1.7), Inches(4.05), Inches(1.55), t, b,
         accent=[TEAL, AMBER, NAVY2, TEAL, PURPLE][i], title_size=15, body_size=12)
phone(s, ASSETS / "observations.png", Inches(9.6), Inches(1.6), Inches(5.2))
text(s, Inches(0.6), Inches(6.85), Inches(8.5), Inches(0.4), "Fictional demo workspace · step-by-step guide in docs/DEMO_GUIDE.md · credentials shared privately", size=11, color=MUTED)

# =========================================================================== 12 Limitations
s = base_slide("Implemented vs. still pending", "Honest status", 12)
card(s, Inches(0.6), Inches(1.65), Inches(6.0), Inches(4.95), "Implemented & tested", [
    "Secure mentor login, school-scoped data, admin-only assignment",
    "Full workflow persisted in PostgreSQL; evidence storage (local / S3)",
    "Classroom Coach RAG + observation analysis with approval",
    "Mentor AI agents on real data; proposal approval loop",
    "Offline outbox with conflict detection; notifications; reports",
    "Deployment configuration written (Docker Compose, HTTPS, backups)",
], accent=GREEN, body_size=17, color=WHITE)
card(s, Inches(6.8), Inches(1.65), Inches(5.95), Inches(4.95), "Pending / limitations", [
    "Not deployed publicly; Docker images not yet built on a server",
    "No native Android/iOS device test yet (web + mobile viewport tested)",
    "WhatsApp sending via deep link only (no provider API)",
    "PDF evidence upload not in the app UI (photos only)",
    "Mentor AI: duplicate proposals across runs; AI text may show school IDs",
    "Coach on CPU: 20–60 s answers; knowledge base has duplicate PDFs, no OCR",
], accent=AMBER, body_size=17, color=WHITE)

# =========================================================================== 13 Deployment & roadmap
s = base_slide("Deployment feasibility and roadmap", "Next steps", 13)
dep = [("Edge", "Caddy · HTTPS ·\nweb app"), ("Backend + worker", "FastAPI"), ("PostgreSQL", "private; nightly\nbackups"), ("Classroom Coach", "Ollama + Chroma\nvolume"), ("Mentor Intelligence", "Claude API")]
text(s, Inches(0.6), Inches(1.6), Inches(12), Inches(0.4), "Prepared: one VM (16 GB RAM) with Docker Compose + S3-compatible storage — awaiting approval, nothing purchased", size=14, bold=True, color=NAVY)
for i, (t, b) in enumerate(dep):
    node(s, Inches(0.6) + i * Inches(2.5), Inches(2.15), Inches(2.3), Inches(1.15), t, b.split("\n"), color=WHITE if i % 2 else BLUE_BG)
text(s, Inches(0.6), Inches(3.4), Inches(12), Inches(0.4),
     "Estimated VM cost about US$40–150/month (2026 prices vary — to be verified); object storage within free tier for the demo; Claude usage capped by token budgets.",
     size=12, color=MUTED)
road = [("Now → evaluation", ["Server dry run & HTTPS", "Private repo + evaluator access", "Demo video"], TEAL),
        ("Next", ["Android build (EAS)", "PDF evidence picker", "De-duplicate proposals", "Offline browser E2E"], NAVY2),
        ("Later (planned)", ["WhatsApp provider integration", "Push notifications", "Supervisor views (with approval)", "Knowledge base re-ingest with OCR"], PURPLE)]
for i, (t, items, c) in enumerate(road):
    card(s, Inches(0.6) + i * Inches(4.15), Inches(4.0), Inches(3.95), Inches(2.6), t, items, accent=c, body_size=13)

# =========================================================================== 14 Integration opportunities
s = base_slide("Integration opportunities", "Beyond the prototype", 14)
ops = [
    ("State school information systems", "Import schools, teachers and timetables instead of manual setup (backend APIs are ready)."),
    ("Teacher communication", "Connect an official WhatsApp Business provider to the existing queue and approval flow."),
    ("Knowledge partners", "Add state curricula and local-language materials to the Coach knowledge base."),
    ("Programme dashboards", "Aggregated, anonymised reports for district teams — only with consent and approval."),
]
for i, (t, b) in enumerate(ops):
    card(s, Inches(0.6) + (i % 2) * Inches(6.15), Inches(1.7) + (i // 2) * Inches(2.35), Inches(5.95), Inches(2.15), t, b, accent=[TEAL, AMBER, NAVY2, PURPLE][i], body_size=14)

# =========================================================================== 15 Close
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
fill(bg, NAVY)
bg.line.fill.background()
text(s, Inches(0.9), Inches(2.2), Inches(11.5), Inches(1.2), "Mentoring that leads to action.", size=44, bold=True, color=WHITE)
text(s, Inches(0.95), Inches(3.5), Inches(11), Inches(1.2),
     ["Four integrated projects · two independent AI assistants · humans in control.",
      "Tested end to end on a local stack; public deployment follows approval."], size=20, color=RGBColor(0xC9, 0xD6, 0xE6))
pill(s, Inches(0.95), Inches(5.0), Inches(3.2), "Docs: README · ARCHITECTURE · TESTING", TEAL, WHITE, size=12)

assert len(prs.slides) == TOTAL, len(prs.slides)
prs.save(OUT)
print(f"saved {OUT} ({len(prs.slides)} slides)")
