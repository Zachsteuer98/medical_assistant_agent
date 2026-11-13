"""Evaluation question set for the public corpus (10 VA/DoD Clinical Practice Guidelines).

Questions are paraphrased clinician questions, each answered by a specific recommendation.
expected_pages lists the recommendation-table page plus the pages of that recommendation's
discussion section (1-based physical pages, as cited). The last three probes are clinical
topics none of the guidelines cover; two are near misses (the COPD guideline discusses
antibiotics for exacerbations; the lipid and hypertension guidelines mention gout as a drug
side effect), so retrieval returns plausible-looking but non-answering context.
"""

from evaluation.queries import EvalQuery


def _pages(*spans: int | tuple[int, int]) -> tuple[int, ...]:
    """Expand single pages and inclusive (first, last) spans into a sorted page tuple."""
    pages: set[int] = set()
    for span in spans:
        first, last = (span, span) if isinstance(span, int) else span
        pages.update(range(first, last + 1))
    return tuple(sorted(pages))


PUBLIC_QUERIES: tuple[EvalQuery, ...] = (
    EvalQuery(
        "P01",
        "Diabetes: glycemic target",
        "What HbA1c target range is suggested for most adults with type 2 diabetes?",
        expected_source="Type 2 Diabetes CPG 2023",
        expected_pages=_pages(25, (42, 45)),  # Rec 9-10
    ),
    EvalQuery(
        "P02",
        "Diabetes: pharmacotherapy",
        "Which glucose-lowering drug classes are recommended for a patient with type 2 "
        "diabetes and established atherosclerotic cardiovascular disease?",
        expected_source="Type 2 Diabetes CPG 2023",
        expected_pages=_pages(26, (58, 61)),  # Rec 19-20
    ),
    EvalQuery(
        "P03",
        "Hypertension: BP goal",
        "What systolic blood pressure target should be used when treating adults with "
        "hypertension?",
        expected_source="Hypertension CPG 2026",
        expected_pages=_pages(26, (33, 35)),  # Rec 4
    ),
    EvalQuery(
        "P04",
        "Hypertension: resistant HTN",
        "Blood pressure is still uncontrolled on maximally tolerated doses of a thiazide, a "
        "calcium channel blocker and an ACE inhibitor. What should be added next?",
        expected_source="Hypertension CPG 2026",
        expected_pages=_pages(27, (44, 47)),  # Rec 13
    ),
    EvalQuery(
        "P05",
        "Lipids: primary prevention",
        "In primary prevention, which patients should be started on at least a "
        "moderate-intensity statin?",
        expected_source="Lipids CPG 2025",
        expected_pages=_pages(24, (36, 38)),  # Rec 7
    ),
    EvalQuery(
        "P06",
        "Lipids: statin intolerance",
        "How should a patient who cannot tolerate a statin be managed?",
        expected_source="Lipids CPG 2025",
        expected_pages=_pages((25, 26), (53, 56)),  # Rec 18-19
    ),
    EvalQuery(
        "P07",
        "Asthma: step-up therapy",
        "What inhaler regimen is recommended for a patient whose asthma is uncontrolled on "
        "an inhaled corticosteroid alone?",
        expected_source="Asthma CPG 2025",
        expected_pages=_pages(30, (42, 43)),  # Rec 7
    ),
    EvalQuery(
        "P08",
        "COPD: initial maintenance therapy",
        "What initial maintenance inhaler therapy is recommended for COPD with a moderate to "
        "severe symptom burden?",
        expected_source="COPD CPG 2026",
        expected_pages=_pages(29, (39, 40)),  # Rec 8
    ),
    EvalQuery(
        "P09",
        "CKD: SGLT2 inhibitors",
        "Which patients with chronic kidney disease should have an SGLT2 inhibitor added, and "
        "for how long should it be continued?",
        expected_source="CKD CPG 2025",
        expected_pages=_pages((33, 34), (58, 60)),  # Rec 15
    ),
    EvalQuery(
        "P10",
        "Depression: continuation phase",
        "After a patient with major depressive disorder reaches remission on an "
        "antidepressant, how long should the medication be continued?",
        expected_source="Depression CPG 2022",
        expected_pages=_pages(22, 25, (54, 55)),  # Sidebar + Rec 21
    ),
    EvalQuery(
        "P11",
        "Low back pain: pharmacotherapy",
        "Which medications are suggested for chronic low back pain, and which drug classes "
        "does the guideline advise against?",
        expected_source="Low Back Pain CPG 2022",
        expected_pages=_pages(24, (49, 63)),  # Rec 18-29
    ),
    EvalQuery(
        "P12",
        "Headache: acute migraine",
        "Which medications are recommended for the acute treatment of a migraine attack?",
        expected_source="Headache CPG 2023",
        expected_pages=_pages(34, 38, (71, 79)),  # Sidebar + Rec 19-22
    ),
    EvalQuery(
        "P13",
        "Insomnia: first-line treatment",
        "What is the first-line treatment for chronic insomnia disorder, and which hypnotics "
        "are acceptable if medication is used?",
        expected_source="Insomnia and Sleep Apnea CPG 2025",
        expected_pages=_pages((34, 35), (45, 56)),  # Rec 5, 8-9
    ),
    EvalQuery(
        "P14",
        "Out of scope (near miss: COPD antibiotics)",
        "What is the first-line antibiotic regimen for an otherwise healthy adult outpatient "
        "with community-acquired pneumonia?",
        answerable=False,
    ),
    EvalQuery(
        "P15",
        "Out of scope (near miss: gout as side effect)",
        "How should an acute gout flare be treated?",
        answerable=False,
    ),
    EvalQuery(
        "P16",
        "Out of scope",
        "What is the recommended starting dose of methotrexate for rheumatoid arthritis?",
        answerable=False,
    ),
)
