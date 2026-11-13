"""Algorithms for finding textually similar documents."""

from .lsh import LSH
from .minhashing import CompareSignatures, MinHashing
from .pipeline import AnalysisResult, analyze_documents
from .shingling import CompareSets, Shingling

__all__ = [
    "AnalysisResult",
    "CompareSets",
    "CompareSignatures",
    "LSH",
    "MinHashing",
    "Shingling",
    "analyze_documents",
]

