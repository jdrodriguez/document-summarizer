---
description: Multiply one piece of content into 12+ platform-native social posts, emails, GBP posts, and video scripts
argument-hint: "<blog post, article, transcript, or content file>"
---

# /content-multiplier -- Content Multiplier

Take one piece of source content and produce 12+ derivative outputs across social media, email, Google Business Profile, and video -- all in the firm's authentic voice. Supports audio/video files (transcribes first), PDFs, Word docs, text files, pasted text, and URLs.

@$1

## Workflow

- **Detect input type** -- if audio/video, chain to `/legal-toolkit:transcription` first; if PDF/DOCX, extract text; if text or URL, proceed directly
- **Establish voice profile** -- locate an existing voice profile or generate one from the firm's content for approval
- **Multiply** into 5 social media posts (3 Facebook/Instagram, 1 LinkedIn, 1 X/Twitter), 3 email newsletter snippets, 3 Google Business Profile posts, and 1 short-form video script
- **Adapt** each output for its platform's native format, length, and conventions
- **Review** with the user -- confirm voice match, refine any outputs that feel off
- Refer to the `multiply-content` skill (SKILL.md) for platform specs, voice profile details, and edge case handling
