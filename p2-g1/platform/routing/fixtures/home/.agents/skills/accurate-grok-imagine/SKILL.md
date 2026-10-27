---
name: "accurate-grok-imagine"
description: "Precision prompting workflow for Grok Imagine xAI image generation and editing. Optimized for photorealistic composites, identity-preserving edits, reference-based compositing, anatomy and lighting repairs, and iterative refinement. Trigger on requests for accurate picture generation or editing with preservation requirements."
---

# accurate-grok-imagine

Precision prompting workflow for Grok Imagine / xAI image generation and editing, optimized for photorealistic composites, identity consistency, lighting coherence, anatomy repair, and iterative refinement.

Use this skill whenever the task involves:
- Editing an existing image with specific preservation requirements
- Creating a photorealistic person, portrait, scene, product, or event image
- Combining up to three reference images
- Maintaining identity, clothing, pose, environment, or camera consistency
- Fixing hands, faces, shadows, scale, lighting, or perspective
- Producing a structured Grok Imagine prompt instead of a loose one-sentence request

Do not use generic keyword stuffing such as “8k, masterpiece, ultra detailed” as the main strategy. Grok Imagine responds best to clear, natural-language editing instructions, reference-image anchoring, and structured decomposition.

---

## Core Rules

### 1. Choose the correct workflow

Use **text-to-image** when:
- No source image exists
- The request is concept art, a fresh scene, a new portrait, a mockup, or a stylized generation
- Exact preservation is not required

Use **image editing** when:
- The user provides a base photo
- The composition, background, clothing, pose, or identity must be preserved
- The task involves inserting, removing, replacing, or modifying part of an image

Use **multi-image editing** when:
- One image supplies the background/composition
- Another supplies a person, face, outfit, object, or visual style

### Universal Prompt Structure
### Default Photorealistic Edit Template
### Multi-Image Composite Template
### Identity-Preservation Template
### Person Insertion Into Group Photo Template
### Lighting and Camera Language
### Event photo
### Portrait
### Candid documentary
### Vintage / archival
### Product
