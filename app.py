import os
import re
import collections
import streamlit as st

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import openai
except Exception:
    openai = None

docx = None

st.set_page_config(page_title="AI Resume Optimizer", layout="centered")

st.title("🤖 AI Resume Optimizer")
st.write("Optimize your resume with AI — Product Demo for AI PM roles")

resume = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

position = st.text_input(
    "Target Position",
    placeholder="e.g. AI Product Manager Intern"
)

jd = st.text_area(
    "Paste Job Description",
    placeholder="Paste the job description here..."
)

# OpenAI key should be provided via Streamlit secrets for deployments.
# Add `OPENAI_API_KEY` in Streamlit Cloud secrets (or set in st.secrets.toml locally).
openai_key = None
if "OPENAI_API_KEY" in st.secrets:
    openai_key = st.secrets["OPENAI_API_KEY"]
elif st.secrets.get("openai", {}).get("api_key"):
    openai_key = st.secrets.get("openai", {}).get("api_key")
else:
    st.info("To enable stronger AI rewrites, add your OpenAI key in Streamlit Secrets as OPENAI_API_KEY.")


# Cache extracted resume text in session state to avoid repeated parsing
def get_cached_resume_text(uploaded_file):
    if not uploaded_file:
        return ""
    key = f"resume:{uploaded_file.name}:{uploaded_file.size}"
    if st.session_state.get('resume_cache_key') != key:
        st.session_state['resume_cache_key'] = key
        st.session_state['resume_text'] = extract_pdf_text(uploaded_file)
    return st.session_state.get('resume_text', '')


def extract_pdf_text(uploaded_file):
    if not uploaded_file:
        return ""
    if PdfReader is None:
        try:
            return uploaded_file.getvalue().decode(errors="ignore")
        except Exception:
            return ""
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        texts = []
        for p in reader.pages:
            texts.append(p.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        try:
            return uploaded_file.getvalue().decode(errors="ignore")
        except Exception:
            return ""
    # If pypdf yielded empty text, try pdfminer as a fallback
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.getvalue()
        try:
            from pdfminer.high_level import extract_text as pm_extract_text
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(raw)
                tmp.flush()
                text = pm_extract_text(tmp.name)
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            if text and text.strip():
                return text
        except Exception:
            pass
    except Exception:
        pass


STOPWORDS = set([
    "the", "and", "to", "of", "a", "in", "for", "with", "on", "by",
    "an", "be", "is", "are", "as", "that", "this", "from", "or",
    "we", "you", "your", "our", "at", "it",
])


def get_keywords(text, top_n=40):
    words = re.findall(r"[a-zA-Z0-9+#-]+", text.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 2]
    cnt = collections.Counter(words)
    return [w for w, _ in cnt.most_common(top_n)]


def parse_jd_sections(jd_text):
    lines = [l.strip() for l in jd_text.splitlines() if l.strip()]
    sections = {"requirements": [], "responsibilities": [], "preferred": [], "other": []}
    cur = "other"
    for l in lines:
        low = l.lower()
        if any(k in low for k in ["requirement", "requirements", "qualifications", "must have", "required"]):
            cur = "requirements"
            continue
        if any(k in low for k in ["responsibilit", "responsibilities", "you will"]):
            cur = "responsibilities"
            continue
        if any(k in low for k in ["prefer", "preferred", "nice to have", "bonus"]):
            cur = "preferred"
            continue
        sections[cur].append(l)
    return sections


def compute_match(resume_text, jd_text):
    jd_k = get_keywords(jd_text, top_n=60)
    res_words = set(re.findall(r"[a-zA-Z0-9+#-]+", resume_text.lower()))
    matched = [k for k in jd_k if k in res_words]
    score = int(len(matched) / max(1, len(jd_k)) * 100)
    missing = [k for k in jd_k if k not in res_words]
    return score, matched, missing


def split_resume_sections(text):
    # naive split by common headings
    headings = ["experience", "work experience", "professional experience", "education", "skills", "projects", "summary", "certifications"]
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    sections = {"experience": [], "education": [], "skills": [], "other": []}
    cur = "other"
    for l in lines:
        low = l.lower()
        matched_heading = None
        for h in headings:
            if low.startswith(h):
                matched_heading = h
                break
        if matched_heading:
            if "education" in matched_heading:
                cur = "education"
            elif "skill" in matched_heading:
                cur = "skills"
            elif "experience" in matched_heading:
                cur = "experience"
            else:
                cur = "other"
            continue
        sections[cur].append(l)
    return sections


def extract_experience_bullets(exp_lines):
    # group lines into bullets: lines starting with -, •, * or separated by indent
    bullets = []
    for l in exp_lines:
        stripped = re.sub(r'^[-\*\u2022]\s*', '', l).strip()
        if len(stripped) > 10:
            bullets.append(stripped)
    return bullets


ACTION_VERBS = ["Led", "Developed", "Designed", "Built", "Improved", "Managed", "Implemented", "Analyzed", "Created", "Owned", "Drove", "Optimized"]


def improve_bullet_demo(bullet, jd_keywords):
    # Context-aware demo rewrite using the actual bullet and JD keywords.
    b = re.sub(r'^[\-\*\u2022]\s*', '', bullet).strip()

    # common technologies / tools to detect
    TECHNOLOGIES = [
        'tableau', 'sql', 'python', 'pandas', 'tensorflow', 'pytorch', 'spark', 'hadoop',
        'excel', 'looker', 'powerbi', 'keras', 'scikit-learn', 'jira', 'confluence', 'figma'
    ]

    # pick a strong verb: prefer original verb if useful
    tokens = b.split()
    orig_verb = tokens[0].rstrip(',:').lower() if tokens else ''
    verb = None
    if orig_verb and orig_verb not in STOPWORDS and len(orig_verb) > 1:
        verb = orig_verb.capitalize()
    else:
        verb = ACTION_VERBS[hash(b) % len(ACTION_VERBS)]

    # find technologies mentioned in original
    tools = []
    for t in TECHNOLOGIES:
        if re.search(rf"(?i)\b{re.escape(t)}\b", b):
            tools.append(t)

    # extract a short object / focus from original (phrases after verb)
    obj_match = re.search(r"(?:{}\s+)(.+)".format(re.escape(tokens[0])) if tokens else r"(.+)", b, re.IGNORECASE)
    if obj_match:
        obj_phrase = obj_match.group(1).strip()
        # trim to a reasonable length
        obj = ' '.join(obj_phrase.split()[:8]).rstrip('.,')
    else:
        obj = b

    # determine outcome language from JD keywords
    outcome_terms = [k for k in jd_keywords if k.lower() in 'business product metrics impact insights retention engagement conversion revenue growth efficiency accuracy'.split()]
    outcome = ''
    if outcome_terms:
        outcome = ' to ' + (' and '.join(outcome_terms[:2]))
    else:
        # fallback outcome suggestions based on role
        outcome = ' to generate actionable insights for product decisions'

    # assemble tools phrase
    tools_phrase = ''
    if tools:
        tools_phrase = ' using ' + ', '.join([t.capitalize() for t in tools])

    # build improved bullet with concrete phrasing
    improved = f"{verb} {obj}{tools_phrase}{outcome}, enabling data-informed product prioritization and stakeholder alignment."

    # if the improved bullet is too similar to original, add explicit specificity
    if re.sub(r'\W+', '', improved.lower()) == re.sub(r'\W+', '', b.lower()):
        improved = f"{verb} {obj}{tools_phrase}{outcome}, focused on driving measurable product impact."

    return improved


def improve_bullet_openai(bullet, jd, api_key):
    if openai is None:
        return improve_bullet_demo(bullet, get_keywords(jd, 20))
    openai.api_key = api_key
    prompt = (
        "You are an expert resume writer optimizing bullets for an AI Product Manager role.\n"
        "Rewrite the following resume bullet to be achievement-focused, specific, and aligned to the provided job description.\n"
        "Do NOT add fabricated numeric metrics. Use concrete language and include relevant keywords from the JD. Return a single optimized bullet only.\n\n"
        f"Job description:\n{jd}\n\n"
        f"Original bullet:\n{bullet}\n\n"
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=160,
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
        # ensure single-line
        return ' '.join(text.splitlines())
    except Exception:
        return improve_bullet_demo(bullet, get_keywords(jd, 20))

def get_added_keywords(original, improved, jd_keywords=None, max_items=10):
    o_tokens = set(re.findall(r"[a-zA-Z0-9+#-]+", original.lower()))
    i_tokens = re.findall(r"[a-zA-Z0-9+#-]+", improved.lower())
    added = [t for t in i_tokens if t not in o_tokens and t not in STOPWORDS]
    # prefer tokens that also appear in JD keywords
    jd_set = set(k.lower() for k in (jd_keywords or []))
    added_unique = []
    for t in added:
        if t not in added_unique:
            added_unique.append(t)
    # prioritize jd keywords first
    jd_added = [t for t in added_unique if t in jd_set]
    other_added = [t for t in added_unique if t not in jd_set]
    picks = jd_added + other_added
    return picks[:max_items]


def highlight_improved(improved, highlights):
    # highlights: iterable of lowercase tokens to highlight
    text = improved
    for h in sorted(set(highlights), key=lambda s: -len(s)):
        if not h:
            continue
        pattern = re.compile(rf"(?i)\b{re.escape(h)}\b")
        text = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)
    return text


def generate_improvements(resume_text, jd_text, use_openai=False, api_key=None):
    score, matched, missing = compute_match(resume_text, jd_text)
    jd_keywords = get_keywords(jd_text, top_n=60)
    sections = split_resume_sections(resume_text)
    exp_bullets = extract_experience_bullets(sections.get('experience', []))
    improved = []
    added_keywords_per_bullet = []
    for b in exp_bullets:
        if use_openai and api_key:
            nb = improve_bullet_openai(b, jd_text, api_key)
        else:
            nb = improve_bullet_demo(b, jd_keywords)
        if nb.strip().lower() == b.strip().lower():
            nb = nb + ' (refined)'
        # compute added keywords
        added = get_added_keywords(b, nb, jd_keywords)
        improved.append(nb)
        added_keywords_per_bullet.append(added)

    return {
        'score': score,
        'matched': matched,
        'missing': missing,
        'original_bullets': exp_bullets,
        'improved_bullets': improved,
        'added_keywords': added_keywords_per_bullet,
        'jd_keywords': jd_keywords,
    }


st.markdown('**Workflow:** Upload Resume → Paste JD → Analyze → Generate')


if st.button('Analyze Resume'):
    if not (resume and jd and position):
        st.warning('Please upload resume PDF, paste the job description, and enter target position.')
    else:
        with st.spinner('Extracting resume and analyzing JD...'):
            # use cached extraction to avoid repeated parsing
            resume_text = get_cached_resume_text(resume)
            jd_sections = parse_jd_sections(jd)
            score, matched, missing = compute_match(resume_text, jd)

        # Debugging info: show extracted text length and preview used for analysis
        st.subheader('Resume extraction debug')
        st.write(f"Extracted resume text length: {len(resume_text)} characters")
        st.write(resume_text[:500] or '(no text extracted)')

        st.subheader('Resume Match Score')
        st.metric('Match Score', f"{score}%")

        st.subheader('Matched Skills / Keywords')
        st.write(', '.join(matched) or '(none)')

        st.subheader('Missing Skills / Keywords')
        st.write(', '.join(missing[:50]) or '(none)')

        st.subheader('JD Sections Extracted')
        st.write({k: jd_sections[k][:10] for k in jd_sections})

        st.subheader('Specific Recommendations')
        recs = []
        if missing:
            recs.append(f"Add keywords and examples demonstrating: {', '.join(missing[:8])}.")
        recs.append('Rewrite experience bullets to emphasize product outcomes, stakeholder impact, and relevant technologies.')
        st.write('\n'.join(['- ' + r for r in recs]))


if st.button('Generate Optimized Resume'):
    if not (resume and jd and position):
        st.warning('Please upload resume PDF, paste the job description, and enter target position.')
    else:
        resume_text = extract_pdf_text(resume)
        use_openai = bool(openai and openai_key)
        with st.spinner('Generating AI suggestions...'):
            result = generate_improvements(resume_text, jd, use_openai=use_openai, api_key=openai_key)

        st.subheader('AI Improvement Preview')
        st.write('Showing original bullets, AI suggested rewrite, and explainable added keywords highlighted.')
        for orig, imp, added in zip(result['original_bullets'], result['improved_bullets'], result['added_keywords']):
            st.markdown('**Original:**')
            st.write(orig)
            st.markdown('**AI Suggested Improvement:**')
            # highlight added tokens and JD keywords present
            highlights = set(added)
            # also highlight any JD keywords that appear in the improved text but not in original
            jd_present = [k for k in result['jd_keywords'] if re.search(rf"(?i)\\b{re.escape(k)}\\b", imp) and not re.search(rf"(?i)\\b{re.escape(k)}\\b", orig)]
            for k in jd_present:
                highlights.add(k)
            imp_html = highlight_improved(imp, highlights)
            st.markdown(imp_html, unsafe_allow_html=True)

            st.markdown('**Why — Added keywords:**')
            if added or jd_present:
                for k in (jd_present + added):
                    st.write(f'- {k}')
            else:
                st.write('- (no new keywords detected)')

            st.write('---')

        st.subheader('Resume Match Score')
        st.metric('Match Score', f"{result['score']}%")

        st.success('AI suggestions generated.')

