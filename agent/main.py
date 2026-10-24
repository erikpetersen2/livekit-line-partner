import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
    inference,
)
from livekit.plugins import openai, silero

logger = logging.getLogger("line-partner-agent")

load_dotenv(".env.local")


class Assistant(Agent):
    """Placeholder agent used to prove the self-hosted voice pipeline end to end.

    Replaced by the real Line Partner cue/listen/prompt state machine once this
    pipeline is verified working against the local `livekit-server --dev` instance.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a placeholder voice agent used only to verify the "
                "self-hosted LiveKit pipeline works end to end. Greet the user "
                "briefly and confirm you can hear them."
            ),
        )


server = AgentServer()


@server.rtc_session(agent_name="line-partner")
async def line_partner_session(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # Self-hosted pipeline: direct OpenAI plugins instead of LiveKit Inference (which
    # is tied to a LiveKit Cloud project), mini-tier models to keep per-session cost low.
    # No noise-cancellation plugin here - the template's default (ai_coustics) is metered
    # through LiveKit Cloud; see NOTES.md for the full tradeoff writeup.
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-mini-transcribe"),
        llm=openai.responses.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(model="gpt-4o-mini-tts", voice="ash"),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            # v1-mini runs locally on CPU, free to use - no LiveKit Cloud dependency.
            turn_detection=inference.TurnDetector(version="v1-mini"),
            # Adaptive interruption defaults on and calls out to a LiveKit Cloud service
            # we don't have access to (401s, then falls back after ~4s of retries). Pin
            # to plain VAD-based interruption so self-hosted sessions start immediately.
            interruption={"mode": "vad"},
        ),
    )

    await session.start(agent=Assistant(), room=ctx.room)
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
