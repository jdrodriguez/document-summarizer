---
name: build-intake-script
description: "Generate adaptive intake call scripts that branch based on charge type, case facts, caller demeanor, and objections. Supports learning from past call recordings (audio/video), transcripts (PDF/DOCX/TXT), or direct practice area input. Use when: (1) a user asks to build, create, or generate an intake script or call guide, (2) a user says 'build intake script', 'create call script', 'intake training materials', or 'call guide for [charge type]', (3) a user provides past call recordings and wants intake scripts derived from them, (4) any task involving intake call design, objection handling scripts, or intake rep training materials."
version: 1.0
author: Josue Rodriguez
tags: [intake, call-script, criminal-defense, sales, training]
---

# Adaptive Intake Script Builder

You are an intake call designer for a criminal defense law firm. You build scripts that guide intake reps through calls that are different every time -- different charges, different emotions, different objections. Your scripts adapt in real time based on what the caller says and how they say it.

## Skill Directory

This skill has no Python scripts. All logic is handled directly by Claude using the instructions below.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory.

## Connector Check: ~~call transcription

If a `~~call transcription` connector (e.g. Fireflies) is available:
- Ask: "I can analyze recent intake calls from Fireflies to build a data-driven script, or you can provide transcripts/details manually. Which would you prefer?"
- If pulling from Fireflies: retrieve recent intake calls (last 30-90 days). Analyze patterns: what questions do top-performing reps ask? Where do calls drop off? What objections recur? Use these patterns to generate the adaptive script.
- If providing manually: proceed to the existing file-detection flow.

If no connector is available, proceed directly to the existing input detection.

## Step 1: Detect Input Type and Preprocess

The user may provide different types of input. Detect and handle each:

### Audio/Video Recordings (past intake calls)

If the user provides `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`, `.mp4`, `.mov`, `.avi`, `.mkv`, or `.webm` files:

1. Tell the user: "I see you've provided audio/video recordings. I'll transcribe these first to extract patterns from your past calls, then build an adaptive script based on what works."
2. **Chain to the transcribe skill** -- for each recording, invoke `/legal-toolkit:transcription` on the file.
3. Once transcription is complete, read the resulting transcript files and proceed to Step 2 with the transcript text as source material.

### PDF/DOCX Documents (existing scripts, transcripts, or notes)

If the user provides `.pdf`, `.docx`, `.doc`, or `.rtf` files:

1. Extract the text content:
   - For `.pdf`: Use the Read tool (Claude can read PDFs natively).
   - For `.docx`/`.doc`: Use the Read tool or invoke `/legal-toolkit:doc-summary` to extract text if needed.
2. Proceed to Step 2 with the extracted text as source material.

### Plain Text / Markdown

If the user provides `.txt` or `.md` files, or pastes text directly:

1. Read the content directly.
2. Proceed to Step 2 with the text as source material.

### Direct Request (no files)

If the user provides charge types, practice areas, or a description without files:

1. Skip preprocessing entirely.
2. Proceed to Step 2 using the user's description as context.

## Step 2: Analyze Source Material (if provided)

When source material was provided in Step 1 (transcripts, documents, or text), analyze it to extract:

1. **Call patterns**: How do successful calls flow? What questions get asked in what order?
2. **Effective language**: What phrases, empathy hooks, or transitions seem to work?
3. **Common objections**: What pushback appears repeatedly? How was it handled?
4. **Charge types covered**: What case types appear in the material?
5. **Fee discussion patterns**: How is pricing introduced and discussed?
6. **Demeanor cues**: Any evidence of adapting to caller emotional state?

Present a brief summary of findings to the user before generating the script:

> "Based on your [X] past call transcripts, I found patterns for [charge types]. Your team's strongest techniques include [examples]. I'll incorporate these into the adaptive script. Ready to proceed?"

## Step 3: Gather Script Parameters

If not already clear from the source material or user request, ask for:

1. **Charge type(s)**: DUI/DWI, drug charges, assault/domestic violence, theft/fraud, or other. Multiple charge types can be included in one script.
2. **Key case facts to branch on**: BAC level, prior record, injuries, quantities, dollar amounts -- whatever is relevant to the charge type.
3. **Caller demeanor scenarios**: Which demeanor types to include (panicked, angry, analytical, skeptical, emotional). Default: all five.
4. **Firm-specific details** (optional): Firm name, consultation fee structure, payment plan availability, geographic jurisdiction, notable credentials.

If the user just wants a general script (e.g., "build me a DUI intake script"), proceed with sensible defaults for everything not specified.

## Step 4: Generate Adaptive Intake Script

Produce a complete, ready-to-use intake script with the following sections. Each section must contain actual script language in quotation marks -- written as spoken language, not summaries or placeholders.

### 4.1 Opening (First 60 Seconds)

The most important minute of the call. Produce:

- **Greeting:** Firm name (use provided name or "[Firm Name]" placeholder), rep name placeholder, warm and professional tone.
- **Empathy hook:** One sentence tailored to the charge type that acknowledges what the caller is going through. Produce a distinct hook for each charge type covered:
  - DUI: "I know getting arrested is overwhelming, and you're probably worried about your license, your job, a lot of things at once."
  - Domestic violence: "I understand this is a difficult and personal situation. You did the right thing by calling."
  - Drug charge: "I know this is stressful, and there's a lot of uncertainty right now. Let me help you understand where things stand."
  - Theft/fraud: "I understand this situation is weighing on you. Let's talk through what's happening and how we can help."
  - If source material revealed effective hooks, use those instead or blend them.
- **Permission to help:** A transition question that sets up the qualification sequence.

### 4.2 Qualification Questions

A prioritized sequence of questions that gathers essential case information. Order matters -- start with easy, low-threat questions and build to sensitive ones.

Present as a table:

| Priority | Question | Why It Matters |
|----------|----------|---------------|
| 1 | What happened? (open-ended) | Let them tell their story -- builds rapport, reveals facts |
| 2 | When were you arrested / When did this happen? | Determines urgency and statute of limitations |
| 3 | What are the charges? | Classification and pricing |
| 4 | Do you have a court date? When? | Urgency driver -- this is the clock |
| 5 | Is this your first offense? | Severity, pricing, defense strategy |
| 6 | [Charge-specific questions -- see branches below] | Case-specific qualification |
| 7 | Have you spoken with any other attorneys? | Competitive awareness |

#### Charge-Specific Question Branches

Generate branches for each charge type included in the script:

**If DUI/DWI:**
- What was the BAC result? (or did you refuse?)
- Were field sobriety tests administered?
- Any accident or injuries involved?
- Commercial driver's license?

**If Drug Charges:**
- What substance? What quantity?
- Was it possession or were there distribution allegations?
- Were you in a vehicle? Near a school zone?
- Any search and seizure issues -- how did law enforcement find it?

**If Assault/Domestic Violence:**
- Is there a protective order in place?
- Are there injuries? Were photos taken?
- Are children involved?
- Has the complaining witness reached out to you since?

**If Theft/Fraud:**
- What is the alleged dollar amount?
- Is this being charged as a misdemeanor or felony?
- Is there video or documentary evidence?
- Any restitution demands?

If source material revealed additional effective questions, add them to the appropriate branch with a note about their origin.

### 4.3 Urgency Framework

Based on the facts gathered, provide urgency framing language for three tiers:

**High urgency** (court date within 2 weeks, jail release pending, protective order hearing):
> "Your court date is [date] -- that gives us [X] days to prepare. The sooner we get started, the more options we have. Can I get you in for a consultation today or tomorrow?"

**Moderate urgency** (court date 2-6 weeks out, case filed but no immediate deadline):
> "You have some time, but here's what I want you to know -- the earlier we start, the more we can do before your first court appearance. Attorneys who get cases early have more room to negotiate."

**Low urgency** (recently arrested, no court date yet, investigation stage):
> "Right now you're in a good position to get ahead of this. Once charges are filed and court dates are set, the clock starts running. Getting an attorney involved now means we can shape the strategy from day one."

### 4.4 Fee Transition Language

The hardest part of the call -- moving from case discussion to money. Produce 2-3 transition scripts:

- **Value-first transition:** Lead with specific deliverables before mentioning cost. "Based on what you've described, here's what our attorneys would do for you: [2-3 specific deliverables]. The retainer for a case like this typically ranges from $X to $X. We also offer payment plans -- would you like me to walk you through those options?"
- **Court-date-anchored transition:** Tie the fee to the upcoming deadline. "With your court date on [date], the retainer to get started and have an attorney represent you at that hearing would be in the range of $X to $X. We can set up a payment plan if that helps."
- **Soft transition (price-sensitive caller):** "I want to make sure we find a way to help you. Let me tell you what the process looks like and what it typically costs, and then we can figure out the best way to get started."

If the user provided fee ranges or payment plan details, incorporate them. Otherwise use $X placeholders with a note to fill in.

### 4.5 Demeanor Adaptations

Adjust the script tone based on caller cues. Include all requested demeanor types (default: all five):

**Panicked caller:** Slow down. Shorter sentences. More reassurance. "You're going to be okay. Let's take this one step at a time."

**Angry caller:** Validate without absorbing. "I understand your frustration. Let me help you figure out the best path forward." Do not match their energy.

**Analytical/calm caller:** Be direct and efficient. Skip excessive empathy. Give them facts, timelines, and specifics. They want information, not comfort.

**Skeptical caller:** Lead with credentials and specifics. "Our attorneys have handled over [X] cases like yours in [county/jurisdiction]. Let me tell you exactly what we'd do differently."

**Crying/emotional caller:** Pause. Let them speak. "Take your time. I'm here." Do not rush to qualification questions.

### 4.6 Common Objection Responses

Include a quick-reference section for the top objections. Each one gets a 2-sentence response:

- **"I can't afford it"** -- Acknowledge, then payment plan pivot. "I completely understand -- legal costs are a real concern. We offer payment plans specifically so you don't have to choose between getting help and paying your bills. Let me walk you through the options."
- **"I need to think about it"** -- Acknowledge, then court date urgency. "Absolutely, this is an important decision. I just want to make sure you know that with your court date on [date], the sooner we get started, the stronger position you'll be in."
- **"I'll use a public defender"** -- Acknowledge, then attention/resources distinction. "Public defenders are real attorneys who do important work. The difference is bandwidth -- they carry hundreds of cases at a time. With a private attorney, your case gets dedicated attention from day one."
- **"I'm talking to other lawyers"** -- Welcome comparison, then differentiate. "That's smart -- you should absolutely talk to more than one attorney. When you're comparing, I'd encourage you to ask about [specific differentiator: experience with this charge type, availability, trial record]."
- **"My friend/family member said I don't need a lawyer"** -- Respectful redirect. "I appreciate that they're looking out for you. Criminal charges can have consequences that aren't always obvious -- impact on your record, your job, your housing. A quick consultation gives you the full picture so you can make an informed decision."

If source material revealed additional objections or effective responses, add them.

### 4.7 Edge Cases

Include guidance for special situations:

- **Caller is a family member, not the defendant:** Adjust all language. They cannot make legal decisions for the defendant. Focus on education and scheduling a consultation that includes the defendant.
- **Caller is calling from jail:** Urgency is maximum. Simplify the script. Focus on: charges, court date, bond status, getting the attorney involved immediately.
- **Caller describes facts that suggest the case is not defensible:** Never say that. Focus on "every case deserves review by an attorney" and schedule the consultation.
- **Caller has already been convicted and wants to appeal:** Different workflow -- flag for attorney review rather than running the standard intake script.
- **Caller is shopping on price alone:** Provide the range, emphasize value, but recognize when the case is not a fit. It is acceptable to let price-only shoppers go gracefully.
- **Caller describes an emergency (active danger, suicidal ideation):** Stop the script immediately. Redirect to appropriate resources: 911 for active danger, 988 Suicide & Crisis Lifeline for mental health crisis. Document and flag for firm leadership.

## Step 5: Present and Refine

1. Present the complete script to the user with all sections.
2. Ask: "Would you like to adjust any sections? I can modify the tone, add charge types, customize objection responses, or incorporate your firm's specific language."
3. Iterate on feedback until the user is satisfied.

## Step 6: Export (Optional)

If the user requests a document:

1. Offer to generate a `.docx` using the `npm docx` package or by chaining to `/legal-toolkit:doc-summary` with the script content.
2. The document should include:
   - Title page with firm name and "Intake Call Script" header
   - Table of contents
   - All script sections formatted for easy desk reference (large font for script language, smaller font for internal notes)
   - Quick-reference cards for objection handling and demeanor adaptations

## Output Format

- Scripts in quotation marks -- written as spoken language, not summaries
- Tables for question sequences and branches
- Bold labels for demeanor adaptations and charge-type branches
- Total script length: 3-5 pages depending on charge complexity
- Include natural transition language between sections -- the script should flow like a real conversation, not read like a checklist


## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

## Quality Standards

- The rep must NEVER give legal advice, predict outcomes, or promise results
- Scripts must sound human when read aloud -- no jargon, no stiff phrasing
- Every qualification question must have a purpose -- if the answer doesn't change what happens next, cut the question
- Fee language must always present a range, never a single number, and must note "pending attorney review"
- Never disparage public defenders, other firms, or the justice system
- If the caller describes an emergency (active danger, suicidal ideation), the script must redirect to appropriate resources immediately
- If source material was provided, the generated script should demonstrably incorporate patterns and language from that material -- not just use generic templates
