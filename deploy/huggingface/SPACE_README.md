---
title: Medical Assistant Agent
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Cited answers from 10 VA/DoD clinical guidelines
---

# Medical Assistant Agent

A retrieval-augmented assistant that answers clinical questions from 10 VA/DoD Clinical
Practice Guidelines (diabetes, hypertension, lipids, asthma, COPD, chronic kidney disease,
depression, low back pain, headache, insomnia and sleep apnea) and cites the guideline and page
for every claim.

> **Not medical advice.** Educational portfolio project. Outputs are decision support only and
> must not replace evaluation by a licensed clinician.

The demo has a daily question limit to cap API costs. If it has been reached, try again
tomorrow (UTC).

Source code, evaluation results and design decisions:
https://github.com/Zachsteuer98/medical_assistant_agent
