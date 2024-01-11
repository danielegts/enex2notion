import json
import re
from typing import List
import logging

from bs4 import Tag
from notion_client import Client
import html

from enex2notion.utils_colors import extract_color
from enex2notion.cli_args import args

logger = logging.getLogger(__name__)


def resolve_string_properties(tags: List[Tag]):
    properties = set()

    tag_map = {
        "b": lambda e: ("b",),
        "i": lambda e: ("i",),
        "u": lambda e: ("_",),
        "s": lambda e: ("s",),
        "span": _resolve_span,
        "a": _resolve_link,
    }

    for tag in tags:
        if tag_map.get(tag.name):
            tag_property = tag_map[tag.name](tag)

            if tag_property:
                if isinstance(tag_property, list):
                    properties.update(tag_property)
                else:
                    properties.add(tag_property)

    return properties


def _resolve_span(tag: Tag):
    properties = []

    style = tag.get("style")
    if not style:
        return []

    color = extract_color(style)
    if color is not None:
        properties.append(("h", color))

    if re.match(r".*font-weight:\s*bold", style):
        properties.append(("b",))

    if re.match(r".*font-style:\s*italic", style):
        properties.append(("i",))

    return properties


def _resolve_link(tag: Tag):
    if tag.get("href"):
        evernote_url = tag.get("href")
        if "evernote://" in tag.get("href"):
            try:
                notion_url = _get_notion_url(evernote_url)

                if notion_url is None:
                    logger.error(f"Notion URL retrieval failed: {evernote_url}")
                    return "a", evernote_url
                else:
                    return "a", notion_url
            except Exception as e:
                logger.error(
                    f"Notion URL retrieval failed: {evernote_url} with"
                    f" exception {e}"
                )
        else:
            return "a", tag["href"]
    return None


def _get_notion_url_from_title(title):
    title = html.unescape(title)
    payload = {
        "query": f'"{title}"',  # we need the exact match
        "filter": {"value": "page", "property": "object"},
    }

    notion = Client(auth=args.notion_api_secret)

    results = notion.request(path="search", method="post", body=payload)[
        "results"
    ]

    for result in results:
        if result["properties"]["Title"]["title"][0]["plain_text"] == title:
            return result["url"]

    return None


def _get_notion_url(evernote_url):
    return _get_notion_url_from_title(_get_evernote_title(evernote_url))


def _get_evernote_title(evernote_url):
    with open(args.links_dict, "r", encoding="utf-8") as fp:
        translation_dict = json.load(fp)

    if evernote_url in translation_dict.keys():
        return translation_dict[evernote_url]
    else:
        evernote_id = evernote_url.split("/")[-2].lower()
        return [
            value
            for key, value in translation_dict.items()
            if evernote_id in key.lower()
        ][0]
