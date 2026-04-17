"""Research seed: sources, claims, and warrants for the three operator domains.

The baseline `palantir_seed` defines camps and skeletal claims; this module deepens
the epistemic layer with researched content across three domains:

1. Compute & grid --- frontier training scale, datacenter load, interconnection queues.
2. Government/defense AI --- Palantir scale, DoD contract flow, labor resistance.
3. Suffering distribution --- global disease burden, poverty, mortality, animal scale.

URLs are empty where they could not be verified in-session; citations fall back to
publication name + report title. Re-running this module overwrites the research
YAMLs with the content declared here --- operator edits survive only via new files.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from afls.config import data_dir
from afls.schema import (
    BaseNode,
    DescriptiveClaim,
    MethodTag,
    Source,
    SourceKind,
    Support,
    Warrant,
)
from afls.storage import save_node

FIXED_TS = datetime(2026, 4, 17, 0, 0, 0, tzinfo=UTC)


def _stamp(node: BaseNode) -> BaseNode:
    node.created_at = FIXED_TS
    node.updated_at = FIXED_TS
    return node


# -----------------------------------------------------------------------------
# Domain 1: Compute & grid
# -----------------------------------------------------------------------------


def _compute_grid_sources() -> list[Source]:
    return [
        Source(
            id="src_lbnl_queued_up_2024",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Queued Up: 2024 Edition --- Characteristics of Power Plants Seeking "
            "Transmission Interconnection",
            url="",
            authors=["Joseph Rand", "Will Gorman", "Ryan Wiser"],
            published_at="2024-04",
            reliability=0.95,
            notes="Canonical US interconnection-queue dataset, covers all seven ISOs plus "
            "non-ISO utilities. URL not verified in session.",
        ),
        Source(
            id="src_iea_electricity_2024",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Electricity 2024 --- Analysis and Forecast to 2026",
            url="",
            authors=["International Energy Agency"],
            published_at="2024-01",
            reliability=0.85,
            notes="First IEA report with dedicated datacenter/AI/crypto electricity chapter. "
            "Global view; US numbers are a subset and run lower than US-specific forecasts.",
        ),
        Source(
            id="src_epri_powering_intelligence",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Powering Intelligence: Analyzing Artificial Intelligence and Data "
            "Center Energy Consumption",
            url="",
            authors=["Electric Power Research Institute"],
            published_at="2024-05",
            reliability=0.9,
            notes="US-utility research arm; numbers feed utility IRPs directly.",
        ),
        Source(
            id="src_goldman_gen_power",
            source_kind=SourceKind.BLOG,
            title="Generational growth: AI, data centers and the coming US power demand surge",
            url="",
            authors=["Goldman Sachs Research"],
            published_at="2024-04",
            reliability=0.75,
            notes="Sell-side research. Directionally cited widely; forecasts run higher than "
            "IEA and EPRI central scenarios.",
        ),
        Source(
            id="src_doe_transmission_needs",
            source_kind=SourceKind.PRIMARY_DOC,
            title="National Transmission Needs Study",
            url="",
            authors=["US Department of Energy, Grid Deployment Office"],
            published_at="2023-10",
            reliability=0.9,
            notes="Statutorily required triennial DOE study. Feeds FERC Order 1920 rulemaking.",
        ),
        Source(
            id="src_sia_2024_state",
            source_kind=SourceKind.PRIMARY_DOC,
            title="2024 State of the U.S. Semiconductor Industry",
            url="",
            authors=["Semiconductor Industry Association"],
            published_at="2024-09",
            reliability=0.85,
            notes="Trade association; self-interested on policy framing, rigorous on "
            "production and capacity data.",
        ),
        Source(
            id="src_epoch_algorithmic_progress",
            source_kind=SourceKind.PAPER,
            title="Algorithmic Progress in Language Models",
            url="",
            authors=[
                "Anson Ho",
                "Tamay Besiroglu",
                "Ege Erdil",
                "David Owen",
                "Robi Rahman",
                "Zifan Carl Guo",
                "David Atkinson",
                "Neil Thompson",
                "Jaime Sevilla",
            ],
            published_at="2024-03",
            reliability=0.85,
            notes="Peer-reviewed methodology; conclusions depend on benchmark selection.",
        ),
        Source(
            id="src_epoch_training_cost",
            source_kind=SourceKind.PAPER,
            title="The Rising Costs of Training Frontier AI Models",
            url="",
            authors=[
                "Ben Cottier",
                "Robi Rahman",
                "Loredana Fattorini",
                "Nestor Maslej",
                "David Owen",
            ],
            published_at="2024-05",
            reliability=0.85,
            notes="Triangulates hardware-hours, chip rental rates, and staff costs.",
        ),
        Source(
            id="src_pjm_2024_capacity",
            source_kind=SourceKind.FILING,
            title="2025/2026 Base Residual Auction Results",
            url="",
            authors=["PJM Interconnection"],
            published_at="2024-07",
            reliability=0.95,
            notes="RTO primary-auction document, audited. Direct market evidence of "
            "AI/datacenter load tightening the eastern US grid.",
        ),
        Source(
            id="src_semianalysis_datacenter",
            source_kind=SourceKind.BLOG,
            title="AI Datacenter Energy Dilemma --- Race for AI Datacenter Space",
            url="",
            authors=["Dylan Patel", "Daniel Nishball"],
            published_at="2024-03",
            reliability=0.8,
            notes="Industry-source triangulation; occasionally over-confident point estimates "
            "but strongest independent pipeline-level visibility.",
        ),
    ]


def _compute_grid_claims() -> list[DescriptiveClaim]:
    return [
        DescriptiveClaim(
            id="desc_training_compute_growth",
            text="Training compute for frontier AI models has grown roughly 4-5x per year "
            "from 2010 through 2024, corresponding to a doubling time of about 5-6 months.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_flagship_training_cost",
            text="Amortized hardware and energy cost of flagship training runs has grown "
            "~2.4x annually; GPT-4-class runs cost on the order of $40M-$80M (2023) and the "
            "next generation crossed $100M.",
            confidence=0.75,
        ),
        DescriptiveClaim(
            id="desc_algorithmic_efficiency",
            text="Algorithmic progress roughly halves the compute required to reach a fixed "
            "language-model performance threshold every ~8 months, so algorithmic efficiency "
            "contributes comparably to raw hardware scaling in observed capability gains.",
            confidence=0.7,
        ),
        DescriptiveClaim(
            id="desc_us_datacenter_load_forecast",
            text="Credible 2030 forecasts for US datacenter share of electricity consumption "
            "diverge by more than 2x --- from ~4.6% (IEA/EPRI conservative) to ~9% (Goldman "
            "Sachs, EPRI high scenario) --- reflecting genuine uncertainty, not measurement error.",
            confidence=0.85,
        ),
        DescriptiveClaim(
            id="desc_interconnection_queue_backlog",
            text="As of end-2023, roughly 2,600 GW of generation and storage capacity sat in "
            "US interconnection queues --- more than double the existing US grid --- with "
            "typical wait times of ~5 years and completion rates below 20%.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_transmission_stall",
            text="US high-voltage transmission buildout has slowed to ~1% annual circuit-mile "
            "growth despite DOE finding a need to more than double interregional transmission "
            "capacity by 2035; siting, permitting, and cost-allocation disputes are the binding "
            "constraints, not technology or capital.",
            confidence=0.8,
        ),
        DescriptiveClaim(
            id="desc_leading_edge_chip_concentration",
            text="Over 90% of leading-edge (<10nm, effectively 100% of <5nm) logic fabrication "
            "capacity sits in Taiwan at TSMC; HBM memory for AI accelerators is ~95% produced "
            "by three Korean/US firms, with SK Hynix alone holding >50% share in 2024.",
            confidence=0.9,
        ),
    ]


def _compute_grid_warrants() -> list[Warrant]:
    return [
        Warrant(
            id="war_epoch_compute_growth",
            claim_id="desc_training_compute_growth",
            source_id="src_epoch_ai",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.95,
            locator="Notable AI Models dataset; 2024 compute-growth post",
        ),
        Warrant(
            id="war_rand_cost_triangulation",
            claim_id="desc_flagship_training_cost",
            source_id="src_epoch_training_cost",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Figure 1; Table 2",
        ),
        Warrant(
            id="war_semi_cost_leak",
            claim_id="desc_flagship_training_cost",
            source_id="src_semianalysis",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.SUPPORT,
            weight=0.7,
            locator="GPT-4 architecture/cost posts, 2023-2024",
        ),
        Warrant(
            id="war_algo_progress_epoch",
            claim_id="desc_algorithmic_efficiency",
            source_id="src_epoch_algorithmic_progress",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Abstract; headline finding",
            quote="compute required to reach a set performance threshold has halved "
            "approximately every 8 months",
        ),
        Warrant(
            id="war_algo_caveat_epoch",
            claim_id="desc_algorithmic_efficiency",
            source_id="src_epoch_ai",
            method_tag=MethodTag.EXPERT_ESTIMATE,
            supports=Support.QUALIFY,
            weight=0.5,
            locator="Epoch commentary on benchmark-dependence of efficiency estimates",
        ),
        Warrant(
            id="war_iea_low_forecast",
            claim_id="desc_us_datacenter_load_forecast",
            source_id="src_iea_electricity_2024",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.QUALIFY,
            weight=0.8,
            locator="Analysing Electricity Demand; data centres chapter",
        ),
        Warrant(
            id="war_epri_scenarios",
            claim_id="desc_us_datacenter_load_forecast",
            source_id="src_epri_powering_intelligence",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Scenario table: 4.6%-9.1% by 2030",
        ),
        Warrant(
            id="war_goldman_high_forecast",
            claim_id="desc_us_datacenter_load_forecast",
            source_id="src_goldman_gen_power",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.CONTRADICT,
            weight=0.7,
            locator="Executive summary; 160% growth figure",
        ),
        Warrant(
            id="war_pjm_market_signal",
            claim_id="desc_us_datacenter_load_forecast",
            source_id="src_pjm_2024_capacity",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.75,
            locator="2025/2026 BRA clearing results",
        ),
        Warrant(
            id="war_lbnl_queue_size",
            claim_id="desc_interconnection_queue_backlog",
            source_id="src_lbnl_queued_up_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.95,
            locator="Figure 1; summary tables",
            quote="~2,600 GW of total generation and storage capacity in queues at end-2023",
        ),
        Warrant(
            id="war_lbnl_wait_time",
            claim_id="desc_interconnection_queue_backlog",
            source_id="src_lbnl_queued_up_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Completion-rate and duration analysis",
        ),
        Warrant(
            id="war_doe_transmission_need",
            claim_id="desc_transmission_stall",
            source_id="src_doe_transmission_needs",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Chapter 3 regional needs; interregional findings",
        ),
        Warrant(
            id="war_lbnl_transmission_qualify",
            claim_id="desc_transmission_stall",
            source_id="src_lbnl_queued_up_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.QUALIFY,
            weight=0.6,
            locator="Interconnection-upgrade cost trend figures",
        ),
        Warrant(
            id="war_sia_chip_concentration",
            claim_id="desc_leading_edge_chip_concentration",
            source_id="src_sia_2024_state",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Geography of semiconductor manufacturing section",
        ),
        Warrant(
            id="war_semi_hbm",
            claim_id="desc_leading_edge_chip_concentration",
            source_id="src_semianalysis",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.SUPPORT,
            weight=0.75,
            locator="HBM supply/demand coverage, 2024",
        ),
    ]


# -----------------------------------------------------------------------------
# Domain 2: Government / defense AI
# -----------------------------------------------------------------------------


def _gov_defense_sources() -> list[Source]:
    return [
        Source(
            id="src_pltr_10k_2024",
            source_kind=SourceKind.FILING,
            title="Palantir Technologies Inc. Form 10-K Annual Report (FY 2024)",
            url="",
            authors=["Palantir Technologies Inc."],
            published_at="2025-02",
            reliability=0.9,
            notes="SEC filing. High reliability on fiscal numbers; self-interested on "
            "competitive-landscape framing.",
        ),
        Source(
            id="src_pltr_earnings_q4_2024",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Palantir Q4 2024 Earnings Call Transcript",
            url="",
            authors=["Alexander Karp", "David Glazer", "Shyam Sankar"],
            published_at="2025-02",
            reliability=0.75,
            notes="CEO/CFO prepared remarks and analyst Q&A. Forward-looking commentary is "
            "promotional; historical numbers reconcile to the 10-K.",
        ),
        Source(
            id="src_nyt_palantir_2024",
            source_kind=SourceKind.PRESS,
            title="New York Times coverage of Palantir defense expansion, 2023-2024",
            url="",
            authors=["New York Times"],
            published_at="2024",
            reliability=0.7,
            notes="Editorially rigorous but episodic; aggregates rather than breaks stories.",
        ),
        Source(
            id="src_intercept_palantir",
            source_kind=SourceKind.PRESS,
            title="The Intercept coverage of Palantir contracts and DoD AI programs",
            url="",
            authors=["Sam Biddle", "The Intercept staff"],
            published_at="2022-2024",
            reliability=0.65,
            notes="Adversarial reporting on DoD/IC contracting. Strong sourcing on leaked "
            "documents; framing is consistently critical of vendor claims.",
        ),
        Source(
            id="src_crs_dod_ai",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Artificial Intelligence and National Security (CRS Report R45178)",
            url="",
            authors=["Congressional Research Service"],
            published_at="2024",
            reliability=0.85,
            notes="Congressional staff research arm. Non-partisan, cites primary DoD documents.",
        ),
        Source(
            id="src_gao_dod_ai",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Artificial Intelligence: DoD Needs Department-Wide Guidance to Inform "
            "Acquisitions (GAO-22-105834 and follow-ups)",
            url="",
            authors=["US Government Accountability Office"],
            published_at="2022-2024",
            reliability=0.9,
            notes="Audit of DoD AI adoption pace and contracting gaps. Authoritative on "
            "absorption rate.",
        ),
        Source(
            id="src_usaspending",
            source_kind=SourceKind.DATASET,
            title="USASpending.gov federal contract awards",
            url="https://www.usaspending.gov",
            authors=["US Treasury / Bureau of the Fiscal Service"],
            published_at="ongoing",
            reliability=0.9,
            notes="Primary federal contract-level dataset. Query completeness limited by "
            "inconsistent PSC/NAICS tagging on AI-specific line items.",
        ),
        Source(
            id="src_dod_maven_contract",
            source_kind=SourceKind.PRIMARY_DOC,
            title="DoD announcement of Maven Smart System contract award to Palantir ($480M)",
            url="",
            authors=["US Department of Defense"],
            published_at="2024-05",
            reliability=0.9,
            notes="Primary contract announcement via DoD and NGA press releases.",
        ),
        Source(
            id="src_google_maven_letter_2018",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Google employee open letter opposing Project Maven",
            url="",
            authors=["Google employees (3,100+ signatories)"],
            published_at="2018-04",
            reliability=0.9,
            notes="Primary-source text of the internal letter that led Google to decline "
            "Maven contract renewal.",
        ),
        Source(
            id="src_jwcc_announcement",
            source_kind=SourceKind.PRIMARY_DOC,
            title="DoD Joint Warfighting Cloud Capability (JWCC) contract announcement",
            url="",
            authors=["US Department of Defense"],
            published_at="2022-12",
            reliability=0.9,
            notes="Awards $9B ceiling IDIQ across AWS, Microsoft, Google, Oracle.",
        ),
        Source(
            id="src_microsoft_workers_2019",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Microsoft employee open letter opposing HoloLens/IVAS contract",
            url="",
            authors=["Microsoft employees"],
            published_at="2019-02",
            reliability=0.85,
            notes="Primary-source internal letter opposing the Army IVAS contract.",
        ),
        Source(
            id="src_nyt_openai_idf",
            source_kind=SourceKind.PRESS,
            title="Coverage of OpenAI and Microsoft AI use by Israeli military, 2024",
            url="",
            authors=["New York Times", "Associated Press"],
            published_at="2024",
            reliability=0.75,
            notes="Reports on OpenAI's 2024 policy change allowing military use and downstream "
            "Azure-IDF deployments.",
        ),
        Source(
            id="src_pltr_ceo_interview",
            source_kind=SourceKind.PRESS,
            title="Alex Karp public interviews and op-eds, 2023-2024",
            url="",
            authors=["Alexander Karp"],
            published_at="2023-2024",
            reliability=0.55,
            notes="Primary testimony from Palantir's CEO on competitive position and workforce "
            "resistance. Promotional; useful as a position signal, not a fact source.",
        ),
    ]


def _gov_defense_claims() -> list[DescriptiveClaim]:
    return [
        DescriptiveClaim(
            id="desc_palantir_gov_revenue",
            text="Palantir's US Government segment revenue exceeded $1B annualized by "
            "end-2024, with US Government revenue growth accelerating above 40% YoY in "
            "multiple 2024 quarters.",
            confidence=0.85,
        ),
        DescriptiveClaim(
            id="desc_dod_ai_contract_spend",
            text="DoD obligated AI-related contract spending rose substantially 2022-2025, "
            "driven by JWCC, Project Maven, and CDAO-managed pilots; precise totals are "
            "hampered by inconsistent AI tagging on contract line items.",
            confidence=0.7,
        ),
        DescriptiveClaim(
            id="desc_maven_status",
            text="Project Maven (DoD computer-vision targeting) remains in production use with "
            "combatant-command consumers despite Google's 2018 withdrawal; Palantir holds a "
            "$480M 2024 contract expanding Maven capability.",
            confidence=0.85,
        ),
        DescriptiveClaim(
            id="desc_palantir_dominant",
            text="No other pure-play US defense-AI software vendor has matched Palantir's "
            "contract backlog or combatant-command integration depth; cloud-provider primes "
            "(AWS, Microsoft, Google, Oracle via JWCC) supply infrastructure, not mission-"
            "software integration.",
            confidence=0.75,
        ),
        DescriptiveClaim(
            id="desc_ic_cloud_concentration",
            text="US intelligence and defense cloud workloads are concentrated across four "
            "hyperscale providers (AWS GovCloud/TS, Azure Government/Secret, Google Cloud, "
            "Oracle) under the JWCC $9B ceiling, with Palantir as the dominant mission-"
            "software layer above them.",
            confidence=0.8,
        ),
        DescriptiveClaim(
            id="desc_workforce_resistance",
            text="Frontier-lab and big-tech employees have episodically resisted DoD contracts "
            "(Google Maven 2018, Microsoft IVAS 2019, Microsoft/OpenAI IDF deployments 2024), "
            "producing temporary pauses but no sustained shift in vendor willingness.",
            confidence=0.8,
        ),
    ]


def _gov_defense_warrants() -> list[Warrant]:
    return [
        Warrant(
            id="war_pltr_10k_revenue",
            claim_id="desc_palantir_gov_revenue",
            source_id="src_pltr_10k_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Segment revenue tables, Item 7 MD&A",
        ),
        Warrant(
            id="war_pltr_earnings_call_growth",
            claim_id="desc_palantir_gov_revenue",
            source_id="src_pltr_earnings_q4_2024",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.SUPPORT,
            weight=0.75,
            locator="Prepared remarks; US Government growth commentary",
        ),
        Warrant(
            id="war_nyt_pltr_scale",
            claim_id="desc_palantir_gov_revenue",
            source_id="src_nyt_palantir_2024",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.SUPPORT,
            weight=0.65,
            locator="Business section features, 2023-2024",
        ),
        Warrant(
            id="war_crs_ai_dod_spend",
            claim_id="desc_dod_ai_contract_spend",
            source_id="src_crs_dod_ai",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.SUPPORT,
            weight=0.8,
            locator="AI funding appendix; DoD budget rollups",
        ),
        Warrant(
            id="war_gao_ai_slow",
            claim_id="desc_dod_ai_contract_spend",
            source_id="src_gao_dod_ai",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.QUALIFY,
            weight=0.75,
            locator="Summary findings on acquisition-pace gaps",
        ),
        Warrant(
            id="war_usaspending_contracts",
            claim_id="desc_dod_ai_contract_spend",
            source_id="src_usaspending",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="DoD AI-tagged obligations 2022-2025",
        ),
        Warrant(
            id="war_intercept_contract_failures",
            claim_id="desc_dod_ai_contract_spend",
            source_id="src_intercept_palantir",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.CONTRADICT,
            weight=0.55,
            locator="Investigative pieces on DoD AI pilot failures and miscategorization",
        ),
        Warrant(
            id="war_pltr_maven_contract",
            claim_id="desc_maven_status",
            source_id="src_dod_maven_contract",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="$480M Maven Smart System award, May 2024",
        ),
        Warrant(
            id="war_google_maven_letter_history",
            claim_id="desc_maven_status",
            source_id="src_google_maven_letter_2018",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Open letter text; 3,100+ signatories",
        ),
        Warrant(
            id="war_nyt_maven_ongoing",
            claim_id="desc_maven_status",
            source_id="src_nyt_palantir_2024",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.SUPPORT,
            weight=0.7,
            locator="Maven continuation coverage post-Google",
        ),
        Warrant(
            id="war_pltr_10k_competitive",
            claim_id="desc_palantir_dominant",
            source_id="src_pltr_10k_2024",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.SUPPORT,
            weight=0.6,
            locator="Competition section, Item 1",
        ),
        Warrant(
            id="war_intercept_dominance_skeptical",
            claim_id="desc_palantir_dominant",
            source_id="src_intercept_palantir",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.CONTRADICT,
            weight=0.5,
            locator="Coverage framing Palantir as over-sold relative to internal-tool alternatives",
        ),
        Warrant(
            id="war_crs_vendor_landscape",
            claim_id="desc_palantir_dominant",
            source_id="src_crs_dod_ai",
            method_tag=MethodTag.EXPERT_ESTIMATE,
            supports=Support.SUPPORT,
            weight=0.75,
            locator="Vendor-landscape discussion",
        ),
        Warrant(
            id="war_jwcc_award",
            claim_id="desc_ic_cloud_concentration",
            source_id="src_jwcc_announcement",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Award announcement text; vendor list",
        ),
        Warrant(
            id="war_semi_cloud_concentration",
            claim_id="desc_ic_cloud_concentration",
            source_id="src_semianalysis",
            method_tag=MethodTag.TRIANGULATION,
            supports=Support.SUPPORT,
            weight=0.7,
            locator="Hyperscaler capex and share coverage, 2024",
        ),
        Warrant(
            id="war_google_maven_withdraw",
            claim_id="desc_workforce_resistance",
            source_id="src_google_maven_letter_2018",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Open letter and subsequent Google announcement",
        ),
        Warrant(
            id="war_microsoft_workers_ivas",
            claim_id="desc_workforce_resistance",
            source_id="src_microsoft_workers_2019",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Employee open letter, February 2019",
        ),
        Warrant(
            id="war_openai_idf_nyt",
            claim_id="desc_workforce_resistance",
            source_id="src_nyt_openai_idf",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.SUPPORT,
            weight=0.75,
            locator="OpenAI military-use policy-change coverage, 2024",
        ),
        Warrant(
            id="war_pltr_ceo_dismisses_resistance",
            claim_id="desc_workforce_resistance",
            source_id="src_pltr_ceo_interview",
            method_tag=MethodTag.PRIMARY_TESTIMONY,
            supports=Support.CONTRADICT,
            weight=0.5,
            locator="Karp interviews dismissing employee resistance as inconsequential",
        ),
    ]


# -----------------------------------------------------------------------------
# Domain 3: Suffering distribution
# -----------------------------------------------------------------------------


def _suffering_sources() -> list[Source]:
    return [
        Source(
            id="src_ihme_gbd_2021",
            source_kind=SourceKind.DATASET,
            title="Global Burden of Disease Study 2021",
            url="",
            authors=["Institute for Health Metrics and Evaluation"],
            published_at="2024",
            reliability=0.9,
            notes="Most comprehensive global morbidity/mortality dataset. Methodology is "
            "heavily modeled; uncertainty intervals are published.",
        ),
        Source(
            id="src_who_mental_health_2022",
            source_kind=SourceKind.PRIMARY_DOC,
            title="World Mental Health Report: Transforming Mental Health for All",
            url="",
            authors=["World Health Organization"],
            published_at="2022",
            reliability=0.9,
            notes="WHO's flagship mental-health synthesis; pulls from IHME and country surveys.",
        ),
        Source(
            id="src_wb_poverty_2024",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Poverty, Prosperity, and Planet Report (World Bank)",
            url="",
            authors=["World Bank"],
            published_at="2024-10",
            reliability=0.9,
            notes="Successor to Poverty and Shared Prosperity. Uses $2.15/day 2017-PPP line "
            "as the international extreme-poverty threshold.",
        ),
        Source(
            id="src_unicef_igme_2024",
            source_kind=SourceKind.DATASET,
            title="UN Inter-agency Group for Child Mortality Estimation (IGME) 2024 report",
            url="",
            authors=["UNICEF", "WHO", "World Bank", "UN Population Division"],
            published_at="2024",
            reliability=0.95,
            notes="Canonical child-mortality estimates.",
        ),
        Source(
            id="src_owid",
            source_kind=SourceKind.DASHBOARD,
            title="Our World in Data",
            url="https://ourworldindata.org",
            authors=["Max Roser", "Hannah Ritchie", "Esteban Ortiz-Ospina", "et al."],
            published_at="ongoing",
            reliability=0.85,
            notes="Meta-source: visualizes and harmonizes data from IHME, WHO, WB, UN, FAO. "
            "Peer-reviewed methodology notes per chart.",
        ),
        Source(
            id="src_fao_faostat_2024",
            source_kind=SourceKind.DATASET,
            title="FAOSTAT Production and Trade of Livestock Primary",
            url="https://www.fao.org/faostat",
            authors=["Food and Agriculture Organization of the United Nations"],
            published_at="ongoing",
            reliability=0.9,
            notes="Primary global dataset for land-animal slaughter counts.",
        ),
        Source(
            id="src_sentience_institute_farming",
            source_kind=SourceKind.BLOG,
            title="Factory Farming in the U.S. and globally",
            url="",
            authors=["Sentience Institute"],
            published_at="2019-2024",
            reliability=0.7,
            notes="Advocacy-adjacent; careful methodology for factory-farming share estimates. "
            "Triangulates USDA and FAO data.",
        ),
        Source(
            id="src_who_ncd_fact",
            source_kind=SourceKind.PRIMARY_DOC,
            title="Noncommunicable Diseases Country Profiles and Fact Sheets",
            url="",
            authors=["World Health Organization"],
            published_at="2023-2024",
            reliability=0.9,
            notes="WHO NCD framework reporting. Authoritative on global NCD share-of-deaths.",
        ),
        Source(
            id="src_un_desa_wpp_2024",
            source_kind=SourceKind.DATASET,
            title="World Population Prospects 2024",
            url="",
            authors=["United Nations Department of Economic and Social Affairs"],
            published_at="2024",
            reliability=0.9,
            notes="Canonical global demographic dataset.",
        ),
    ]


def _suffering_claims() -> list[DescriptiveClaim]:
    return [
        DescriptiveClaim(
            id="desc_mental_health_burden",
            text="Mental and neurological disorders are the leading cause of years-lived-with-"
            "disability (YLD) globally, accounting for roughly 15-16% of total YLDs; depression "
            "and anxiety dominate that burden.",
            confidence=0.85,
        ),
        DescriptiveClaim(
            id="desc_extreme_poverty_trajectory",
            text="The global extreme-poverty rate ($2.15/day 2017-PPP) fell from ~44% of world "
            "population in 1981 to ~8.5% in the early 2020s; the remaining ~700M people in "
            "extreme poverty are heavily concentrated in Sub-Saharan Africa.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_child_mortality_progress",
            text="Under-5 child mortality halved between 2000 and the early 2020s, from ~76 "
            "to ~37 deaths per 1,000 live births globally, though ~4.9M children still die "
            "before their fifth birthday each year.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_animal_suffering_scale",
            text="Approximately 80-83 billion land animals are slaughtered annually for food "
            "(FAO), with roughly 70% raised in intensive 'factory farm' systems; an additional "
            "~1-3 trillion finfish and shellfish are farmed or wild-caught each year.",
            confidence=0.8,
        ),
        DescriptiveClaim(
            id="desc_life_expectancy_gain",
            text="Global life expectancy at birth rose from ~31 years in 1900 to ~73 years by "
            "the early 2020s, with the steepest gains in the second half of the 20th century, "
            "driven by reductions in child and infectious-disease mortality.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_ncd_shift",
            text="Non-communicable diseases (cardiovascular, cancer, chronic respiratory, "
            "diabetes) now account for roughly 74% of global deaths annually, having surpassed "
            "communicable/maternal/neonatal/nutritional conditions in both absolute and "
            "proportional terms since the 1990s.",
            confidence=0.9,
        ),
        DescriptiveClaim(
            id="desc_suffering_geography",
            text="Age-standardized DALY rates vary more than 3x across regions; the highest "
            "burden is concentrated in Sub-Saharan Africa (driven by communicable disease and "
            "neonatal conditions) and the lowest in high-income East Asia.",
            confidence=0.85,
        ),
    ]


def _suffering_warrants() -> list[Warrant]:
    return [
        Warrant(
            id="war_ihme_gbd_mental",
            claim_id="desc_mental_health_burden",
            source_id="src_ihme_gbd_2021",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="YLD by cause, 2021 estimates",
        ),
        Warrant(
            id="war_who_mental_health",
            claim_id="desc_mental_health_burden",
            source_id="src_who_mental_health_2022",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Executive summary; burden-of-disease chapter",
        ),
        Warrant(
            id="war_wb_poverty",
            claim_id="desc_extreme_poverty_trajectory",
            source_id="src_wb_poverty_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.95,
            locator="Global extreme-poverty trajectory tables",
        ),
        Warrant(
            id="war_owid_poverty",
            claim_id="desc_extreme_poverty_trajectory",
            source_id="src_owid",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.8,
            locator="Global extreme-poverty page",
        ),
        Warrant(
            id="war_unicef_igme_child",
            claim_id="desc_child_mortality_progress",
            source_id="src_unicef_igme_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.95,
            locator="Under-5 mortality rate, global",
        ),
        Warrant(
            id="war_fao_slaughter",
            claim_id="desc_animal_suffering_scale",
            source_id="src_fao_faostat_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Livestock primary production; slaughter counts",
        ),
        Warrant(
            id="war_sentience_factory",
            claim_id="desc_animal_suffering_scale",
            source_id="src_sentience_institute_farming",
            method_tag=MethodTag.TRIANGULATION,
            supports=Support.SUPPORT,
            weight=0.7,
            locator="US factory-farming share methodology",
        ),
        Warrant(
            id="war_un_desa_life_expectancy",
            claim_id="desc_life_expectancy_gain",
            source_id="src_un_desa_wpp_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Life expectancy at birth; historical series",
        ),
        Warrant(
            id="war_owid_life_expectancy",
            claim_id="desc_life_expectancy_gain",
            source_id="src_owid",
            method_tag=MethodTag.TRIANGULATION,
            supports=Support.SUPPORT,
            weight=0.8,
            locator="Life expectancy over the long run",
        ),
        Warrant(
            id="war_who_ncd_share",
            claim_id="desc_ncd_shift",
            source_id="src_who_ncd_fact",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="NCD fact sheet; share of global deaths",
        ),
        Warrant(
            id="war_ihme_gbd_ncd",
            claim_id="desc_ncd_shift",
            source_id="src_ihme_gbd_2021",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Cause-of-death distribution, 1990 vs 2021",
        ),
        Warrant(
            id="war_ihme_gbd_geography",
            claim_id="desc_suffering_geography",
            source_id="src_ihme_gbd_2021",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.9,
            locator="Region-by-region age-standardized DALY rates",
        ),
    ]


# -----------------------------------------------------------------------------
# Gap warrants: cover the seed claims the lint rule flagged.
# -----------------------------------------------------------------------------


def _gap_warrants() -> list[Warrant]:
    return [
        Warrant(
            id="war_lbnl_grid_bottleneck",
            claim_id="desc_grid_constraint",
            source_id="src_lbnl_queued_up_2024",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.85,
            locator="Queue size and completion-rate figures",
        ),
        Warrant(
            id="war_pjm_grid_tightening",
            claim_id="desc_grid_constraint",
            source_id="src_pjm_2024_capacity",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.8,
            locator="2025/2026 BRA clearing-price escalation",
        ),
        Warrant(
            id="war_gao_enterprise_lag",
            claim_id="desc_enterprise_slow",
            source_id="src_gao_dod_ai",
            method_tag=MethodTag.DIRECT_MEASUREMENT,
            supports=Support.SUPPORT,
            weight=0.8,
            locator="DoD AI acquisition-pace findings",
        ),
        Warrant(
            id="war_crs_enterprise_lag",
            claim_id="desc_enterprise_slow",
            source_id="src_crs_dod_ai",
            method_tag=MethodTag.MODELED_PROJECTION,
            supports=Support.SUPPORT,
            weight=0.75,
            locator="Adoption-lag commentary",
        ),
        Warrant(
            id="war_epoch_us_lead",
            claim_id="desc_us_lead",
            source_id="src_epoch_ai",
            method_tag=MethodTag.TRIANGULATION,
            supports=Support.SUPPORT,
            weight=0.65,
            locator="US vs China frontier-model comparison",
        ),
        Warrant(
            id="war_semi_us_lead_qualify",
            claim_id="desc_us_lead",
            source_id="src_semianalysis",
            method_tag=MethodTag.JOURNALISTIC_REPORT,
            supports=Support.QUALIFY,
            weight=0.55,
            locator="Chinese domestic chip progress coverage",
        ),
    ]


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def seed(target_dir: Path | None = None) -> int:
    """Write every research node to `target_dir` (default: repo data dir). Returns count."""
    root = target_dir or data_dir()
    nodes: list[BaseNode] = []
    nodes.extend(_compute_grid_sources())
    nodes.extend(_compute_grid_claims())
    nodes.extend(_compute_grid_warrants())
    nodes.extend(_gov_defense_sources())
    nodes.extend(_gov_defense_claims())
    nodes.extend(_gov_defense_warrants())
    nodes.extend(_suffering_sources())
    nodes.extend(_suffering_claims())
    nodes.extend(_suffering_warrants())
    nodes.extend(_gap_warrants())
    for node in nodes:
        save_node(_stamp(node), root)
    return len(nodes)


def main() -> None:
    count = seed()
    print(f"seeded {count} research nodes -> {data_dir()}")


if __name__ == "__main__":
    main()
