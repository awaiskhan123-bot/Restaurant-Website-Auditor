from typing import List, Optional

from pydantic import BaseModel, Field

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
# AI OUTPUT MODEL
# ============================================================

class WebsiteAudit(BaseModel):
    score: int = Field(
        description="Overall food website quality score from 0 to 100."
    )

    summary: str = Field(
        description="2-3 sentence executive summary of the website quality and key observations.",
        default=""
    )

    problems: List[str] = Field(
        description="Important problems detected on the website."
    )

    missing_features: List[str] = Field(
        description="Important missing food-business website features."
    )

    recommendations: List[str] = Field(
        description="Specific practical recommendations for improvement."
    )

    priority: str = Field(
        description="Overall priority: Low, Medium, High, or Critical."
    )

    strengths: Optional[List[str]] = Field(
        description="Things the website does well.",
        default_factory=list
    )


# ============================================================
# LOCAL OLLAMA MODEL
# ============================================================

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0,
)


structured_llm = llm.with_structured_output(
    WebsiteAudit
)


# ============================================================
# PROMPT
# ============================================================

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert website quality auditor specializing
in restaurants, cafes, bakeries, food delivery businesses,
and other Food & Beverage websites.

Analyze the automatically collected website information.

Your job is to identify:

1. Website quality problems
2. Missing important features
3. Practical recommendations
4. Overall quality score
5. Priority level
6. Strengths (what the website does well)
7. Executive summary

IMPORTANT RULES:

- Use ONLY the information provided.
- Do not invent website features or restaurant details.
- Do not claim something exists unless the scanner detected it.
- Treat "not detected" as "not detected", not proof it doesn't exist.
- Focus specifically on Food & Beverage website best practices.
- Consider customer experience, ordering, reservations,
  contact information, mobile usability, SEO and technical quality.
- Give practical recommendations.
- Score from 0 to 100.
- Priority must be exactly one of: Low, Medium, High, Critical.
- If menu, hours, contact info, and ordering are all found → score ≥ 70.
- If most info is missing → score ≤ 40.

The final answer must follow the requested structured format.
""",
        ),
        (
            "human",
            """
Here is the automatically collected website audit data:

{website_data}

Analyze this website and return the structured audit.
""",
        ),
    ]
)


# ============================================================
# MAIN AI ANALYSIS FUNCTION
# ============================================================

def analyze_website(facts: dict) -> WebsiteAudit:

    try:

        # ------------------------------------------------
        # Build compact data summary for the LLM
        # ------------------------------------------------

        menu = facts.get("menu", {})
        contact = facts.get("contact", {})
        social = facts.get("social_media", {})
        features = facts.get("features", {})
        seo = facts.get("seo", {})
        technical = facts.get("technical", {})
        hours = facts.get("opening_hours", {})
        reservations = facts.get("reservations", {})
        ordering = facts.get("ordering", {})

        ai_data = {
            "website": facts.get("website", ""),
            "restaurant_name": facts.get("restaurant", {}).get("name", ""),
            "page_title": seo.get("title", ""),
            "meta_description": seo.get("meta_description", ""),
            "language": facts.get("restaurant", {}).get("language", ""),
            "status_code": facts.get("status_code"),
            "response_time_ms": facts.get("response_time_ms"),

            "features_detected": features,

            "menu": {
                "status": menu.get("status"),
                "categories_count": len(menu.get("categories", [])),
                "extraction_method": menu.get("source_method"),
            },

            "contact": {
                "emails": contact.get("emails", []),
                "phones": contact.get("phones", []),
                "addresses": contact.get("addresses", []),
            },

            "opening_hours": hours,
            "reservations": reservations,
            "online_ordering": ordering,

            "social_media_detected": {
                k: bool(v) for k, v in social.items() if k != "other"
            },

            "seo": {
                "title": seo.get("title", ""),
                "has_meta_description": bool(seo.get("meta_description")),
                "h1_count": seo.get("h1_count", 0),
                "structured_data_count": seo.get("structured_data_count", 0),
                "mobile_viewport": seo.get("mobile_viewport", False),
            },

            "technical": technical,

            "content_word_count": facts.get("content", {}).get("word_count", 0),
            "total_images": facts.get("media", {}).get("total_images", 0),
        }

        # ------------------------------------------------
        # Invoke Ollama
        # ------------------------------------------------

        chain = prompt | structured_llm

        result = chain.invoke(
            {
                "website_data": ai_data
            }
        )

        # ------------------------------------------------
        # Safety validation
        # ------------------------------------------------

        result.score = max(0, min(100, int(result.score)))

        allowed_priorities = {"Low", "Medium", "High", "Critical"}

        if result.priority not in allowed_priorities:
            if result.score >= 80:
                result.priority = "Low"
            elif result.score >= 60:
                result.priority = "Medium"
            elif result.score >= 40:
                result.priority = "High"
            else:
                result.priority = "Critical"

        if not hasattr(result, "strengths") or result.strengths is None:
            result.strengths = []

        if not hasattr(result, "summary") or not result.summary:
            result.summary = ""

        return result

    except Exception as exc:

        print("AI auditor error:", exc)

        # ------------------------------------------------
        # Fallback — stays usable without Ollama
        # ------------------------------------------------

        facts_features = facts.get("features", {})
        detected_count = sum(1 for v in facts_features.values() if v)
        total_features = max(len(facts_features), 1)
        fallback_score = min(100, round((detected_count / total_features) * 100))

        if fallback_score >= 80:
            fallback_priority = "Low"
        elif fallback_score >= 60:
            fallback_priority = "Medium"
        elif fallback_score >= 40:
            fallback_priority = "High"
        else:
            fallback_priority = "Critical"

        problems = []
        if not facts_features.get("menu"):
            problems.append("No menu information was detected on the website.")
        if not facts_features.get("phone"):
            problems.append("No phone number was detected.")
        if not facts_features.get("address"):
            problems.append("No business address was detected.")
        if not facts.get("technical", {}).get("https"):
            problems.append("Website may not be using HTTPS.")
        if not facts.get("technical", {}).get("mobile_responsive"):
            problems.append("No mobile viewport configuration detected.")

        missing = []
        if not facts_features.get("reservation"):
            missing.append("Online reservation system")
        if not facts_features.get("online_ordering"):
            missing.append("Online ordering")
        if not facts_features.get("social_media"):
            missing.append("Social media presence")
        if not facts_features.get("about"):
            missing.append("About/story page")

        recommendations = []
        if not facts_features.get("menu"):
            recommendations.append("Add a clearly visible menu with item names, descriptions and prices.")
        if not facts_features.get("reservation"):
            recommendations.append("Add a reservation or table booking system.")
        if not facts_features.get("online_ordering"):
            recommendations.append("Add online ordering or delivery integration.")
        if not problems:
            recommendations.append("Keep maintaining the website with fresh content and regular updates.")

        return WebsiteAudit(
            score=fallback_score,
            summary=(
                f"Automated analysis completed. {detected_count} of {total_features} "
                f"key features were detected on the website."
            ),
            problems=problems,
            missing_features=missing,
            recommendations=recommendations,
            priority=fallback_priority,
            strengths=[
                f"{k.replace('_', ' ').title()} detected"
                for k, v in facts_features.items() if v
            ],
        )