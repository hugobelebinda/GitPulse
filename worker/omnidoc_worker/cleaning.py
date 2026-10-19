import pandas as pd


def clean_text(raw_text: str) -> str:
    """Normalize extracted lines with a Pandas pipeline."""
    frame = pd.DataFrame({"line": (raw_text or "").splitlines()})
    if frame.empty:
        return ""

    frame["line"] = frame["line"].fillna("").astype(str)
    frame["line"] = frame["line"].str.replace("\u00a0", " ", regex=False)
    frame["line"] = frame["line"].str.replace(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", regex=True)
    frame["line"] = frame["line"].str.replace(r"[ \t]+", " ", regex=True).str.strip()
    frame = frame.loc[frame["line"] != ""].copy()
    if frame.empty:
        return ""

    frame = frame.loc[frame["line"].ne(frame["line"].shift())]
    return "\n".join(frame["line"].tolist())
