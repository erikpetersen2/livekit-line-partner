# Build Notes / Gotchas Log

Running log of real problems hit while building this project and how they were diagnosed and fixed.
This is the raw material for the README's "Gotchas / Troubleshooting" section - write entries here
as things happen, not after the fact from memory.

Format per entry:

## <short problem description> (<date>)
**Symptom:** what was observed
**Diagnosis:** how the cause was found
**Fix:** what resolved it
**Takeaway:** the one-sentence lesson for the README

---

## livekit-server installed natively, not via Docker, for local dev (2026-10-23)
**Symptom:** n/a - a deliberate choice, not a bug.
**Diagnosis:** the official agent-starter-python template and self-hosting docs both default to LiveKit
Inference (tied to LiveKit Cloud, billed through a Cloud project) and the ai_coustics noise-cancellation
plugin (also Cloud-metered). Neither is appropriate for a project meant to demonstrate self-hosted operation.
**Fix:** `livekit-server` is installed as a native Linux binary (downloaded directly from the GitHub release,
not the official curl-pipe-to-bash installer - that got blocked by this session's own safety tooling, which
turned out fine since fetching the release binary directly is more transparent anyway) and run via
`livekit-server --dev` for local Phase 1 work. Docker comes back for Phase 2, where the official container
image is what the Helm chart actually deploys to EKS.
**Takeaway:** local dev doesn't need to mirror the production container runtime 1:1 - optimize for fast
iteration locally, match production exactly only where it actually matters (the deployed artifact itself).

## Dropped the template's default noise-cancellation plugin (2026-10-23)
**Symptom:** n/a - a deliberate choice, not a bug.
**Diagnosis:** the agent-starter-python template wires up `ai_coustics.audio_enhancement(...)` by default.
That plugin is metered through LiveKit Cloud (100 free minutes/month on the Build plan); self-hosting it
requires supplying your own ai-coustics license key, which is a separate paid service unrelated to the
OpenAI/Silero stack already in use here.
**Fix:** omitted entirely for Phase 1. `session.start()` is called with no `room_options`/noise-cancellation
config. Silero VAD plus the LLM's own robustness handle the loss of enhancement for now.
**Takeaway:** revisit if background-noise handling turns out to matter for the real demo recording - either
add ai-coustics with its own key, or note the omission explicitly in the README's "at scale for a customer"
section as a known production gap.

## No microphone found under WSL2 (2026-10-23)
**Symptom:** `lk agent console` failed immediately with `input device: portaudio: no default input device`,
plus a spurious ALSA warning about a config path from LiveKit's own CI build
(`/home/runner/work/livekit-cli/.../alsa.conf`). Python's `sounddevice` library raised `OSError: PortAudio
library not found` when queried directly.
**Diagnosis:** WSL2/WSLg bridges the real Windows microphone in through PulseAudio (`PULSE_SERVER=unix:/mnt/wslg/PulseServer`,
confirmed with `pactl list sources short` showing an `RDPSource`), not through ALSA hardware - `arecord -l`
correctly shows no sound cards, because there are none. Audio libraries that default to raw ALSA (like
PortAudio) need an explicit bridge to find it, and the native `libportaudio2` shared library wasn't even
installed yet.
**Fix:** `sudo apt-get install -y pulseaudio-utils libasound2-plugins alsa-utils libportaudio2
portaudio19-dev`, plus a `~/.asoundrc` pointing ALSA's default pcm/ctl at the `pulse` plugin:
```
pcm.!default { type pulse }
ctl.!default { type pulse }
```
Separately, the `lk` CLI binary's own bundled audio stack (Go/CGo, built on LiveKit's CI) never picked up
this fix - it's statically linked against its own copy, unrelated to the system libraries. Worked around by
using `uv run python main.py console` instead of `lk agent console` - `main.py`'s `cli.run_app(server)`
exposes the same `console`/`dev`/`start` subcommands directly through the Python `livekit-agents` package,
which correctly uses the system PortAudio we fixed. (Console mode is flagged as deprecated in favor of `lk
agent console` - worth re-testing the `lk` binary periodically in case this gets fixed upstream.)
**Takeaway:** in WSL2, assume anything audio-related needs an explicit ALSA-to-Pulse bridge - it's not
automatic even though the Pulse socket itself is preconfigured. And a CLI tool bundling its own native
audio bindings can sidestep fixes that work for everything else on the system.

## Adaptive interruption silently retries against LiveKit Cloud and 401s (2026-10-23)
**Symptom:** every console-mode session spent ~4 seconds retrying and logging warnings before actually
starting: `failed to detect interruption ... WSServerHandshakeError: 401 ... url='wss://agent-gateway.livekit.cloud/v1/bargein'`,
eventually falling back to VAD-based interruption on its own.
**Diagnosis:** `TurnHandlingOptions.interruption` defaults to `{"mode": "adaptive"}` in console/dev mode even
though nothing in our code requested it, and adaptive mode is a LiveKit Cloud-hosted service our local
`devkey`/`secret` pair has no access to - hence the 401, not a misconfiguration on our end.
**Fix:** explicitly set `interruption={"mode": "vad"}` in `TurnHandlingOptions` (see `agent/main.py`) so the
session never attempts the Cloud call at all.
**Takeaway:** self-hosted LiveKit Agents still has a few features that quietly assume a Cloud connection by
default - worth explicitly pinning every `TurnHandlingOptions`/session option rather than trusting defaults,
and watching the startup logs closely the first time any new feature is touched.

## LLM called the wrong tool on a flubbed line instead of staying silent (2026-10-23)
**Symptom:** during a live run-through playing Jack, after a correct line was accepted and the agent moved
on, speaking the next line back got the *previous* NPC line repeated instead of advancing - as if "again"
had been triggered, even though nothing was said that should have meant that.
**Diagnosis:** the architecture is deliberately two-tier: `on_user_turn_completed` checks every actor turn
against the deterministic state machine first, and only falls through to the LLM when the line *doesn't*
match (so the LLM can classify free-form commands like "line?"/"again"/"from the top"/"skip to scene N").
With no logging in place yet, there was no way to see what actually happened - but the likely cause is STT
noise or a near-miss causing the fuzzy matcher to score just under threshold, after which the LLM received
an ordinary, non-command utterance and guessed it meant "repeat_last_line" anyway. The system prompt told
the LLM *when* to call each tool but never told it to do nothing when none of the four commands clearly
applied - so on an ambiguous turn, it called a tool instead of just giving the one-line nudge.
**Fix:** added an explicit instruction - "only call a tool when you're confident the actor meant one of the
four commands; a flubbed attempt at their actual line is NOT a request to repeat/restart/skip, so call
nothing and just give the nudge" - plus `logger.info` calls on every tool invocation and on every line-match
attempt (spoken text, expected text, fuzzy score, matched boolean) so a repeat of this is diagnosable from
the logs instead of guesswork.
**Takeaway:** an LLM given tools for a deterministic pipeline needs to be told not to call them just as
explicitly as it's told when to - "classify or do nothing" has to be stated, not assumed - and any
tool-calling agent needs call-level logging from day one, not added after the first confusing bug report.

(further entries start once Phase 1 build/run work continues)
