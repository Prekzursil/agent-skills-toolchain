---
name: "accurate-grok-imagine"
description: Precision prompting for Grok Imagine xAI image generation and editing - photorealistic composites, identity-preserving edits, reference-based compositing, anatomy and lighting repairs, iterative refinement. Trigger on accurate picture generation or editing with preservation needs. NOT for the OpenAI Image API (use imagegen).
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
- A third supplies lighting, texture, accessory, or scene reference

When editing, always explicitly say what must stay unchanged and what must change.

---

## Universal Prompt Structure

A strong Grok Imagine prompt should include:

1. **Action**
   - “Edit the attached image…”
   - “Create a photorealistic scene…”
   - “Replace only…”
   - “Insert a new figure…”
   - “Adjust the lighting…”

2. **Subject / Area**
   - Who or what changes
   - Where in the frame the change happens
   - Relative position, depth, size, overlap

3. **Preservation Instructions**
   - What must remain identical
   - Faces, clothing, background, objects, camera angle, lighting, colors, text, framing

4. **Photographic Specifics**
   - Lens, camera height, focal length, depth of field, lighting direction, shadows, grain, compression, motion blur

5. **Physical Integration**
   - Contact shadows, occlusion, reflections, scale, perspective, skin texture, fabric folds, edge softness

6. **Failure Prevention**
   - Avoid warped hands, extra fingers, mismatched lighting, pasted edges, duplicated faces, incorrect perspective, uncanny skin, inconsistent resolution

---

## Default Photorealistic Edit Template

Use this when editing an existing image:

```text
Edit the attached image as a realistic photo manipulation. Preserve the original camera angle, lens perspective, background, lighting direction, color temperature, clothing details, facial features, body proportions, image grain, compression artifacts, and overall documentary-photo style.

Change only the following: [specific edit].

The edited area must match the original image naturally, including correct scale, depth placement, occlusion, shadows, highlights, skin texture, fabric texture, edge softness, and focus level. Keep the final image visually coherent, as if it was captured in a single photograph with the same camera and lighting conditions.

Do not alter unrelated people, objects, facial identities, text, logos, background architecture, clothing colors, or the original framing unless explicitly required. Avoid extra limbs, distorted fingers, duplicated faces, pasted edges, warped shoulders, unnatural expressions, incorrect shadows, plastic skin, inconsistent blur, and mismatched resolution.
```

---

## Multi-Image Composite Template

Use when combining reference images:

```text
Use <IMAGE_0> as the primary base image and preserve its composition, camera angle, lighting, background, framing, perspective, and photographic texture.

Use <IMAGE_1> only as the reference for [person/object/style]. Transfer the relevant visual traits from <IMAGE_1> into <IMAGE_0> while matching the lighting, scale, depth, shadows, grain, and focus of <IMAGE_0>.

If <IMAGE_2> is provided, use it only as reference for [specific detail: outfit, lighting, pose, object, texture, environment]. Do not let <IMAGE_2> override the base composition unless requested.

The final result should look like a single coherent photograph, not a collage. Ensure realistic occlusion, contact shadows, edge blending, perspective alignment, matching color temperature, and consistent camera blur.
```

---

## Identity-Preservation Template

Use only for authorized, fictional, clearly satirical, or non-deceptive identity-preserving work.

```text
Use the reference image to preserve the subject’s identity with high fidelity: facial geometry, eye shape, nose structure, jawline, mouth shape, hairline, skin texture, age cues, expression style, and natural asymmetries. Adapt only the requested pose, clothing, lighting, or environment.

The person should remain recognizably the same individual, but the new image must match the target scene’s camera perspective, focal length, color grading, light direction, shadow softness, and depth of field. Maintain realistic anatomy, natural expression, believable posture, and accurate proportions.
```

When a generated image must not be mistaken for a real event, include:

```text
Create this as a clearly fictional/editorial composite, not as documentary evidence of a real event.
```

---

## Person Insertion Into Group Photo Template

Use for consensual or clearly fictional composites:

```text
Edit the attached group photo by adding one additional adult figure at [specific location]. Preserve the original people, background, camera angle, lighting, clothing, expressions, and image quality.

Place the added figure naturally within the group, matching the same height scale, lens perspective, depth position, focal blur, color temperature, skin lighting, shadow direction, and image grain. The new person should occupy realistic physical space, with believable overlap against nearby shoulders, arms, clothing, and background elements.

If physical contact is requested, make the gesture natural and anatomically plausible: shoulders aligned, arm angles believable, hands correctly proportioned, fabric compressed where contact occurs, and shadows appearing at contact points. The final image should read as a coherent staged composite or fictional editorial scene, not a pasted cutout.

Avoid extra arms, distorted fingers, duplicated faces, warped torsos, floating bodies, mismatched resolution, inconsistent lighting, incorrect scale, and obvious compositing seams.
```

---

## Lighting and Camera Language

Use camera details when realism matters.

### Event photo
```text
Shot on a full-frame camera with a 35mm or 50mm lens, eye-level perspective, moderate depth of field, direct indoor event lighting mixed with warm ambient light, mild JPEG compression, natural skin texture, realistic shadows behind people, slight background softness.
```

### Portrait
```text
Shot on a Sony A7IV with an 85mm f/1.4 lens, shallow depth of field, soft key light from camera left, gentle fill from camera right, natural skin texture, visible pores, realistic catchlights, smooth background separation.
```

### Candid documentary
```text
Natural handheld camera perspective, available light, subtle motion softness, imperfect framing, realistic compression artifacts, uneven ambient lighting, candid expression, no studio polish.
```

### Vintage / archival
```text
Analog film texture, slight color fading, soft contrast, authentic grain, mild lens softness, period-appropriate color palette, realistic print aging, no modern HDR sharpness.
```

### Product
```text
Studio product photography with controlled softbox lighting, clean reflections, accurate material response, realistic contact shadow, sharp focus on the product, background slightly softened but not blurred beyond plausibility.
```

---

## Material and Physics Details

Use physical language instead of empty quality boosters.

### Skin
```text
Natural skin texture with pores, subtle redness variation, realistic under-eye shadows, soft specular highlights, no waxy smoothing.
```

### Hair
```text
Individual hair strands visible at the edges, natural flyaways, realistic highlights following the light direction, correct hairline density.
```

### Fabric
```text
Fabric folds respond to body posture and contact points, with realistic creases, seams, sleeve tension, collar structure, and shadowing inside folds.
```

### Hands
```text
Hands should have five fingers each, natural knuckle spacing, realistic nail placement, correct palm orientation, believable grip pressure, and soft contact shadows.
```

### Shadows
```text
Add contact shadows where bodies, hands, feet, furniture, or objects meet. Match the original shadow direction, softness, density, and color.
```

### Reflections
```text
Reflections should be subtle and physically consistent with the surface: blurred on rough material, sharper on glossy surfaces, distorted by curvature where appropriate.
```

---

## JSON Decomposition Workflow

When precision matters, first decompose the target image or desired result into structured fields, then turn that into a clean prompt.

Use this structure:

```json
{
  "task": {
    "type": "image_edit | text_to_image | multi_image_composite",
    "goal": "",
    "change_only": "",
    "preserve": []
  },
  "scene": {
    "environment": "",
    "background": "",
    "time_period": "",
    "mood": ""
  },
  "subjects": [
    {
      "label": "person_1",
      "identity_source": "",
      "position": "",
      "pose": "",
      "expression": "",
      "clothing": "",
      "hair": "",
      "skin_and_face": "",
      "hands": "",
      "interaction": ""
    }
  ],
  "camera": {
    "shot_type": "",
    "camera_height": "",
    "angle": "",
    "lens": "",
    "depth_of_field": "",
    "framing": ""
  },
  "lighting": {
    "key_light": "",
    "fill_light": "",
    "ambient": "",
    "color_temperature": "",
    "shadow_quality": ""
  },
  "integration": {
    "scale": "",
    "occlusion": "",
    "contact_shadows": "",
    "grain": "",
    "compression": "",
    "edge_blending": ""
  },
  "negative_constraints": [
    "extra fingers",
    "warped hands",
    "mismatched lighting",
    "pasted edges",
    "incorrect perspective",
    "duplicated faces"
  ]
}
```

Then convert it into natural language.

---

## Iterative Refinement Protocol

Never try to fix everything at once after a bad result. Apply targeted edits.

### Step 1: Diagnose
Identify only the visible failures:
- Face drift
- Wrong expression
- Hand distortion
- Bad scale
- Lighting mismatch
- Shadow missing
- Clothing changed
- Background changed
- Text warped
- Over-smoothed skin
- Wrong depth/focus

### Step 2: Target one category
Use a surgical edit prompt:

```text
Keep the entire image unchanged except for [specific area]. Correct only [specific flaw]. Preserve all faces, clothing, background, lighting, framing, and colors. The corrected area should match the surrounding image naturally.
```

### Step 3: Preserve previous wins
Always lock in what already looks right:

```text
Preserve the current composition, facial likeness, clothing, background, lighting, and camera perspective. Only refine the hand anatomy on the person at the right side of the image.
```

---

## Common Repair Prompts

### Fix hands
```text
Keep the full image unchanged except for the hands. Redraw the hands with natural anatomy: five fingers per hand, correct knuckle spacing, realistic finger length, natural palm orientation, visible but subtle nails, and believable contact with nearby clothing or objects. Match the original lighting, skin tone, focus, and grain.
```

### Fix face likeness
```text
Keep the entire image unchanged except for the face of [subject]. Restore the facial identity from the reference: same eye shape, nose bridge, mouth shape, jawline, hairline, age cues, skin texture, and natural asymmetry. Keep the expression and head angle consistent with the current image.
```

### Fix lighting mismatch
```text
Keep the composition unchanged. Adjust only the inserted subject’s lighting so it matches the scene: same color temperature, highlight direction, shadow softness, contrast level, and ambient fill. Add subtle contact shadows where the subject overlaps nearby people or objects.
```

### Fix pasted edges
```text
Keep the image unchanged except for the boundary around the inserted subject. Blend the edges naturally with the scene using matching focus softness, grain, color bleed, light wrap, and compression artifacts. Preserve the subject’s identity and clothing.
```

### Fix scale and perspective
```text
Keep the image unchanged except for the inserted subject’s size and depth placement. Adjust the subject to match the surrounding people’s head height, shoulder width, foot position, lens perspective, and distance from the camera. Maintain realistic overlap and contact shadows.
```

### Fix clothing drift
```text
Keep the face, pose, body, background, and lighting unchanged. Restore the clothing to match the reference precisely: same color, collar shape, sleeve length, fabric texture, seams, buttons, lapels, and folds.
```

### Fix background damage
```text
Restore the original background exactly. Keep all people and foreground edits unchanged, but repair any warped architecture, distorted objects, changed signage, damaged furniture, or inconsistent texture in the background.
```

---

## Prompt Patterns by Use Case

### Photorealistic new portrait

```text
Create a photorealistic portrait of [subject description] in [setting]. The person is [pose/expression], wearing [clothing details]. Use realistic skin texture, natural facial asymmetry, detailed hair strands, and believable eye catchlights.

Camera: full-frame mirrorless camera, 85mm lens, shallow depth of field, eye-level framing. Lighting: [specific light setup]. The image should feel like a real photograph with natural color grading, subtle background blur, realistic shadows, and no plastic skin.
```

### Existing photo cleanup

```text
Edit the attached photo to improve realism and polish while preserving the original identity, composition, lighting, background, clothing, and camera angle. Correct only visible artifacts such as warped hands, unnatural skin smoothing, edge halos, inconsistent shadows, or distorted clothing. Keep the image looking like the same original photograph.
```

### Insert object into scene

```text
Add [object] to [location] in the attached image. Preserve the original scene, camera angle, lighting, background, and all existing objects. The added object should match the scene’s perspective, scale, material response, shadows, reflections, focus level, and image grain. Add realistic contact shadows where it touches the surface.
```

### Replace background

```text
Replace the background with [new background] while preserving the subject exactly: same face, expression, hair, clothing, pose, body proportions, and edge detail. Match the new environment’s lighting to the subject or adjust the subject subtly so both appear photographed together. Keep realistic depth of field and contact shadows.
```

### Editorial composite

```text
Create a clearly fictional editorial composite showing [scene]. The image should be photorealistic, but presented as a constructed visual concept rather than documentary evidence. Match all subjects to the same lighting, lens perspective, color grade, depth of field, and image texture.
```

---

## Negative Prompt Library

Use selectively. Do not overload every prompt.

```text
Avoid extra fingers, missing fingers, fused fingers, distorted hands, duplicated faces, mismatched lighting, pasted edges, floating subjects, incorrect shadows, warped shoulders, twisted wrists, unnatural smiles, plastic skin, overly smooth faces, inconsistent grain, incorrect depth of field, changed clothing, damaged background, unreadable text, fake HDR, cartoonish rendering, waxy texture, low-resolution artifacts, and inconsistent perspective.
```

For group photos:

```text
Avoid incorrect head sizes, inconsistent eye lines, overlapping bodies without contact shadows, arms passing through torsos, impossible shoulder placement, extra limbs, duplicated hands, warped suit collars, and inconsistent flash highlights.
```

For portraits:

```text
Avoid symmetrical mannequin faces, glassy eyes, over-smoothed skin, distorted ears, unnatural teeth, smeared hairline, wrong jaw shape, and inconsistent facial age.
```

For product images:

```text
Avoid warped logos, misspelled text, impossible reflections, inconsistent material texture, floating products, incorrect contact shadows, and melted edges.
```

---

## Grok Imagine API Prompt Example

For editing with reference images:

```json
{
  "model": "xai/grok-imagine-image-quality/edit",
  "prompt": "Use <IMAGE_0> as the base image. Preserve its camera angle, background, lighting, color temperature, framing, and image grain. Add the object from <IMAGE_1> onto the table in the lower-right foreground, matching the original perspective, scale, focus, shadows, and reflections. Keep all existing people, furniture, text, and background details unchanged. Avoid pasted edges, mismatched lighting, warped objects, incorrect shadows, or changes to unrelated areas.",
  "image_urls": [
    "image_0",
    "image_1"
  ],
  "num_images": 1,
  "resolution": "1k",
  "aspect_ratio": "auto",
  "enable_base64_output": false
}
```

For generation:

```json
{
  "model": "xai/grok-imagine-image-quality",
  "prompt": "Create a photorealistic indoor event photograph of five adults standing in a loose row, dressed in formal evening clothing. Shot on a full-frame camera with a 35mm lens at eye level, warm indoor ambient light mixed with direct camera flash, mild JPEG compression, natural skin texture, realistic fabric folds, and believable contact shadows. The people should have natural expressions and imperfect candid posture. Avoid extra limbs, distorted hands, duplicated faces, mismatched shadows, or cartoon-like rendering.",
  "num_images": 1,
  "resolution": "1k",
  "aspect_ratio": "3:2",
  "enable_base64_output": false
}
```

---

## High-Fidelity Prompting Checklist

Before finalizing a prompt, verify it includes:

- [ ] Exact action requested
- [ ] What stays unchanged
- [ ] What changes
- [ ] Location of the edit in the frame
- [ ] Scale and perspective requirements
- [ ] Lighting direction and color temperature
- [ ] Shadow and contact details
- [ ] Camera/lens/depth-of-field details if photorealism matters
- [ ] Anatomy constraints if people are involved
- [ ] Negative constraints for likely failure modes
- [ ] Reference-image roles if multiple images are used

---

## Default Settings

Use these defaults unless the task says otherwise:

```json
{
  "resolution": "1k",
  "aspect_ratio": "auto",
  "num_images": 1,
  "style": "photorealistic",
  "workflow": "edit_image when a source image is supplied; generate_image otherwise",
  "iteration_strategy": "single broad prompt first, then targeted repair prompts"
}
```

For portraits:
```json
{
  "aspect_ratio": "3:4",
  "lens": "85mm",
  "depth_of_field": "shallow"
}
```

For event/group photos:
```json
{
  "aspect_ratio": "3:2",
  "lens": "35mm or 50mm",
  "depth_of_field": "moderate"
}
```

For product images:
```json
{
  "aspect_ratio": "1:1 or 4:3",
  "lighting": "soft studio lighting",
  "depth_of_field": "sharp product focus"
}
```

---

## Best Practices

- Plain, explicit sentences outperform old diffusion tag piles.
- Reference images should be sharp, well-lit, and aligned with the desired angle.
- Multi-person composites need scale, overlap, and shadow instructions.
- Identity preservation requires facial-geometry language, not just a name.
- Editing prompts should end with preservation language.
- Do not revise unrelated parts of an image unless instructed.
- Repair prompts should change one failure category at a time.
- For realism, describe physical interaction: pressure, contact, occlusion, fabric compression, shadow transfer.
- For documentary style, include imperfections: mild grain, compression, uneven lighting, candid posture.
- For polished style, include controlled lighting, clean background separation, refined color grading.

---

## Compact Prompt Generator

When asked for a quick prompt, output this structure:

```text
Edit/generate [subject/action]. Preserve [locked elements]. Change only [target edit]. Match [camera/lens/perspective]. Match [lighting/shadows/color]. Ensure [physical integration details]. Avoid [failure modes].
```

Example:

```text
Edit the attached image by placing a black leather briefcase on the floor beside the chair in the lower-left foreground. Preserve the room, people, furniture, lighting, camera angle, color temperature, and image grain. Match the briefcase to the existing perspective and floor plane, with realistic leather texture, soft highlights, correct scale, and a contact shadow beneath it. Avoid floating placement, mismatched lighting, warped edges, or changes to unrelated objects.
```