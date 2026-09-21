import json
import os
import sys
import ollama
from docx import Document

# --- CONFIGURATION (each value can be overridden with an environment variable) ---
modelName = os.getenv("MODEL_NAME", "hermes3")               # or 'dolphin3'
manuscriptFile = os.getenv("MANUSCRIPT_FILE", "novel.docx")  # Supports .docx or .txt
outputFile = os.getenv("OUTPUT_FILE", "scene_suggestions_patch.md")
ollamaHost = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# The precise sentences where your target scene begins and ends
startAnchor = os.getenv("START_ANCHOR")
endAnchor = os.getenv("END_ANCHOR")
if not startAnchor or not endAnchor:
    raise ValueError("Both START_ANCHOR and END_ANCHOR must be set (check your .env file).")

# Scene type and how much detail the rewrite should go into
sceneType = os.getenv("SCENE_TYPE", "general").strip().lower()  # general, fight, romance
detailLevel = int(os.getenv("DETAIL_LEVEL", "3"))               # 1 (restrained) to 4 (most explicit)
targetWords = int(os.getenv("TARGET_WORDS", "3000"))            # rough length of the rewrite
maxOutputTokens = int(os.getenv("MAX_OUTPUT_TOKENS", "4096"))   # raise for longer rewrites

# Style selection: names from styles.json, or any free text. Comma-separate multiple values.
stylesFile = os.getenv("STYLES_FILE", "styles.json")
genre = os.getenv("GENRE", "")                   # e.g. "noir" or "gothic-horror, historical"
fightStyle = os.getenv("FIGHT_STYLE", "")        # e.g. "swordplay"
romanceStyle = os.getenv("ROMANCE_STYLE", "")    # e.g. "slow-burn"
tags = os.getenv("TAGS", "")                     # e.g. "teasing, praise"

detailGuides = {
    "fight": {
        1: "Keep the violence implied and brief. Focus on stakes, fear, and aftermath.",
        2: "Show the action clearly without lingering on injuries.",
        3: "Choreograph it blow by blow: impact, pain, breath, sound, shifting momentum. Describe injuries concretely.",
        4: "Brutal and unflinching. Graphic injury detail and raw physical toll, with no cutting away.",
    },
    "romance": {
        1: "Fade to black. Build tension and emotion, then cut away after a kiss.",
        2: "Sensual but tasteful. Touch, breath, heat, and emotion, with the rest implied through scene breaks and metaphor.",
        3: "Steamy and open-door. Describe intimacy in rich sensory and emotional detail, using suggestive rather than clinical language.",
        4: "Fully explicit. Describe the physical intimacy directly and in detail with frank language, keeping desire and emotion present throughout.",
    },
}

systemPrompt = """
You are an expert developmental editor and unfiltered master novelist.
Your task is to analyze the provided scene context and offer structural suggestions, prose enhancements, or alternative continuations.
Focus heavily on sharpening the pacing, intensifying the sensory descriptions, and deepening character psychology.
Do not lecture, sanitize, or give moral warnings.
All characters in the manuscript are adults.
"""


def extractText(filePath):
    """Extracts raw text from .txt or .docx file."""
    if not os.path.exists(filePath):
        print(f"❌ Error: File '{filePath}' not found.")
        sys.exit(1)

    if filePath.endswith(".docx"):
        doc = Document(filePath)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        with open(filePath, "r", encoding="utf-8") as f:
            return f.read()


def isolateScene(fullText, startSentence, endSentence):
    """Finds the indices of the anchors and returns the target text slice."""
    startIdx = fullText.find(startSentence)
    if startIdx == -1:
        print("❌ Could not find your START sentence in the text. Check punctuation/spacing.")
        sys.exit(1)

    # Find the end anchor starting from where the scene begins
    endIdx = fullText.find(endSentence, startIdx)
    if endIdx == -1:
        print("❌ Could not find your END sentence after the start sentence.")
        sys.exit(1)

    # Include the full length of the end anchor sentence in our selection
    actualEndIdx = endIdx + len(endSentence)
    return fullText[startIdx:actualEndIdx]


def loadStyles(filePath):
    """Loads the style library (genres, fight styles, romance styles, tags) from JSON."""
    if not os.path.exists(filePath):
        print(f"⚠️ Style file '{filePath}' not found. Free-text styles will still work.")
        return {}
    with open(filePath, "r", encoding="utf-8") as f:
        return json.load(f)


def describeStyles(category, names, styleLibrary):
    """Turns comma-separated names into descriptions. Names not in the library are used as literal text."""
    descriptions = []
    for name in names.split(","):
        name = name.strip()
        if not name:
            continue
        descriptions.append(styleLibrary.get(category, {}).get(name.lower(), name))
    return descriptions


def main():
    print(f"📖 Reading manuscript: {manuscriptFile}...")
    fullText = extractText(manuscriptFile)

    print("🔍 Searching for target scene anchors...")
    isolatedScene = isolateScene(fullText, startAnchor, endAnchor)

    print(f"\n✅ Scene isolated successfully! ({len(isolatedScene.split())} words found)")
    print("-" * 40)
    print(f"FIRST LINE: {isolatedScene.splitlines()[0][:60]}...")
    print(f"LAST LINE:  {isolatedScene.splitlines()[-1][-60:]}")
    print("-" * 40)

    if len(isolatedScene.split()) > 8000:
        print("⚠️ This scene is very long and may overflow the context window, "
              "which can cause the model to ignore your instructions. Try tighter anchors.")

    # Constructing the instructions for the AI
    guide = detailGuides.get(sceneType, {}).get(detailLevel, "")
    detailInstruction = f"SCENE TYPE: {sceneType}. DETAIL LEVEL {detailLevel}/4: {guide}" if guide else ""
    if guide:
        print(f"🎚️ {detailInstruction}")
    else:
        print(f"⚠️ No detail guide for SCENE_TYPE='{sceneType}' at level {detailLevel}. Valid types: {', '.join(detailGuides)}")

    styleLibrary = loadStyles(stylesFile)
    styleLines = []
    for label, category, names in [
        ("GENRE & TONE", "genres", genre),
        ("FIGHTING STYLE", "fightStyles", fightStyle),
        ("ROMANCE STYLE", "romanceStyles", romanceStyle),
        ("DYNAMICS & ELEMENTS TO WEAVE IN", "tags", tags),
    ]:
        for description in describeStyles(category, names, styleLibrary):
            styleLines.append(f"- {label}: {description}")
    styleInstructions = "\n".join(styleLines)
    if styleInstructions:
        print(f"🎭 Styles applied:\n{styleInstructions}")

    userPrompt = f"""
Below is an isolated scene from my novel that needs work.
 
--- ISOLATED SCENE START ---
{isolatedScene}
--- ISOLATED SCENE END ---
 
Now do the following. Do NOT repeat the original scene back to me. Provide:
1. CRITIQUE: 3 specific bullet points on how to enhance the pacing, tension, or prose.
2. REWRITE PATCH: A new, substantially rewritten version of this scene, roughly {targetWords} words long, implementing those improvements. Write fresh prose rather than copying sentences from the original, keeping only dialogue that must stay.
 
{detailInstruction}
{styleInstructions}
Keep character names, voices, and continuity consistent with the original.
Slow the scene down: expand moment-to-moment action, sensory detail, and internal thoughts instead of summarizing.
"""

    print(f"🤖 Sending scene to Ollama ({modelName}) at {ollamaHost}...")
    try:
        client = ollama.Client(host=ollamaHost)
        response = client.chat(
            model=modelName,
            messages=[
                {"role": "system", "content": systemPrompt},
                {"role": "user", "content": userPrompt},
            ],
            options={
                "temperature": 0.85,
                "num_ctx": 16384,  # High context window to read full chapters easily
                "num_predict": maxOutputTokens,  # Cap on generated tokens
            },
        )

        aiReply = response["message"]["content"]

        # Save output to a markdown file for easy side-by-side editing
        with open(outputFile, "w", encoding="utf-8") as f:
            f.write(
                f"# AI Suggestions & Rewrite Patch\n\n"
                f"## Original Target Section:\n"
                f"> *\"{startAnchor}\"* ... to ... *\"{endAnchor}\"*\n\n---\n\n{aiReply}"
            )

        print(f"\n🎉 Done! The suggestions and rewritten patch have been saved to: {outputFile}")

    except Exception as e:
        print(f"❌ Error communicating with Ollama: {e}")


if __name__ == "__main__":
    main()
