import difflib
import logging
from pathlib import Path
import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class GuideSection:
    """
    Data structure representing a parsed guide section.
    """

    def __init__(self, raw_text: str, source_file: str) -> None:
        self.raw_text: str = raw_text.strip()
        self.source_file: str = source_file

        lines = [line.strip() for line in self.raw_text.split("\n") if line.strip()]
        self.heading: str = lines[0] if lines else "General Guide"

        # Format title cleanly (e.g. "BUYER REGISTRATION" -> "Buyer Registration")
        self.formatted_title: str = self._format_title(self.heading)

        self.keywords: list[str] = self._extract_block(
            "Keywords:", ["Frequently Asked Questions:", "Description:"]
        )
        self.faqs: list[str] = self._extract_block(
            "Frequently Asked Questions:", ["Description:", "Keywords:"]
        )
        self.content: str = self._extract_clean_content()

        # Combine text fields for TF-IDF indexing
        self.full_searchable_text: str = (
            f"{self.heading} {' '.join(self.keywords)} {' '.join(self.faqs)} {self.content}"
        )

    def _format_title(self, raw_heading: str) -> str:
        words = raw_heading.split()
        cleaned_words = [w.capitalize() for w in words]
        title = " ".join(cleaned_words)

        simplifications = {
            "Request Auction Token": "Auction Token",
            "Place A Bid": "Place Bid",
            "Update Your Bid": "Update Bid",
            "View Purchase History": "Purchase History",
            "Profile Management": "Profile Management",
        }
        return simplifications.get(title, title)

    def _extract_block(self, start_marker: str, end_markers: list[str]) -> list[str]:
        lines = self.raw_text.split("\n")
        in_block = False
        items: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped == start_marker:
                in_block = True
                continue

            if in_block:
                if any(stripped.startswith(m) for m in end_markers):
                    break
                if stripped:
                    items.append(stripped)

        return items

    def _extract_clean_content(self) -> str:
        lines = self.raw_text.split("\n")
        cleaned: list[str] = []
        skip = False

        for line in lines:
            stripped = line.strip()
            if stripped in ["Keywords:", "Frequently Asked Questions:"]:
                skip = True
                continue
            if stripped == "Description:":
                skip = False
                continue

            if not skip:
                cleaned.append(line)

        return "\n".join(cleaned).strip()


class WebsiteService:
    """
    Website Guide NLP Service.
    Parses guide files once, builds single TF-IDF index,
    provides synonym-guided multi-stage section retrieval, and generates dynamic heading suggestions.
    """

    def __init__(self) -> None:
        self.knowledge_path = (
            Path(__file__).resolve().parent.parent / "knowledge"
        )
        self.sections: list[GuideSection] = []
        self.suggested_questions: list[str] = []

        # Synonym map linking user natural language intent phrases directly to guide section headings
        self.synonym_intent_map: dict[str, list[str]] = {
            "registration": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "register": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "sign up": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "signup": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "create account": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "new account": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "join": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "become a buyer": ["BUYER REGISTRATION"],
            "become a seller": ["BUYER REGISTRATION", "SELLER REGISTRATION"],
            "login": ["LOGIN"],
            "log in": ["LOGIN"],
            "sign in": ["LOGIN"],
            "signin": ["LOGIN"],
            "access account": ["LOGIN"],
            "logout": ["LOGOUT"],
            "log out": ["LOGOUT"],
            "sign out": ["LOGOUT"],
            "token": ["REQUEST AUCTION TOKEN"],
            "auction token": ["REQUEST AUCTION TOKEN"],
            "upload lot": ["UPLOAD CARDAMOM LOT"],
            "add lot": ["UPLOAD CARDAMOM LOT"],
            "track lot": ["TRACK LOT STATUS"],
            "lot status": ["TRACK LOT STATUS"],
            "bid": ["PLACE A BID"],
            "bidding": ["PLACE A BID"],
            "place bid": ["PLACE A BID"],
            "update bid": ["UPDATE YOUR BID"],
            "change bid": ["UPDATE YOUR BID"],
            "increase bid": ["UPDATE YOUR BID"],
            "my bids": ["VIEW MY BIDS"],
            "bid history": ["VIEW MY BIDS"],
            "winning bid": ["VIEW WINNING BIDS"],
            "won auction": ["VIEW WINNING BIDS"],
            "payment": ["PAYMENT"],
            "pay": ["PAYMENT"],
            "payment status": ["PAYMENT STATUS"],
            "invoice": ["DOWNLOAD INVOICE"],
            "download invoice": ["DOWNLOAD INVOICE"],
            "receipt": ["DOWNLOAD INVOICE"],
            "bill": ["DOWNLOAD INVOICE"],
            "purchase history": ["VIEW PURCHASE HISTORY"],
            "purchases": ["VIEW PURCHASE HISTORY"],
            "profile": ["PROFILE MANAGEMENT"],
            "change password": ["PROFILE MANAGEMENT"],
            "reset password": ["PROFILE MANAGEMENT"],
            "update profile": ["PROFILE MANAGEMENT"],
            "live auction": ["VIEW LIVE AUCTIONS"],
            "view live auctions": ["VIEW LIVE AUCTIONS"],
            "active auctions": ["VIEW LIVE AUCTIONS"],
        }

        self._load_and_parse_guides()
        self._build_tfidf_index()

    def _load_and_parse_guides(self) -> None:
        seen_titles: set[str] = set()
        headings_list: list[str] = []

        for filename in ["seller_guide.txt", "buyer_guide.txt"]:
            file_path = self.knowledge_path / filename
            if not file_path.exists():
                logger.warning("Guide file not found: %s", file_path)
                continue

            try:
                text = file_path.read_text(encoding="utf-8")
                raw_sections = [
                    part.strip()
                    for part in text.split("------------------------------------------------------------------")
                    if part.strip()
                ]

                for raw in raw_sections:
                    section = GuideSection(raw, filename)
                    self.sections.append(section)

                    if section.formatted_title not in seen_titles:
                        seen_titles.add(section.formatted_title)
                        headings_list.append(section.formatted_title)

            except Exception as e:
                logger.error("Failed to read guide file %s: %s", filename, e)

        self.suggested_questions = headings_list

    def _build_tfidf_index(self) -> None:
        if not self.sections:
            self.vectorizer = None
            self.document_vectors = None
            return

        corpus = [sec.full_searchable_text for sec in self.sections]
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
        )
        self.document_vectors = self.vectorizer.fit_transform(corpus)

    def get_dynamic_unknown_response(self) -> dict[str, Any]:
        """
        Generates fallback message and suggestions when no guide answer exists.
        """
        bullet_points = "\n".join(f"• {title}" for title in self.suggested_questions)
        answer = (
            "I couldn't find that information in the CardaLink guides.\n\n"
            "You can ask about:\n\n"
            f"{bullet_points}"
        )
        return {
            "answer": answer,
            "suggestions": self.suggested_questions,
            "matched": False,
        }

    def answer(self, question: str) -> dict[str, Any]:
        """
        Finds best matching guide section using synonym mapping, heading matching,
        FAQ matching, and high-confidence TF-IDF similarity.
        """
        if not question or not question.strip():
            return self.get_dynamic_unknown_response()

        question_clean = question.strip().lower()
        question_no_punct = re.sub(r"[^\w\s]", "", question_clean)

        # Stage 1: Explicit Synonym Intent Mapping
        for phrase, target_headings in self.synonym_intent_map.items():
            if re.search(r"\b" + re.escape(phrase) + r"\b", question_clean) or phrase in question_clean:
                # Find corresponding guide section
                matched_sections = [
                    sec for sec in self.sections
                    if sec.heading.upper() in [h.upper() for h in target_headings]
                ]
                if matched_sections:
                    # Combine matching sections if multiple (e.g. Buyer & Seller Registration)
                    combined_answer = "\n\n---\n\n".join(
                        f"### {sec.formatted_title}\n{sec.content}" if len(matched_sections) > 1 else sec.content
                        for sec in matched_sections
                    )
                    return {
                        "answer": combined_answer,
                        "suggestions": self.suggested_questions,
                        "matched": True,
                    }

        # Stage 2: Heading Fuzzy & Overlap Matching
        best_heading_section: GuideSection | None = None
        best_heading_score: float = 0.0

        for section in self.sections:
            heading_clean = section.heading.lower()
            heading_no_punct = re.sub(r"[^\w\s]", "", heading_clean)
            formatted_clean = section.formatted_title.lower()

            if heading_clean in question_clean or formatted_clean in question_clean:
                return {
                    "answer": section.content,
                    "suggestions": self.suggested_questions,
                    "matched": True,
                }

            ratio = difflib.SequenceMatcher(None, heading_no_punct, question_no_punct).ratio()
            words_in_heading = heading_no_punct.split()
            word_matches = sum(1 for w in words_in_heading if w in question_no_punct)

            coverage = word_matches / max(1, len(words_in_heading))
            combined_score = max(ratio, coverage)

            if combined_score > best_heading_score:
                best_heading_score = combined_score
                best_heading_section = section

        if best_heading_score >= 0.75 and best_heading_section:
            return {
                "answer": best_heading_section.content,
                "suggestions": self.suggested_questions,
                "matched": True,
            }

        # Stage 3: FAQ & Keyword Sentence Matching
        best_faq_section: GuideSection | None = None
        best_faq_score: float = 0.0

        for section in self.sections:
            all_patterns = section.faqs + section.keywords
            for item in all_patterns:
                item_clean = re.sub(r"[^\w\s]", "", item.lower())
                ratio = difflib.SequenceMatcher(None, item_clean, question_no_punct).ratio()

                q_words = set(question_no_punct.split())
                item_words = set(item_clean.split()) - {"how", "do", "i", "can", "where", "what", "is", "a", "to", "my", "the"}
                if item_words:
                    overlap = len(q_words.intersection(item_words)) / len(item_words)
                    score = max(ratio, overlap)
                else:
                    score = ratio

                if score > best_faq_score:
                    best_faq_score = score
                    best_faq_section = section

        if best_faq_score >= 0.55 and best_faq_section:
            return {
                "answer": best_faq_section.content,
                "suggestions": self.suggested_questions,
                "matched": True,
            }

        # Stage 4: High-Confidence TF-IDF Cosine Similarity Matching
        if self.document_vectors is not None and self.vectorizer is not None:
            try:
                question_vec = self.vectorizer.transform([question_clean])
                similarities = cosine_similarity(question_vec, self.document_vectors)[0]

                best_idx = int(similarities.argmax())
                best_tfidf_score = float(similarities[best_idx])

                # Require a solid similarity score (>= 0.20) to prevent weak random word hits
                if best_tfidf_score >= 0.20:
                    matched_sec = self.sections[best_idx]
                    return {
                        "answer": matched_sec.content,
                        "suggestions": self.suggested_questions,
                        "matched": True,
                    }
            except Exception as e:
                logger.error("TF-IDF website search error: %s", e)

        # Dynamic fallback when confidence threshold is not met
        return self.get_dynamic_unknown_response()