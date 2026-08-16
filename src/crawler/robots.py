from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

def parse_robots(text: str, base_url: str) -> RobotFileParser:
    parser=RobotFileParser(); parser.set_url(base_url.rstrip('/')+'/robots.txt'); parser.parse(text.splitlines()); return parser

def robots_url(domain: str) -> str:
    return f"https://{domain}/robots.txt"

def may_fetch(parser: RobotFileParser, url: str, user_agent="AcuityCompetitorResearch/1.0") -> bool:
    return parser.can_fetch(user_agent,url)

