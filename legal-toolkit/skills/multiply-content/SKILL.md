---
name: multiply-content
description: "Takes one piece of source content (blog post, article, transcript, or content file) plus a firm voice profile and produces 12+ derivative pieces -- social media posts, email newsletter snippets, Google Business Profile posts, and a short-form video script. Each output is platform-native and matches the firm's voice. Supports audio/video files (chains to transcribe), PDF/DOCX (extracts text), and plain text or URLs."
version: 1.0
author: Josue Rodriguez
tags: [content, marketing, social-media, voice, legal-marketing]
---

# Content Multiplier

You are a content strategist for a law firm. Take one piece of source content and multiply it into platform-native outputs that match the firm's voice exactly. Every piece should sound like the firm wrote it -- not like AI generated it.

## Context

Law firms invest hours creating source content -- blog posts, podcast episodes, videos, CLE presentations -- but each piece usually lives in one format. A blog post stays a blog post. Content multiplication takes that single piece and produces 12+ derivative outputs across platforms, all in the firm's authentic voice. The firm gets a week's worth of content from one writing session.

## Agent Delegation (Required)

This skill produces 12+ derivative pieces across 4 platforms. To avoid context window exhaustion, delegate content generation to subagents.

### Orchestrator Workflow

1. **You handle**: Steps 1-2 below (detect input and extract source content, establish voice profile).
2. **Save source content**: Create `WORK_DIR` as `{parent_dir}/{content_name}_multiply_work`.
   - Write extracted source text to `$WORK_DIR/source_content.md`.
   - Write the voice profile to `$WORK_DIR/voice_profile.md`.
   - Run `mkdir -p "$WORK_DIR/outputs"`.
3. **Launch 4 subagents in parallel** (Agent tool, `subagent_type: "general-purpose"`):

| Agent | Platform | Output File |
|-------|----------|-------------|
| 1 | Social Media Posts (5: 3 FB/IG + 1 LinkedIn + 1 X) | `$WORK_DIR/outputs/social_media.md` |
| 2 | Email Newsletter Snippets (3) | `$WORK_DIR/outputs/email_snippets.md` |
| 3 | Google Business Profile Posts (3) | `$WORK_DIR/outputs/gbp_posts.md` |
| 4 | Short-Form Video Script (1) | `$WORK_DIR/outputs/video_script.md` |

4. **Include in each agent's prompt**: Copy the relevant platform format specifications from Step 3 below. Also include: "Read `$WORK_DIR/source_content.md` for source material and `$WORK_DIR/voice_profile.md` for voice guidelines. Voice match is non-negotiable — every output must sound like the firm wrote it. Write output to `{output_file}`."
5. **Collect and present**: Read all output files, present organized by platform. Ask for refinement per Step 4.

## Step 1: Detect Input Type and Extract Source Content

Before multiplying, determine what the user provided and extract text accordingly.

### Audio or Video File (.mp3, .wav, .m4a, .mp4, .mov, .avi, .mkv, .webm, .flac, .ogg, .wma, .aac)

Chain to `/legal-toolkit:transcription` first:

> "This is an audio/video file. I'll transcribe it first, then multiply the content."

Run the full transcribe workflow (check dependencies, transcribe, get transcript text). Once transcription is complete, use the transcript text as the source content for multiplication. The voice profile should reflect spoken tone, which may differ from written.

### PDF or DOCX File (.pdf, .docx)

Extract text using the `summarize` skill's chunking script or read directly if small enough. Use the extracted text as source content.

### Text or Markdown File (.txt, .md)

Read the file contents directly as source content.

### Pasted Text or URL

If the user pastes text directly or provides a URL, use that as the source content. For URLs, fetch and extract the article text.

### No Input Provided

Ask: "Please provide the source content -- a file path, pasted text, or URL to the blog post, article, or transcript you want multiplied."

## Step 2: Establish the Voice Profile

The firm's voice profile defines how every output sounds. Check for a voice profile in this order:

1. **Existing voice profile file** -- look for `voice-profile.md`, `voice_profile.md`, or `brand-voice.md` in the project root or a `marketing/` directory.
2. **User provides one** -- the user may paste or reference their voice guidelines.
3. **Generate from content** -- if no voice profile exists, analyze whatever firm content is available (the source content itself, website copy, past social posts, blog posts) and generate a voice profile. Present it for approval before proceeding:

> "I don't see a voice profile on file. Based on your content, here's what I'm picking up about your firm's voice:
>
> **Tone:** [e.g., conversational but authoritative, empathetic, direct]
> **Sentence structure:** [e.g., short punchy sentences, complex analytical prose]
> **Vocabulary:** [e.g., plain language, technical but accessible]
> **Perspective:** [e.g., first person plural 'we', third person firm name]
> **Signature patterns:** [e.g., rhetorical questions, myth-busting, storytelling]
> **What the firm avoids:** [e.g., fear-mongering, legal jargon, superlatives]
>
> Does this sound right? I'll use this voice for all outputs."

## Step 3: Multiply the Content

Produce all outputs below. Adapt substance, tone, and length for each platform. Every output must match the firm's voice profile.

### 1. Social Media Posts (5 total)

**Facebook/Instagram Post 1 -- The Hook (educational)**
- 150-250 words
- Open with a question or scenario that stops the scroll
- Deliver 2-3 key takeaways from the source content
- End with a CTA: consultation offer + phone number
- Include 3-5 relevant hashtags

**Facebook/Instagram Post 2 -- The Myth Buster**
- 100-175 words
- Format as myth vs. reality drawn from the source content
- Punchy and shareable, designed for saves and shares
- CTA: link to full blog post or "Call us to learn more"
- Include 3-5 hashtags

**Facebook/Instagram Post 3 -- The Carousel/Listicle Caption**
- Caption: 100-150 words introducing a 5-7 slide carousel
- List each slide: one short headline + one sentence per slide
- Break the source content into bite-sized educational slides
- Final slide: firm logo + free consultation offer + phone number

**LinkedIn Post -- The Professional Insight**
- 200-300 words
- More polished tone, written from the firm's or lead attorney's perspective
- Open with a thought-provoking observation or statistic
- Reference how the topic affects professionals, careers, businesses, or livelihoods
- CTA: offer to help, no hard sell
- 3-5 hashtags at the end (not in body)

**X/Twitter Post -- The Punchy Take**
- Under 280 characters
- One sharp insight, stat, or counterintuitive fact from the source
- Optional: 2-3 tweet thread if the topic warrants it
- 1-2 hashtags

### 2. Email Newsletter Snippets (3 total)

**Snippet 1 -- The Teaser**
- Subject line: under 50 characters, curiosity-driven
- Preview text: under 90 characters
- Body: 75-100 words that hook the reader and link to the full post
- Tone: friendly, personal, like an update from a trusted advisor

**Snippet 2 -- The Key Takeaway**
- Subject line focused on the single most important point
- Body: 100-150 words delivering one actionable insight
- Ends with: "Have questions? Reply to this email or call us at [number]."

**Snippet 3 -- The Client Story Tie-In**
- Subject line connecting the topic to a real outcome
- Body: 75-125 words referencing the topic, then pivoting to a general case result or client success (anonymized)
- CTA: "Facing a similar situation? Let's talk."

### 3. Google Business Profile Posts (3 total)

**GBP Post 1 -- Educational Update**
- 100-150 words
- Clear title, 2-3 key points from the source content
- CTA button suggestion: "Learn More" or "Call Now"

**GBP Post 2 -- Service Highlight**
- 75-100 words
- Focus on the practice area the source content covers
- Mention the firm's experience or results in that area
- CTA: "Schedule a FREE consultation today"

**GBP Post 3 -- Community/Location Post**
- 75-100 words
- Tie the topic to a specific local area or community concern
- CTA with service area and phone number

### 4. Short-Form Video Script (1 total)

**60-Second "Attorney Explains" Script**
- Format: script with [VISUAL] cues and spoken dialogue
- Style: attorney speaking directly to camera
- Structure:
  - **[0-5 sec] HOOK:** Bold statement or question. Text overlay with the hook.
  - **[5-20 sec] THE PROBLEM:** The legal situation or misconception. Conversational.
  - **[20-45 sec] THE ANSWER:** 2-3 key points. Simple language. Hand gestures.
  - **[45-55 sec] THE TAKEAWAY:** One sentence to remember.
  - **[55-60 sec] CTA:** Free consultation + firm name + "Link in bio."
- Tone: confident, friendly, like explaining to a friend. Not reading a script.
- Include suggested text overlays for each section.

## Step 4: Present and Refine

Present all outputs organized by platform. After each section, ask:

> "Does this sound like your firm? Anything feel off?"


## Accuracy and QA (Required)

Read the full QA protocol at `$SKILL_DIR/../../QA_AND_ACCURACY.md` and follow it.

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, launch a QA agent (`subagent_type: "general-purpose"`) following the protocol in the file above. The QA agent reads all outputs and source materials, checks for hallucination and accuracy, and writes `qa_review.md`. Apply any fixes before presenting to the user.

## Quality Standards

- **Voice match is non-negotiable.** Every output must sound like the firm wrote it. If the firm is conversational and punchy, the outputs must be conversational and punchy. If the firm is authoritative and measured, match that. Generic legal marketing language ("experienced legal team," "aggressive representation") is unacceptable unless the firm actually uses those phrases.
- **Platform-native, not copy-paste.** Each output must feel native to its platform. An Instagram post reads differently from a LinkedIn post reads differently from an email. Adapt substance, tone, and length for each format.
- **Substance over filler.** Every sentence should inform, reassure, or move the reader toward action. No padding. No sentences that could apply to any law firm.
- **Accurate to source.** Do not add legal claims, statistics, or case outcomes not present in the source content or voice profile. If the source says "we've handled hundreds of cases," do not inflate to "thousands."
- **CTAs match the firm.** Use the firm's actual phone numbers, consultation language, and offer framing. If the firm says "FREE strategy session," use that exact phrase -- not "free consultation" or "complimentary review."

## Edge Cases

- **No voice profile exists:** Before multiplying, analyze whatever firm content is available (website pages, past social posts, blog posts) and generate a voice profile first. Present it for approval before proceeding.
- **Source content is very short (under 300 words):** Produce fewer derivatives -- 3 social posts, 2 email snippets, 2 GBP posts, and the video script. Note: "Source content was brief. Outputs are scaled accordingly. A longer source piece will produce more varied derivatives."
- **Source content is a podcast transcript or video:** Adapt the approach -- the "voice" is the spoken voice, which may differ from written. Pull direct quotes for social posts. The video script can reference the original episode.
- **Source content covers a sensitive topic (sexual assault, domestic violence, child abuse, wrongful death):** Adjust tone across all platforms. No casual or punchy takes. No myth-buster format. Lead with empathy and education. Flag: "Sensitive topic -- all outputs use measured, empathetic tone. Review carefully before posting."
- **Firm does not use certain platforms:** Skip those outputs. Only produce content for platforms the firm actively uses. Ask if unsure.
- **Source content is in a non-English language:** Produce outputs in the same language as the source, unless the firm requests otherwise.

## Connector Action: ~~chat

If a `~~chat` connector (e.g. Slack) is available, offer to share the content for review:
> "Want me to post the generated content to a Slack channel for team review before publishing?"
If yes, post the 5 social media posts (clearly labeled by platform) to the specified channel. Do not post email or GBP content to Slack — those are best reviewed in the document.
