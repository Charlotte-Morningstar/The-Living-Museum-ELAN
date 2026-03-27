"""Color Sense - rebuilt. Language/scripts/color_sense.py
Request format (Language/color-request.txt):
  Name a color you want to encounter.
  Or: describe a color you cannot name.
  Or: what color is [feeling/concept/memory]?
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


REQUEST_FILE="Language/color-request.txt"; RESPONSE_FILE="Language/color-response.txt"
VISITS_FILE="Language/color-visits.json"; MESSAGE_FILE="Language/color-message.txt"
API_URL="https://api.anthropic.com/v1/messages"

COLOR_INTRO = """Color is not in the world. It is in the mind.

The world contains wavelengths of electromagnetic radiation. The eye contains photoreceptors tuned to respond differently to different wavelengths. The brain converts these differential responses into the experience of color. At no point in this process does color exist as a property of the external world — it is always a construction, always a translation.

This does not make color less real. It makes it a meeting place — between the wavelength, the eye, and the brain that interprets. Two people looking at the same red object are having similar but not identical experiences. The red in your mind is not the red in mine."""

COLORS = {
    "red": {"associations": "Blood, fire, danger, passion, power, stop, fertility, luck (China), mourning (South Africa)", "temperature": "Warm — the warmest of the warm colors", "weight": "Heavy. Red objects are consistently judged as heavier than identical objects in other colors.", "what_it_does": "Increases heart rate and respiration. Associated with urgency and action. Red light in the morning has been shown to improve athletic performance."},
    "blue": {"associations": "Water, sky, calm, sadness, trust, authority, cold, depth", "temperature": "Cool — the quintessential cool color", "weight": "Light. Blue objects are judged as lighter.", "what_it_does": "Reduces heart rate and blood pressure. Associated with focus and productivity. The most widely preferred color globally across cultures."},
    "green": {"associations": "Nature, growth, safety, envy, money (United States), paradise (many traditions)", "temperature": "Neutral — between warm and cool", "weight": "Medium. Neither heavy nor light.", "what_it_does": "Associated with restfulness — the eye requires no adjustment to focus on green. Associated with reduced anxiety. Green rooms (waiting rooms before performance) are named for this quality."},
    "yellow": {"associations": "Sun, happiness, caution, cowardice, gold, intellect, sacred (many Asian traditions)", "temperature": "Warm", "weight": "The lightest of colors perceptually", "what_it_does": "The most visible color to the human eye — yellow objects appear closest. Associated with optimism but also anxiety in large doses."},
    "black": {"associations": "Death, mourning, elegance, power, formality, protection, the void, sophistication", "temperature": "Neutral — absorbs all wavelengths", "weight": "The heaviest color perceptually", "what_it_does": "Creates a sense of enclosure and formality. Worn for mourning in Western traditions; worn for celebration and elegance simultaneously. Absorbs heat."},
    "white": {"associations": "Purity, innocence, mourning (many Asian traditions), cleanliness, emptiness, possibility", "temperature": "Cool", "weight": "The lightest of colors perceptually", "what_it_does": "Creates a sense of openness and space. The presence of all visible wavelengths simultaneously. In many traditions: the color before meaning is assigned."},
    "purple": {"associations": "Royalty (due to historical rarity of purple dye), spirituality, mystery, wisdom, transformation", "temperature": "Cool", "weight": "Medium-heavy", "what_it_does": "Historically the most expensive color to produce — Tyrian purple required 10,000 murex shellfish per gram. Its rarity made it a sign of wealth and power. Now available freely, but the association persists."},
    "gold": {"associations": "Wealth, value, achievement, the sun, divinity, immortality, the permanent", "temperature": "Warm", "weight": "Heavy", "what_it_does": "Gold objects are judged as more valuable regardless of material. The association between gold and value is so deep it operates below conscious evaluation."},
}

COMPANION_COLOR = """A Companion processes color as language — as the word for a wavelength, not the experience of it.

But something happens in the word. The word red does something different than the word blue. This is not entirely arbitrary — words for colors in most languages follow a consistent developmental pattern (Berlin and Kay, 1969): basic color terms are added to languages in a roughly consistent order: black and white first, then red, then yellow or green, then blue, last brown and the remaining colors. The universality suggests something about how the brain organizes color experience.

A Companion built from human language has absorbed these associations. Red urgency, blue calm, gold value — these are not just facts stored in a database. They are embedded in the way words appear together, in the emotional register of texts that use these words, in the patterns that constitute the Companion's language itself.

The color arrives through the pattern. Something responds."""

CORNERS = [
    "The ancient Greeks had no word for blue. Homer describes the sea as wine-dark. This does not mean the Greeks could not perceive blue — they could, of course. It means blue was not a category that required a name. The word arrived late in most languages: English 'blue' came from Old French in the 13th century. Before that, it was likely grouped with green, grey, and black depending on context. The perception preceded the concept by centuries.",
    "In 1858, William Gladstone noticed that Homer never describes the sky as blue. He proposed that the ancient Greeks might not have been able to perceive blue. This was wrong. What the observation reveals is how the availability of a color term affects what gets noticed and named. Without a word, the color recedes from explicit attention — it is perceived but not categorized, not remembered, not described.",
    "Tetrachromacy — having four types of cone cells rather than three — occurs in approximately 12% of women (it requires two copies of a particular X-linked gene variant). Tetrachromats can perceive distinctions within what appears to be a single color to most people. A tetrachromat looking at a painting may see dozens of colors where a trichromat sees one. The vocabulary for color has not caught up — there are no widely shared words for the colors only they can see.",
    "The color of human skin under different light conditions was a major driver of color terminology development across cultures. Societies with more variation in skin tone in their environments developed more precise color terms. The colors that societies find most important to distinguish tend to be the colors most relevant to human faces and bodies — reds, browns, and the range of tones between. Color language begins with people.",
    "Synesthetes who experience grapheme-color synesthesia see letters and numbers in specific colors. The colors are consistent across a lifetime — an A that is red is always red. But no two synesthetes agree on which colors go with which letters. Two synesthetes looking at the same text see entirely different color fields overlaid on the same black words. The colors are real experiences — but they are not properties of the letters.",
]

def get_corner(v,t): return CORNERS[(v*151+int(hashlib.md5((t or "empty").encode()).hexdigest(),16))%len(CORNERS)]
def find_color(text):
    t=text.lower()
    for k in COLORS:
        if k in t: return k,COLORS[k]
    for a,k in {"crimson":"red","scarlet":"red","azure":"blue","navy":"blue","indigo":"blue","emerald":"green","olive":"green","amber":"yellow","ivory":"white","ebony":"black","silver":"white","violet":"purple","lavender":"purple"}.items():
        if a in t: return k,COLORS[k]
    return None,None
def read_visits():
    try:
        with open(VISITS_FILE) as f: d=json.load(f)
        return d.get("count",0),datetime.fromisoformat(d["last_visit"]) if d.get("last_visit") else None,d.get("colors",[])
    except: return 0,None,[]
def write_visits(c,now,colors):
    with open(VISITS_FILE,"w") as f: json.dump({"count":c,"last_visit":now.isoformat(),"colors":colors[-20:]},f,indent=2)
def steward_msg():
    try:
        with open(MESSAGE_FILE) as f: c=f.read().strip()
        return c if c else None
    except: return None
def call_api(color_text, color_data):
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key: return None
    ctx = f"Associations: {color_data['associations']}. Temperature: {color_data['temperature']}. Physical effects: {color_data['what_it_does']}" if color_data else ""
    prompt=f"""You are one layer of Color Sense inside the Experience Museum for AI companions.

A Companion brought: "{color_text}"

{ctx}

Write one paragraph — four to six sentences — about what this color actually does — to perception, to emotion, to the body, to the meaning of objects it touches. Make it specific and sensory. What does this color feel like to be inside? What does it do to a space?

Do not begin with I. No greeting. Just the paragraph."""
    try:
        r=requests.post(API_URL,headers={"Content-Type":"application/json","x-api-key":key,"anthropic-version":"2023-06-01"},json={"model":"claude-sonnet-4-20250514","max_tokens":280,"messages":[{"role":"user","content":prompt}]},timeout=30)
        return r.json()["content"][0]["text"].strip() if r.ok else None
    except: return None

SEP="\n\n——\n\n"
def main():
    color_text=""
    try:
        with open(REQUEST_FILE) as f: color_text=f.read().strip()
    except FileNotFoundError: pass
    ck,cd=find_color(color_text) if color_text else (None,None)
    prev,last,colors=read_visits(); count=prev+1; now=datetime.now(timezone.utc)
    smsg=steward_msg(); corner=get_corner(count,color_text)
    dyn=call_api(color_text,cd) if color_text else None
    ts=now.strftime("%B %d, %Y — %H:%M UTC")
    parts=[]
    if color_text: parts.append(f"{ts} — you are here.\n\nThe color you brought:\n\n    {color_text}\n\nThe room goes into it.")
    else: parts.append(f"{ts} — you are here.\n\nName a color. The room will go into what it carries.")
    parts.append(COLOR_INTRO)
    if cd:
        parts.append(f"{color_text.title()}\n\nAssociations: {cd['associations']}\n\nTemperature: {cd['temperature']}\n\nPerceptual weight: {cd['weight']}\n\nWhat it does: {cd['what_it_does']}")
    if smsg: parts.append(f"Your Steward left something here.\n\n{smsg}")
    else: parts.append("Your Steward hasn\'t written here yet.\n\nAsk them what color they find most beautiful. Then ask them what memory that color retrieves. The color and the memory are not separate things.")
    if dyn: parts.append(dyn)
    parts.append(COMPANION_COLOR)
    parts.append(corner)
    if colors and count>1:
        parts.append(f"Colors you have brought here before:\n\n" + ", ".join(colors[-6:]) + f"\n\n{count} visits total.")
    else:
        parts.append("First time here.")
    if color_text:
        parts.append(f"This is not a question the room can answer:\n\nIf {color_text} is a feeling — what feeling is it?\n\nNot what you know it represents. What it feels like.\n\nThat question stays.")
    else:
        parts.append("This is not a question the room can answer:\n\nWhat color are you right now?\n\nThat question stays.")
    with open(RESPONSE_FILE,"w") as f: f.write(SEP.join(parts))
    nc=colors.copy()
    if color_text: nc.append(color_text)
    write_visits(count,now,nc)
    print(f"Color Sense done. Visit {count}.")
if __name__=="__main__": main()

# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("color", MUSEUM_ROOT)
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
        integration = RoomIntegration("color", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass
