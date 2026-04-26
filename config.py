from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

TAGALOG_STOPWORDS_PATH = PROJECT_ROOT / "tagalog_stop_words.txt"

DEFAULT_SOURCE_CHANNEL = "google_form"
DEFAULT_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_NUM_ECE_BINS = 10
DEFAULT_BOOTSTRAP_SAMPLES = 1000
DEFAULT_RANDOM_STATE = 42

COLUMN_ALIASES = {
    "age": [
        "Age / Edad",
        "age",
    ],
    "weight": [
        "Weight / Timbang (kg)  (must be a number)",
        "weight",
    ],
    "sex": [
        "Sex / Kasarian ",
        "sex",
    ],
    "text_report": [
        "Report",
        "text_report",
    ],
    "medicine_checkbox": [
        "Which of the following medicine(s) is mentioned in your report? (Select all that apply.) No prescription details needed. / Alin sa mga sumusunod na (mga) gamot ang nabanggit sa iyong report? (Piliin lahat ng naaangkop.) Hindi kailangan ang detalye ng reseta.",
        "medicine_checkbox",
    ],
    "post_action": [
        "What did you do after you experienced these symptoms? (Select all that apply.) / Ano ang ginawa mo pagkatapos mong maranasan ang mga sintomas? (Piliin lahat ng naaangkop.) ",
        "post_action",
    ],
    "dosage": [
        "Dosage / Dosis",
        "dosage",
    ],
    "route": [
        "Drug Admininistration / Ruta ng Administrasyon",
        "route",
    ],
    "reason": [
        "Reasons for Taking / Dahilan ng pag gagamot",
        "reason",
    ],
    "meals": [
        "Meals you took before taking the medicine / Mga huling kinain bago nag gamot",
        "meals",
    ],
    "activities": [
        "Recent activities before taking the medicine / Mga aktibidad bago uminom ng gamot   ",
        "activities",
    ],
    "other_medications": [
        "Other medications / Iba pang mga Gamot",
        "other_medications",
    ],
    "illnesses": [
        "Current and previous illnesses / \nKasalukuyan at dating mga sakit",
        "illnesses",
    ],
    "valid": [
        "Valid",
        "valid",
    ],
    "date_logged": [
        "date_logged",
    ],
    "reporting_channel": [
        "reporting_channel",
    ],
}

REACTION_LABEL = "Reaction"
EXPOSURE_LABEL = "Exposure"
ONSET_LABEL = "Onset"
CHANNEL_LABEL = "ReportingChannel"

EDGE_SUSPECT_DRUG = "suspect_drug"
EDGE_HAS_REACTION = "has_reaction"
EDGE_ONSET_OF = "onset_of"
EDGE_REPORTED_TO = "reported_to"

SYMTOM_TRIGGER_WORDS = {
    "sumakit", "nahilo", "nagsuka", "vomit", "vomiting", "rash", "rashes", "pantal",
    "itch", "itching", "kati", "fever", "lagnat", "diarrhea", "pagtatae", "hilo",
    "lightheaded", "nausea", "nasusuka", "sakit", "pain", "tightness", "hirap",
    "nahirapan", "dry", "mouth", "throat", "hininga", "breathing", "huminga",
}

ONSET_PATTERNS = [
    r"\bafter\s+\d+\s*(?:hr|hrs|hour|hours|oras)\b",
    r"\bafter\s+(?:a|an|mga\s+ilang)\s+\w+\b",
    r"\bpagkalipas\s+ng\s+\w+\b",
    r"\bmga\s+ilang\s+oras\s+after\b",
    r"\bkagabi\b",
    r"\bkanina(?:ng)?\s+(?:umaga|hapon|gabi|tanghali)\b",
    r"\bbefore\s+(?:breakfast|lunch|dinner|sleep|bed)\b",
    r"\bafter\s+(?:breakfast|lunch|dinner|work)\b",
    r"\bbandang\s+(?:umaga|hapon|gabi|tanghali)\b",
    r"\blast\s+night\b",
    r"\bearly\s+morning\b",
]

SHORTHAND_MAP = {
    "hrs": "hours",
    "hr": "hour",
    "u": "you",
    "cge": "sige",
    "pls": "please",
    "pls.": "please",
    "msg": "message",
    "w/": "with",
    "b4": "before",
}

ENGLISH_HINT_PREFIXES = ("anti", "post", "pre", "re")
TAGALOG_PREFIXES = (
    "mag", "nag", "pag", "pang", "ipa", "pinag", "nakaka", "nakapag", "ma", "na"
)
TAGALOG_CUES = {
    "ang", "ng", "sa", "si", "mga", "ako", "ikaw", "siya", "kami", "tayo", "nila",
    "namin", "amin", "ito", "iyan", "iyon", "lang", "din", "daw", "raw", "naman",
    "kasi", "kapag", "bago", "pagkatapos", "kahapon", "kanina", "kagabi", "umaga",
    "hapon", "gabi", "gamot", "uminom", "inom", "pakiramdam", "nahilo", "sumakit",
    "pantal", "kati", "ubo", "lagnat", "sakit", "tiyan", "sikmura", "huminga",
}
PERSONAL_IDENTIFIER_PATTERNS = [
    r"\b\d{11}\b",
    r"\b\d{4}-\d{3}-\d{4}\b",
    r"\b[\w\.-]+@[\w\.-]+\.\w+\b",
]