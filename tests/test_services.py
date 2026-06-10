"""Test core service functions — pure logic, no external calls."""

from app.services.deepseek import (
    _score_salary,
    _score_role,
    _score_experience,
    fallback_evaluate_job,
    _fallback_extract_keywords,
)
from app.services.text import compact_text, keyword_hits, normalize_source_key


def test_compact_text():
    assert "Hello world" in compact_text("  Hello   world  \n\n\nfoo  ")


def test_keyword_hits():
    assert keyword_hits("Python SQL Docker", ["python", "sql", "java"]) == ["python", "sql"]


def test_normalize_source_key():
    assert normalize_source_key({"source_key": "abc"}) == "abc"


def test_score_salary_overlap():
    assert _score_salary("15K-25K", "18K-20K") == 15


def test_score_salary_gap():
    assert _score_salary("5K-8K", "18K-20K") < 0


def test_score_role_match():
    assert _score_role("高级产品经理", ["产品经理"]) == 15


def test_score_experience():
    assert _score_experience("要求3-5年经验", resume_years=4) == 10


def test_fallback_evaluate_job():
    resume = {
        "target_roles": ["产品经理"], "years": 4,
        "core_skills": ["需求分析", "产品设计"], "industries": ["SaaS"], "summary": "4年",
    }
    job = {"title": "高级产品经理", "company": "科技", "salary": "15K-25K", "city": "重庆", "description": "产品规划 3-5年"}
    settings = {"target_cities": ["重庆"], "salary_expectation": "15K-25K", "blocked_keywords": [], "min_score_to_chat": 55}
    result = fallback_evaluate_job(resume, job, settings)
    assert result["score"] > 50


def test_fallback_evaluate_blocked():
    resume = {"target_roles": ["产品"], "years": 3, "core_skills": ["设计"], "industries": [], "summary": ""}
    job = {"title": "PM", "company": "XX", "salary": "5K", "city": "重庆", "description": "培训贷"}
    settings = {"target_cities": ["重庆"], "salary_expectation": "", "blocked_keywords": ["培训贷"], "min_score_to_chat": 55}
    assert fallback_evaluate_job(resume, job, settings)["decision"] == "skip"


def test_fallback_extract_keywords():
    assert len(_fallback_extract_keywords("任职要求：Python SQL 产品设计")) > 0
