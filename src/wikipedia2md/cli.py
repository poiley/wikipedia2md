#!/usr/bin/env python3

import json
import sys
import re
import argparse
import wikipedia
from wikipedia import WikipediaPage
from bs4 import BeautifulSoup
import logging
import click
from pathlib import Path
from typing import Optional
import os
import importlib.resources
from datetime import datetime
from urllib.parse import urljoin

ACCEPTED_URL_PREFIXES = ('http://wikipedia.org', 'https://wikipedia.org', 
                         'http://www.wikipedia.org', 'https://www.wikipedia.org')

def get_package_data(filename: str) -> str:
    """Get the contents of a data file from the package."""
    try:
        # Try importlib.resources first (Python 3.7+)
        with importlib.resources.open_text("wikipedia2md", filename) as f:
            return f.read()
    except Exception:
        # Fallback to file-based loading
        package_dir = os.path.dirname(__file__)
        file_path = os.path.join(package_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    RESET = '\033[0m'


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds color to log messages"""
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[31m\033[1m',  # Bold Red
    }
    RESET = '\033[0m'

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)

    def should_use_colors(self):
        """Determine if colors should be used"""
        # First check environment variable
        if os.environ.get('FORCE_COLOR', '0') == '1':
            return True
        # Then try Click's context
        try:
            ctx = click.get_current_context()
            return not ctx.color is False
        except RuntimeError:
            # No Click context available
            return False

    def format(self, record):
        # Save original values
        original_message = record.msg
        
        use_colors = self.should_use_colors()
        if use_colors:
            # Add color codes
            color = self.COLORS.get(record.levelname, '')
            if color:
                if record.levelname in ['ERROR', 'CRITICAL']:
                    record.msg = f"{color}{record.msg}{self.RESET}"
        
        # Format without levelname
        result = record.msg
        
        # Restore original values
        record.msg = original_message
        
        return result


def walk_dom(soup):
    """
    Recursively traverse DOM in document order, yielding relevant elements.
    """
    processed_elements = set()  # Track elements we've already yielded
    relevant_elements = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "img", "ul", "ol", "li"}
    
    def is_valid_element(element):
        """Helper to check if an element is valid for traversal"""
        return element and hasattr(element, 'name') and element.name
    
    def _walk(element):
        if not is_valid_element(element):
            return

        element_name = element.name
        logging.debug(f"TRAVERSE: Entering element <{element_name}> with {len(list(element.children))} children")

        # Skip Wikidata edit images early
        if element_name == "img":
            src = element.get("src", "")
            if "edit-ltr-progressive" in src:
                logging.debug("TRAVERSE: Skipping Wikidata edit image")
                return

        # First traverse into all children
        for child in element.children:
            if is_valid_element(child):
                logging.debug(f"TRAVERSE: Moving to child <{child.name}>")
                yield from _walk(child)

        # Then yield this element if it's one we care about and haven't processed
        if element_name in relevant_elements and element not in processed_elements:
            logging.debug(f"TRAVERSE: Yielding element <{element_name}>")
            processed_elements.add(element)
            yield element
        else:
            logging.debug(f"TRAVERSE: Skipping element <{element_name}> (already processed or not interesting)")

    # Start traversal from the soup's contents
    for element in soup.contents:
        if is_valid_element(element):
            logging.debug(f"TRAVERSE: Starting traversal from root element <{element.name}>")
            yield from _walk(element)


REFERENCE_PATTERN = re.compile(r'\[\d+\](?:\[\d+\])*$')
WHITESPACE_PATTERN = re.compile(r'\s+')
SENTENCE_BOUNDARY_PATTERN = re.compile(r'([.!?])\s*([A-Z])')
BRACKETS_AND_WHITESPACE_PATTERN = re.compile(r'\[.*?\]|\s+')

def clean_text_value(text):
    """Helper to clean and normalize text values"""
    # Remove reference brackets and extra whitespace in one pass
    return BRACKETS_AND_WHITESPACE_PATTERN.sub(
        lambda m: ' ' if m.group(0).isspace() else '', 
        text.strip()
    )

def infobox_to_markdown(infobox):
    """Convert Wikipedia infobox to markdown table format"""
    markdown_lines = []
    
    # Get and process the image if present
    image_cell = infobox.find('td', class_='infobox-image')
    if image_cell and (img := image_cell.find('img')):
        src = img.get('src', '')
        if src.startswith('//'):
            src = 'https:' + src
        alt = img.get('alt', 'Image')
        markdown_lines.extend([f"![{alt}]({src})", ""])

    # Start the table with headers
    markdown_lines.extend(["| Attribute | Value |", "|-----------|--------|"])

    def process_data_content(data):
        """Process data cell content into clean, comma-separated values"""
        # Remove unwanted elements first
        for element in data.find_all(['style', 'sup', 'span']):
            element.decompose()
        
        # Process lists first if present
        if data.find('ul') or data.find('div', class_='hlist'):
            items = data.find_all('li')
            if items:
                return ', '.join(filter(None, (clean_text_value(item.get_text()) for item in items)))
        
        # Process regular content
        parts = []
        current_text = []
        
        def flush_current_text():
            if current_text:
                text = clean_text_value(''.join(current_text))
                if text:
                    parts.append(text)
                current_text.clear()
        
        for elem in data.children:
            if not elem or not str(elem).strip():
                continue
                
            if elem.name == 'a':
                flush_current_text()
                if text := clean_text_value(elem.get_text()):
                    parts.append(text)
            elif elem.name == 'br':
                flush_current_text()
            elif elem.string:
                text = elem.string.strip()
                # If it's just a comma or whitespace, flush current text and add separator
                if text in [',', ', ']:
                    flush_current_text()
                elif text:  # Otherwise add to current text
                    current_text.append(text)
        
        # Add any remaining text
        flush_current_text()
        
        # Join all parts, ensuring no double commas
        result = []
        for part in parts:
            part = part.strip(' ,')
            if part:
                result.append(part)
        
        return ', '.join(result)

    # Process each row
    for row in infobox.find_all('tr'):
        # Skip the title row and image-only rows
        if row.find('th', class_='infobox-above') or (row.find('td', class_='infobox-image') and not row.find('th')):
            continue
            
        # Get label and data
        if (label := row.find('th', class_='infobox-label')) and (data := row.find('td', class_='infobox-data')):
            label_text = label.get_text(strip=True).replace('\n', ' ')
            if data_text := process_data_content(data):
                # Escape pipe characters in the data text
                data_text = data_text.replace('|', '\\|')
                markdown_lines.append(f"| {label_text} | {data_text} |")

    return '\n'.join(markdown_lines)


def make_markdown_from_page(page, obsidian=False, no_links=False):
    html = page.html()
    soup = BeautifulSoup(html, "html.parser")
    
    logging.debug("=" * 80)
    logging.debug("Starting page processing")
    logging.debug(f"Page title: {page.title}")
    logging.debug(f"HTML length: {len(html)}")
    logging.debug("=" * 80)

    markdown_lines = []
    skipping_section = False
    skip_level = None
    forbidden_sections = frozenset(["see also", "references", "external links", "contents", "notes", "bibliography", "citations"])
    list_items = []
    heading_elements = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

    def get_heading_level(element_name):
        """Get heading level from element name, returns None if not a heading"""
        return int(element_name[-1]) if element_name in heading_elements else None

    # Add frontmatter if Obsidian mode is enabled
    if obsidian:
        # Extract categories from the page using the Wikipedia API
        categories = []
        try:
            # Get categories from the Wikipedia API
            categories = [cat.split('Category:')[-1] for cat in page.categories
                        if not cat.startswith('Category:Help:') and
                           not any(x in cat.lower() for x in ['hidden', 'cs1', 'webarchive', 'articles'])]
        except Exception as e:
            logging.warning(f"Failed to get categories: {e}")
            categories = []

        # Generate Wikipedia URL
        wiki_url = f"https://en.wikipedia.org/wiki/{page.title.replace(' ', '_')}"

        markdown_lines.extend([
            "---",
            f'title: "{page.title}"',
            f'wikipedia_url: "{wiki_url}"',
            f'date_converted: "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"',
            "tags:",
            *[f"  - {cat}" for cat in categories[:10]],  # Limit to top 10 categories
            "---",
            ""
        ])

    # Add page title first
    markdown_lines.extend([f"# {page.title}", ""])

    # Process infobox if present
    infobox = soup.find('table', class_='infobox')
    if infobox:
        logging.debug("Found infobox, converting to markdown")
        infobox_md = infobox_to_markdown(infobox)
        if infobox_md:
            markdown_lines.extend([infobox_md, ""])
        infobox.decompose()
        logging.debug("Removed infobox from DOM")

    def link_to_markdown(a_tag):
        text = a_tag.get_text(strip=True)
        if no_links:  # If no_links is True, just return the text
            return text
        
        if href := a_tag.get("href", ""):
            if href.startswith("http"):
                return f"[{text}]({href})"
            elif href.startswith("/wiki/"):
                return f"[{text}](https://en.wikipedia.org{href})"
        return text

    def image_to_markdown(img_tag):
        alt_text = img_tag.get("alt", "").strip() or "Image"
        if src := img_tag.get("src", ""):
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = "https://en.wikipedia.org" + src
            return f"![{alt_text}]({src})"
        return ""

    def process_node_text(node):
        """Helper function to process text from nodes with potential links"""
        parts = []
        for child in node.children:
            if child.name == "a":
                if text := link_to_markdown(child):
                    logging.debug(f"  Processing link: {text}")
                    parts.append(text)
            elif child.name == "sup":
                logging.debug("  Skipping reference number (sup tag)")
                continue
            elif child.string and (text := child.string.strip()):
                logging.debug(f"  Processing text: {text}")
                parts.append(text)
        return ' '.join(filter(None, parts))

    def process_paragraph_text(node):
        """Process paragraph text while preserving whitespace"""
        parts = []
        last_was_text = False
        needs_space = False
        
        for child in node.children:
            if child.name == "a":
                if text := link_to_markdown(child):
                    logging.debug(f"  Link: Found '{text}'")
                    if needs_space:
                        parts.append(' ')
                    parts.append(text)
                    last_was_text = False
                    needs_space = True
            elif child.name == "sup":
                logging.debug("  Skipping reference number (sup tag)")
                continue
            elif child.name == "img":
                if text := image_to_markdown(child):
                    logging.debug(f"  Image in paragraph: {text}")
                    if needs_space:
                        parts.append(' ')
                    parts.append(text)
                    last_was_text = False
                    needs_space = True
            elif child.string and (text := child.string):
                stripped = text.strip()
                if stripped:
                    logging.debug(f"  Text: '{text}'")
                    if needs_space and not text.startswith((' ', '\n')):
                        parts.append(' ')
                    parts.append(text)
                    last_was_text = True
                    needs_space = not text.endswith((' ', '\n'))

        return ''.join(parts).strip()

    def should_skip_element(element):
        """Helper to determine if an element should be skipped"""
        if element.get('role') == 'navigation':
            return True
        if 'toc' in (element.get('class', []) or []):
            return True
        if 'navigation-box' in (element.get('class', []) or []):
            return True
        return False

    # Process each node
    for node in walk_dom(soup):
        element_name = node.name

        # Check if we should exit skip mode for sections
        if skipping_section and (level := get_heading_level(element_name)):
            if level <= skip_level:
                skipping_section = False
                skip_level = None
                logging.debug(f"Exiting skip mode at heading level {level}")

        # Skip if we're in a forbidden section
        if skipping_section:
            continue

        # Skip navigation/TOC elements
        if should_skip_element(node):
            continue

        # Process different node types
        if element_name in heading_elements:
            # Check if this heading starts a forbidden section
            heading_text = process_node_text(node).lower()
            if heading_text in forbidden_sections:
                skipping_section = True
                skip_level = get_heading_level(element_name)
                logging.debug(f"Entering skip mode at heading '{heading_text}' (level {skip_level})")
                continue

            # Handle pending list items before heading
            if list_items:
                markdown_lines.extend(["\n".join(list_items), ""])
                list_items = []

            # Add the heading
            level = get_heading_level(element_name)
            heading_text = process_node_text(node)
            markdown_lines.extend(["", f"{'#' * level} {heading_text}", ""])
            logging.debug(f"Added heading: {heading_text} (level {level})")

        elif element_name == "img":
            # Handle pending list items before image
            if list_items:
                markdown_lines.extend(["\n".join(list_items), ""])
                list_items = []

            if img_text := image_to_markdown(node):
                markdown_lines.extend(["", img_text, ""])
                logging.debug(f"Added image: {img_text}")

        elif element_name == "li" and not skipping_section:
            if item_text := process_node_text(node):
                # Remove reference numbers
                item_text = re.sub(REFERENCE_PATTERN, '', item_text).strip()
                list_items.append(f"- {item_text}")
                logging.debug(f"LIST ITEM: Added: '- {item_text}'")

        elif element_name == "p":
            # Handle pending list items before paragraph
            if list_items:
                markdown_lines.extend(["\n".join(list_items), ""])
                list_items = []

            if skipping_section:
                continue
                
            if paragraph_text := process_paragraph_text(node):
                # Clean up multiple spaces while preserving sentence boundaries
                paragraph_text = re.sub(WHITESPACE_PATTERN, ' ', paragraph_text)
                paragraph_text = re.sub(SENTENCE_BOUNDARY_PATTERN, r'\1 \2', paragraph_text)
                markdown_lines.append(paragraph_text)
                logging.debug(f"Added paragraph: {paragraph_text[:50]}...")

    # Handle any remaining list items at the end
    if list_items:
        markdown_lines.extend(["\n".join(list_items), ""])

    # Clean up multiple empty lines
    while markdown_lines and not markdown_lines[-1]:
        markdown_lines.pop()

    # Join lines and clean up multiple empty lines
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(markdown_lines))


class WikiPageNotFoundError(Exception):
    """Raised when a Wikipedia page cannot be found"""
    pass

def fetch_wiki_page(query: str, lang: str = "en") -> "WikipediaPage":
    """
    Attempt to retrieve a Wikipedia page for the given query.
    If direct lookup fails, do a full-text search and prompt the user for up to 5 options.
    
    Args:
        query: The search query or Wikipedia URL
        lang: The language code for Wikipedia (default: "en")
        
    Raises:
        WikiPageNotFoundError: If no matching page is found
        wikipedia.PageError: If the page doesn't exist
        wikipedia.DisambiguationError: If multiple matches are found
        ValueError: If language code is invalid
    """
    global ACCEPTED_URL_PREFIXES
    ACCEPTED_URL_PREFIXES += (f"http://{lang}.wikipedia.org", f"https://{lang}.wikipedia.org")
    
    # Load and validate language code
    iso639_data = json.loads(get_package_data("iso-639.json"))
    iso639_langs = {item['code']: item['name'] for item in iso639_data}
    
    if lang not in iso639_langs:
        raise ValueError(f"Invalid language code: {lang}")

    wikipedia.set_lang(lang)
    logging.info(f"🔍 Searching for {Colors.CYAN}'{query}'{Colors.RESET} in {Colors.CYAN}{iso639_langs[lang].title()}{Colors.RESET}")

    # Check if query is a Wikipedia URL
    if query.startswith(ACCEPTED_URL_PREFIXES):
        # Extract title from URL
        title = query.split('/wiki/')[-1].replace('_', ' ')
        page = wikipedia.page(title, auto_suggest=False)
        logging.info(f"📰 Found article from URL: {Colors.CYAN}'{page.title}'{Colors.RESET} - {Colors.GREEN}{page.url}{Colors.RESET}")
        return page
        
    try:
        page = wikipedia.page(query, auto_suggest=False)
        logging.info(f"📰 Found article: {Colors.CYAN}'{page.title}'{Colors.RESET} - {Colors.GREEN}{page.url}{Colors.RESET}")
        return page
    except (wikipedia.PageError, wikipedia.DisambiguationError) as e:
        logging.warning(f"⚠️ Direct match for '{query}' failed. Attempting a fallback search.")
        
        # Fallback if direct match fails
        search_results = wikipedia.search(query, results=5)
        if not search_results:
            raise WikiPageNotFoundError(f"No matches found for '{query}'")

        if isinstance(e, wikipedia.DisambiguationError):
            click.echo("📡 Multiple matches found. Please choose one of the following:")
            for idx, option in enumerate(search_results, start=1):
                click.echo(f"{idx}. {option}")
            choice = click.prompt("Enter a number (or press Enter to cancel)", type=str, default="", show_default=False)

            if not choice.isdigit():
                raise WikiPageNotFoundError("No valid choice provided")

            choice_num = int(choice)
            if choice_num < 1 or choice_num > len(search_results):
                raise WikiPageNotFoundError("Choice out of range")

            chosen_title = search_results[choice_num - 1]
            page = wikipedia.page(chosen_title, auto_suggest=False)
            
            logging.info(f"📰 Found article: {Colors.GREEN}'{page.title}'{Colors.RESET}")
            return page
        
        raise  # Re-raise the original exception if not handled


def setup_logging(log_level: int) -> None:
    """Configure logging with the specified level and formatter"""
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Store any existing handlers that might be from pytest
    existing_handlers = []
    for handler in root_logger.handlers[:]:
        # Keep pytest's handlers (they don't have a stream attribute)
        if not hasattr(handler, 'stream'):
            existing_handlers.append(handler)
        else:
            root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = ColoredFormatter('%(message)s')
    
    # Create our stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Restore existing handlers and add our new one
    root_logger.handlers = existing_handlers
    root_logger.addHandler(handler)
    
    # Ensure propagation is enabled
    root_logger.propagate = True

@click.command()
@click.argument('title', required=False)
@click.option('--url', '-u', help='Wikipedia URL to convert to markdown')
@click.option('--output-dir', '-o', default='.',
              help='Directory to save the markdown file (default: current directory)')
@click.option('--obsidian', '-O', is_flag=True, help='Enable Obsidian mode')
@click.option('--no-links', '-N', is_flag=True, help='Disable links in the output')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--loglevel', '-L', default='INFO',
              help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
def main(title, url, output_dir, obsidian, no_links, verbose, loglevel):
    """Convert Wikipedia articles to markdown format.
    
    Provide either a TITLE to search for or use --url to specify a Wikipedia URL directly.
    """
    try:
        # Set logging level based on verbose flag or loglevel option
        if verbose:
            log_level = logging.DEBUG
        else:
            try:
                log_level = getattr(logging, loglevel.upper())
            except AttributeError:
                click.echo(f"❌ Error: Invalid log level: {loglevel}", err=True)
                sys.exit(1)

        setup_logging(log_level)
        if verbose and log_level == logging.DEBUG:
            logging.debug("🐞 Debug mode enabled")
        logging.info("🚀 Starting page processing")

        # Validate input arguments
        if not title and not url:
            click.echo("❌ Error: Either TITLE or --url must be provided", err=True)
            sys.exit(1)
        if title and url:
            click.echo("❌ Error: Cannot specify both TITLE and --url", err=True)
            sys.exit(1)

        try:
            query = url if url else title
            page = fetch_wiki_page(query)
            markdown = make_markdown_from_page(page, obsidian=obsidian, no_links=no_links)

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            filename = f"{page.title.replace('/', '-')}.md"
            file_path = output_path / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

            logging.info(f"✅ Successfully created {Colors.CYAN}'{file_path}'{Colors.RESET}")
            return 0

        except (wikipedia.PageError, WikiPageNotFoundError) as e:
            click.echo(f"❌ Error: {str(e)}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Fatal error: {str(e)}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Fatal error: {str(e)}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    main() 