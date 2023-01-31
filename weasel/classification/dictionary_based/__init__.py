# -*- coding: utf-8 -*-
"""Dictionary based time series classifiers."""
__all__ = [
    "WEASEL_V2",
    "WEASEL",
    "MUSE_V2",
    "MUSE",

]

from weasel.classification.dictionary_based._muse_v2 import MUSE_V2
from weasel.classification.dictionary_based._weasel_v2 import WEASEL_V2

from weasel.classification.dictionary_based._muse import MUSE
from weasel.classification.dictionary_based._weasel import WEASEL
