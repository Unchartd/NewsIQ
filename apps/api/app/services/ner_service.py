"""Service for extracting named entities (NER) from text using spaCy with fallback."""

import logging
import re
from typing import Dict, List, Set, Tuple

import spacy

logger = logging.getLogger(__name__)


class NERService:
    """Named Entity Recognition service using spaCy with clean rules-based fallback."""

    def __init__(self):
        self.nlp = None
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Attempting auto-download...")
            try:
                import subprocess
                import sys
                subprocess.run(
                    [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Successfully downloaded and loaded 'en_core_web_sm'")
            except Exception as e:
                logger.error("Failed to download spaCy model: %s. Using regex fallback.", e)

    def _regex_fallback_ner(self, text: str) -> List[Tuple[str, str]]:
        """Fallback rule-based NER using regex to identify potential Persons, Orgs, and Locations.
        
        Extracts consecutive capitalized words and runs simple heuristics.
        """
        entities = []
        if not text:
            return entities

        # Simple pattern to match capitalized word sequences (potential proper nouns)
        # Matches sequences like 'United States', 'Elon Musk', 'Google Inc.'
        pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        matches = re.findall(pattern, text)

        # Basic dictionaries for common categories
        org_indicators = {"Google", "Microsoft", "Apple", "Federal", "Reserve", "Inc", "Co", "Corp", "Organization", "Council", "Nations", "UN", "NATO", "EU"}
        loc_indicators = {"US", "UK", "USA", "India", "London", "Washington", "Delhi", "Mumbai", "Paris", "Berlin", "Tokyo", "State", "City", "China", "Europe", "Asia"}

        seen: Set[str] = set()
        for entity in matches:
            if entity in seen or len(entity) < 3:
                continue
            seen.add(entity)

            # Rule-based categorization
            words = set(entity.split())
            if words.intersection(org_indicators):
                entities.append((entity, "ORG"))
            elif words.intersection(loc_indicators) or entity in loc_indicators:
                entities.append((entity, "LOCATION"))
            else:
                # Default to PERSON for standard capitalized names
                entities.append((entity, "PERSON"))

        return entities

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract entities (PERSON, ORG, LOCATION, EVENT) from text.
        
        Returns a list of dicts: [{"value": "Entity Name", "type": "PERSON"}]
        """
        if not text or not text.strip():
            return []

        extracted = []
        seen = set()

        if self.nlp:
            try:
                # Process text with spaCy (limit to 100k chars for safety)
                doc = self.nlp(text[:100000])
                for ent in doc.ents:
                    # Map spaCy labels to standard categories
                    label = ent.label_
                    if label in ("PERSON", "ORG", "GPE", "LOC", "EVENT"):
                        category = "LOCATION" if label in ("GPE", "LOC") else label
                        # Clean up text
                        val = ent.text.strip().replace("\n", " ")
                        if len(val) >= 3 and val not in seen:
                            seen.add(val)
                            extracted.append({"value": val, "type": category})
                return extracted
            except Exception as e:
                logger.error("spaCy entity extraction failed: %s. Falling back to regex.", e)

        # Fallback to regex NER
        fallback_entities = self._regex_fallback_ner(text)
        for val, category in fallback_entities:
            val_clean = val.strip()
            if len(val_clean) >= 3 and val_clean not in seen:
                seen.add(val_clean)
                extracted.append({"value": val_clean, "type": category})

        return extracted


ner_service = NERService()
