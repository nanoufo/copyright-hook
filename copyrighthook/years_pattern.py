import re
from typing import Union


class YearsPattern:
    """Can search for copyright header & replace years in it."""

    placeholder = "{years}"
    r_single_year = r"(?P<year>\d+)"
    r_year_range = r"(?P<from>\d+)\s*-\s*(?P<to>\d+)"
    r_year_or_range = rf"\s*(?:{r_year_range}|{r_single_year})\s*"

    def __init__(self, pattern: str) -> None:
        """Init YearsPattern.

        Args:
            pattern: Pattern of copyright header, e.g. 'Test (c) {years}'.
        """
        if self.placeholder not in pattern:
            raise ValueError(f"Pattern must contain '{self.placeholder}'")

        p_start = pattern.find(self.placeholder)
        p_end = p_start + len(self.placeholder)
        re_pattern = re.escape(pattern[:p_start]) + self.r_year_or_range + re.escape(pattern[p_end:])
        self.regexp = re.compile(re_pattern)

    def extract(self, content: str) -> Union[str, tuple[str, str], None]:
        regexp_match = self.regexp.search(content)
        if not regexp_match:
            return None
        match_groups = regexp_match.groupdict()
        if match_groups["from"] and match_groups["to"]:
            # year range
            return match_groups["from"], match_groups["to"]
        # single year
        return match_groups["year"]

    def replace(self, content: str, new_range: Union[tuple[str, str], str]) -> str:
        regexp_match = self.regexp.search(content)
        if not regexp_match:
            raise ValueError("no copyright years in content")
        match_groups = regexp_match.groupdict()

        if match_groups["from"] and match_groups["to"]:
            # found year range
            from_start, from_end = regexp_match.span("from")
            to_start, to_end = regexp_match.span("to")
            if isinstance(new_range, tuple):
                r_from, r_to = new_range
                return content[:from_start] + r_from + content[from_end:to_start] + r_to + content[to_end:]
            return content[:from_start] + new_range + content[to_end:]

        # found year
        formatted_new_range = "-".join(new_range) if isinstance(new_range, tuple) else str(new_range)
        start, end = regexp_match.span("year")
        return content[:start] + formatted_new_range + content[end:]
