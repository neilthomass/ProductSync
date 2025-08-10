import numpy as np
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Tuple, Optional
import logging
import torch

logger = logging.getLogger(__name__)

class TextClassifier:
    def __init__(self, model_name: str = "facebook/bart-large-mnli", use_gpu: bool = False):
        """
        Initialize the feedback classifier.
        Phase 0: Zero-shot using facebook/bart-large-mnli as specified in README
        Phase 1: Fine-tuned model (to be implemented)
        """
        self.device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        
        # Default label taxonomy as specified in README
        self.default_labels = [
            "bug/crash", "bug/performance", "feature/roadmap", "feature/quality-of-life",
            "ux/usability", "docs", "pricing", "security", "integration/notion",
            "integration/slack", "integration/discord"
        ]
        
        try:
            if "mnli" in model_name.lower():
                # Zero-shot classification
                self.classifier = pipeline(
                    "zero-shot-classification",
                    model=model_name,
                    device=0 if self.device == "cuda" else -1
                )
                self.mode = "zero-shot"
                logger.info(f"Initialized zero-shot classifier with {model_name}")
            else:
                # Fine-tuned model
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                self.model.to(self.device)
                self.mode = "fine-tuned"
                logger.info(f"Initialized fine-tuned classifier with {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize classifier: {e}")
            raise
    
    def classify_zero_shot(self, text: str, candidate_labels: Optional[List[str]] = None) -> Dict:
        """Classify text using zero-shot approach."""
        if not candidate_labels:
            candidate_labels = self.default_labels
        
        try:
            result = self.classifier(text, candidate_labels, multi_label=True)
            return {
                "labels": result["labels"],
                "scores": result["scores"],
                "text": text
            }
        except Exception as e:
            logger.error(f"Zero-shot classification failed: {e}")
            return {
                "labels": [],
                "scores": [],
                "text": text
            }
    
    def classify_fine_tuned(self, text: str) -> Dict:
        """Classify text using fine-tuned model."""
        if self.mode != "fine-tuned":
            raise ValueError("Model not initialized for fine-tuned classification")
        
        try:
            inputs = self.tokenizer(
                text,
                truncation=True,
                padding="max_length",
                max_length=256,
                return_tensors="pt"
            )
            
            with torch.no_grad():
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                outputs = self.model(**inputs)
                logits = outputs.logits
                
                # Apply sigmoid for multi-label classification
                probs = torch.sigmoid(logits).cpu().numpy()[0]
                
                # Get labels above threshold
                threshold = 0.5
                predicted_labels = []
                predicted_scores = []
                
                for i, score in enumerate(probs):
                    if score > threshold:
                        predicted_labels.append(self.default_labels[i])
                        predicted_scores.append(float(score))
                
                return {
                    "labels": predicted_labels,
                    "scores": predicted_scores,
                    "text": text
                }
        except Exception as e:
            logger.error(f"Fine-tuned classification failed: {e}")
            return {
                "labels": [],
                "scores": [],
                "text": text
            }
    
    def classify(self, text: str, candidate_labels: Optional[List[str]] = None) -> Dict:
        """Main classification method that routes to appropriate classifier."""
        if self.mode == "zero-shot":
            return self.classify_zero_shot(text, candidate_labels)
        elif self.mode == "fine-tuned":
            return self.classify_fine_tuned(text)
        else:
            raise ValueError(f"Unknown classification mode: {self.mode}")
    
    def get_label_scores(self, text: str, candidate_labels: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Get label-score pairs for a text."""
        result = self.classify(text, candidate_labels)
        return list(zip(result["labels"], result["scores"]))
    
    def get_top_labels(self, text: str, top_k: int = 3, candidate_labels: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Get top-k labels for a text."""
        label_scores = self.get_label_scores(text, candidate_labels)
        return sorted(label_scores, key=lambda x: x[1], reverse=True)[:top_k] 
