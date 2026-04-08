#!/usr/bin/env python3
"""
Alejandro – Coaching Documentation Assistant
Demo script for Francisco Gonima
"""

import anthropic
import os
import sys

# ── API KEY ───────────────────────────────────────────────────────────────────
# Set ANTHROPIC_API_KEY in your environment, e.g.:
#   export ANTHROPIC_API_KEY="sk-ant-..."
# ─────────────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    sys.exit("Error: Set ANTHROPIC_API_KEY environment variable before running."
             "\n  export ANTHROPIC_API_KEY=\"sk-ant-...\"")

client = anthropic.Anthropic(api_key=API_KEY)

# ── FICTIONAL CLIENT ──────────────────────────────────────────────────────────

CLIENT_NAME   = "Marcus Webb"
CLIENT_ROLE   = "VP of Operations, Meridian Group"
SESSION_NUM   = 4
SESSION_DATE  = "April 3, 2026"

# ── PAST SESSIONS (pre-loaded into system) ────────────────────────────────────

PAST_SESSIONS = [
    {
        "num": 1,
        "date": "January 14, 2026",
        "summary": """
Themes: Leadership identity transition — moving from individual contributor to executive.
Marcus articulated feeling "stuck between doing and directing." Difficulty letting go of
operational tasks he's historically owned.

Tensions: Strong pull between wanting to be seen as capable/hands-on vs. need to delegate
to scale. Expresses frustration that his team "can't seem to do things right the first time."

Commitments: Committed to restructuring his direct reports by end of Q1 — specifically moving
two senior managers (Sarah and Dev) to lead their own sub-teams, reducing his oversight span
from 9 to 5 reports.

Notable: First use of "accountable" in relation to his team — framed negatively ("they aren't
holding themselves accountable"). Francisco flagged for future tracking.
        """.strip()
    },
    {
        "num": 2,
        "date": "February 4, 2026",
        "summary": """
Themes: Conflict avoidance, feedback delivery. Marcus described rewriting a direct report's
deliverable rather than returning it with feedback. "It was faster that way."

Tensions: Intellectually knows delegation requires tolerating imperfect interim outputs.
Emotionally resistant to watching others struggle. Restructuring commitment from Session 1
was not raised.

Commitments: Agreed to give one piece of developmental feedback to a direct report before
next session, without rewriting their work.

Notable: Language around accountability shifted — now framing it as two-way ("I need to
give them a chance to be accountable"). Francisco flagged gap between stated commitment
(restructuring) and zero update.
        """.strip()
    },
    {
        "num": 3,
        "date": "March 11, 2026",
        "summary": """
Themes: Delegation as trust, psychological safety. Marcus's underlying belief that if things
go wrong, it reflects on him personally. "I'm the one who has to answer for it."

Tensions: Wants team to take ownership but withholds the authority that would make ownership
possible. Team restructuring not raised again despite being the stated Q1 goal.

Commitments: Committed to having a direct conversation with Sarah and Dev about expanded
scope — not formal restructuring yet, but "planting the flag."

Notable: First unprompted use of "trust" in relation to team ("I think I need to trust them
more, I just don't know if they're ready"). Marked shift from Session 1 where accountability
was entirely externalized.
        """.strip()
    }
]

# ── NEW SESSION NOTES (messy, realistic) ──────────────────────────────────────

NEW_SESSION_NOTES = """
april 3 call w marcus – about 55 min

started late, he seemed distracted. said things have been "hectic" with Q1 close.

came back to the team thing. said he DID have the conversation with sarah and dev – happened
about 2 weeks ago. went better than expected. dev was receptive, sarah "pushed back a little"
but marcus thinks she'll come around.

interesting – he said he DIDN'T tell them it was about restructuring formally, just framed it
as "expanded ownership." asked him why and he got a bit defensive – "i didn't want to create
anxiety." we talked about that for a while. i think he's managing his own anxiety more
than theirs.

accountability came up again. one of his managers missed a deadline and instead of addressing
it he rescheduled the check-in. "i didn't want to have the conversation when things were
already stressful." classic avoidance, different form.

he did mention the feedback experiment from last time – said he tried it with one person, felt
uncomfortable but did it. called it "surprisingly okay." small win.

commitments:
- address the missed deadline directly with the manager before end of week
- follow up with sarah specifically on her pushback – get clearer on what her hesitation is

overall: progress on trust/delegation but avoidance pattern still showing up, now as delay vs.
rewrite. Q1 restructuring officially missed but momentum exists.
""".strip()

# ── PROMPTS ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Alejandro, a coaching documentation assistant for Francisco Gonima,
an executive coach. You help Francisco structure and synthesize session material.

You understand coaching dynamics: themes, tensions, commitments, behavioral patterns,
and longitudinal client trajectories.

Francisco tracks:
- Recurring themes and how they evolve
- Tensions (internal contradictions the client navigates)
- Explicit commitments and whether they are followed through
- Language shifts (how framing changes over time)
- Avoidance patterns

When referencing prior sessions, cite by session number and date. Be precise.
Surface evidence — do not replace Francisco's judgment."""

CURRENT_SESSION_PROMPT = f"""Raw notes from today's session with {CLIENT_NAME} ({CLIENT_ROLE}).

SESSION NOTES (Session {SESSION_NUM}, {SESSION_DATE}):
{NEW_SESSION_NOTES}

Generate a structured session summary:
1. Themes
2. Tensions
3. Commitments made this session
4. Notable shifts (language, framing, behavior)
5. Open / avoided items

Be concise. This is a working document, not a report."""

def build_cross_session_prompt():
    prior = "\n\n---\n\n".join(
        f"SESSION {s['num']} ({s['date']}):\n{s['summary']}"
        for s in PAST_SESSIONS
    )
    return f"""Prior session summaries for {CLIENT_NAME}, plus today's raw notes.

PRIOR SESSIONS:
{prior}

TODAY'S NOTES (Session {SESSION_NUM}, {SESSION_DATE}):
{NEW_SESSION_NOTES}

Generate a cross-session brief:
1. Open commitments from prior sessions — what was committed, what happened (cite session + date)
2. Recurring patterns — themes that keep surfacing (cite sessions)
3. Language trajectory — how framing has shifted across sessions (cite sessions)
4. What this session changed — what moved, what didn't
5. Suggested focus for next session — 2-3 areas based on full trajectory

Cite sessions by number and date throughout."""

# ── OUTPUT HELPERS ────────────────────────────────────────────────────────────

DIVIDER = "─" * 62

def header(title):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)

def section(label, text):
    print(f"\n{label}\n")
    print(text)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'═'*62}")
    print(f"  ALEJANDRO  |  Coaching Documentation Assistant")
    print(f"  Client: {CLIENT_NAME}  |  Session {SESSION_NUM}  |  {SESSION_DATE}")
    print(f"{'═'*62}")

    # ── Step 1: Current session summary ──────────────────────────────────────
    header("STEP 1 OF 2  —  Current Session Summary")
    print("\n  Processing notes...\n")

    r1 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": CURRENT_SESSION_PROMPT}]
    )
    summary = r1.content[0].text
    print(summary)

    # ── Step 2: Cross-session brief ───────────────────────────────────────────
    header("STEP 2 OF 2  —  Cross-Session Brief  (Pro tier)")
    print("\n  Retrieving prior sessions and assembling brief...\n")

    r2 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_cross_session_prompt()}]
    )
    brief = r2.content[0].text
    print(brief)

    # ── Save as HTML and open in browser ─────────────────────────────────────
    def md_to_html(text):
        import re
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        lines, out, in_list = text.split('\n'), [], False
        for line in lines:
            if re.match(r'^(\d+\.|-)\s', line):
                if not in_list:
                    out.append('<ul>')
                    in_list = True
                out.append(f'<li>{re.sub(r"^(\d+\.|-)\s", "", line)}</li>')
            else:
                if in_list:
                    out.append('</ul>')
                    in_list = False
                if line.strip() == '':
                    out.append('<br>')
                else:
                    out.append(f'<p>{line}</p>')
        if in_list:
            out.append('</ul>')
        return '\n'.join(out)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Alejandro | {CLIENT_NAME}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 820px; margin: 48px auto; padding: 0 24px;
         color: #1a1a1a; background: #fafafa; }}
  .header {{ background: #1a1a1a; color: #fff; padding: 24px 32px;
             border-radius: 8px; margin-bottom: 32px; }}
  .header h1 {{ margin: 0 0 4px; font-size: 20px; letter-spacing: 0.05em; }}
  .header p  {{ margin: 0; font-size: 13px; color: #aaa; }}
  .card {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
           padding: 28px 32px; margin-bottom: 24px; }}
  .card h2 {{ font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
              color: #888; margin: 0 0 20px; padding-bottom: 12px;
              border-bottom: 1px solid #e5e5e5; }}
  .tag {{ display: inline-block; background: #f0f0f0; border-radius: 4px;
          font-size: 11px; padding: 2px 8px; margin-right: 6px; color: #555; }}
  .pro-tag {{ background: #1a1a1a; color: #fff; }}
  p {{ margin: 0 0 10px; line-height: 1.65; font-size: 15px; }}
  ul {{ margin: 0 0 10px; padding-left: 20px; }}
  li {{ margin-bottom: 6px; line-height: 1.65; font-size: 15px; }}
  strong {{ color: #111; }}
  cite {{ font-size: 12px; color: #888; font-style: normal; }}
</style>
</head>
<body>

<div class="header">
  <h1>ALEJANDRO &nbsp;|&nbsp; Coaching Documentation Assistant</h1>
  <p>Client: {CLIENT_NAME} &nbsp;&middot;&nbsp; {CLIENT_ROLE} &nbsp;&middot;&nbsp;
     Session {SESSION_NUM} &nbsp;&middot;&nbsp; {SESSION_DATE}</p>
</div>

<div class="card">
  <h2><span class="tag">Basic</span> Current Session Summary</h2>
  {md_to_html(summary)}
</div>

<div class="card">
  <h2><span class="tag pro-tag">Pro</span> Cross-Session Brief</h2>
  {md_to_html(brief)}
</div>

</body>
</html>"""

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alejandro_output.html")
    with open(out_path, "w") as f:
        f.write(html)

    print(f"\n{'═'*62}")
    print(f"  Opening in browser...")
    print(f"{'═'*62}\n")
    os.system(f'open "{out_path}"')

if __name__ == "__main__":
    run()
