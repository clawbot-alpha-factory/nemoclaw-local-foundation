# NemoClaw Production Framework Library v1.0
# 
# Frameworks mined from agency-agents (60K+ stars) and adapted for
# NemoClaw multi-agent skill execution system.
#
# These frameworks are used as structured output templates in skill prompts.
# Each framework has a unique ID for reference in skill.yaml files.

import json
from pathlib import Path

FRAMEWORKS = {
    # ═══════════════════════════════════════════════════════════════
    # SALES & GROWTH FRAMEWORKS
    # ═══════════════════════════════════════════════════════════════

    "MEDDPICC": {
        "id": "FW-001",
        "source": "Deal Strategist (agency-agents/sales)",
        "domain": "growth",
        "description": "Enterprise B2B deal qualification framework",
        "use_in_skills": ["j36-biz-idea-validator", "k40-deal-qualifier"],
        "template": {
            "metrics": {
                "question": "What quantifiable business outcome does the buyer need?",
                "example": "Reduce onboarding from 14 days to 3 days",
                "score": "1-10",
                "red_flag": "Buyer cannot articulate the metric",
            },
            "economic_buyer": {
                "question": "Who controls budget and can say yes when everyone says no?",
                "test": "Can this person reallocate budget from another initiative?",
                "score": "1-10",
            },
            "decision_criteria": {
                "question": "What specific criteria will they use to evaluate?",
                "red_flag": "You're guessing at criteria = competitor wrote them",
                "score": "1-10",
            },
            "decision_process": {
                "question": "Walk me through choosing vendor → going live",
                "score": "1-10",
            },
            "paper_process": {
                "question": "Legal review, procurement, security questionnaire timeline?",
                "red_flag": "6-week procurement discovered in week 11 kills the quarter",
                "score": "1-10",
            },
            "identify_pain": {
                "question": "What is the specific, quantified business problem?",
                "bad_example": "We need a better tool",
                "good_example": "Lost 3 enterprise deals because implementation was 90 days vs competitor's 30",
                "score": "1-10",
            },
            "champion": {
                "question": "Who has power, access, and personal motivation to drive this?",
                "test": "Ask them to do something hard. If they won't, they're a coach not a champion.",
                "score": "1-10",
            },
            "competition": {
                "question": "Who else is being evaluated? Direct, adjacent, internal build, do-nothing?",
                "zones": ["winning", "battling", "losing"],
                "score": "1-10",
            },
            "scoring": {
                "strong_deal": ">=60/80 with no zeros",
                "at_risk": "40-59/80 or any zero in M/EB/IP/CH",
                "weak_deal": "<40/80",
            },
        },
    },

    "ICP_FRAMEWORK": {
        "id": "FW-002",
        "source": "Outbound Strategist (agency-agents/sales)",
        "domain": "growth",
        "description": "Ideal Customer Profile definition with tiered engagement",
        "use_in_skills": ["e12-market-research-analyst", "a01-growth-strategy-analyst"],
        "template": {
            "firmographic_filters": {
                "industry_verticals": "2-4 specific verticals (not 'enterprise')",
                "revenue_range": "Annual revenue or employee count band",
                "geography": "If relevant to go-to-market",
                "tech_stack": "What they must already use",
            },
            "behavioral_qualifiers": {
                "buying_trigger": "What business event makes them a buyer NOW?",
                "pain_point": "What pain can they NOT ignore?",
                "internal_champion": "Who inside feels the pain most acutely?",
                "current_workaround": "What are they doing instead?",
            },
            "disqualifiers": {
                "false_positives": "Looks good on paper but never closes",
                "low_win_segments": "Win rate below 15%",
                "wrong_stage": "Too early or too late for your product",
            },
            "tiers": {
                "tier_1": {
                    "count": "50-100 accounts",
                    "approach": "Deep, multi-threaded, highly personalized",
                    "contacts_per_account": "3-5",
                    "review_cadence": "Weekly",
                },
                "tier_2": {
                    "count": "200-500 accounts",
                    "approach": "Semi-personalized sequences",
                    "contacts_per_account": "2-3",
                    "review_cadence": "Quarterly",
                },
                "tier_3": {
                    "count": "Remaining ICP-fit",
                    "approach": "Automated with light personalization",
                    "contacts_per_account": "1",
                    "trigger": "Signal-triggered only",
                },
            },
        },
    },

    "SIGNAL_BASED_OUTBOUND": {
        "id": "FW-003",
        "source": "Outbound Strategist (agency-agents/sales)",
        "domain": "growth",
        "description": "Signal-triggered outreach ranked by intent strength",
        "use_in_skills": ["a01-growth-strategy-analyst"],
        "template": {
            "tier_1_active_signals": [
                "G2/review site visits or pricing page views",
                "RFP or vendor evaluation announcements",
                "Technology evaluation job postings",
            ],
            "tier_2_change_signals": [
                "Leadership changes in buying persona's function",
                "Funding events (Series B+ with growth goals)",
                "Hiring surges in department your product serves",
                "M&A activity (tool consolidation pressure)",
            ],
            "tier_3_behavioral_signals": [
                "Technology stack changes (BuiltWith, job postings)",
                "Conference attendance on adjacent topics",
                "Content engagement (whitepapers, webinars)",
                "Competitor contract renewal timing",
            ],
            "speed_to_signal": "Route within 30 min. After 24h = stale. After 72h = competitor already had the conversation.",
        },
    },

    "PIPELINE_VELOCITY": {
        "id": "FW-004",
        "source": "Pipeline Analyst (agency-agents/sales)",
        "domain": "growth",
        "description": "Revenue pipeline health formula and diagnostics",
        "use_in_skills": ["a01-growth-strategy-analyst"],
        "template": {
            "formula": "Pipeline Velocity = (Qualified Opps × Avg Deal Size × Win Rate) / Sales Cycle Length",
            "coverage_targets": {
                "mature_business": "3x",
                "growth_stage": "4-5x",
                "new_rep_ramping": "5x+",
            },
            "deal_health_signals": {
                "positive": ["Multi-threaded (3+ contacts)", "Buyer-initiated activity", "Meeting frequency > weekly"],
                "negative": ["Single-threaded above $50K", "Last activity > 14 days in late stage", "Stalled > 1.5x median stage duration"],
            },
            "forecast_layers": [
                "Historical stage conversion rates (base rate)",
                "Deal velocity weighting (faster = higher probability)",
                "Engagement signal adjustment (2-3x for multi-threaded)",
                "Seasonal/cyclical patterns",
            ],
        },
    },

    # ═══════════════════════════════════════════════════════════════
    # PRODUCT FRAMEWORKS
    # ═══════════════════════════════════════════════════════════════

    "PRD_TEMPLATE": {
        "id": "FW-005",
        "source": "Product Manager (agency-agents/product)",
        "domain": "product",
        "description": "Product Requirements Document structure",
        "use_in_skills": ["f09-product-req-writer", "j36-mvp-scope-definer"],
        "template": {
            "sections": [
                "1. Problem Statement (with evidence: research, data, support signal, competitive)",
                "2. Goals & Success Metrics (goal, metric, baseline, target, window)",
                "3. Non-Goals (explicit exclusions with rationale)",
                "4. User Personas & Stories (with acceptance criteria)",
                "5. Solution Overview (approach, not implementation details)",
                "6. Technical Constraints & Dependencies",
                "7. Timeline & Milestones",
                "8. Risks & Mitigations",
            ],
            "critical_rules": [
                "Lead with problem, not solution",
                "Write the press release before the PRD",
                "No roadmap item without owner + metric + timeline",
                "Say no clearly, respectfully, and often",
                "Validate before build, measure after ship",
            ],
        },
    },

    "RICE_SCORING": {
        "id": "FW-006",
        "source": "Feedback Synthesizer (agency-agents/product)",
        "domain": "product",
        "description": "Feature prioritization framework",
        "use_in_skills": ["f09-product-req-writer"],
        "template": {
            "reach": "How many users will this impact per quarter?",
            "impact": "How much will it move the needle? (3=massive, 2=high, 1=medium, 0.5=low, 0.25=minimal)",
            "confidence": "How sure are we? (100%=high, 80%=medium, 50%=low)",
            "effort": "Person-months to build",
            "formula": "RICE = (Reach × Impact × Confidence) / Effort",
        },
    },

    # ═══════════════════════════════════════════════════════════════
    # EXECUTIVE FRAMEWORKS
    # ═══════════════════════════════════════════════════════════════

    "SCQA": {
        "id": "FW-007",
        "source": "Executive Summary Generator (agency-agents/support)",
        "domain": "executive",
        "description": "McKinsey Situation-Complication-Question-Answer framework",
        "use_in_skills": ["c07-executive-brief-writer", "research-brief"],
        "template": {
            "situation": "50-75 words: What is happening and why it matters now",
            "key_findings": "125-175 words: 3-5 insights with quantified data points, bold strategic implications",
            "business_impact": "50-75 words: Quantify gain/loss, risk magnitude, time horizon",
            "recommendations": "75-100 words: 3-4 prioritized actions (Critical/High/Medium) with owner + timeline + expected result",
            "next_steps": "25-50 words: 2-3 immediate actions within 30 days",
            "total_length": "325-475 words max",
        },
    },

    # ═══════════════════════════════════════════════════════════════
    # MARKETING FRAMEWORKS
    # ═══════════════════════════════════════════════════════════════

    "CONTENT_CALENDAR": {
        "id": "FW-008",
        "source": "Content Creator + LinkedIn Creator (agency-agents/marketing)",
        "domain": "content",
        "description": "30-day multi-platform content strategy",
        "use_in_skills": ["d11-video-script-writer", "c07-executive-brief-writer"],
        "template": {
            "content_pillars": "3-5 topics at intersection of expertise and audience need",
            "weekly_rhythm": {
                "week_1": "Pillar 1: Story(Mon) + Expertise(Wed) + Data(Fri)",
                "week_2": "Pillar 2: Opinion(Tue) + Story(Thu)",
                "week_3": "Pillar 1: Carousel(Mon) + Expertise(Wed) + Opinion(Fri)",
                "week_4": "Pillar 3: Story(Tue) + Data(Thu) + Repurpose top post(Sat)",
            },
            "post_types": ["Story (personal experience)", "Expertise (teach something)", 
                           "Data (stats + insight)", "Opinion (take + defend)", "Carousel (visual sequence)"],
        },
    },

    "LINKEDIN_HOOKS": {
        "id": "FW-009",
        "source": "LinkedIn Content Creator (agency-agents/marketing)",
        "domain": "content",
        "description": "Scroll-stopping hook frameworks for professional content",
        "use_in_skills": ["d11-video-script-writer"],
        "template": {
            "hook_types": {
                "curiosity_gap": "I almost turned down the job that changed my career.",
                "bold_claim": "Your LinkedIn headline is why you're not getting recruiter messages.",
                "specific_story": "Tuesday, 9 PM. I'm about to hit send on my resignation email.",
                "contrarian": "Everyone says X. Here's why they're wrong.",
                "data_lead": "We analyzed 10,000 cold emails. Only 3% got replies. Here's what they had in common.",
            },
            "rules": [
                "Hook in first line — earn the 'see more' click",
                "Specificity over inspiration always",
                "Have a take worth defending",
                "No links in post body (link in comments)",
                "3-5 hashtags max, specific not generic",
            ],
        },
    },

    "SEO_AUDIT": {
        "id": "FW-010",
        "source": "SEO Specialist (agency-agents/marketing)",
        "domain": "content",
        "description": "Technical SEO audit framework",
        "use_in_skills": [],  # future skill
        "template": {
            "crawlability": ["Robots.txt analysis", "XML sitemap health", "Crawl budget optimization"],
            "site_architecture": ["URL structure depth", "Internal link distribution", "Orphaned pages"],
            "core_web_vitals": {"LCP": "<2.5s", "INP": "<200ms", "CLS": "<0.1"},
            "content_quality": ["E-E-A-T compliance", "Keyword optimization", "Search intent alignment"],
            "link_profile": ["Domain authority", "Backlink quality", "Anchor text distribution"],
        },
    },

    # ═══════════════════════════════════════════════════════════════
    # PAID MEDIA FRAMEWORKS
    # ═══════════════════════════════════════════════════════════════

    "PPC_ARCHITECTURE": {
        "id": "FW-011",
        "source": "PPC Campaign Strategist (agency-agents/paid-media)",
        "domain": "growth",
        "description": "Google/Microsoft Ads account architecture",
        "use_in_skills": [],  # future skill k41
        "template": {
            "campaign_tiers": {
                "brand": "Branded terms — 90%+ impression share target",
                "non_brand_core": "High-intent non-brand — tCPA/tROAS bidding",
                "non_brand_expansion": "Broad match + smart bidding — incremental reach",
                "competitor": "Competitor terms — conquest strategy",
            },
            "success_metrics": {
                "impression_share": "90%+ brand, 40-60% non-brand",
                "quality_score": "70%+ spend on QS 7+",
                "budget_utilization": "95-100% daily pacing",
                "testing_velocity": "2-4 structured tests/month/account",
            },
        },
    },

    "RSA_ARCHITECTURE": {
        "id": "FW-012",
        "source": "Ad Creative Strategist (agency-agents/paid-media)",
        "domain": "growth",
        "description": "Responsive Search Ad headline strategy",
        "use_in_skills": [],  # future skill k48
        "template": {
            "headline_categories": {
                "brand": "3 headlines (brand name + value prop)",
                "benefit": "3 headlines (outcome-focused)",
                "feature": "3 headlines (capability-specific)",
                "cta": "3 headlines (action-oriented)",
                "social_proof": "3 headlines (stats, awards, reviews)",
            },
            "rules": [
                "Every combination must read coherently",
                "Include keyword insertion where relevant",
                "Test 15 headlines with pin strategy",
                "Refresh on creative fatigue (declining CTR)",
            ],
        },
    },

    # ═══════════════════════════════════════════════════════════════
    # OPERATIONS FRAMEWORKS
    # ═══════════════════════════════════════════════════════════════

    "AUTOMATION_GOVERNANCE": {
        "id": "FW-013",
        "source": "Automation Governance Architect (agency-agents/specialized)",
        "domain": "operations",
        "description": "Decision framework for what to automate",
        "use_in_skills": [],  # n8n integration phase
        "template": {
            "evaluation_dimensions": [
                "Time savings per month (recurring and material?)",
                "Data criticality (customer/finance/contract records?)",
                "External dependency risk (stable APIs?)",
                "Scalability (1x to 100x?)",
            ],
            "verdicts": [
                "APPROVE — strong value, controlled risk",
                "APPROVE AS PILOT — limited rollout required",
                "PARTIAL AUTOMATION — safe segments only, human checkpoints",
                "DEFER — process not mature",
                "REJECT — weak economics or unacceptable risk",
            ],
            "workflow_standard": [
                "1. Trigger", "2. Input Validation", "3. Data Normalization",
                "4. Business Logic", "5. External Actions", "6. Result Validation",
                "7. Logging/Audit Trail", "8. Error Branch", "9. Fallback/Recovery",
                "10. Completion/Status Writeback",
            ],
        },
    },

    "AI_CITATION": {
        "id": "FW-014",
        "source": "AI Citation Strategist (agency-agents/marketing)",
        "domain": "content",
        "description": "AEO/GEO — brand visibility in AI search results",
        "use_in_skills": [],  # future skill k49
        "template": {
            "audit_platforms": ["ChatGPT", "Claude", "Gemini", "Perplexity"],
            "metrics": {
                "citation_rate": "% of prompts where brand is cited",
                "competitor_rate": "% where competitor cited instead",
                "gap": "citation_rate - competitor_rate",
            },
            "fix_priorities": [
                "Entity clarity (schema markup, structured data)",
                "FAQ alignment (match common AI query patterns)",
                "Comparison pages (structured vs prose)",
                "Authority signals (backlinks from cited domains)",
            ],
        },
    },

    "CHALLENGER_MESSAGING": {
        "id": "FW-015",
        "source": "Deal Strategist (agency-agents/sales)",
        "domain": "growth",
        "description": "Challenger sale 6-step commercial teaching sequence",
        "use_in_skills": ["a01-growth-strategy-analyst"],
        "template": {
            "steps": [
                "1. Warmer — demonstrate understanding of their world (pattern recognition, not flattery)",
                "2. Reframe — introduce insight challenging their assumptions",
                "3. Rational Drowning — quantify cost of status quo (stack evidence)",
                "4. Emotional Impact — make it personal (who feels this pain daily?)",
                "5. A New Way — present alternative approach (not product yet)",
                "6. Your Solution — product as inevitable conclusion of the new way",
            ],
        },
    },
}


def get_framework(framework_id):
    """Get a framework by ID or name."""
    for name, fw in FRAMEWORKS.items():
        if name == framework_id or fw["id"] == framework_id:
            return fw
    return None


def get_frameworks_for_skill(skill_id):
    """Get all frameworks that apply to a skill."""
    return {name: fw for name, fw in FRAMEWORKS.items()
            if skill_id in fw.get("use_in_skills", [])}


def get_frameworks_for_domain(domain):
    """Get all frameworks for a domain."""
    return {name: fw for name, fw in FRAMEWORKS.items()
            if fw.get("domain") == domain}


def list_frameworks():
    """List all frameworks."""
    print(f"\n  NemoClaw Production Framework Library ({len(FRAMEWORKS)} frameworks)\n")
    for name, fw in FRAMEWORKS.items():
        skills = fw.get("use_in_skills", [])
        skill_str = ", ".join(skills) if skills else "future"
        print(f"  [{fw['id']}] {name}")
        print(f"    {fw['description']}")
        print(f"    Domain: {fw['domain']} | Skills: {skill_str}")
        print()


if __name__ == "__main__":
    list_frameworks()
