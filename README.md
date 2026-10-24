# Line Partner

A voice agent built on self-hosted [LiveKit](https://livekit.io) that runs lines with actors: it plays the other
characters' cue lines, listens for your line, and prompts you with the first few words if you go up (forget it).
Built as a reference implementation for how to design, deploy, and operate a production LiveKit voice-AI
application - self-hosted on Kubernetes, with IaC, security hardening, and observability treated as first-class,
not afterthoughts.

> **Status: work in progress.** This README is a skeleton being filled in as the project is built. See
> [NOTES.md](./NOTES.md) for the running build log this will be written from.

## Why this exists

Written up by [Erik Petersen](https://github.com/erikpetersen2) as a hands-on reference implementation exploring
self-hosted LiveKit, voice-AI pipelines, and production deployment on Kubernetes/EKS.

## Commands

- `line?` - prompt with the first few words of your next line
- `from the top` - restart the scene
- `skip to scene N` - jump to a specific scene
- `again` - repeat the last cue line

## Architecture

_TODO (Phase 5): diagram covering client <-> LiveKit SFU <-> agent worker <-> STT/LLM/TTS providers, with ports
and network paths labeled._

### Design decisions

_TODO: self-hosted vs. LiveKit Cloud, STT->LLM->TTS pipeline vs. realtime speech-to-speech model, deterministic
line-matching vs. LLM-generated cue delivery, and why._

## Deploying it

_TODO (Phase 2): step-by-step deploy instructions (`pulumi up`, Helm install, token generation)._

## Tearing it down

_TODO: one-command teardown (`pulumi destroy`), confirming $0 ongoing AWS cost._

## Gotchas / Troubleshooting

_TODO (Phase 5): pulled from [NOTES.md](./NOTES.md) - real problems hit (UDP/firewall, TURN, host networking,
latency) and how they were diagnosed._

## Running this at scale for a customer

_TODO: multi-node with Redis, autoscaling, regions, observability, and cost, as if advising a customer deploying
this in production._

## License

[MIT](./LICENSE)
