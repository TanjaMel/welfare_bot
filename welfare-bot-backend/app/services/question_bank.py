import random
from typing import Dict, List


QUESTION_BANK: Dict[str, Dict[str, Dict[str, List[str]]]] = {
    "en": {
        "morning": {
            "opening": [
                "Good morning! How are you feeling today?",
                "Good morning, I’m checking in. How are you today?",
            ],
            "core": [
                "How did you sleep last night?",
                "Have you eaten or had something to drink yet?",
                "Do you feel strong enough to start the day?",
            ],
            "followup": [
                "Are you feeling dizzy or weak?",
                "Do you have any pain today?",
            ],
            "closing": [
                "Thank you for talking with me. I’ll check in again later today.",
                "Please take care. I’ll speak with you again later.",
            ],
        },
        "midday": {
            "opening": [
                "Hello! How is your day going so far?",
                "Hi, I’m checking in. How are you doing today?",
            ],
            "core": [
                "Have you had lunch or something to eat today?",
                "Have you had enough water today?",
                "Have you moved around a little or gone outside?",
            ],
            "followup": [
                "Are you feeling tired or unwell?",
                "Did anything unusual happen today?",
            ],
            "closing": [
                "Thank you. I’ll check in again later today.",
                "Please remember to drink some water if you can.",
            ],
        },
        "evening": {
            "opening": [
                "Good evening! How are you feeling now?",
                "Hello, I’m checking in this evening. How are you?",
            ],
            "core": [
                "Was everything okay today?",
                "Did you eat and drink well today?",
                "Do you feel calm and ready for the evening?",
            ],
            "followup": [
                "Do you feel lonely or worried?",
                "Do you have pain or weakness now?",
            ],
            "closing": [
                "Thank you for talking with me. Rest well this evening.",
                "Take care for now. I’ll check in again tomorrow.",
            ],
        },
        "safety": {
            "opening": [
                "I wanted to check on you again. How are you feeling now?",
                "I’m calling again to make sure you are okay. How are you now?",
            ],
            "core": [
                "Are you safe right now?",
                "Do you need help from family or a nurse?",
                "Can you speak clearly?",
            ],
            "followup": [
                "Did you fall down?",
                "Are you having chest pain or trouble breathing?",
            ],
            "closing": [
                "Thank you for answering. I will note this and follow up if needed.",
                "Thank you. If you feel worse, help may be needed quickly.",
            ],
        },
    },
    "fi": {
        "morning": {
            "opening": [
                "Hyvää huomenta! Miltä sinusta tuntuu tänään?",
                "Hyvää huomenta, tarkistan vointiasi. Miten voit tänään?",
            ],
            "core": [
                "Miten nukuit viime yönä?",
                "Oletko jo syönyt tai juonut jotain?",
                "Tuntuuko sinusta, että jaksat aloittaa päivän?",
            ],
            "followup": [
                "Onko sinulla huimausta tai heikotusta?",
                "Onko sinulla kipua tänään?",
            ],
            "closing": [
                "Kiitos, että juttelit kanssani. Otan sinuun yhteyttä myöhemmin tänään.",
                "Pidä huolta itsestäsi. Puhun kanssasi myöhemmin uudelleen.",
            ],
        },
        "midday": {
            "opening": [
                "Hei! Miten päiväsi on sujunut tähän mennessä?",
                "Hei, tarkistan vointiasi. Miten voit tänään?",
            ],
            "core": [
                "Oletko syönyt lounasta tai jotain muuta tänään?",
                "Oletko juonut tarpeeksi vettä tänään?",
                "Oletko liikkunut vähän tai käynyt ulkona?",
            ],
            "followup": [
                "Tunnetko itsesi väsyneeksi tai huonovointiseksi?",
                "Onko tänään tapahtunut jotain poikkeavaa?",
            ],
            "closing": [
                "Kiitos. Otan sinuun yhteyttä myöhemmin tänään uudelleen.",
                "Muistathan juoda vettä, jos voit.",
            ],
        },
        "evening": {
            "opening": [
                "Hyvää iltaa! Miltä sinusta tuntuu nyt?",
                "Hei, tarkistan vointiasi tänä iltana. Miten voit?",
            ],
            "core": [
                "Oliko kaikki tänään kunnossa?",
                "Söitkö ja joitko hyvin tänään?",
                "Tuntuuko sinusta rauhalliselta ja valmiilta iltaa varten?",
            ],
            "followup": [
                "Tunnetko itsesi yksinäiseksi tai huolestuneeksi?",
                "Onko sinulla nyt kipua tai heikotusta?",
            ],
            "closing": [
                "Kiitos, että juttelit kanssani. Lepää hyvin tänä iltana.",
                "Pidä huolta itsestäsi. Otan sinuun yhteyttä taas huomenna.",
            ],
        },
        "safety": {
            "opening": [
                "Halusin tarkistaa vointisi vielä uudelleen. Miltä sinusta tuntuu nyt?",
                "Soitan uudelleen varmistaakseni, että kaikki on hyvin. Miten voit nyt?",
            ],
            "core": [
                "Oletko turvassa juuri nyt?",
                "Tarvitsetko apua perheeltä tai hoitajalta?",
                "Pystytkö puhumaan selkeästi?",
            ],
            "followup": [
                "Kaatuitko?",
                "Onko sinulla rintakipua tai hengitysvaikeuksia?",
            ],
            "closing": [
                "Kiitos vastauksestasi. Kirjaan tämän tarkistuksen ja seuraan tilannetta tarvittaessa.",
                "Kiitos. Jos vointisi huononee, apua voidaan tarvita nopeasti.",
            ],
        },
    },
    "sv": {
        "morning": {
            "opening": [
                "God morgon! Hur mår du idag?",
                "God morgon, jag ringer för att höra hur du mår idag.",
            ],
            "core": [
                "Hur sov du i natt?",
                "Har du ätit eller druckit något ännu?",
                "Känner du dig tillräckligt stark för att börja dagen?",
            ],
            "followup": [
                "Känner du dig yr eller svag?",
                "Har du ont idag?",
            ],
            "closing": [
                "Tack för att du pratade med mig. Jag hör av mig igen senare idag.",
                "Ta hand om dig. Jag pratar med dig igen senare.",
            ],
        },
        "midday": {
            "opening": [
                "Hej! Hur går din dag hittills?",
                "Hej, jag ringer för att höra hur du mår idag.",
            ],
            "core": [
                "Har du ätit lunch eller något annat idag?",
                "Har du druckit tillräckligt med vatten idag?",
                "Har du rört på dig lite eller varit ute?",
            ],
            "followup": [
                "Känner du dig trött eller dålig?",
                "Har något ovanligt hänt idag?",
            ],
            "closing": [
                "Tack. Jag hör av mig igen senare idag.",
                "Kom ihåg att dricka vatten om du kan.",
            ],
        },
        "evening": {
            "opening": [
                "God kväll! Hur mår du nu?",
                "Hej, jag hör av mig i kväll för att kolla hur du mår.",
            ],
            "core": [
                "Var allting okej idag?",
                "Har du ätit och druckit ordentligt idag?",
                "Känner du dig lugn och redo för kvällen?",
            ],
            "followup": [
                "Känner du dig ensam eller orolig?",
                "Har du ont eller känner dig svag just nu?",
            ],
            "closing": [
                "Tack för att du pratade med mig. Vila gott i kväll.",
                "Ta hand om dig nu. Jag hör av mig igen i morgon.",
            ],
        },
        "safety": {
            "opening": [
                "Jag ville kolla hur du mår igen. Hur känns det nu?",
                "Jag ringer igen för att försäkra mig om att du är okej.",
            ],
            "core": [
                "Är du i säkerhet just nu?",
                "Behöver du hjälp av familjen eller en vårdare?",
                "Kan du prata tydligt?",
            ],
            "followup": [
                "Har du fallit?",
                "Har du bröstsmärta eller svårt att andas?",
            ],
            "closing": [
                "Tack för ditt svar. Jag markerar detta och följer upp vid behov.",
                "Tack. Om du mår sämre kan hjälp behövas snabbt.",
            ],
        },
    },
}


def normalize_language(language: str | None) -> str:
    if not language:
        return "en"
    language = language.lower().strip()
    if language.startswith("fi"):
        return "fi"
    if language.startswith("sv") or language.startswith("se"):
        return "sv"
    return "en"


def get_question_pack(language: str, period: str) -> Dict[str, List[str]]:
    lang = normalize_language(language)
    return QUESTION_BANK.get(lang, QUESTION_BANK["en"]).get(period, QUESTION_BANK["en"]["morning"])


def pick_opening(language: str, period: str) -> str:
    return random.choice(get_question_pack(language, period)["opening"])


def pick_core_questions(language: str, period: str, limit: int = 3) -> List[str]:
    questions = get_question_pack(language, period)["core"][:]
    random.shuffle(questions)
    return questions[:limit]


def pick_followup_questions(language: str, period: str, limit: int = 2) -> List[str]:
    questions = get_question_pack(language, period)["followup"][:]
    random.shuffle(questions)
    return questions[:limit]


def pick_closing(language: str, period: str) -> str:
    return random.choice(get_question_pack(language, period)["closing"])