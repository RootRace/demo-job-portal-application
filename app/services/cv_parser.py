import os
import re
from flask import current_app
from docx import Document
import spacy
from spacy.matcher import Matcher

EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.I)
PHONE_RE = re.compile(r'(\+?\d{1,3}[\s\-]?)?(?:\d[\d\-\s]{6,}\d)')
EDUCATION_KEYWORDS = ['B.Tech','M.Tech','BSc','MSc','MBA','BE','ME','PhD']


try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


def _load_nlp():
    model = current_app.config.get('SPACY_MODEL', 'en_core_web_sm')
    try:
        return spacy.load(model)
    except Exception:
        return spacy.load('en_core_web_sm')


nlp = None


def ensure_nlp():
    global nlp
    if nlp is None:
        nlp = _load_nlp()
    return nlp


def extract_text_from_pdf(file_path):
    import fitz  
    text = ''
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text += page.get_text('text') + '\n'
    return text


def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return '\n'.join(p.text for p in doc.paragraphs)


def normalize_whitespace(s):
    return re.sub(r'\s+', ' ', s).strip()


def find_email(text):
    m = EMAIL_RE.search(text)
    return m.group(0).strip() if m else ''


def find_phone(text):
    m = PHONE_RE.search(text)
    if not m:
        return ''
    phone = re.sub(r'[^\d\+]', '', m.group(0))
    return phone


def extract_name_location_education(text):
    nlp = ensure_nlp()
    doc = nlp(text)
    name, location, education = '', '', ''

    name_match = re.search(r'(?i)(?:Name|Full Name)\s*[:\-]\s*(.+)', text)
    if name_match:
        name = name_match.group(1).split('\n')[0].strip()
    else:
        for ent in doc.ents:
            if ent.label_ == 'PERSON':
                name = ent.text.strip()
                break

    loc_match = re.search(r'(?i)(?:Location|City)\s*[:\-]\s*(.+)', text)
    if loc_match:
        location = loc_match.group(1).split('\n')[0].strip()
    else:
        for ent in doc.ents:
            if ent.label_ in ['GPE', 'LOC']:
                location = ent.text.strip()
                break

    for kw in EDUCATION_KEYWORDS:
        if kw.lower() in text.lower():
            education = kw
            break

    return name, location, education


def extract_skills(text):
    nlp = ensure_nlp()
    doc = nlp(text)
    matcher = Matcher(nlp.vocab)

    pattern = [{'POS': 'PROPN', 'OP': '+'}, {'POS': 'NOUN', 'OP': '*'}]
    matcher.add('SKILL_PATTERN', [pattern])

    matches = matcher(doc)
    skills_set = set()

    for match_id, start, end in matches:
        span = doc[start:end].text.strip()
        if 1 <= len(span.split()) <= 4:
            skills_set.add(span)

    common_skills = ['Python','Java','Django','Flask','React','JavaScript','SQL','C++','AWS','Docker','Kubernetes','HTML','CSS','Node','ERPNext']
    for token in doc:
        if token.text in common_skills:
            skills_set.add(token.text)

    return ', '.join(sorted(skills_set))


def extract_experience(text):
    exp_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years|yrs)\s*(?:of)?\s*(?:experience|exp)?', text, re.I)
    if exp_m:
        return exp_m.group(1)
    else:
        nlp = ensure_nlp()
        doc = nlp(text)
        for sent in doc.sents:
            if 'experience' in sent.text.lower():
                nums = [token.text for token in sent if token.like_num]
                if nums:
                    return nums[0]
    return ''


def extract_info_from_cv(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        raw_text = extract_text_from_pdf(file_path)
    elif ext in ('.doc', '.docx'):
        raw_text = extract_text_from_docx(file_path)
    else:
        return {}

    text = normalize_whitespace(raw_text)

    email = find_email(raw_text)
    phone = find_phone(raw_text)
    name, location, education = extract_name_location_education(raw_text)
    skills = extract_skills(raw_text)
    experience_years = extract_experience(raw_text)

    return {
        'full_name': name,
        'email': email,
        'phone': phone,
        'location': location,
        'skills': skills,
        'experience_years': experience_years,
        'education': education,
        'resume_text': text[:3000]
    }
