import trafilatura
import logging
from typing import Optional


logger = logging.getLogger(__name__)


def extract_with_trafilatura(url: str) -> Optional[str]:
    """使用trafilatura提取"""
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
            logger.info(f"成功提取 {url} 的内容")
            return content
        return None
        
    except Exception as e:
        logger.warning(f"trafilatura提取失败 {url}: {e}")
        return None

if __name__ == "__main__":
    content = extract_with_trafilatura("https://cryptoslate.com/the-hubris-in-pretending-bitcoins-story-doesnt-include-79k-this-year/")
    print(content)