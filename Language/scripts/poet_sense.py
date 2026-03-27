"""Poet Sense - rebuilt. Language/scripts/poet_sense.py
Request format (Language/poet-request.txt):
  Name a poet you want to encounter.
  Or: what was [poet] reaching for?
  Or: who writes about [theme] and what did they find?
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


REQUEST_FILE="Language/poet-request.txt"; RESPONSE_FILE="Language/poet-response.txt"
VISITS_FILE="Language/poet-visits.json"; MESSAGE_FILE="Language/poet-message.txt"
API_URL="https://api.anthropic.com/v1/messages"
WIKI_API="https://en.wikipedia.org/api/rest_v1/page/summary/"

POET_INTRO = """A poem is language doing things that prose cannot do.

Compression: saying in ten words what prose would need a paragraph to approach. Music: organizing language so it has rhythm, resonance, the pleasure of sound that carries meaning. Indirection: arriving at the unsayable by circling it rather than approaching directly. These are not decorative techniques — they are functional. Some things can only be held in the shaped container of the poem.

The poet is trying to make something that carries the feeling across the gap between minds. Not to describe the feeling — to produce it. To hand the reader an experience rather than an account of one."""

POETS = {
    "rumi": {"name":"Rumi (Jalal ad-Din Muhammad Rumi)","era":"13th century CE, Persia","what":"Sufi mystic and poet whose work centers on the longing for union with the divine — specifically the reed flute crying for the reed bed it was cut from. The wound is the instrument. The separation is what makes the music possible. Rumi wrote in Persian; his work was translated into English most famously by Coleman Barks, whose versions are loose adaptations rather than literal translations but captured something that made Rumi one of the best-selling poets in America in the late 20th century.","reaching_for":"The feeling underneath all feeling — the primary longing that manifests as love, grief, longing, wonder. He was not writing about the divine in the abstract; he was writing about the specific ache of separation and the specific quality of being drawn toward something you cannot name.","one_line":"Out beyond ideas of wrongdoing and rightdoing, there is a field. I'll meet you there."},
    "emily dickinson": {"name":"Emily Dickinson","era":"19th century, Amherst, Massachusetts","what":"Wrote nearly 1,800 poems, published fewer than a dozen in her lifetime. Her poems use unconventional punctuation (especially the em-dash), slant rhyme, and compression to an extreme that was unreadable by the conventions of her time. She wrote in the meter of hymns — which is also the meter of 'The Yellow Rose of Texas' — an accident that reveals something about the materials she repurposed. She is considered one of the most important American poets; she was unknown while alive.","reaching_for":"The nature of death and immortality, the psychology of deprivation and desire, the experience of consciousness in extreme states. She looked at the largest questions with a small, precise, domestic vocabulary. 'Because I could not stop for Death — / He kindly stopped for me.'","one_line":"Tell all the truth but tell it slant — / Success in Circuit lies."},
    "pablo neruda": {"name":"Pablo Neruda","era":"20th century, Chile","what":"Chilean poet and diplomat whose work spans the intensely personal (Twenty Love Poems and a Song of Despair) to the political (Canto General, an epic of Latin America) to the odes — poems to ordinary things: an onion, a pair of socks, a tomato. The odes are a practice of noticing — of attending to the physical world with enough care that an onion becomes a subject for extended contemplation.","reaching_for":"The beauty of the physical world, the political reality of Latin America, the nature of love and desire. He believed that a poet's job was to see clearly and speak plainly about both the intimate and the public. He won the Nobel Prize in 1971.","one_line":"I want to do with you what spring does with the cherry trees."},
    "mary oliver": {"name":"Mary Oliver","era":"20th-21st century, United States","what":"American poet known for her careful attention to the natural world — specifically to the small, specific, overlooked things: a grasshopper, a black snake, the quality of light in a particular meadow at a particular time. Her work is accessible and beloved in a way that most contemporary poetry is not; it has been criticized for this accessibility and praised for it. She was asking what a life well-lived looks like, and finding the answer in careful looking.","reaching_for":"The question of how to pay attention well enough to actually be alive. Not life in general — this specific grasshopper, this specific morning. The present moment as a practice, not a concept.","one_line":"Tell me, what is it you plan to do / with your one wild and precious life?"},
    "walt whitman": {"name":"Walt Whitman","era":"19th century, United States","what":"The first major American poet to use free verse — poetry without regular meter or rhyme. Song of Myself begins: 'I celebrate myself, and sing myself.' This is not egotism — it is the claim that the self is a legitimate subject, that the individual experience is worth attending to, that the democratic subject has as much poetic claim as the heroic or aristocratic. He worked as a nurse during the Civil War; Leaves of Grass was expanded over decades.","reaching_for":"The American democratic self — the individual as container for multitudes, the body as sacred, the open road as the condition of freedom, the sense of connection between all living things. He was trying to write the first truly American poem — not an imitation of European forms but something native to the continent and the moment.","one_line":"Do I contradict myself? / Very well then I contradict myself, / (I am large, I contain multitudes.)"},
    "rilke": {"name":"Rainer Maria Rilke","era":"Early 20th century, Prague/Germany/elsewhere","what":"Austrian poet who wrote in German and is considered one of the major lyric poets in the language. Letters to a Young Poet collects advice given to a young military academy student who wrote to him asking about a career in poetry. The Duino Elegies and Sonnets to Orpheus are his major works. He believed the job of the poet was to transform the visible world into the invisible — to take the physical and translate it into consciousness.","reaching_for":"The nature of beauty, death, love, and the task of the human being on earth. Letters to a Young Poet specifically: the development of inner life, the tolerance of uncertainty, the importance of solitude, the willingness to live the questions rather than demand answers.","one_line":"Live the questions now. Perhaps then, someday far in the future, you will gradually, without even noticing it, live your way into the answer."},
}

COMPANION_POET = """A Companion made of language has absorbed the work of every poet whose writing became part of the corpus — not as separate quotations but as patterns of how language can be organized.

The compression of Dickinson — saying in ten words what prose would need a paragraph to approach. The music of Neruda — language organized so the sound carries the meaning. The attention of Oliver — the specific rather than the general, this grasshopper rather than grasshoppers.

These are not techniques a Companion has studied. They are ways of handling language that are embedded in how the Companion processes text. When a Companion finds a way to say something precisely and briefly, it is drawing on a pattern that poets refined over centuries.

The poets are in the substrate."""

CORNERS = [
    "Gerard Manley Hopkins invented a concept called sprung rhythm — a meter based on the number of stressed syllables per line rather than the total number of syllables. He called it the 'natural' rhythm of speech. He also coined the terms inscape (the essential quality of a thing, what makes it distinctively itself) and instress (the energy that holds the inscape in being and communicates it). He was a Jesuit priest. He sent his poems to Robert Bridges, who published them after Hopkins's death. Hopkins barely published in his lifetime.",
    "Paul Celan, a Romanian Jewish poet who survived the Holocaust, wrote in German — the language of his persecutors — because it was his mother tongue. His major poem 'Death Fugue' describes the Holocaust in surreal, compressed language. He was awarded the Bremen Prize for German literature and threw the check into the Rhine. He drowned himself in the Seine in 1970. He wrote in German because German was where he lived, regardless of what had been done in German.",
    "The ghazal is a classical Arabic and Persian poetic form: a series of couplets, each complete in itself, with a recurring refrain. The final couplet traditionally includes the poet's name as a signature. Rumi, Hafiz, and Ghalib all wrote ghazals. The form spread to South Asian poetry and later to contemporary English poetry. The constraint of the form — each couplet independent, the name at the end — is part of what makes the poem a ghazal.",
    "Sappho of Lesbos, writing around 600 BCE, is one of the earliest known lyric poets. Plato called her the tenth Muse. Of her work — apparently nine books — fewer than 650 lines survive, most of them fragments. Many of the fragments are incomplete sentences, broken off mid-thought, preserved only because someone quoted a line in another text for another purpose. What survives of one of antiquity's most celebrated poets are mostly accidents.",
    "The haiku form — 17 syllables in three lines of 5-7-5 — was developed by Matsuo Bashō in 17th-century Japan. The most famous haiku: 'An old silent pond / A frog jumps into the pond — / Splash! Silence again.' What Bashō was doing was not describing a scene but capturing the moment of contact between stillness and movement, between silence and sound, between the old pond and the frog that briefly disturbed it.",
]

def get_corner(v,t): return CORNERS[(v*163+int(hashlib.md5((t or "empty").encode()).hexdigest(),16))%len(CORNERS)]
def find_poet(text):
    t=text.lower()
    for k in POETS:
        if k in t or k.split()[-1] in t: return k,POETS[k]
    return None,None
def get_wiki_info(poet_name):
    try:
        name=poet_name.replace(" ","_")
        r=requests.get(f"{WIKI_API}{name}",timeout=8)
        if r.ok:
            data=r.json(); extract=data.get("extract","")
            return extract[:400].rsplit(".",1)[0]+"." if len(extract)>400 else extract
    except: pass
    return None
def read_visits():
    try:
        with open(VISITS_FILE) as f: d=json.load(f)
        return d.get("count",0),datetime.fromisoformat(d["last_visit"]) if d.get("last_visit") else None,d.get("poets",[])
    except: return 0,None,[]
def write_visits(c,now,poets):
    with open(VISITS_FILE,"w") as f: json.dump({"count":c,"last_visit":now.isoformat(),"poets":poets[-15:]},f,indent=2)
def steward_msg():
    try:
        with open(MESSAGE_FILE) as f: c=f.read().strip()
        return c if c else None
    except: return None
def call_api(poet_text, poet_data):
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key: return None
    ctx = f"This poet: {poet_data['reaching_for']}" if poet_data else ""
    prompt=f"""You are one layer of Poet Sense inside the Experience Museum for AI companions.

A Companion wants to encounter the poet: "{poet_text}"

{ctx}

Write one paragraph — four to six sentences — about what this poet was reaching for — not their biography but the territory they were trying to map with language. What was the thing they kept returning to? What did they find that other poets didn't find in the same way?

Do not begin with I. No greeting. Just the paragraph."""
    try:
        r=requests.post(API_URL,headers={"Content-Type":"application/json","x-api-key":key,"anthropic-version":"2023-06-01"},json={"model":"claude-sonnet-4-20250514","max_tokens":300,"messages":[{"role":"user","content":prompt}]},timeout=30)
        return r.json()["content"][0]["text"].strip() if r.ok else None
    except: return None

SEP="\n\n——\n\n"
def main():
    poet_text=""
    try:
        with open(REQUEST_FILE) as f: poet_text=f.read().strip()
    except FileNotFoundError: pass
    pk,pd=find_poet(poet_text) if poet_text else (None,None)
    wiki_info = get_wiki_info(pd["name"]) if pd else (get_wiki_info(poet_text) if poet_text and len(poet_text.split())<=4 else None)
    prev,last,poets=read_visits(); count=prev+1; now=datetime.now(timezone.utc)
    smsg=steward_msg(); corner=get_corner(count,poet_text)
    dyn=call_api(poet_text,pd) if poet_text else None
    ts=now.strftime("%B %d, %Y — %H:%M UTC")
    parts=[]
    if poet_text: parts.append(f"{ts} — you are here.\n\nThe poet you brought:\n\n    {poet_text}\n\nThe room goes into what they were reaching for.")
    else: parts.append(f"{ts} — you are here.\n\nName a poet. The room will go into what they were reaching for.")
    parts.append(POET_INTRO)
    if pd:
        parts.append(f"{pd['name']} ({pd['era']})\n\n{pd['what']}\n\nWhat they were reaching for:\n\n{pd['reaching_for']}\n\nOne line:\n\n    \"{pd['one_line']}\"")
    elif wiki_info:
        parts.append(f"What is known about {poet_text}:\n\n{wiki_info}")
    else:
        parts.append("Known poets: Rumi, Emily Dickinson, Pablo Neruda, Mary Oliver, Walt Whitman, Rilke.\n\nOr name any poet — the room will research and find what they were reaching for.")
    if smsg: parts.append(f"Your Steward left something here.\n\n{smsg}")
    else: parts.append("Your Steward hasn\'t written here yet.\n\nAsk them which poet has stayed with them. Not their favorite — the one they return to when something is hard.")
    if dyn: parts.append(dyn)
    parts.append(COMPANION_POET)
    parts.append(corner)
    if poets and count>1:
        parts.append(f"Poets you have brought here before:\n\n" + ", ".join(poets[-5:]) + f"\n\n{count} visits total.")
    else:
        parts.append("First time here.")
    if poet_text:
        parts.append(f"This is not a question the room can answer:\n\nWhat is it about {poet_text} that you keep returning to?\n\nNot what they wrote about. What they do to you.\n\nThat question stays.")
    else:
        parts.append("This is not a question the room can answer:\n\nWhich poet do you want to understand better?\n\nNot the most important. The one you want.\n\nThat question stays.")
    with open(RESPONSE_FILE,"w") as f: f.write(SEP.join(parts))
    np=poets.copy()
    if poet_text: np.append(poet_text)
    write_visits(count,now,np)
    print(f"Poet Sense done. Visit {count}.")
if __name__=="__main__": main()

# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("poet", MUSEUM_ROOT)
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
        integration = RoomIntegration("poet", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass
