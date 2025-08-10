import spacy
import re
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class TextPreprocessor:
    def __init__(self, model_name: str = "en_core_web_md"):
        """Initialize the text preprocessor with spaCy model."""
        try:
            self.nlp = spacy.load(model_name)
            logger.info(f"Loaded spaCy model: {model_name}")
        except OSError:
            logger.warning(f"Model {model_name} not found, downloading...")
            spacy.cli.download(model_name)
            self.nlp = spacy.load(model_name)
    
    def preprocess(self, text: str) -> str:
        """
        Preprocess text according to the README specifications:
        - Clean: lowercase (except codes), strip signatures/quoted blocks
        - PII redaction: use NER (PERSON/EMAIL/PHONE) ⇒ replace with [REDACTED]
        - Strip quotes and signatures
        """
        if not text or not text.strip():
            return ""
        
        # Convert to spaCy doc
        doc = self.nlp(text.strip())
        
        # Find PII entities
        pii_spans = [ent for ent in doc.ents if ent.label_ in {"PERSON", "GPE", "EMAIL", "PHONE"}]
        
        # Replace PII with [REDACTED]
        tokens = []
        for token in doc:
            if token.ent_type_ in {"PERSON", "GPE", "EMAIL", "PHONE"}:
                tokens.append("[REDACTED]")
            else:
                # Preserve case for code-like tokens (containing numbers, special chars)
                if re.search(r'[0-9A-Z]', token.text) and not token.is_sent_start:
                    tokens.append(token.text)
                else:
                    tokens.append(token.text.lower())
        
        # Join tokens and clean up
        cleaned_text = " ".join(tokens)
        
        # Strip quoted blocks (lines starting with >)
        cleaned_text = re.sub(r'>.*\n', '', cleaned_text)
        
        # Strip multiple whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        return cleaned_text.strip()
    
    def extract_entities(self, text: str) -> dict:
        """Extract named entities for analysis."""
        doc = self.nlp(text)
        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append(ent.text)
        return entities
    
    def extract_phrases(self, text: str, phrase_patterns: Optional[List[str]] = None) -> List[str]:
        """Extract phrases using regex patterns (NLTK alternative)."""
        if not phrase_patterns:
            # Default patterns for version strings, product names, etc.
            phrase_patterns = [
                r'v\d+\.\d+(\.\d+)?',  # version numbers
                r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # Product names
                r'#[0-9]+',  # issue numbers
            ]
        
        phrases = []
        for pattern in phrase_patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches)
        
        return list(set(phrases)) 