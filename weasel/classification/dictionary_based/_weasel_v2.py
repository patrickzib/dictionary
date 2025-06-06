# -*- coding: utf-8 -*-
"""WEASEL 2.0

A Random Dilated Dictionary Transform for Fast, Accurate and Constrained Memory
Time Series Classification.

"""

__author__ = ["patrickzib"]
__all__ = ["WEASEL_V2"]

import numpy as np
from joblib import Parallel, delayed
from scipy.sparse import hstack
from sklearn.linear_model import RidgeClassifierCV
from sklearn.utils import check_random_state
from aeon.classification.base import BaseClassifier

from weasel.transformations.collection.dictionary_based import SFADilation


class WEASEL_V2(BaseClassifier):
    """Word Extraction for Time Series Classification (WEASEL) v2.0.

    Overview: Input n series length m
    WEASEL is a dictionary classifier that builds a bag-of-patterns using SFA
    for different window lengths and learns a logistic regression classifier
    on this bag.

    WEASEL 2.0 has three key parameters that are automcatically set based on the
    length of the time series:
    (1) Minimal window length: Typically defaulted to 4
    (2) Maximal window length: Typically chosen from
        24, 44 or 84 depending on the time series length.
    (3) Ensemble size: Typically chosen from 50, 100, 150, to derive
        a feature vector of roughly 20𝑘 up to 70𝑘 features (distinct words).

    From the other parameters passed, WEASEL chosen random values for each set
    of configurations. E.g. for each of 150 configurations, a random value is chosen
    from the below options.

    Parameters
    ----------
    min_window : int, default=4,
        Minimal length of the subsequences to compute words from.
    norm_options : array of bool, default=[False],
        If the array contains True, words are computed over mean-normed TS
        If the array contains False, words are computed over raw TS
        If both are set, words are computed for both.
        A value will be randomly chosen for each parameter-configuration.
    word_lengths : array of int, default=[7, 8],
        Length of the words to compute. A value will be randomly chosen for each
        parameter-configuration.
    use_first_differences: array of bool, default=[True, False],
        If the array contains True, words are computed over first order differences.
        If the array contains False, words are computed over the raw time series.
        If both are set, words are computed for both.
    feature_selection: {"chi2_top_k", "none", "random"}, default: chi2_top_k
        Sets the feature selections strategy to be used. Large amounts of memory may be
        needed depending on the setting of bigrams (true is more) or
        alpha (larger is more).
        'chi2_top_k' reduces the number of words to at most 'max_feature_count',
        dropping values based on p-value.
        'random' reduces the number to at most 'max_feature_count',
        by randomly selecting features.
        'none' does not apply any feature selection and yields large bag of words
    max_feature_count : int, default=30_000
       size of the dictionary - number of words to use - if feature_selection set to
       "chi2" or "random". Else ignored.
    n_jobs : int, default=4
        The number of jobs to run in parallel for both `fit` and `predict`.
        ``-1`` means using all processors.   
    random_state: int or None, default=None
        Seed for random, integer

    Attributes
    ----------
    n_classes_ : int
        The number of classes.
    classes_ : list
        The classes labels.

    See Also
    --------
    MUSE

    References
    ----------
    .. [1] Patrick Schäfer and Ulf Leser, "WEASEL 2.0 -- A Random Dilated Dictionary
    Transform for Fast, Accurate and Memory Constrained Time Series Classification",
    Preprint, https://arxiv.org/abs/2301.10194

    Notes
    -----
    
    Examples
    --------
    >>> from weasel.classification.dictionary_based import WEASEL_V2
    >>> from aeon.datasets import load_unit_test
    >>> X_train, y_train = load_unit_test(split="train", return_X_y=True)
    >>> X_test, y_test = load_unit_test(split="test", return_X_y=True)
    >>> clf = WEASEL_V2()
    >>> clf.fit(X_train, y_train)
    WEASEL_V2(...)
    >>> y_pred = clf.predict(X_test)
    """

    _tags = {
        "capabilitys:multithreading": True,
        "classifier_type": "dictionary",
    }

    def __init__(
            self,
            min_window=4,
            norm_options=[False],
            word_lengths=[7, 8],
            use_first_differences=[True, False],
            feature_selection="chi2_top_k",
            max_feature_count=30_000,
            random_state=None,
            n_jobs=4,
    ):
        self.alphabet_sizes = [2]
        self.binning_strategies = ["equi-depth", "equi-width"]

        self.anova = False
        self.variance = True
        self.bigrams = False
        self.lower_bounding = True
        self.remove_repeat_words = False

        self.norm_options = norm_options
        self.word_lengths = word_lengths

        self.random_state = random_state

        self.min_window = min_window
        self.max_window = 84
        self.ensemble_size = 150
        self.max_feature_count = max_feature_count
        self.use_first_differences = use_first_differences
        self.feature_selection = feature_selection
        self.sections = 1

        self.window_sizes = []
        self.series_length = 0
        self.n_instances = 0

        self.SFA_transformers = []

        self.clf = None
        self.n_jobs = n_jobs

        # set_num_threads(n_jobs)

        super(WEASEL_V2, self).__init__()

    def _fit(self, X, y):
        """Build a WEASEL classifiers from the training set (X, y).

        Parameters
        ----------
        X : 3D np.array of shape = [n_instances, n_dimensions, series_length]
            The training data.
        y : array-like, shape = [n_instances]
            The class labels.

        Returns
        -------
        self :
            Reference to self.
        """
        # Window length parameter space dependent on series length
        self.n_instances, self.series_length = X.shape[0], X.shape[-1]
        XX = X.squeeze(1)

        # avoid overfitting with too many features
        if self.n_instances < 250:  # TODO 150??
            self.max_window = 24
            self.ensemble_size = 50
        elif self.series_length < 100:
            self.max_window = 44
            self.ensemble_size = 100
        else:
            self.max_window = 84
            self.ensemble_size = 150

        self.max_window = int(min(self.series_length, self.max_window))
        if self.min_window > self.max_window:
            raise ValueError(
                f"Error in WEASEL, min_window ="
                f"{self.min_window} is bigger"
                f" than max_window ={self.max_window},"
                f" series length is {self.series_length}"
                f" try set min_window to be smaller than series length in "
                f"the constructor, but the classifier may not work at "
                f"all with very short series"
            )

        # Randomly choose window sizes
        self.window_sizes = np.arange(self.min_window, self.max_window + 1, 1)

        parallel_res = Parallel(n_jobs=self.n_jobs, timeout=99999, prefer="threads")(
            delayed(_parallel_fit)(
                i,
                XX,
                y.copy(),
                self.window_sizes,
                self.alphabet_sizes,
                self.word_lengths,
                self.series_length,
                self.norm_options,
                self.use_first_differences,
                self.binning_strategies,
                self.variance,
                self.anova,
                self.bigrams,
                self.lower_bounding,
                self.n_jobs,
                self.max_feature_count,
                self.ensemble_size,
                self.feature_selection,
                self.remove_repeat_words,
                self.sections,
                self.random_state,
            )
            for i in range(self.ensemble_size)
        )

        sfa_words = []
        for (words, transformer) in parallel_res:
            self.SFA_transformers.extend(transformer)
            sfa_words.extend(words)

        # merging arrays from different threads
        if type(sfa_words[0]) is np.ndarray:
            all_words = np.concatenate(sfa_words, axis=1)
        else:
            all_words = hstack(sfa_words)

        self.clf = RidgeClassifierCV(alphas=np.logspace(-1, 5, 10))

        self.clf.fit(all_words, y)
        self.total_features_count = all_words.shape[1]
        if hasattr(self.clf, "best_score_"):
            self.cross_val_score = self.clf.best_score_

        return self

    def _predict(self, X) -> np.ndarray:
        """Predict class values of n instances in X.

        Parameters
        ----------
        X : 3D np.array of shape = [n_instances, n_dimensions, series_length]
            The data to make predictions for.

        Returns
        -------
        y : array-like, shape = [n_instances]
            Predicted class labels.
        """
        bag = self._transform_words(X)
        return self.clf.predict(bag)

    def _predict_proba(self, X) -> np.ndarray:
        """Predict class probabilities for n instances in X.

        Parameters
        ----------
        X : 3D np.array of shape = [n_instances, n_dimensions, series_length]
            The data to make predict probabilities for.

        Returns
        -------
        y : array-like, shape = [n_instances, n_classes_]
            Predicted probabilities using the ordering in classes_.
        """
        bag = self._transform_words(X)
        scores = self.clf.decision_function(bag)
        if len(scores.shape) == 1:
            indices = (scores > 0).astype(np.int)
        else:
            indices = scores.argmax(axis=1)
        return self.classes_[indices]

        # return self.clf.predict_proba(bag)

    def _transform_words(self, X):
        XX = X.squeeze(1)

        parallel_res = Parallel(n_jobs=self.n_jobs, timeout=99999, prefer="threads")(
            delayed(transformer.transform)(XX) for transformer in self.SFA_transformers
        )

        all_words = []
        for words in parallel_res:
            # words = words.astype(np.float32) / norm
            all_words.append(words)

        # X_features = self.rocket.transform(X)

        if type(all_words[0]) is np.ndarray:
            # all_words.append(X_features)
            all_words = np.concatenate(all_words, axis=1)
        else:
            # all_words.append(csr_matrix(X_features.values))
            all_words = hstack(all_words)

        return all_words


def _parallel_fit(
        i,
        X,
        y,
        window_sizes,
        alphabet_sizes,
        word_lengths,
        series_length,
        norm_options,
        use_first_differences,
        binning_strategies,
        variance,
        anova,
        bigrams,
        lower_bounding,
        n_jobs,
        max_feature_count,
        ensemble_size,
        feature_selection,
        remove_repeat_words,
        sections,
        random_state,
):
    if random_state is None:
        rng = check_random_state(None)
    else:
        rng = check_random_state(random_state + i)

    window_size = rng.choice(window_sizes)
    dilation = np.maximum(
        1,
        np.int32(2 ** rng.uniform(0, np.log2((series_length - 1) / (window_size - 1)))),
    )

    alphabet_size = rng.choice(alphabet_sizes)

    # maximize word-length
    word_length = min(window_size - 2, rng.choice(word_lengths))
    norm = rng.choice(norm_options)
    binning_strategy = rng.choice(binning_strategies)

    all_transformers = []
    all_words = []
    for first_difference in use_first_differences:
        transformer = getSFADilated(
            alphabet_size,
            alphabet_sizes,
            anova,
            bigrams,
            binning_strategy,
            dilation,
            ensemble_size,
            feature_selection,
            first_difference,
            i,
            lower_bounding,
            max_feature_count,
            n_jobs,
            norm,
            remove_repeat_words,
            sections,
            variance,
            window_size,
            word_length,
        )

        # generate SFA words on sample
        words = transformer.fit_transform(X, y)
        all_words.append(words)
        all_transformers.append(transformer)
    return all_words, all_transformers


def getSFADilated(
        alphabet_size,
        alphabet_sizes,
        anova,
        bigrams,
        binning_strategy,
        dilation,
        ensemble_size,
        feature_selection,
        first_difference,
        i,
        lower_bounding,
        max_feature_count,
        n_jobs,
        norm,
        remove_repeat_words,
        sections,
        variance,
        window_size,
        word_length,
):
    transformer = SFADilation(
        variance=variance,
        word_length=word_length,
        alphabet_size=alphabet_size,
        window_size=window_size,
        norm=norm,
        anova=anova,
        binning_method=binning_strategy,
        remove_repeat_words=remove_repeat_words,
        bigrams=bigrams,
        dilation=dilation,
        lower_bounding=lower_bounding,
        first_difference=first_difference,
        feature_selection=feature_selection,
        sections=sections,
        max_feature_count=max_feature_count // ensemble_size,  # TODO * 2
        random_state=i,
        return_sparse=False,
        n_jobs=n_jobs,
    )
    return transformer
