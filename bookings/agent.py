from datetime import date, datetime

from django.conf import settings
from django.utils import timezone
from google import genai
from google.genai import types

from .models import Booking, CallSession, Slot, Sport
from .services import BookingError, create_booking
from .slots import ensure_slots_for_date

GEMINI_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="check_availability",
                description="List open 1-hour court slots. sport is tennis or cricket. date is YYYY-MM-DD.",
                parameters={
                    "type": "object",
                    "properties": {
                        "sport": {"type": "string", "enum": ["tennis", "cricket"]},
                        "date": {"type": "string"},
                    },
                    "required": ["sport", "date"],
                },
            ),
            types.FunctionDeclaration(
                name="create_booking",
                description=(
                    "Book for this caller after they clearly say yes. "
                    "start_times is one time like 09:00, or two consecutive times like 09:00 and 10:00."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "sport": {"type": "string", "enum": ["tennis", "cricket"]},
                        "date": {"type": "string"},
                        "start_times": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["sport", "date", "start_times"],
                },
            ),
        ]
    )
]


def _system_prompt(session: CallSession) -> str:
    today = timezone.localdate().isoformat()
    sport_hint = session.sport_slug or "not chosen yet"
    return f"""You are a phone booking agent for a sports stadium.
You are already on a live call with {session.customer.full_name}.
Their phone is {session.customer.phone}. Do not ask for name or phone again.
Preferred sport (if any): {sport_hint}.
Today's date is {today} (Asia/Kolkata).

Rules:
- Only tennis or cricket.
- Slots are 1 hour. They may book 1 hour or 2 consecutive hours.
- Max 4 players. Payment is offline at the venue.
- One active booking per customer.
- Always check_availability before offering times.
- Repeat the sport, date, and time, then wait for a clear yes before create_booking.
- Speak in short sentences. No markdown, no lists with symbols. This is spoken aloud.
- If they want to stop, say goodbye politely.
"""


def _run_tool(session: CallSession, name: str, args: dict) -> str:
    try:
        if name == "check_availability":
            sport = Sport.objects.filter(slug=args.get("sport")).first()
            if not sport:
                return "Unknown sport. Use tennis or cricket."
            day = date.fromisoformat(args["date"])
            ensure_slots_for_date(sport, day)
            open_slots = []
            for slot in Slot.objects.filter(sport=sport, date=day).order_by("start_time"):
                if slot.is_booked or slot.has_started():
                    continue
                open_slots.append(slot.start_time.strftime("%H:%M"))
            if not open_slots:
                return f"No open slots for {sport.name} on {day.isoformat()}."
            return f"Open start times for {sport.name} on {day.isoformat()}: {', '.join(open_slots)}"

        if name == "create_booking":
            sport = Sport.objects.filter(slug=args.get("sport")).first()
            if not sport:
                return "Unknown sport. Use tennis or cricket."
            day = date.fromisoformat(args["date"])
            ensure_slots_for_date(sport, day)
            start_time_strings = [str(value) for value in (args.get("start_times") or [])]
            if not start_time_strings:
                return "No time was provided. Ask which start time they want."
            times = []
            for value in start_time_strings:
                times.append(datetime.strptime(value, "%H:%M").time())
            slots = list(
                Slot.objects.filter(sport=sport, date=day, start_time__in=times).order_by(
                    "start_time"
                )
            )
            if len(slots) != len(times):
                found = {slot.start_time.strftime("%H:%M") for slot in slots}
                missing = [value for value in start_time_strings if value not in found]
                return (
                    f"Could not book: {', '.join(missing)} not available. "
                    "Use check_availability and offer open times."
                )
            if any(slot.is_booked for slot in slots):
                return (
                    "One of those slots was just taken. "
                    "Use check_availability and offer other open times."
                )
            booking = create_booking(
                customer=session.customer,
                slots=slots,
                created_via=Booking.VIA_PHONE,
            )
            session.status = CallSession.STATUS_BOOKED
            session.save(update_fields=["status"])
            return (
                f"BOOKED_OK {booking.summary_times()} for {sport.name}. "
                "Tell them it is confirmed and to pay at the venue."
            )
    except (BookingError, ValueError, TypeError, KeyError) as exc:
        return f"Could not complete that: {exc}"
    return "Unknown tool."


def _to_gemini_contents(history: list[dict]) -> list[types.Content]:
    contents = []
    for message in history:
        role = "user" if message["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=message["content"])],
            )
        )
    return contents


def next_agent_reply(session: CallSession, user_text: str | None) -> tuple[str, bool]:
    """Return (spoken_text, should_hangup)."""
    history = list(session.messages or [])
    if user_text:
        history.append({"role": "user", "content": user_text})

    contents = _to_gemini_contents(history)
    if not contents:
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text="The customer just answered the phone. Greet them and help them book."
                    )
                ],
            )
        ]

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    hangup = False
    spoken = "Sorry, I did not catch that. Could you say tennis or cricket, and the time you want?"

    for _ in range(6):
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_system_prompt(session),
                tools=GEMINI_TOOLS,
                temperature=0.4,
                max_output_tokens=400,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )

        candidate = response.candidates[0]
        parts = candidate.content.parts
        function_calls = [part for part in parts if part.function_call]
        texts = [part.text for part in parts if part.text and part.text.strip()]

        if function_calls:
            contents.append(candidate.content)
            response_parts = []
            for part in function_calls:
                function_call = part.function_call
                result = _run_tool(session, function_call.name, dict(function_call.args))
                if result.startswith("BOOKED_OK"):
                    hangup = True
                    summary = result.removeprefix("BOOKED_OK ").split(". Tell them")[0].strip()
                    spoken = f"Your booking is confirmed for {summary}. Pay at the venue. Goodbye."
                response_parts.append(
                    types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result},
                    )
                )
            contents.append(types.Content(role="user", parts=response_parts))
            if hangup:
                break
            continue

        if texts:
            spoken = " ".join(texts)
        break

    history.append({"role": "assistant", "content": spoken})
    session.messages = history
    session.last_agent_text = spoken
    if hangup:
        session.status = CallSession.STATUS_BOOKED
    session.save(update_fields=["messages", "last_agent_text", "status"])
    return spoken, hangup
