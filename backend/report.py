import json
from datetime import datetime
from pathlib import Path


# ============================================================
# REPORT DIRECTORY
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent.parent

REPORTS_DIR = BASE_DIR / "reports"

REPORTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CONVERT AI RESULT TO DICTIONARY
# ============================================================

def convert_ai_result(audit):

    if isinstance(
        audit,
        dict
    ):
        return audit

    return {
        "score": getattr(
            audit,
            "score",
            0
        ),

        "problems": getattr(
            audit,
            "problems",
            []
        ),

        "missing_features": getattr(
            audit,
            "missing_features",
            []
        ),

        "recommendations": getattr(
            audit,
            "recommendations",
            []
        ),

        "priority": getattr(
            audit,
            "priority",
            "Unknown"
        ),
    }


# ============================================================
# SAVE AUDIT REPORT
# ============================================================

def save_audit_report(
    facts,
    audit
):

    timestamp = datetime.now()

    timestamp_string = timestamp.strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"website_audit_"
        f"{timestamp_string}.json"
    )

    report_path = REPORTS_DIR / filename

    ai_analysis = convert_ai_result(
        audit
    )

    # --------------------------------------------------------
    # COMPLETE REPORT
    # --------------------------------------------------------

    report = {
        "report_information": {
            "report_name": "AI Food Website Quality Audit",
            "generated_at": timestamp.isoformat(),
            "generated_at_readable": timestamp.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "version": "2.0.0",
            "mode": "real-time",
        },

        "website": {
            "url": facts.get(
                "website",
                ""
            ),

            "requested_url": facts.get(
                "requested_url",
                ""
            ),

            "final_url": facts.get(
                "final_url",
                ""
            ),

            "page_title": facts.get(
                "page_title",
                ""
            ),

            "status_code": facts.get(
                "status_code"
            ),
        },

        # ----------------------------------------------------
        # PERFORMANCE
        # ----------------------------------------------------

        "performance": facts.get(
            "performance",
            {}
        ),

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        "security": facts.get(
            "security",
            {}
        ),

        # ----------------------------------------------------
        # SEO
        # ----------------------------------------------------

        "seo": facts.get(
            "seo",
            {}
        ),

        # ----------------------------------------------------
        # CONTENT
        # ----------------------------------------------------

        "content": facts.get(
            "content",
            {}
        ),

        # ----------------------------------------------------
        # IMAGES
        # ----------------------------------------------------

        "images": facts.get(
            "images",
            {}
        ),

        # ----------------------------------------------------
        # TECHNICAL
        # ----------------------------------------------------

        "technical": facts.get(
            "technical",
            {}
        ),

        # ----------------------------------------------------
        # FOOD BUSINESS
        # ----------------------------------------------------

        "food_business": facts.get(
            "food_business",
            {}
        ),

        # ----------------------------------------------------
        # LINKS
        # ----------------------------------------------------

        "links": facts.get(
            "links",
            {}
        ),

        # ----------------------------------------------------
        # FORMS
        # ----------------------------------------------------

        "forms": facts.get(
            "forms",
            {}
        ),

        # ----------------------------------------------------
        # CTA
        # ----------------------------------------------------

        "cta": facts.get(
            "cta",
            {}
        ),

        # ----------------------------------------------------
        # CONTACT
        # ----------------------------------------------------

        "contact": facts.get(
            "contact",
            {}
        ),

        # ----------------------------------------------------
        # TECHNOLOGY
        # ----------------------------------------------------

        "technology": facts.get(
            "technology",
            []
        ),

        # ----------------------------------------------------
        # GENERAL INFORMATION
        # ----------------------------------------------------

        "general": {
            "language": facts.get(
                "language",
                ""
            ),

            "word_count": facts.get(
                "word_count",
                0
            ),

            "mobile_responsive": facts.get(
                "mobile_responsive_indicator",
                False
            ),

            "total_links": facts.get(
                "total_links",
                0
            ),

            "has_email": facts.get(
                "has_email",
                False
            ),

            "has_phone": facts.get(
                "has_phone",
                False
            ),

            "has_social_media": facts.get(
                "has_social_media",
                False
            ),
        },

        # ----------------------------------------------------
        # AUTOMATIC ANALYSIS
        # ----------------------------------------------------

        "automatic_analysis": {
            "score": facts.get(
                "score",
                0
            ),

            "quality_label": facts.get(
                "quality_label",
                ""
            ),

            "priority": facts.get(
                "priority",
                ""
            ),

            "problems": facts.get(
                "problems",
                []
            ),

            "missing_features": facts.get(
                "missing_features",
                []
            ),

            "recommendations": facts.get(
                "recommendations",
                []
            ),
        },

        # ----------------------------------------------------
        # AI ANALYSIS
        # ----------------------------------------------------

        "ai_analysis": ai_analysis,
    }

    # --------------------------------------------------------
    # WRITE JSON
    # --------------------------------------------------------

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print(
        f"Audit report saved: {report_path}"
    )

    # Return path relative to project
    # so the frontend can display it.

    try:

        return str(
            report_path.relative_to(
                BASE_DIR
            )
        )

    except ValueError:

        return str(
            report_path
        )