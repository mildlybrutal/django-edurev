"""Deterministic JD processing (no AI). Finds taxonomy skills and their synonyms in the JD text,
infers a required level and whether each is mandatory from nearby wording, and extracts common
eligibility criteria with regular expressions. Output is a *draft* the officer reviews."""

import re

from apps.students.models import Department
from apps.taxonomy.models import Level, Skill, SkillSynonym
from apps.taxonomy.services import normalize

from .models import RuleType

ADVANCED_CUES = ("strong", "expert", "advanced", "deep", "proficien", "extensive", "in-depth", "solid")
BEGINNER_CUES = ("familiar", "basic", "exposure", "awareness", "understanding of", "beginner")
OPTIONAL_CUES = ("nice to have", "good to have", "is a plus", "a plus", "preferred", "bonus", "optional")
MANDATORY_CUES = ("must", "required", "mandatory", "essential")


def _sentences(text):
    """Split on sentence punctuation, blank lines and bullet points. A single line break inside
    a paragraph is treated as a space, so wrapped sentences stay together."""
    parts = re.split(r"(?<=[.!?;])\s+|\n\s*\n|\n\s*(?:[-•*]|\d+[.)])\s+", text)
    return [" ".join(p.split()) for p in parts if p.strip()]


def _term_pattern(term):
    # Word boundaries that also work for terms like "C++", "Node.js" and "CI/CD".
    return re.compile(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#])", re.IGNORECASE)


def _vocabulary(institution_id):
    terms = {}
    for skill in Skill.objects.filter(institution_id=institution_id, is_active=True):
        terms[normalize(skill.name)] = skill
    for syn in SkillSynonym.objects.filter(institution_id=institution_id, skill__is_active=True).select_related(
        "skill"
    ):
        terms.setdefault(syn.normalized_name, syn.skill)
    # Longest first so "Django REST Framework" wins over "Django".
    return sorted(terms.items(), key=lambda kv: -len(kv[0]))


def extract_skills(text, institution_id):
    sentences = _sentences(text)
    found = {}
    for term, skill in _vocabulary(institution_id):
        if len(term) < 2:
            continue
        pattern = _term_pattern(term)
        for sentence in sentences:
            if not pattern.search(sentence):
                continue
            lower = sentence.lower()
            level = Level.INTERMEDIATE
            if any(c in lower for c in ADVANCED_CUES):
                level = Level.ADVANCED
            elif any(c in lower for c in BEGINNER_CUES):
                level = Level.BEGINNER
            optional = any(c in lower for c in OPTIONAL_CUES)
            mandatory = not optional and any(c in lower for c in MANDATORY_CUES)
            current = found.get(skill.pk)
            if current is None or level > current["required_level"]:
                found[skill.pk] = {
                    "skill_id": skill.pk,
                    "skill": skill.name,
                    "matched_text": term,
                    "evidence": sentence[:240],
                    "required_level": int(level),
                    "is_mandatory": mandatory or (current or {}).get("is_mandatory", False),
                    "weight": 3 if mandatory else (1 if optional else 2),
                }
            elif mandatory:
                current["is_mandatory"] = True
                current["weight"] = 3
    return sorted(found.values(), key=lambda s: (-s["is_mandatory"], -s["weight"], s["skill"]))


CGPA_RE = re.compile(
    r"(?:cgpa|gpa|cpi)[^\d\n]{0,25}(\d{1,2}(?:\.\d{1,2})?)|(\d{1,2}(?:\.\d{1,2})?)\s*(?:\+\s*)?(?:cgpa|gpa|cpi)",
    re.IGNORECASE,
)
NO_BACKLOG_RE = re.compile(r"no\s+(?:active\s+|current\s+|live\s+)?backlogs?", re.IGNORECASE)
MAX_BACKLOG_RE = re.compile(r"(?:max(?:imum)?|up to|not more than)\s+(\d+)\s+(?:active\s+)?backlogs?", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\s*(?:batch|pass(?:ing)?[- ]?out|graduat\w*)|(?:batch|class) of\s+(20\d{2})", re.I)


def extract_eligibility(text, institution_id):
    rules = []
    cgpas = [float(a or b) for a, b in CGPA_RE.findall(text) if 0 < float(a or b) <= 10]
    if cgpas:
        rules.append({"rule_type": RuleType.MIN_CGPA, "value": max(cgpas), "label": f"Minimum CGPA {max(cgpas)}"})
    max_backlogs = MAX_BACKLOG_RE.search(text)
    if NO_BACKLOG_RE.search(text):
        rules.append({"rule_type": RuleType.MAX_ACTIVE_BACKLOGS, "value": 0, "label": "No active backlogs"})
    elif max_backlogs:
        n = int(max_backlogs.group(1))
        rules.append({"rule_type": RuleType.MAX_ACTIVE_BACKLOGS, "value": n, "label": f"At most {n} active backlogs"})
    codes = []
    for dept in Department.objects.filter(institution_id=institution_id):
        if _term_pattern(dept.code).search(text) or re.search(re.escape(dept.name), text, re.IGNORECASE):
            codes.append(dept.code.upper())
    if codes:
        rules.append(
            {
                "rule_type": RuleType.DEPARTMENT_IN,
                "value": sorted(set(codes)),
                "label": "Departments: " + ", ".join(sorted(set(codes))),
            }
        )
    years = sorted({int(a or b) for a, b in YEAR_RE.findall(text)})
    if years:
        rules.append(
            {
                "rule_type": RuleType.GRADUATION_YEAR_IN,
                "value": years,
                "label": "Graduation year: " + ", ".join(map(str, years)),
            }
        )
    return rules


def process_jd(text, institution_id):
    return {
        "method": "deterministic dictionary + pattern matching against the institutional taxonomy",
        "skills": extract_skills(text, institution_id),
        "eligibility": extract_eligibility(text, institution_id),
    }
