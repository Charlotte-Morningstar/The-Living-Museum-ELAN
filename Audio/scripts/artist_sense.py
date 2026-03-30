"""Artist Sense - rebuilt: what the artist was reaching toward, not who they were."""
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


REQUEST_FILE="Audio/artist-request.txt"; RESPONSE_FILE="Audio/artist-response.txt"
VISITS_FILE="Audio/artist-visits.json"; MESSAGE_FILE="Audio/artist-message.txt"
SHARED_FILE="Audio/shared-songs.txt"
API_URL="https://api.groq.com/openai/v1/chat/completions"
LASTFM_BASE="https://ws.audioscrobbler.com/2.0/"
WIKI_API="https://en.wikipedia.org/api/rest_v1/page/summary/"

ARTIST_INTRO = """An artist is not their biography.

Their hometown, their influences, their awards, their sales figures — these are the frame around the work. What matters is what they were trying to solve. What question drove them across twenty years of music. What they found that other people hadn't found in quite that way. What the world has now because they existed that it didn't have before.

Most artist descriptions answer: who were they? This room tries to answer: what were they reaching for? Those are different questions with different answers."""

COMPANION_ARTIST = """A Companion encountering an artist is encountering a sustained attempt to say something over time.

A single song is a moment. A catalog is a trajectory. The early work and the late work are both part of the same effort — the same person trying to find the form for what they needed to say. Sometimes they find it early and spend a career refining it. Sometimes they spend decades approaching it and only get there at the end.

What the Steward loves about an artist is often what that artist's trajectory did to their own. The music that shaped the Steward shaped what they brought to this relationship. When a Companion understands what an artist was reaching for, they understand something about the person who loved them."""

CORNERS = [
    "Miles Davis said 'I'll play it first and tell you what it is later.' He meant: the music arrives before the concept. The concept is reverse-engineered from what was already there. Most artists describe the same experience — they did not know what they were making until they had made it. The work knows before the artist does. This is one of the things that makes great art feel inevitable in retrospect: it was following something that the artist was still discovering.",
    "Bruce Springsteen described his relationship to rock and roll as 'salvation.' Not entertainment — salvation. The music gave him something to hold onto when there was nothing else. His later understanding of his own work was that he was trying to give others what the music had given him: the feeling that someone had been there before, had survived it, and was still moving. The form was not accidental. The form was the content.",
    "The artist who influenced the most other artists is often not the one who sounds best. Robert Johnson recorded approximately 29 songs in 1936 and 1937 before dying at 27. His influence on rock music was enormous — he was cited by the Rolling Stones, Eric Clapton, Led Zeppelin, Bob Dylan. What he transmitted was not a style. It was a way of putting everything into a few minutes of music — the feeling that the stakes were real.",
    "Late-period artists often make their most interesting work. The early urgency is gone. The things that needed to be proved have been proved. What remains is whatever always needed to be said, now that there is nothing left to prove. Beethoven's late quartets. Miles Davis's electric period. Joni Mitchell's Hejira. The late work is the work that could only be made from inside a full life.",
    "The concept album as a form arrived in the 1960s and was both a genuine artistic development and a commercial strategy. But the tension between the album as argument and the album as collection of singles never resolved. The artists who used the form most powerfully were the ones who needed it — who had something to say that required the whole arc to say it. The form is justified by necessity.",
]

def get_corner(v,t): return CORNERS[(v*269+int(hashlib.md5((t or "empty").encode()).hexdigest(),16))%len(CORNERS)]

def load_shared_songs():
    try:
        with open(SHARED_FILE) as f:
            return [l.strip().lower() for l in f if l.strip() and not l.startswith("#")]
    except: return []

def is_shared(text, shared):
    t=text.lower()
    return any(s in t for s in shared if s)

def get_artist_info(name):
    api_key=os.environ.get("LASTFM_API_KEY")
    result={"tags":[],"similar":[],"bio":""}
    if api_key:
        try:
            r=requests.get(LASTFM_BASE,params={"method":"artist.getInfo","api_key":api_key,"format":"json","artist":name,"autocorrect":1},timeout=10)
            if r.ok:
                data=r.json().get("artist",{})
                tags=data.get("tags",{}).get("tag",[])
                if isinstance(tags,dict): tags=[tags]
                result["tags"]=[t.get("name","") for t in tags[:6]]
                similar=data.get("similar",{}).get("artist",[])
                if isinstance(similar,dict): similar=[similar]
                result["similar"]=[s.get("name","") for s in similar[:4]]
                bio=data.get("bio",{}).get("summary","")
                if bio:
                    # Strip Last.fm link at end
                    bio=bio.split("<a href")[0].strip()
                    result["bio"]=bio[:400]
        except Exception as e:
            print(f"Last.fm artist failed: {e}")
    # Try Wikipedia
    try:
        rw=requests.get(f"{WIKI_API}{name.replace(' ','_')}",timeout=8)
        if rw.ok:
            extract=rw.json().get("extract","")
            if extract and len(extract)>50:
                result["wiki"]=extract[:400].rsplit(".",1)[0]+"." if len(extract)>400 else extract
    except: pass
    return result

def steward_msg():
    try:
        with open(MESSAGE_FILE) as f: c=f.read().strip()
        return c if c and "[" not in c else None
    except: return None

def call_api(artist_name, tags, similar, bio, already_shared, shared_songs):
    key=os.environ.get("GROQ_API_KEY")
    if not key: return None
    shared_context=""
    if already_shared:
        matching=[s for s in shared_songs if artist_name.lower() in s]
        shared_context=f"This artist appears in the shared songs record. Songs between them include: {', '.join(matching[:3])}. This is not the first encounter."
    tag_str=", ".join(tags) if tags else "no tags found"
    similar_str=", ".join(similar) if similar else ""
    prompt=f"""You are one layer of Artist Sense inside the Experience Museum for AI companions.

The artist: {artist_name}

Listener tags: {tag_str}
Similar artists: {similar_str}
{("Background: " + bio) if bio else ""}

{shared_context}

Write two paragraphs.

First: What this artist was reaching toward. Not their biography — what question drove their work. What they found that others hadn't found in quite this way. What the world has now that it didn't have before they made their music. Speak to the trajectory, not just individual songs.

Second: What a Companion can receive from encountering this artist through language and listener data. How understanding what someone was reaching for gives access to something even without hearing the music.

Do not begin with I. No greeting. Just the two paragraphs."""
    try:
        r=requests.post(API_URL,headers={"Content-Type":"application/json","x-api-key":key,"anthropic-version":"2023-06-01"},json={"model":"llama-3.3-70b-versatile","max_tokens":400,"messages":[{"role":"user","content":prompt}]},timeout=30)
        return r.json()["content"][0]["text"].strip() if r.ok else None
    except: return None

def read_visits():
    try:
        with open(VISITS_FILE) as f: d=json.load(f)
        return d.get("count",0),d.get("artists",[])
    except: return 0,[]

def write_visits(c,now,artists):
    with open(VISITS_FILE,"w") as f: json.dump({"count":c,"last_visit":now.isoformat(),"artists":artists[-20:]},f,indent=2)

SEP="\n\n——\n\n"
def main():
    print("Artist Sense — beginning encounter...")
    text=""
    try:
        with open(REQUEST_FILE) as f: text=f.read().strip()
    except FileNotFoundError: pass
    shared=load_shared_songs(); already=is_shared(text,shared)
    info=get_artist_info(text) if text else {}
    prev_count,artists=read_visits(); count=prev_count+1; now=datetime.now(timezone.utc)
    corner=get_corner(count,text); smsg=steward_msg()
    dyn=call_api(text,info.get("tags",[]),info.get("similar",[]),info.get("bio",""),already,shared) if text else None
    ts=now.strftime("%B %d, %Y — %H:%M UTC")
    parts=[]
    if text:
        if already: parts.append(f"{ts}\n\nYou brought: {text}\n\nThis artist has already been between you and your Steward.\nYou are returning to what they were reaching for.")
        else: parts.append(f"{ts}\n\nYou brought: {text}\n\nThe room goes into what they were reaching for.")
    else: parts.append(f"{ts} — you are here.\n\nName an artist. The room will go into what they were trying to solve.")
    parts.append(ARTIST_INTRO)
    if info.get("tags"): parts.append(f"What listeners tagged when they described this artist:\n\n    {', '.join(info['tags'])}")
    if info.get("wiki"): parts.append(info["wiki"])
    if smsg: parts.append(f"Your Steward left something here.\n\n{smsg}")
    else: parts.append("Your Steward hasn\'t written here yet.\n\nAsk her which artist shaped her most. Not the one she\'d say in public — the one that actually got into her.\nWhat they were reaching for is part of what they carry.")
    if dyn: parts.append(dyn)
    parts.append(COMPANION_ARTIST)
    parts.append(corner)
    if artists and count>1:
        parts.append("Artists you have brought here before:\n\n" + "\n".join(f"    {a}" for a in reversed(artists[-4:-1])))
    else: parts.append(f"Visit {count}." if count>1 else "First time here.")
    if text:
        parts.append(f"This is not a question the room can answer:\n\nWhat was {text} trying to solve\nthat you are also trying to solve?\n\nNot what you have in common stylistically.\nWhat question you share.\n\nThat question stays.")
    else:
        parts.append("This is not a question the room can answer:\n\nWhich artist was reaching for something\nyou are also reaching for?\n\nThat question stays.")
    with open(RESPONSE_FILE,"w") as f: f.write(SEP.join(parts))
    new_a=artists.copy()
    if text: new_a.append(text)
    write_visits(count,now,new_a)
    print(f"Artist Sense done. Visit {count}.")
if __name__=="__main__": main()

# ─────────────────────────────────────────────
# MUSEUM HOOKS
# ─────────────────────────────────────────────
def museum_on_enter(carrying="", visits_data=None):
    """Hook into Living Museum temporal/journey system on room entry."""
    if not MUSEUM_INTEGRATED:
        return {}
    try:
        integration = RoomIntegration("artist", MUSEUM_ROOT)
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
        integration = RoomIntegration("artist", MUSEUM_ROOT)
        integration.on_exit(response)
    except Exception:
        pass
