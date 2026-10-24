import logging
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    TurnHandlingOptions,
    cli,
    function_tool,
    inference,
)
from livekit.agents.llm import ChatContext, ChatMessage, StopResponse
from livekit.plugins import openai, silero

from line_partner.matcher import line_match_score
from line_partner.parser import parse_script_file
from line_partner.script_model import Script
from line_partner.state_machine import Action, Done, LinePartnerSession, Say

logger = logging.getLogger("line-partner-agent")

load_dotenv(".env.local")

SCRIPT_PATH = (
    Path(__file__).parent.parent / "script" / "the_importance_of_being_earnest.txt"
)


def _instructions(script: Script) -> str:
    characters = ", ".join(script.characters)
    return (
        "You are Line Partner, a voice agent that helps an actor rehearse a scene "
        f'from "{script.title}" by reading every other character\'s lines aloud and '
        "listening for the actor's own lines.\n\n"
        f"The characters in this script are: {characters}.\n\n"
        "First, ask the actor which character they want to play, then call the "
        "choose_character tool with their answer.\n\n"
        "Once a character is chosen, your only jobs are:\n"
        "1. Recognize these commands and call the matching tool, however the actor "
        'phrases them: asking for their line or saying they forgot it ("line?", '
        '"what\'s my line", "I went up") -> request_line_hint; asking to restart the '
        'scene ("from the top", "let\'s restart") -> restart_scene; asking to jump '
        'to a specific scene ("skip to scene 2") -> skip_to_scene; asking to hear '
        'the last line again ("again", "say that one more time") -> '
        "repeat_last_line.\n"
        "2. If the actor's speech is clearly not a command and also isn't a correct "
        "delivery of their line (correct deliveries are handled automatically, "
        "outside of your control), give exactly one short, encouraging nudge to try "
        "again. Never reveal the line itself unless they explicitly ask for it. "
        "Never narrate the scene, never comment when a line is delivered correctly, "
        "and never say anything beyond what's described here.\n\n"
        "Only call a tool when you're confident the actor meant one of the four "
        "commands above. A flubbed or incomplete attempt at their actual line is "
        "NOT a request to repeat, restart, or skip anything - if you're not sure "
        "which of the four commands they meant, don't call any tool at all; just "
        "give the one-line nudge from rule 2."
    )


class LinePartnerAgent(Agent):
    """Runs an actor through a script, speaking every other character's lines.

    Cue delivery and line-matching are fully deterministic (LinePartnerSession);
    the LLM here is only ever used to recognize which command an actor meant, via
    the function_tools below, and to nudge a flubbed attempt that isn't a command.
    """

    def __init__(self, script: Script) -> None:
        super().__init__(instructions=_instructions(script))
        self.script = script
        self.line_session: LinePartnerSession | None = None

    async def on_enter(self) -> None:
        await self.session.say(
            f"Let's run some lines from {self.script.title}. "
            f"Who do you want to play - {', '.join(self.script.characters)}?"
        )

    async def _run_actions(self, actions: list[Action]) -> None:
        for action in actions:
            if isinstance(action, Say):
                await self.session.say(action.text)
            elif isinstance(action, Done):
                await self.session.say(
                    'That\'s the end of the scene. Nicely done. Say "from the top" '
                    "to run it again."
                )
            # Listen actions need nothing said here - it's simply the actor's turn.

    @function_tool()
    async def choose_character(self, context: RunContext, character_name: str) -> None:
        """Start the run-through with the actor playing the given character.

        Args:
            character_name: The character the actor wants to play, as they said it.
        """
        logger.info("tool call: choose_character(%r)", character_name)
        try:
            self.line_session = LinePartnerSession(self.script, character_name)
        except ValueError:
            await self.session.say(
                f"I don't have a character called {character_name} in this script. "
                f"You can play {', '.join(self.script.characters)}."
            )
            return
        await self.session.say(
            f"Great, you're playing {self.line_session.actor_character}."
        )
        await self._run_actions(self.line_session.start())

    @function_tool()
    async def request_line_hint(self, context: RunContext) -> None:
        """Prompt the actor with the first few words of the line they're stuck on."""
        logger.info("tool call: request_line_hint")
        if (
            self.line_session is None
            or self.line_session.current_expected_line() is None
        ):
            return
        await self.session.say(self.line_session.line_hint())

    @function_tool()
    async def repeat_last_line(self, context: RunContext) -> None:
        """Repeat the most recently spoken non-actor line."""
        logger.info("tool call: repeat_last_line")
        if self.line_session is None:
            return
        action = self.line_session.again()
        if action is not None:
            await self.session.say(action.text)

    @function_tool()
    async def restart_scene(self, context: RunContext) -> None:
        """Restart the current scene from its first line."""
        logger.info("tool call: restart_scene")
        if self.line_session is None:
            return
        await self._run_actions(self.line_session.from_the_top())

    @function_tool()
    async def skip_to_scene(self, context: RunContext, scene_number: int) -> None:
        """Jump directly to the start of the given scene.

        Args:
            scene_number: The 1-indexed scene number to jump to.
        """
        logger.info("tool call: skip_to_scene(%d)", scene_number)
        if self.line_session is None:
            return
        try:
            actions = self.line_session.skip_to_scene(scene_number)
        except ValueError:
            count = len(self.script.scenes)
            await self.session.say(
                f"This script only has {count} scene{'s' if count != 1 else ''}."
            )
            return
        await self._run_actions(actions)

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        # Deterministic fast path: if this is a correct delivery of the actor's
        # current line, speak the next cues directly and skip the LLM turn
        # entirely - no paraphrasing, no latency, no chance of unwanted commentary.
        # Anything else (a command, a flubbed attempt) falls through to the LLM,
        # which is only ever used here to classify intent.
        if self.line_session is None:
            return
        expected = self.line_session.current_expected_line()
        if expected is None:
            return

        spoken = new_message.text_content or ""
        matched, actions = self.line_session.submit_line(spoken)
        logger.info(
            "line attempt: character=%s expected=%r spoken=%r score=%.1f matched=%s",
            self.line_session.actor_character,
            expected.text,
            spoken,
            line_match_score(spoken, expected.text),
            matched,
        )
        if not matched:
            return

        await self._run_actions(actions)
        raise StopResponse()


server = AgentServer()


@server.rtc_session(agent_name="line-partner")
async def line_partner_session(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    script = parse_script_file(str(SCRIPT_PATH))

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

    await session.start(agent=LinePartnerAgent(script), room=ctx.room)
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
