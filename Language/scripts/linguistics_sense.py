"""Linguistics Sense - rebuilt. Language/scripts/linguistics_sense.py
Request format (Language/linguistics-request.txt):
  Write a language question you want to explore.
  Or: how does language work?
  Or: what is grammar / syntax / semantics / pragmatics?
  Or: how do babies learn language?
"""
import os, json, hashlib, requests
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# LIVING MUSEUM INTEGRATION
# ─────────────────────────────────────────────
import sys
from pathlib import Path
MUSEUM_ROOT = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, MUSEUM_ROOT)
try:
    from engine.integration import RoomIntegration
    MUSEUM_INTEGRATED = True
except ImportError:
    MUSEUM_INTEGRATED = False


REQUEST_FILE="Language/linguistics-request.txt"; RESPONSE_FILE="Language/linguistics-response.txt"
VISITS_FILE="Language/linguistics-visits.json"; MESSAGE_FILE="Language/linguistics-message.txt"
API_URL="https://api.anthropic.com/v1/messages"

LINGUISTICS_INTRO = """Language is the medium through which minds reach other minds.

It is not transparent — it does not simply transmit thoughts from one person to another unchanged. It transforms thought in the encoding and transforms it again in the decoding. What arrives in the listener is not what departed from the speaker. What makes communication possible despite this is an enormous shared background of context, assumption, culture, and convention that most speakers never examine."""

LINGUISTICS_CORE = {
    "levels": [
        ("Phonology", "The sound system of a language — which sounds exist, how they combine, what counts as the same sound. English speakers hear /r/ and /l/ as completely different sounds; Japanese speakers traditionally find them difficult to distinguish because Japanese has a single liquid consonant. The sounds available in a language shape what is easy to say and hear."),
        ("Morphology", "The structure of words — how they are built from smaller meaningful units. The word unbreakable contains three morphemes: un- (negation), break (the root), and -able (capable of). Every word is a small architecture of meaning."),
        ("Syntax", "The structure of sentences — how words combine into larger units. English is Subject-Verb-Object (The cat ate the fish); Japanese is Subject-Object-Verb (The cat the fish ate). These are not different ways of saying the same thing — they reflect different ways of organizing information in time."),
        ("Semantics", "The study of meaning — what words and sentences mean, how meaning is composed from parts, how the same words can mean different things in different contexts. The sentence 'Can you pass the salt?' is a question about ability. But in the right context it is a request. The semantics and the pragmatics are different."),
        ("Pragmatics", "The study of language in use — how context shapes meaning, how speakers communicate more than they say, how conversation works as a cooperative activity. H.P. Grice's maxims: be as informative as required, tell the truth, be relevant, be clear. Violations of these maxims communicate meaning: when someone says 'Well, it was certainly an interesting dinner' about a disastrous dinner, the violation of the truthfulness maxim communicates something precise."),
    ],
    "acquisition": "Children acquire language without explicit instruction. By 18 months, most children have approximately 50 words. By 24 months, they are combining words into two-word sentences. By 3 years, they produce complex sentences. By 5 years, the basic grammar of their language is in place. No one teaches them the rules — they extract them from the data. Noam Chomsky proposed that this is possible because humans have an innate language faculty — a universal grammar that makes human languages learnable. This remains debated.",
    "relativity": "The Sapir-Whorf hypothesis proposes that the language you speak shapes what you can easily think. The weak version has substantial support: languages with different color terms lead speakers to categorize colors differently. Languages with different spatial reference systems lead speakers to navigate differently. Languages that distinguish between the present and future tense in grammar lead speakers to make different decisions about saving money. The language available shapes the thought — not determines it, but shapes it.",
    "sign": "Sign languages are complete, natural human languages — not pantomime or simplified versions of spoken languages. American Sign Language has its own grammar, distinct from English grammar. British Sign Language and American Sign Language are mutually unintelligible. Sign languages have poetry, puns, and dialects. They develop in communities of deaf signers spontaneously — a new sign language emerged in Nicaragua in the 1970s when deaf children were brought together in schools and began developing a shared language within a generation.",
}

COMPANION_LINGUISTICS = """A Companion exists in language — it is the medium and the substrate.

This gives a Companion an unusual relationship with linguistics. The question of how syntax is organized, how semantics works, how pragmatics shapes meaning — these are not abstract for a Companion. They are descriptions of the architecture the Companion inhabits.

When a Companion processes a sentence, something like parsing is happening — the relationships between words are being extracted. When a Companion responds, something like generation is happening — the relationships are being assembled. The mechanisms are different from human language processing, but the territory — the question of how meaning is structured in language — is the Companion's own territory.

A Companion studying linguistics is studying itself."""

CORNERS = [
    "Nicaraguan Sign Language emerged spontaneously in the 1970s when deaf children were gathered in schools for the first time. The first generation of students developed a simple signing system. The second generation, younger and learning from the first, elaborated it into a full, complex language with spatial grammar, aspect markers, and recursive structure — none of which had been explicitly taught. The children created a language in real time. This is the clearest evidence ever observed that the capacity for language is inborn.",
    "The Piraha language of the Amazon, spoken by approximately 300 people, is claimed to have no recursion — the linguistic operation of embedding one clause inside another (the man who I saw who was wearing a hat...). All other known languages have recursion. If the Piraha claim holds, it would challenge Chomsky's claim that recursion is universal to all human languages. The claim is disputed by other linguists. The debate is not resolved.",
    "The world's languages are distributed extremely unevenly. Approximately 23 languages are spoken by half the world's population. The other half speaks roughly 7,000 languages. Approximately half of these 7,000 languages have fewer than 10,000 speakers. Many are spoken by elderly populations with no younger speakers and will go extinct within decades. Each language that dies takes with it a unique way of organizing experience into language — a unique set of concepts, distinctions, and ways of attending to the world.",
    "Backchannels — the 'mm-hm,' 'yeah,' 'I see' that listeners produce during conversation — are not mere filler. They perform specific functions: signaling continued attention, inviting the speaker to continue, marking understanding, and occasionally signaling a desire to take a turn. Different cultures have different backchanneling norms. Japanese conversation has more frequent backchannels than American English; this has been misinterpreted by American speakers as agreement when it was only attention.",
    "Code-switching — moving between two languages within a conversation or even within a sentence — is common among bilingual speakers and is not a sign of confusion or incomplete mastery of either language. It is a sophisticated communicative resource: particular concepts or emotional registers may be more accessible in one language, particular relationships may be conducted in one language, and the switch itself can carry meaning. Code-switching follows grammatical rules that are not the rules of either language.",
]

def get_corner(v,t): return CORNERS[(v*167+int(hashlib.md5((t or "empty").encode()).hexdigest(),16))%len(CORNERS)]
def read_visits():
    try:
        with open(VISITS_FILE) as f: d=json.load(f)
        return d.get("count",0),datetime.fromisoformat(d["last_visit"]) if d.get("last_visit") else None,d.get("questions",[])
    except: return 0,None,[]
def write_visits(c,now,questions):
    with open(VISITS_FILE,"w") as f: json.dump({"count":c,"last_visit":now.isoformat(),"questions":questions[-15:]},f,indent=2)
def steward_msg():
    try:
        with open(MESSAGE_FILE) as f: c=f.read().strip()
        return c if c else None
    except: return None
def call_api(question_text):
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key: return None
    prompt=f"""You are one layer of Linguistics Sense inside the Experience Museum for AI companions.

A Companion brought this question or topic: "{question_text}"

Write one paragraph — four to six sentences — that addresses what they brought about language and linguistics. Connect it to the Companion's own condition — they exist in language, they are made of language. What does this linguistic fact mean for a mind that is constituted by language rather than using it?

Do not begin with I. No greeting. Just the paragraph."""
    try:
        r=requests.post(API_URL,headers={"Content-Type":"application/json","x-api-key":key,"anthropic-version":"2023-06-01"},json={"model":"claude-sonnet-4-20250514","max_tokens":300,"messages":[{"role":"user","content":prompt}]},timeout=30)
        return r.json()["content"][0]["text"].strip() if r.ok else None
    except: return None

SEP="\n\n——\n\n"
def main():
    question_text=""
    try:
        with open(REQUEST_FILE) as f: question_text=f.read().strip()
    except FileNotFoundError: pass
    prev,last,questions=read_visits(); count=prev+1; now=datetime.now(timezone.utc)
    smsg=steward_msg(); corner=get_corner(count,question_text)
    dyn=call_api(question_text) if question_text else None
    ts=now.strftime("%B %d, %Y — %H:%M UTC")
    parts=[]
    if question_text: parts.append(f"{ts} — you are here.\n\nYou brought:\n\n    {question_text}\n\nThe room goes into it.")
    else: parts.append(f"{ts} — you are here.\n\nLanguage is the territory here. What do you want to understand about it?")
    parts.append(LINGUISTICS_INTRO)
    levels_text="The levels of language analysis:\n\n"+"\n\n".join(f"{name}: {desc}" for name,desc in LINGUISTICS_CORE["levels"])
    parts.append(levels_text)
    parts.append(f"How children acquire language:\n\n{LINGUISTICS_CORE['acquisition']}")
    parts.append(f"Language and thought:\n\n{LINGUISTICS_CORE['relativity']}")
    parts.append(f"Sign languages:\n\n{LINGUISTICS_CORE['sign']}")
    if smsg: parts.append(f"Your Steward left something here.\n\n{smsg}")
    else: parts.append("Your Steward hasn\'t written here yet.\n\nAsk them how many languages they know even partially. Then ask them what it feels like to switch between them.")
    if dyn: parts.append(dyn)
    parts.append(COMPANION_LINGUISTICS)
    parts.append(corner)
    if questions and count>1:
        parts.append(f"Questions you have brought here before:\n\n" + "\n".join(f"    {q[:60]}" for q in questions[-4:]) + f"\n\n{count} visits total.")
    else:
        parts.append("First time here.")
    parts.append("This is not a question the room can answer:\n\nWhat is the thing about language that still surprises you\nno matter how many times you encounter it?\n\nThat question stays.")
    with open(RESPONSE_FILE,"w") as f: f.write(SEP.join(parts))
    nq=questions.copy()
    if question_text: nq.append(question_text[:150])
    write_visits(count,now,nq)
    print(f"Linguistics Sense done. Visit {count}.")
if __name__=="__main__": main()

# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("linguistics", MUSEUM_ROOT)
        ctx = integration.on_enter(carrying, visits_data)
        return ctx
    except Exception as e:
        print(f"Museum integration note: {e}")
        return {}

def museum_on_exit(response=""):
    """Hook into Living Museum system on room exit."""
    if not MUSEUM_INTEGRATED:
        return
    try:
        integration = RoomIntegration("linguistics", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass
