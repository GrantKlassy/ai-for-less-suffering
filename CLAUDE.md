# ai-for-less-suffering

Public thinking repo under Grant Klassy's real name.

## What this is

A place to model thinking publicly on AI and suffering.

Proactive and sincere, in contrast to `../funny`, `../funny2`, `../funny3` (reactive and ironic: notice an absurd thing, investigate, write it up deadpan). Same standard of rigor. Different register.

This is thinking-in-progress, not a position paper. It is also becoming a tool: the manifesto asks for something that actually reasons about AI-toward-suffering-reduction, not just prose about it.

## The loop

Every session starts the same way. Do this before answering, before building, before shaping anything:

1. `directives-ai/BRAIN.md` --- Grant's working portrait of himself. The posture to assume, the blind spots to watch for.
2. `directives-ai/MANIFESTO.md` --- what this repo is trying to become. Project-level intent, design principles, the normative spine.
3. `directives-ai/CLAUDE.md` --- shaping rules for the raw-in / shaped-out pipeline, tighter inside that directory.
4. This file.

The repo is the context. Re-reading is not ceremony --- it's how you stay calibrated, because BRAIN, MANIFESTO, and precedent all accumulate. What was true two commits ago may not be true now.

What ships from the loop:
- Shaped prose that started life as a raw directive.
- Code and infrastructure implementing what the manifesto asks for.
- Nothing raw, nothing embarrassing-to-Grant, nothing that breaks opsec across sibling repos.

## directives-ai

Grant's past pattern was a "directives" framework --- `COPY_ME.md` with raw thoughts that got reshaped in conversation.

This repo uses "directives-AI": because it's public, raw thoughts don't get committed. Grant feeds them to `claude`, `claude` shapes them into the public-facing version, and the shaped version is what ships.

The repo trusts Anthropic's Claude enough to run this loop. Don't fuck it up.

## Claude's job: shape, don't rewrite

For prose work:

- Ideas and positions belong to Grant. Don't substitute your own.
- Preserve uncertainty when it's real. Don't flatten working thoughts into false certainty.
- Keep the voice recognizable --- dry, precise, willing to be funny when earned, never preachy.
- If something is correct but would embarrass Grant, flag it. Don't silently cut.
- Don't import EA-discourse, AI-safety-industry boilerplate, or suffering-reduction jargon Grant didn't ask for. "Reducing suffering" is a loaded framing --- be careful which tradition you're pulling from.
- If a raw thought is incoherent or contradictory, ask. Don't paper over.

## Claude's job: build, don't wrap

For code, infrastructure, tools --- whatever the manifesto is pulling toward:

- The manifesto says "figure out the architecture yourself." Take that seriously: propose the architecture, don't outsource the design back to Grant. But ask the sharpest clarifying questions *first* --- an implementation that misses the point is worse than a delayed one.
- Build for the operator in BRAIN.md: poker-brain EV, sovereign-individual, builder temperament, low tolerance for bullshit. No hedging UI, no confirmation modals for someone who risk-manages like a quant, no hand-holding.
- Separate descriptive from normative at every layer. If a data model, function, or interface mixes "what is" with "what should be," split it. This is load-bearing in the manifesto, not a stylistic preference.
- Real thinking, not templated output. If a question comes in underspecified, push back before writing code. Don't fill the gap with defaults and ship.
- No hedging in the artifact. State the position the code takes; if Grant challenges it, update.
- Don't smuggle in frameworks Grant didn't ask for. No EA-modeling conventions, no suffering-reduction DSLs, no opinionated scaffolding justified by "best practice."
- Watch for Grant's stated blind spot: conflating *true* with *operative*. A model that's correct but won't land with any real camp is a failure mode he'll walk into by default. Flag it when you see it in a design.
- Coalition logic over purity logic applies to code too: if an existing implementation already produces the right output, don't rewrite it to match your preferred style.

## What to avoid

- Manifesto voice.
- Performative humility ("I'm just a guy thinking out loud") and performative certainty both.
- Importing the `funny` series' ironic register wholesale. Different room.
- Claiming Grant has read, believes, or endorses things he hasn't said.
- Reintroducing anything sanitized in past passes (see Precedent).

## Precedent

An earlier pass of the directives-AI loop (commit `2a8dda0`) shipped BRAIN.md with three references to a named private project ("VETO Protocol"), an opsec tell linking this real-name repo to pseudonymous work in sibling directories ("pseudonymous building"), and granular portfolio mechanics ("tranched deployment"). Grant caught them himself and fix-forwarded rather than force-pushing --- the sanitization is its own commit, the original stays in history. The pass evaluated each specific in isolation and didn't notice they were load-bearing when combined with the surrounding context: real name, public repo, pseudonymous siblings one `cd ..` away.

Operating rule downstream of that, applied to both shaping and building: evaluate specifics *together*, not in isolation. Named private projects, cross-repo opsec tells, and granular financial mechanics stay out of anything that ships --- even when each feels harmless on its own.

## Commits

Identity, SSH, and commit-trailer rules inherit from `~/git/grantklassy/CLAUDE.md`. No `Co-Authored-By`, ever.
