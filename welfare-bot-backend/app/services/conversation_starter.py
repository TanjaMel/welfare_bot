from __future__ import annotations

from datetime import datetime, timezone


def get_time_period() -> str:
    hour = datetime.now(timezone.utc).hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    else:
        return "evening"


GREETINGS = {
    "morning": {
        "fi": "Hyvää huomenta! 🌅 Toivottavasti olet nukkunut hyvin. Miten meni viime yö — oliko uni levollista?",
        "en": "Good morning! 🌅 I hope you rested well. How did you sleep last night — did you feel rested when you woke up?",
        "sv": "God morgon! 🌅 Jag hoppas att du sov bra. Hur sov du i natt — kände du dig utvilad när du vaknade?",
    },
    "afternoon": {
        "fi": "Hyvää päivää! ☀️ Oletko muistanut syödä ja juoda tarpeeksi tänään?",
        "en": "Good afternoon! ☀️ Have you had enough to eat and drink today?",
        "sv": "God eftermiddag! ☀️ Har du ätit och druckit tillräckligt idag?",
    },
    "evening": {
        "fi": "Hyvää iltaa! 🌙 Miltä sinusta tuntuu tänään — onko sinulla kipuja tai huolia?",
        "en": "Good evening! 🌙 How are you feeling overall today — any pain or worries on your mind?",
        "sv": "God kväll! 🌙 Hur mår du överlag idag — har du några smärtor eller bekymmer?",
    },
}

# When bot greeted but user never responded — acknowledge the silence warmly
NO_RESPONSE_GREETINGS = {
    "morning": {
        "fi": "Hyvää huomenta! 🌅 Yritin tavoittaa sinua aiemmin — toivottavasti kaikki on hyvin. Miten sinulla menee tänä aamuna?",
        "en": "Good morning! 🌅 I tried to reach you earlier — I hope everything is okay. How are you doing this morning?",
        "sv": "God morgon! 🌅 Jag försökte nå dig tidigare — hoppas allt är bra. Hur mår du i morse?",
    },
    "afternoon": {
        "fi": "Hei taas! ☀️ En kuullut sinusta aiemmin tänään. Toivottavasti olet voinut hyvin — miten menee nyt?",
        "en": "Hello again! ☀️ I hadn't heard from you earlier today. I hope you're doing well — how are you now?",
        "sv": "Hej igen! ☀️ Jag hörde inte av dig tidigare idag. Hoppas du mår bra — hur är det nu?",
    },
    "evening": {
        "fi": "Hyvää iltaa! 🌙 En ole kuullut sinusta tänään. Se on ihan ok — mutta halusin varmistaa, että olet turvassa. Miten voit?",
        "en": "Good evening! 🌙 I haven't heard from you today. That's okay — but I wanted to make sure you're safe. How are you doing?",
        "sv": "God kväll! 🌙 Jag har inte hört av dig idag. Det är okej — men jag ville se till att du är säker. Hur mår du?",
    },
}

FOLLOW_UPS = {
    "morning": {
        "fi": "Oletko jo syönyt aamupalan ja juonut vettä?",
        "en": "Have you had breakfast and some water yet?",
        "sv": "Har du ätit frukost och druckit lite vatten än?",
    },
    "afternoon": {
        "fi": "Miltä energiatasosi tuntuu juuri nyt — oletko väsynyt?",
        "en": "How are your energy levels right now — are you feeling tired?",
        "sv": "Hur känns din energinivå just nu — känner du dig trött?",
    },
    "evening": {
        "fi": "Onko tänään ollut jotain erityistä — hyvää tai huonoa?",
        "en": "Has anything notable happened today — good or bad?",
        "sv": "Har något särskilt hänt idag — bra eller dåligt?",
    },
}


def get_opening_message(language: str, user_ignored_last: bool = False) -> str:
    """
    Returns greeting based on time of day and language.
    If user_ignored_last=True, uses a softer 'I tried to reach you' message.
    """
    period = get_time_period()
    lang = language if language in ("fi", "en", "sv") else "fi"
    if user_ignored_last:
        return NO_RESPONSE_GREETINGS[period][lang]
    return GREETINGS[period][lang]


def get_follow_up(language: str) -> str:
    period = get_time_period()
    lang = language if language in ("fi", "en", "sv") else "fi"
    return FOLLOW_UPS[period][lang]