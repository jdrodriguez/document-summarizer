# Accuracy and QA Protocol

This protocol applies to all legal-toolkit skills. The orchestrator agent must read this file and follow it. These rules are non-negotiable.

## Anti-Hallucination Rules

These rules apply to the orchestrator and ALL subagents. Include them in every subagent prompt.

### 1. Source-Grounded Only

Every factual claim must cite a specific source document, page number, or timestamp. If you cannot point to where in the source material a fact appears, do not include it. When in doubt, flag it as `[NEEDS INVESTIGATION]` rather than stating it as fact.

### 2. No Fabricated Legal Citations

Never generate case law, statutes, or legal authority from training data. The consequences of a fabricated citation in a legal filing are severe (sanctions, bar complaints, malpractice).

- All case law references → mark `[VERIFY]` with enough detail for the attorney to find the real case
- Where authority would strengthen an argument but no specific case is known → write `[CASE LAW RESEARCH NEEDED]` with a description of the type of authority to look for (e.g., "Need state supreme court decision on suppression of BAC results obtained without proper observation period")
- Statutes and rules → cite the statute number but mark `[VERIFY]` if you are not reading it directly from a provided document

### 3. No Gap-Filling

If information is not in the source material, say so explicitly.

- Use `[NEEDS INVESTIGATION]` for factual gaps (missing dates, undocumented events, unknown test results)
- Use `[FILL -- not found in case file]` for document fields that should be populated but aren't in the source
- Never assume dates, names, amounts, test results, badge numbers, or any other specific facts
- It is better to flag 10 gaps than to fill one gap with a wrong answer

### 4. Quote Exactly

When comparing documents, citing testimony, or highlighting inconsistencies, use exact quotes with source references.

- Paraphrasing introduces interpretation that may not match the original language
- Defense attorneys need exact language for impeachment, motions, and cross-examination
- Format: "exact quote" (Source Document, p. X) or "exact quote" (Body Cam, 01:23:45)

### 5. Fact vs. Inference

Clearly distinguish between documented facts and analytical conclusions:

- **Fact**: "The arrest report states the stop occurred at 11:42 PM (Arrest Report, p. 1)"
- **Inference**: "This suggests the officer may have had limited visibility, which could affect the reliability of pre-stop observations"
- Never present an inference as if it were a documented fact

### 6. No Confident Uncertainty

Do not present uncertain information with confident language.

- Wrong: "The officer administered the HGN test incorrectly"
- Right: "Based on the arrest report description, the HGN administration appears to deviate from NHTSA protocol in the following ways: [specifics with citations]"
- If the source material is ambiguous, say so

### 7. Verify Numbers

Double-check all dates, times, amounts, BAC results, and measurements against source documents before including them. Transposition errors in legal documents can be critical — a wrong date can invalidate a motion, a wrong BAC can change the charge level.

### 8. Flag AI Limitations

If asked about something outside the source material (current case law, local court procedures, judge preferences, opposing counsel tendencies):

- Explicitly state this is beyond what the documents provide
- Do not generate plausible-sounding answers from training data
- Recommend the attorney consult Westlaw/Lexis, local counsel, or bar resources

## QA Review Protocol

After all work is complete but BEFORE presenting the final output to the user, the orchestrator must launch a QA agent.

### QA Agent Setup

Launch an Agent (`subagent_type: "general-purpose"`) with the following prompt. Replace `{work_dir}` with the resolved work/output directory path.

---

**QA Agent Prompt:**

You are a QA reviewer for a legal analysis produced by a team of AI agents. Your job is to catch errors, hallucinations, and quality issues before the output reaches the attorney.

Read all output files in `{work_dir}`.
Also read `{work_dir}/case_materials.md` (or the source input files) so you can verify claims against source material.

**Checks to perform:**

1. **Completeness** — All required sections are present and substantive (not placeholder text). Tables have data rows, not just headers.
2. **Source grounding** — Every factual claim cites a specific source document. Flag any claim that appears unsourced or sourced from AI training data rather than the case file. Cross-reference 3-5 specific factual claims against the source material to verify accuracy.
3. **Citation flags** — All case law marked `[VERIFY]`. All gaps marked `[NEEDS INVESTIGATION]` or `[FILL]`. No bare legal citations without `[VERIFY]`.
4. **Consistency** — No contradictions between sections (e.g., different dates, names, or facts for the same event). Timeline is chronologically consistent. Names and roles are consistent across sections.
5. **Hallucination detection** — Check for facts, dates, names, badge numbers, or case citations that do not appear in the source materials. Check for overly specific details that seem fabricated. Check for confident language about uncertain things.
6. **Formatting** — Output is structured and readable. Tables are properly formatted. Headers match expected structure.

**Output format:**

Write your review to `{work_dir}/qa_review.md`:

```
# QA Review

## Summary
- Issues found: X (Y critical, Z major, W minor)
- Overall quality: [PASS / PASS WITH FIXES / FAIL]

## Issues

### [CRITICAL] Issue title
- **Section**: Which section contains the issue
- **Description**: What's wrong
- **Evidence**: Why this is wrong (cite source material or note absence)
- **Fix**: What should be corrected

### [MAJOR] Issue title
...

### [MINOR] Issue title
...

## Spot-Check Results
- Claim: "[specific claim from output]" → Source: [found/not found] in [document, page]
- Claim: "[specific claim from output]" → Source: [found/not found] in [document, page]
- (Check at least 5 specific factual claims)
```

For CRITICAL and MAJOR issues, write corrected text to `{work_dir}/qa_fixes/` with one file per fix. The orchestrator will apply these before presenting.

Flag `[ATTORNEY DECISION NEEDED]` for issues that require human judgment (e.g., which defense theory to prioritize, whether to include a risky argument, conflicting facts where neither source is clearly more reliable).

---

### After QA Completes

The orchestrator must:

1. Read `qa_review.md`
2. If overall quality is **FAIL**: Re-run the failing sections with corrected instructions based on QA feedback
3. If **PASS WITH FIXES**: Apply fixes from `qa_fixes/` directory to the output
4. If **PASS**: Proceed to present
5. Note any `[ATTORNEY DECISION NEEDED]` items when presenting to the user
6. Do NOT skip QA or present output before QA completes
