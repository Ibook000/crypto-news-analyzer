import logging
from typing import Optional
try:
    import trafilatura
    _TRAFILATURA_AVAILABLE = True
except Exception:
    _TRAFILATURA_AVAILABLE = False


logger = logging.getLogger(__name__)


def extract_with_trafilatura(url: str) -> Optional[str]:
    if not _TRAFILATURA_AVAILABLE:
        return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            content = trafilatura.extract(
                downloaded,
                favor_precision=False,
                deduplicate=True,
                favor_recall=True,
                include_comments=False,
                include_tables=False,
                include_images=False,
                output_format="txt"
            )
            return content
        return None
    except Exception:
        return None

if __name__ == "__main__":
    content = extract_with_trafilatura("https://cryptoslate.com/the-hubris-in-pretending-bitcoins-story-doesnt-include-79k-this-year/")
    print(content)