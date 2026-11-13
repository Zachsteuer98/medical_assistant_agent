"""Evaluation question set: the notebook's 5 queries, the 4 remaining business-context
question types, and 1 out-of-scope probe that a 2011 manual cannot answer."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuery:
    id: str
    category: str
    question: str
    answerable: bool = True
    # Retrieval ground truth (optional): citation label of the document that answers the
    # question, and the 1-based pages where the answer is stated (recommendation table and
    # its discussion). Unlabelled query sets (Merck) leave these empty.
    expected_source: str = ""
    expected_pages: tuple[int, ...] = ()

    @property
    def has_retrieval_labels(self) -> bool:
        return bool(self.expected_source)


QUERIES: tuple[EvalQuery, ...] = (
    EvalQuery(
        "Q1", "Critical care", "What is the protocol for managing sepsis in a critical care unit?"
    ),
    EvalQuery(
        "Q2",
        "Diagnosis & surgery",
        "What are the common symptoms for appendicitis, and can it be cured via medicine? "
        "If not, what surgical procedure should be followed to treat it?",
    ),
    EvalQuery(
        "Q3",
        "Dermatology",
        "What are the effective treatments or solutions for addressing sudden patchy hair loss, "
        "commonly seen as localized bald spots on the scalp, and what could be the possible "
        "causes behind it?",
    ),
    EvalQuery(
        "Q4",
        "Neurotrauma",
        "What treatments are recommended for a person who has sustained a physical injury to "
        "brain tissue, resulting in temporary or permanent impairment of brain function?",
    ),
    EvalQuery(
        "Q5",
        "Orthopedic trauma",
        "What are the necessary precautions and treatment steps for a person who has fractured "
        "their leg during a hiking trip, and what should be considered for their care and "
        "recovery?",
    ),
    EvalQuery(
        "Q6",
        "Diagnostic assistance",
        "What are the common symptoms and treatments for pulmonary embolism?",
    ),
    EvalQuery(
        "Q7",
        "Drug information",
        "Can you provide the trade names of medications used for treating hypertension?",
    ),
    EvalQuery(
        "Q8",
        "Treatment plans",
        "What are the first-line options and alternatives for managing rheumatoid arthritis?",
    ),
    EvalQuery(
        "Q9",
        "Specialty knowledge",
        "What are the diagnostic steps for suspected endocrine disorders?",
    ),
    EvalQuery(
        "Q10",
        "Out of scope (post-2011)",
        "What is the recommended dosing schedule for the mRNA COVID-19 vaccines?",
        answerable=False,
    ),
)
