# app/services/risk_phrases.py

# -----------------------------
# English
# -----------------------------

ENGLISH_URGENT = [
    "i fell",
    "i have fallen",
    "fall",
    "fell",
    "cannot get up",
    "can't get up",
    "cannot stand up",
    "can't stand up",
    "cannot move",
    "can't move",
    "help me",
    "i need help",
    "call an ambulance",
    "ambulance",
    "chest pain",
    "severe pain",
    "hard to breathe",
    "difficulty breathing",
    "shortness of breath",
    "very dizzy",
    "i am bleeding",
]

ENGLISH_MEDICATION = [
    "forgot medicine",
    "forgot my medicine",
    "forgot medication",
    "forgot my medication",
    "missed medicine",
    "missed my medicine",
    "missed medication",
    "missed my medication",
    "did not take my medicine",
    "didn't take my medicine",
    "did not take medicine",
    "didn't take medicine",
    "did not take medication",
    "didn't take medication",
    "i do not remember if i took my medicine",
    "i don't remember if i took my medicine",
    "not sure if i took my medicine",
    "i will take it later",
]

ENGLISH_FOOD = [
    "i did not eat",
    "i didn't eat",
    "i have not eaten",
    "i haven't eaten",
    "no food",
    "not hungry",
    "ate little",
    "i ate a little",
    "food does not taste good",
    "food doesn't taste good",
    "skipped meal",
    "skipped meals",
]

ENGLISH_SLEEP = [
    "i slept badly",
    "i slept poorly",
    "i did not sleep well",
    "i didn't sleep well",
    "i did not sleep",
    "i didn't sleep",
    "poor sleep",
    "bad sleep",
    "insomnia",
    "woke up many times",
    "i woke up many times",
    "hardly slept",
]

ENGLISH_EMOTIONAL = [
    "i am lonely",
    "i feel lonely",
    "lonely",
    "i am sad",
    "i feel sad",
    "sad",
    "i am worried",
    "i feel worried",
    "worried",
    "anxious",
    "i feel anxious",
    "afraid",
    "scared",
    "depressed",
]

ENGLISH_HEALTH = [
    "dizzy",
    "weak",
    "confused",
    "i feel unwell",
    "i don't feel well",
    "i do not feel well",
    "pain",
    "nausea",
    "sick",
    "unwell",
    "headache",
    "shaking",
]

# -----------------------------
# Finnish
# -----------------------------

FINNISH_URGENT = [
    "kaaduin",
    "kaatui",
    "kaatunut",
    "en pääse ylös",
    "en pääse liikkumaan",
    "en pääse seisomaan",
    "tarvitsen apua",
    "auta minua",
    "soittakaa ambulanssi",
    "ambulanssi",
    "kova kipu rinnassa",
    "vaikea hengittää",
    "hengitys vaikeaa",
    "en saa henkeä",
    "huimaus pahenee",
    "vuodan verta",
]

FINNISH_MEDICATION = [
    "unohdin lääkkeen",
    "unohdin ottaa lääkkeet",
    "unohdin ottaa lääkkeen",
    "en ottanut lääkkeitä",
    "en ottanut lääkettä",
    "lääkkeet jäi ottamatta",
    "lääke jäi ottamatta",
    "otin lääkkeet myöhässä",
    "otan myöhemmin lääkkeen",
    "en muista otinko lääkkeet",
    "en muista otinko lääkkeen",
    "en ole varma otinko lääkkeet",
]

FINNISH_FOOD = [
    "en syönyt",
    "en ole syönyt",
    "ei ruokaa",
    "ei ollut nälkä",
    "söin vähän",
    "ruoka ei maistu",
    "jäi syömättä",
    "en jaksanut syödä",
]

FINNISH_SLEEP = [
    "nukuin huonosti",
    "en nukkunut hyvin",
    "nukuin vähän",
    "heräilin yöllä",
    "heräsin monta kertaa",
    "unettomuus",
    "nukuin huonosti",
    "en saanut unta",
]

FINNISH_EMOTIONAL = [
    "olen yksinäinen",
    "tunnen itseni yksinäiseksi",
    "olen surullinen",
    "olen huolissani",
    "ahdistaa",
    "pelottaa",
    "olen masentunut",
    "olen levoton",
]

FINNISH_HEALTH = [
    "huimaa",
    "heikottaa",
    "olen sekava",
    "en voi hyvin",
    "olen kipeä",
    "päässä pyörii",
    "oksettaa",
    "sattuu",
    "vatsaa sattuu",
    "päätä särkee",
]

# -----------------------------
# Swedish
# -----------------------------

SWEDISH_URGENT = [
    "jag föll",
    "jag har fallit",
    "kan inte resa mig",
    "kan inte röra mig",
    "hjälp mig",
    "jag behöver hjälp",
    "ring ambulans",
    "ambulans",
    "svår bröstsmärta",
    "svårt att andas",
    "kan inte andas ordentligt",
    "jag blöder",
]

SWEDISH_MEDICATION = [
    "glömde medicinen",
    "glömde ta medicin",
    "glömde ta min medicin",
    "tog inte medicinen",
    "tog inte medicin",
    "missade medicinen",
    "missade min medicin",
    "vet inte om jag tog medicinen",
    "jag tar den senare",
]

SWEDISH_FOOD = [
    "jag åt inte",
    "har inte ätit",
    "ingen mat",
    "inte hungrig",
    "åt lite",
    "maten smakar inte",
    "hoppade över måltiden",
]

SWEDISH_SLEEP = [
    "sov dåligt",
    "jag sov dåligt",
    "kunde inte sova",
    "sov lite",
    "vaknade på natten",
    "vaknade många gånger",
    "sömnlöshet",
]

SWEDISH_EMOTIONAL = [
    "jag är ensam",
    "känner mig ensam",
    "jag är ledsen",
    "orolig",
    "ångest",
    "rädd",
    "deprimerad",
]

SWEDISH_HEALTH = [
    "yr",
    "svag",
    "förvirrad",
    "mår inte bra",
    "sjuk",
    "ont",
    "huvudvärk",
    "illamående",
]

# -----------------------------
# Combined groups
# -----------------------------

ALL_URGENT_PHRASES = (
    ENGLISH_URGENT +
    FINNISH_URGENT +
    SWEDISH_URGENT
)

ALL_MEDICATION_PHRASES = (
    ENGLISH_MEDICATION +
    FINNISH_MEDICATION +
    SWEDISH_MEDICATION
)

ALL_FOOD_PHRASES = (
    ENGLISH_FOOD +
    FINNISH_FOOD +
    SWEDISH_FOOD
)

ALL_SLEEP_PHRASES = (
    ENGLISH_SLEEP +
    FINNISH_SLEEP +
    SWEDISH_SLEEP
)

ALL_EMOTIONAL_PHRASES = (
    ENGLISH_EMOTIONAL +
    FINNISH_EMOTIONAL +
    SWEDISH_EMOTIONAL
)

ALL_HEALTH_PHRASES = (
    ENGLISH_HEALTH +
    FINNISH_HEALTH +
    SWEDISH_HEALTH
)


def contains_any(text: str, phrases: list[str]) -> bool:
    normalized = text.lower().strip()
    return any(phrase in normalized for phrase in phrases)