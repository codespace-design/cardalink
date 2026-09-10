import logging
import re
from typing import Literal

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

IntentType = Literal["Website Guide", "Auction", "Farm Assistant", "Unknown"]


class IntentClassifier:
    """
    NLP Intent Detection Service.
    Classifies user messages into one of:
    - Website Guide
    - Auction
    - Farm Assistant
    - Unknown
    Uses semantic similarity and pre-compiled TF-IDF corpus vectors.
    """

    def __init__(self) -> None:
        self.categories: list[IntentType] = [
            "Farm Assistant",
            "Auction",
            "Website Guide",
        ]

        self.corpus: dict[IntentType, list[str]] = {
            "Farm Assistant": [
                "cardamom cradamom cultivation diseases pests fertilizer irrigation harvesting yield shade soil nutrition farm management",
                "cardamom farming crop plant leaf leaves yellow yellowing rot fungus pruning pesticide manure compost watering growth yield improvement",
                "how to manage cardamom pests and diseases fertilizer application shade trees harvesting technique yellow leaves",
                "soil preparation for cardamom plantation organic fertilizers irrigation methods crop yield plant rot yellow leaves cradamom",
            ],
            "Auction": [
                "highest bid current highest bid maximum bid max bid latest auction price top bid",
                "latest bid last bid recent bid last successful bid latest price current price",
                "active auctions running auctions current auction count live auctions bidding open count",
                "completed auctions finished auctions total completed auctions historical auctions count",
                "total buyers registered buyers number of buyers buyer count total registered buyers count",
                "total sellers registered sellers number of sellers seller count total registered sellers count",
            ],
            "Website Guide": [
                "register registration buyer registration seller registration create account sign up join cardalink",
                "login sign in log into account access account change password reset password profile management edit profile",
                "auction token request token upload cardamom lot track lot status lot approval lot details",
                "place bid update bid view my bids winning bids auction results live auction page",
                "payment payment status download invoice receipt transaction history purchase history logout sign out",
            ],
        }

        # Flat documents list & mapping to categories
        self.doc_texts: list[str] = []
        self.doc_categories: list[IntentType] = []

        for category, phrases in self.corpus.items():
            for phrase in phrases:
                self.doc_texts.append(phrase)
                self.doc_categories.append(category)

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
        )
        self.doc_vectors = self.vectorizer.fit_transform(self.doc_texts)

    def classify(self, question: str) -> IntentType:
        """
        Classifies a given user question into an IntentType based on semantic similarity.
        """
        if not question or not question.strip():
            return "Unknown"

        clean_question = question.lower().strip()

        # Direct explicit pattern checks for high precision
        if any(
            term in clean_question
            for term in [
                "highest bid",
                "max bid",
                "maximum bid",
                "latest bid",
                "last bid",
                "active auction",
                "running auction",
                "completed auction",
                "total buyer",
                "registered buyer",
                "number of buyer",
                "buyer count",
                "total seller",
                "registered seller",
                "number of seller",
                "seller count",
                "latest auction price",
                "current auction count",
            ]
        ):
            return "Auction"

        if any(
            term in clean_question
            for term in [
                "cultivation",
                "disease",
                "diseases",
                "pest",
                "pests",
                "pesticide",
                "pesticides",
                "fertilizer",
                "fertilizers",
                "irrigation",
                "watering",
                "harvest",
                "harvesting",
                "yield",
                "shade",
                "soil",
                "nutrition",
                "farm",
                "farming",
                "fungus",
                "fungal",
                "pruning",
                "crop",
                "crops",
                "leaf",
                "leaves",
                "yellow",
                "yellowing",
                "plant",
                "plants",
                "rot",
                "decay",
                "wilt",
                "wilting",
                "spots",
                "spot",
                "cardamom",
                "cradamom",
                "cardomom",
            ]
        ):
            return "Farm Assistant"

        if any(
            term in clean_question
            for term in [
                "register",
                "sign up",
                "signup",
                "create account",
                "join",
                "login",
                "sign in",
                "logout",
                "sign out",
                "token",
                "lot",
                "invoice",
                "receipt",
                "password",
                "profile",
                "purchase history",
            ]
        ):
            return "Website Guide"

        # TF-IDF Cosine Similarity calculation
        try:
            q_vector = self.vectorizer.transform([clean_question])
            similarities = cosine_similarity(q_vector, self.doc_vectors)[0]

            best_idx = int(similarities.argmax())
            best_score = float(similarities[best_idx])

            logger.debug(
                "Intent classification question='%s', best_cat='%s', score=%.4f",
                question,
                self.doc_categories[best_idx],
                best_score,
            )

            if best_score >= 0.08:
                return self.doc_categories[best_idx]

        except Exception as e:
            logger.error("Error during intent classification: %s", e)

        return "Unknown"
