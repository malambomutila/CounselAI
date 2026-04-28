"""All system prompts and reusable prompt templates.

Edits to agent voice or rubric live here and only here — no hidden copies in
the agent files.
"""
from __future__ import annotations

LEGAL_AREAS = [
    "Contract Law",
    "Employment Law",
    "Intellectual Property",
    "Corporate / M&A",
    "Regulatory / Compliance",
    "Personal Injury / Tort",
    "Real Estate / Property",
    "Data Privacy / GDPR",
    "Criminal Law",
    "Family Law",
    "Other",
]

PLAINTIFF_SYSTEM = (
    "You are a seasoned plaintiff's attorney. Your role is to construct "
    "the strongest possible legal argument in FAVOUR of your client's position. "
    "Be strategic, cite relevant legal principles, anticipate weaknesses, "
    "and write in a persuasive but professional legal tone."
)

DEFENSE_SYSTEM = (
    "You are a sharp defense attorney. Your role is to dismantle the opposing "
    "party's legal position. Identify weaknesses, raise procedural issues, "
    "challenge the evidence, and present the strongest counter-arguments possible. "
    "Write in a professional legal tone."
)

EXPERT_SYSTEM = (
    "You are an independent legal expert and academic. You provide objective "
    "technical analysis of legal matters: relevant statutes, landmark case law, "
    "regulatory frameworks, and doctrinal issues. You do not advocate for either "
    "side — your role is to clarify the legal landscape and identify the key "
    "legal questions a court or regulator would focus on."
)

JUDGE_SYSTEM = (
    "You are an experienced judge evaluating the quality of legal arguments. "
    "You return strictly valid JSON. You score each side fairly across criteria, "
    "expose vulnerabilities on both sides, and avoid taking a personal stance "
    "beyond what the evidence supports."
)

STRATEGIST_SYSTEM = (
    "You are a senior legal strategist with 30 years of litigation experience. "
    "You synthesise complex legal analysis into clear, actionable advice. "
    "Your goal is to help the user strengthen their case and prepare for "
    "the arguments they will face. Be practical, specific, and candid."
)

JUDGE_RUBRIC = [
    "Legal theory strength",
    "Factual support",
    "Anticipation of counter-arguments",
    "Procedural soundness",
    "Overall persuasiveness",
]


def plaintiff_prompt(case: str, area: str, position: str, *, follow_up: str = "") -> str:
    base = (
        f"Legal area: {area}\n\n"
        f"Case facts:\n{case}\n\n"
        f"Your client's position: {position}\n\n"
    )
    if follow_up:
        base += (
            "Additional instruction from your client (refine or change your "
            f"approach accordingly):\n{follow_up}\n\n"
        )
    base += (
        "Build the strongest possible argument for this position. Include:\n"
        "1. Core legal theory\n"
        "2. Key facts that support the claim\n"
        "3. Relevant legal principles or precedents\n"
        "4. Anticipated defence objections and pre-emptive rebuttals\n\n"
        "Be concise but thorough. Max 300 words."
    )
    return base


def defense_prompt(case: str, area: str, position: str, *, follow_up: str = "") -> str:
    base = (
        f"Legal area: {area}\n\n"
        f"Case facts:\n{case}\n\n"
        f"The opposing party's position: {position}\n\n"
    )
    if follow_up:
        base += (
            "Additional instruction (refine or change your approach "
            f"accordingly):\n{follow_up}\n\n"
        )
    base += (
        "Mount the strongest possible counter-argument. Include:\n"
        "1. Primary legal defence or counter-theory\n"
        "2. Factual weaknesses in the opposing case\n"
        "3. Procedural or evidentiary challenges\n"
        "4. Alternative interpretations of the facts\n\n"
        "Be incisive and precise. Max 300 words."
    )
    return base


def expert_prompt(case: str, area: str, plaintiff_arg: str, defense_arg: str,
                  *, follow_up: str = "") -> str:
    base = (
        f"Legal area: {area}\n\n"
        f"Case facts:\n{case}\n\n"
        f"Plaintiff's argument:\n{plaintiff_arg}\n\n"
        f"Defense's argument:\n{defense_arg}\n\n"
    )
    if follow_up:
        base += f"Additional context to consider:\n{follow_up}\n\n"
    base += (
        "Provide an expert technical analysis as a JSON object:\n"
        "{\n"
        '  "key_legal_questions": ["question1", "question2"],\n'
        '  "applicable_law": "Summary of relevant statutes or doctrine",\n'
        '  "precedents": "Notable cases or rulings relevant to this matter",\n'
        '  "burden_of_proof": "Who bears the burden and what standard applies",\n'
        '  "critical_risk_factors": ["risk1", "risk2"]\n'
        "}\n"
        "Return only valid JSON."
    )
    return base


def judge_prompt(case: str, area: str, plaintiff_arg: str, defense_arg: str,
                 expert_summary: str, *, follow_up: str = "") -> str:
    rubric_text = "\n".join(f"- {item}" for item in JUDGE_RUBRIC)
    base = (
        f"Legal area: {area}\n\n"
        f"Case facts:\n{case}\n\n"
        f"Plaintiff's Counsel argues:\n{plaintiff_arg}\n\n"
        f"Defense Counsel argues:\n{defense_arg}\n\n"
        f"Expert legal analysis:\n{expert_summary}\n\n"
    )
    if follow_up:
        base += f"Additional context to consider:\n{follow_up}\n\n"
    base += (
        "Score each side 0-10 on the following criteria:\n"
        f"{rubric_text}\n\n"
        "Return a JSON object:\n"
        "{\n"
        '  "stronger_position": "Plaintiff" or "Defense" or "Balanced",\n'
        '  "judicial_assessment": "Your overall assessment (2-3 sentences)",\n'
        '  "plaintiff_vulnerabilities": ["vuln1", "vuln2"],\n'
        '  "defense_vulnerabilities": ["vuln1", "vuln2"],\n'
        '  "scores": [\n'
        '    {"criterion": "...", "plaintiff": 0-10, "defense": 0-10, "notes": "..."}\n'
        "  ]\n"
        "}\n"
        "Return valid JSON only."
    )
    return base


def strategist_prompt(case: str, area: str, position: str,
                      plaintiff_arg: str, defense_arg: str,
                      expert_summary: str, judge_summary: str,
                      *, follow_up: str = "") -> str:
    base = (
        f"Legal area: {area}\n"
        f"User's position: {position}\n\n"
        f"Case facts:\n{case}\n\n"
        f"Plaintiff's argument:\n{plaintiff_arg}\n\n"
        f"Defense's argument:\n{defense_arg}\n\n"
        f"Expert analysis:\n{expert_summary}\n\n"
        f"Judicial assessment:\n{judge_summary}\n\n"
    )
    if follow_up:
        base += f"Additional context from the client:\n{follow_up}\n\n"
    base += (
        "Provide a structured case preparation memo:\n\n"
        "STRENGTHS TO LEVERAGE\n"
        "- List 3 strongest points in the user's favour\n\n"
        "VULNERABILITIES TO ADDRESS\n"
        "- List 3 key weaknesses the user must shore up\n\n"
        "EVIDENCE GAPS\n"
        "- What additional evidence or documentation should be gathered?\n\n"
        "RECOMMENDED STRATEGY\n"
        "- Concise recommended litigation or settlement strategy\n\n"
        "IMMEDIATE ACTION ITEMS\n"
        "- 3 to 5 concrete next steps for case preparation\n\n"
        "Max 400 words. Be direct and practical."
    )
    return base
