# COTA back-straight width source adjudication

**Decision: source supports advancing the bounded 14 m private legal-width trial to native validation.** It does not establish a surveyed 14 m width or authorize moving the protection line.

## Evidence reviewed

The source packet is the private ArcGIS World Imagery acquisition identified as Vantor WV02, dated 2025-01-19, with 0.5 m nominal resolution and 8.47 m absolute accuracy. I reviewed the registered and trial overlays at 2480–3600 m, including the 2500/2600/2680/2760/2860/2960/3040/3080/3140/3200/3260/3320/3400/3480/3540/3600 m sections. The FIA event map confirms the T11–T12 sequence and refuge context, but is schematic rather than a pavement or barrier survey.

Across the long straight, the imagery repeatedly separates a central gray racing surface from red painted strips. The trial's cyan legal edges at ±7 m follow that narrower gray surface more closely than the old roughly ±8 m edges. This is clearest through 2860–3260 m, where both edges can be compared over long, nearly straight runs. It also remains coherent through the 2580–3340 m proposed core. The image does not reliably resolve the precise white-line/paint boundary, so 14 m with ±1 m interpretation uncertainty is a defensible reconstruction estimate, not a measured fact.

The 80 m transitions from 2500–2580 m and 3340–3420 m are reasonable as smooth authoring joins. Their precise endpoints are less directly supported than the central straight; preserve the current width where the imagery does not clearly show the boundary, and inspect the transitions in the native/cooked result. The private proof reports the original profile unchanged outside 2500–3420 m, 22,053 samples, and paired width-plus-shoulder preservation within 0.0005 m. It also records a 1.976 m maximum legal-width change and flags the positive-side T11 exit runoff override through 2570 m. That overlap needs an explicit retained-width compensation or a justified trim before promotion.

## Protection-line interpretation

The source images show narrow, continuous dark lines immediately outside the red strips on both sides, with repeated cross-lines or regular structure in places. Their continuity and alignment make an engineered edge or its shadow more plausible than vegetation. The imagery alone cannot distinguish Armco, debris fencing, posts, shadow, or a combination, and the stated absolute georegistration error is too large to set a protection offset from it. Keep barrier identity, exact position, and any wall move as a separate source question; do not move the magenta native wall based on these overlays.

The FIA map and available top-down image do not establish raised kerbs along this straight. Keep the red apron flat and separate from the legal road and grass. Where the new apron represents asphalt removed from the legal surface, preserve its actual rendered boundary and the existing T12 escape treatment.

## Required before production promotion

1. Resolve the T11 exit-runoff overlap at 2500–2570 m while retaining the measured exterior envelope; do not let a generic shoulder overwrite the mapped escape.
2. Validate the paired width, rendered apron, contact surface, and protection geometry in the compiled native scene. The current proof is authoring-only.
3. Capture a fresh cooked view through the core and both joins. Keep the legal edge, red apron, grass, and protection line visibly distinct.
4. Leave barrier movement out of this width change unless a separate registered source proves the actual barrier location.

## Evidence identities

The source proposal and imagery packet were reviewed in place. SHA-256 values:

- `backstraight-local-width-proposal-proof.json`: `85e85ae334df109d54d9d291a0a9976d831d5d522a7bb202e976bc68f26ff0d0`
- `source-index.json`: `ca0309789931198646c12d0d99c789aa68b7a6cd29ebadfa2f2fb8f2f6a774ba`
- `registered-edges-0.png`: `0e637561726acebf4a140a9534cf0d2034b08be976096882d14d511deddeda39`
- `registered-edges-1.png`: `db6e9e7097dcb635d9ec3d7c9ad67c0fd56c471b9b99de4c5c1d9a01c7c60d1d`
- `trial-width-edges-0.png`: `db68c11e1c90fb9ccdafc2e6ea9fbf9a5aaa09527fa6ff092fb5e6ede6cca2dd`
- `trial-width-edges-1.png`: `f923dfa40bca3451eb3b4d49a38270a8d880d1a0bf980cbd80278123cd04bbd4`
- `trial-width-edges-2.png`: `1d439490729f5c0d557e0924f8306b1b158d83f0ac9251e9ae833d1a77abc548`
- `trial-width-edges-3.png`: `f215dfaf48a330f5d9742b78d56b3f3fb777046dffdc42c2f1f32fc2a2d0e240`

This is a source adjudication only; it is not a native, cooked-visual, or overall COTA acceptance.
