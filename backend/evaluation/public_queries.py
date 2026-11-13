"""Evaluation question set for the public corpus (10 VA/DoD Clinical Practice Guidelines).

Questions are paraphrased clinician questions, each answered by a specific recommendation.
expected_pages lists the recommendation-table page plus the pages of that recommendation's
discussion section (1-based physical pages, as cited). expected_facts is the reference answer
for the correctness judge, paraphrased from the recommendation table and checked against the
PDF text. The last three probes are clinical
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
        expected_facts=(
            "An HbA1c range of 7.0-8.5% is suggested for most patients, if it can be safely "
            "achieved (Rec 10).",
        ),
    ),
    EvalQuery(
        "P02",
        "Diabetes: pharmacotherapy",
        "Which glucose-lowering drug classes are recommended for a patient with type 2 "
        "diabetes and established atherosclerotic cardiovascular disease?",
        expected_source="Type 2 Diabetes CPG 2023",
        expected_pages=_pages(26, (58, 61)),  # Rec 19-20
        expected_facts=(
            "Recommend a GLP-1 receptor agonist or an SGLT2 inhibitor with proven cardiovascular "
            "benefit, to reduce major adverse cardiovascular events (Rec 19).",
        ),
    ),
    EvalQuery(
        "P03",
        "Hypertension: BP goal",
        "What systolic blood pressure target should be used when treating adults with "
        "hypertension?",
        expected_source="Hypertension CPG 2026",
        expected_pages=_pages(26, (33, 35)),  # Rec 4
        expected_facts=(
            "Treat to a systolic blood pressure goal below 130 mmHg, depending on patient "
            "characteristics and preferences (Rec 4).",
        ),
    ),
    EvalQuery(
        "P04",
        "Hypertension: resistant HTN",
        "Blood pressure is still uncontrolled on maximally tolerated doses of a thiazide, a "
        "calcium channel blocker and an ACE inhibitor. What should be added next?",
        expected_source="Hypertension CPG 2026",
        expected_pages=_pages(27, (44, 47)),  # Rec 13
        expected_facts=(
            "Add spironolactone or amiloride when blood pressure is uncontrolled on maximally "
            "tolerated triple therapy (thiazide-type diuretic, calcium channel blocker, ACE "
            "inhibitor or ARB) (Rec 13).",
        ),
    ),
    EvalQuery(
        "P05",
        "Lipids: primary prevention",
        "In primary prevention, which patients should be started on at least a "
        "moderate-intensity statin?",
        expected_source="Lipids CPG 2025",
        expected_pages=_pages(24, (36, 38)),  # Rec 7
        expected_facts=(
            "Patients with diabetes (Rec 7).",
            "Patients with an estimated 10-year cardiovascular risk of 10% or higher (Rec 7).",
            "Patients with LDL-C of 190 mg/dL or higher (Rec 7).",
        ),
    ),
    EvalQuery(
        "P06",
        "Lipids: statin intolerance",
        "How should a patient who cannot tolerate a statin be managed?",
        expected_source="Lipids CPG 2025",
        expected_pages=_pages((25, 26), (53, 56)),  # Rec 18-19
        expected_facts=(
            "Stop the statin for a washout period, then re-challenge with the same or a different "
            "statin or a lower dose (Rec 18).",
            "If re-challenge fails, try intermittent (non-daily) statin dosing (Rec 18).",
            "If the patient still cannot take a statin, use a non-statin: bempedoic acid, "
            "ezetimibe, a fibrate, or a PCSK9 monoclonal antibody (Rec 19).",
        ),
    ),
    EvalQuery(
        "P07",
        "Asthma: step-up therapy",
        "What inhaler regimen is recommended for a patient whose asthma is uncontrolled on "
        "an inhaled corticosteroid alone?",
        expected_source="Asthma CPG 2025",
        expected_pages=_pages(30, (42, 43)),  # Rec 7
        expected_facts=(
            "Use an inhaled corticosteroid combined with a rapid-onset long-acting beta agonist "
            "(e.g., formoterol) as both the controller and the reliever (Rec 7).",
        ),
    ),
    EvalQuery(
        "P08",
        "COPD: initial maintenance therapy",
        "What initial maintenance inhaler therapy is recommended for COPD with a moderate to "
        "severe symptom burden?",
        expected_source="COPD CPG 2026",
        expected_pages=_pages(29, (39, 40)),  # Rec 8
        expected_facts=(
            "Start dual long-acting bronchodilator therapy (LABA/LAMA) rather than monotherapy "
            "(Rec 8).",
        ),
    ),
    EvalQuery(
        "P09",
        "CKD: SGLT2 inhibitors",
        "Which patients with chronic kidney disease should have an SGLT2 inhibitor added, and "
        "for how long should it be continued?",
        expected_source="CKD CPG 2025",
        expected_pages=_pages((33, 34), (58, 60)),  # Rec 15
        expected_facts=(
            "Add an SGLT2 inhibitor to a maximally tolerated ACE inhibitor or ARB in CKD patients "
            "with any of: type 2 diabetes, albuminuria (UACR >200 mg/g), or heart failure (Rec "
            "15).",
            "Continue the SGLT2 inhibitor until dialysis starts (Rec 15).",
        ),
    ),
    EvalQuery(
        "P10",
        "Depression: continuation phase",
        "After a patient with major depressive disorder reaches remission on an "
        "antidepressant, how long should the medication be continued?",
        expected_source="Depression CPG 2022",
        expected_pages=_pages(22, 25, (54, 55)),  # Sidebar + Rec 21
        expected_facts=(
            "Continue the antidepressant at the therapeutic dose for at least six months after "
            "remission to reduce relapse risk (Rec 21).",
        ),
    ),
    EvalQuery(
        "P11",
        "Low back pain: pharmacotherapy",
        "Which medications are suggested for chronic low back pain, and which drug classes "
        "does the guideline advise against?",
        expected_source="Low Back Pain CPG 2022",
        expected_pages=_pages(24, (49, 63)),  # Rec 18-29
        expected_facts=(
            "Suggested: duloxetine for chronic low back pain (Rec 18) and NSAIDs (Rec 19).",
            "Advised against: opioids for chronic low back pain (Rec 27) and benzodiazepines (Rec "
            "29).",
            "Also advised against: non-benzodiazepine muscle relaxants for chronic low back pain, "
            "acetaminophen, monoclonal antibodies, and systemic corticosteroids (Recs 24-26, 28).",
        ),
    ),
    EvalQuery(
        "P12",
        "Headache: acute migraine",
        "Which medications are recommended for the acute treatment of a migraine attack?",
        expected_source="Headache CPG 2023",
        expected_pages=_pages(34, 38, (71, 79)),  # Sidebar + Rec 19-22
        expected_facts=(
            "Triptans (eletriptan, frovatriptan, rizatriptan, sumatriptan, sumatriptan-naproxen, "
            "zolmitriptan) are recommended (Rec 19).",
            "The aspirin/acetaminophen/caffeine combination is recommended (Rec 20).",
            "Acetaminophen, aspirin, ibuprofen or naproxen, and the gepants rimegepant or "
            "ubrogepant, are suggested (Recs 21-22).",
        ),
    ),
    EvalQuery(
        "P13",
        "Insomnia: first-line treatment",
        "What is the first-line treatment for chronic insomnia disorder, and which hypnotics "
        "are acceptable if medication is used?",
        expected_source="Insomnia and Sleep Apnea CPG 2025",
        expected_pages=_pages((34, 35), (45, 56)),  # Rec 5, 8-9
        expected_facts=(
            "CBT-I is the recommended treatment and is suggested over pharmacotherapy as first "
            "line (Recs 5, 8).",
            "If medication is used, suggested agents are doxepin, an orexin receptor antagonist "
            "(daridorexant, lemborexant, suvorexant), or eszopiclone, zaleplon or zolpidem (Rec "
            "9).",
        ),
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
