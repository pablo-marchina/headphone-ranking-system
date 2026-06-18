from .amazon import AmazonBrasilCollector
from .asr import ASRCollector
from .base import BaseCollector
from .headphonescom import HeadphonesComCollector
from .independent_reviewers import IndependentReviewerCollector
from .innerfidelity import InnerFidelityCollector
from .mercadolivre import MercadoLivrePriceCollector
from .kabum import KabumPriceCollector
from .price_aggregator import ZoomJacoteiCollector
from .shopee import ShopeeCollector
from .squig import SquigCollector

__all__ = [
    "BaseCollector",
    "SquigCollector",
    "InnerFidelityCollector",
    "HeadphonesComCollector",
    "ASRCollector",
    "IndependentReviewerCollector",
    "KabumPriceCollector",
    "ZoomJacoteiCollector",
    "ShopeeCollector",
    "AmazonBrasilCollector",
    "MercadoLivrePriceCollector",
]
