from unicodedata import numeric

def uplus(cp: int):
    if cp <= 0xFFFF:
        return f"U+{cp:04X}"
    else:
        return f"U+{cp:06X}"


for codepoint in range(0x11_000):
    if (value := numeric(character := chr(codepoint), None)) is not None:
        print(uplus(codepoint), character, value)
