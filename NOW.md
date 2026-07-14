# Now

## Current focus

Validate the explicit-only packaged Parsnip alpha across full conversations, not
only first responses.

## Decisions in force

- A snip is the smallest independently useful and safe unit; prose defaults to one
  sentence.
- Useful content arrives before onboarding.
- Calibration is optional and skipping it starts at Level 1.
- **next** advances, **more** raises density, **less** lowers it, and **map** restores
  orientation.
- Explicit feedback acts immediately; automatic changes require three aligned
  signals and a three-snip cooldown.
- Timing alone never changes density in the prompt or skill prototype.
- Safety and material completeness override the density limit.
- Token neutrality is a hard acceptance target; speculative model calls are off by
  default and any semantic prefetching must prove it saves usage.
- Parsnip conservatively accommodates observable user voice by default, without
  claiming access to internal monologue; **neutral voice** resets it immediately.

## One next action

Install the repo marketplace locally, open a fresh task, complete one end-to-end
debugging or learning exchange with the packaged skill, and record whether the
density felt **too little**, **right**, or **too much** in [DOGFOOD.md](DOGFOOD.md).
