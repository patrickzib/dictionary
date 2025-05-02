# -*- coding: utf-8 -*-
"""WEASEL+MUSE classifier.

A Random Dilated Multivariate Dictionary Transform for Fast, Accurate and
Constrained Memory Time Series Classification.

"""

__author__ = ["patrickzib"]
__all__ = ["MUSE_V2"]

import math
import warnings

import numpy as np
from joblib import Parallel, delayed
from scipy.sparse import hstack
from sklearn.linear_model import RidgeClassifierCV
from sklearn.utils import check_random_state
from aeon.classification.base import BaseClassifier

from weasel.transformations.collection.dictionary_based import SFADilation


class MUSE_V2(BaseClassifier):
    """MUSE (MUltivariate Symbolic Extension) v2.0.

    This is a MUSE+dilation implementation in a very early state.

    Parameters
    ----------
    ensemble_size : int, default=60
        Generates `ensemble_size` many random configurations to generate words.
    max_feature_count : int, default=30_000
       size of the dictionary - number of words to use - if feature_selection set to
       "chi2_top_k" or "random". Else ignored.
    min_window : int , default=4,
        Minimal window size to chose from. A random value is chosen per config.
    max_window : int, default=24,
        Maxmimal window size to chose from. A random value is chosen per config.
    binning_method : {"equi-depth", "equi-width", "information-gain", "kmeans",
                     "quantile"}, default=["equi-depth"]
        the binning method(s) used to derive the breakpoints. A random value is
        chosen per config.
    norm_options : array of bool, default=[False],
        If the array contains True, words are computed over mean-normed TS
        If the array contains False, words are computed over raw TS
        If both are set, words are computed for both.
        A value will be randomly chosen for each parameter-configuration.
    word_lengths : array of int, default=[7, 8],
        Length of the words to compute. A value will be randomly chosen for each
        parameter-configuration.
    use_first_differences: bool, default=True,
        If the array contains True, words are computed over first order differences
        and the raw time seris. If set to False, only the raw time series is used.
    feature_selection: {"chi2_top_k", "none", "random"}, default=chi2
        Sets the feature selections strategy to be used. Large amounts of memory may be
        needed depending on the setting of bigrams (true is more) or
        alpha (larger is more).
        'chi2_top_k' reduces the number of words to at most 'max_feature_count',
        dropping values based on p-value.
        'random' reduces the number to at most 'max_feature_count',
        by randomly selecting features.
        'none' does not apply any feature selection and yields large bag of words
    n_jobs : int, default=1
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
    WEASEL

    References
    ----------
    .. [1] 

    Notes
    -----
    
    Examples
    --------
    >>> from weasel.classification.dictionary_based import MUSE_V2
    >>> from aeon.datasets import load_unit_test
    >>> X_train, y_train = load_unit_test(split="train", return_X_y=True)
    >>> X_test, y_test = load_unit_test(split="test", return_X_y=True)
    >>> clf = MUSE_V2()
    >>> clf.fit(X_train, y_train)
    MUSE_V2(...)
    >>> y_pred = clf.predict(X_test)
    """

    _tags = {
        "capability:multivariate": True,
        "capability:multithreading": True,
        "X_inner_mtype": "numpy3D",  # which mtypes do _fit/_predict support for X?
        "classifier_type": "dictionary",
    }

    def __init__(
            self,
            ensemble_size=60,
            max_feature_count=20_000,
            min_window=4,
            max_window=24,
            binning_strategies=["equi-depth"],
            norm_options=[False],
            word_lengths=[8],
            use_first_differences=True,
            feature_selection="chi2",
            random_state=None,
            n_jobs=1,
    ):

        self.alphabet_sizes = [2]

        self.anova = False
        self.variance = True
        self.use_first_differences = use_first_differences

        self.norm_options = norm_options
        self.word_lengths = word_lengths
        self.min_window = min_window
        self.max_window = max_window
        self.ensemble_size = ensemble_size
        self.max_feature_count = max_feature_count
        self.feature_selection = feature_selection
        self.binning_strategies = binning_strategies

        self.bigrams = False
        self.random_state = random_state

        self.window_sizes = []
        self.SFA_transformers = []
        self.clf = None

        self.n_jobs = n_jobs
        self.total_features_count = 0
        self.feature_selection = feature_selection

        super(MUSE_V2, self).__init__()

    def _fit(self, X, y):
        """Build a WEASEL+MUSE classifiers from the training set (X, y).

        Parameters
        ----------
        X : nested pandas DataFrame of shape [n_instances, 1]
            Nested dataframe with univariate time-series in cells.
        y : array-like, shape = [n_instances]
            The class labels.

        Returns
        -------
        self :
            Reference to self.
        """
        y = np.asarray(y)

        # add first order differences in each dimension to TS
        if self.use_first_differences:
            X = self._add_first_order_differences(X)
        self.n_dims = X.shape[1]

        self.highest_dim_bit = (math.ceil(math.log2(self.n_dims))) + 1

        if self.n_dims == 1:
            warnings.warn(
                "MUSE Warning: Input series is univariate; MUSE is designed for"
                + " multivariate series. It is recommended WEASEL is used instead."
            )

        if self.variance and self.anova:
            raise ValueError("MUSE Warning: Please set either variance or anova.")

        self.series_length = X.shape[-1]
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

        self.window_sizes = np.arange(self.min_window, self.max_window + 1, 1)

        parallel_res = Parallel(n_jobs=self.n_jobs, prefer="threads")(
            delayed(_parallel_fit)(
                ind,
                X,
                y.copy(),  # no clue why, but this copy is required.
                self.window_sizes,
                self.alphabet_sizes,
                self.word_lengths,
                self.norm_options,
                self.use_first_differences,
                self.binning_strategies,
                self.variance,
                self.anova,
                self.bigrams,
                self.n_jobs,
                self.max_feature_count,
                self.ensemble_size,
                self.feature_selection,
                self.random_state,
            )
            # for ind in range(self.n_dims)
            for ind in range(self.ensemble_size)
        )

        self.SFA_transformers = []
        all_words = []
        for (
                sfa_words,
                transformer,
        ) in parallel_res:
            self.SFA_transformers.append(transformer)  # Append! Not Extent! 2d Array
            all_words.extend(sfa_words)

        if type(all_words[0]) is np.ndarray:
            all_words = np.concatenate(all_words, axis=1)
        else:
            all_words = hstack((all_words))

        self.clf = RidgeClassifierCV(alphas=np.logspace(-3, 3, 10))

        self.clf.fit(all_words, y)
        self.total_features_count = all_words.shape[-1]

        if hasattr(self.clf, "best_score_"):
            self.cross_val_score = self.clf.best_score_

        return self

    def _predict(self, X) -> np.ndarray:
        """Predict class values of n instances in X.

        Parameters
        ----------
        X : nested pandas DataFrame of shape [n_instances, 1]
            Nested dataframe with univariate time-series in cells.

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
        X : nested pandas DataFrame of shape [n_instances, 1]
            Nested dataframe with univariate time-series in cells.

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

    def _transform_words(self, X):
        if self.use_first_differences:
            X = self._add_first_order_differences(X)

        parallel_res = Parallel(n_jobs=self.n_jobs, prefer="threads")(
            delayed(_parallel_transform_words)(X, self.SFA_transformers[ind])
            for ind in range(self.ensemble_size)
        )

        all_words = []
        for sfa_words in parallel_res:
            all_words.extend(sfa_words)
        if type(all_words[0]) is np.ndarray:
            all_words = np.concatenate(all_words, axis=1)
        else:
            all_words = hstack((all_words))

        return all_words

    def _add_first_order_differences(self, X):
        X_new = np.zeros((X.shape[0], X.shape[1] * 2, X.shape[2]))
        X_new[:, 0: X.shape[1], :] = X
        diff = np.diff(X, 1)
        X_new[:, X.shape[1]:, : diff.shape[2]] = diff
        return X_new


def _parallel_transform_words(X, SFA_transformers):
    # On each dimension, perform SFA

    all_words = []
    for dim in range(X.shape[1]):
        words = SFA_transformers[dim].transform(X[:, dim])
        all_words.append(words)

    return all_words


def _parallel_fit(
        ind,
        X,
        y,
        window_sizes,
        alphabet_sizes,
        word_lengths,
        norm_options,
        use_first_differences,
        binning_strategies,
        variance,
        anova,
        bigrams,
        n_jobs,
        max_feature_count,
        ensemble_size,
        feature_selection,
        random_state,
):
    if random_state is not None:
        rng = check_random_state(random_state + ind)
    else:
        rng = check_random_state(random_state)

    window_size = rng.choice(window_sizes)
    alphabet_size = rng.choice(alphabet_sizes)
    word_length = min(window_size - 2, rng.choice(word_lengths))
    norm = rng.choice(norm_options)
    first_difference = rng.choice([False])
    binning_strategy = rng.choice(binning_strategies)

    series_length = X.shape[-1]
    dilation = max(
        1,
        np.int32(2 ** rng.uniform(0, np.log2((series_length - 1) / (window_size - 1)))),
    )

    all_words = []
    SFA_transformers = []

    # On each dimension, perform SFA
    for dim in range(X.shape[1]):
        X_dim = X[:, dim]

        transformer = SFADilation(
            variance=variance,
            word_length=word_length,
            alphabet_size=alphabet_size,
            window_size=window_size,
            norm=norm,
            anova=anova,
            binning_method=binning_strategy,
            # remove_repeat_words=remove_repeat_words,
            bigrams=bigrams,
            dilation=dilation,
            # lower_bounding=lower_bounding,
            first_difference=first_difference,
            feature_selection=feature_selection,
            max_feature_count=int(max_feature_count / (ensemble_size * X.shape[1])),
            random_state=ind,
            return_sparse=False,
            n_jobs=n_jobs,
        )
        all_words.append(transformer.fit_transform(X_dim, y))
        SFA_transformers.append(transformer)

    return all_words, SFA_transformers
