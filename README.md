# WEASEL 2.0 - A Random Dilated Dictionary Transform for Fast, Accurate and Constrained Memory Time Series Classification

WEASEL 2.0 combines a novel dilation mapping, small dictionaries and hyper-parameter ensembling to obtain a fast, accurate, and constrained memory TSC. WEASEL 2.0 is significantly more accurate than its predecessor dictionary methods (BOSS, TDE, WEASEL), and in the same group as SotA non-ensemble methods. 

### Accuracy against dictionary classifiers
![UCR_accuracy_subset](https://user-images.githubusercontent.com/7783034/214376239-0115e87e-e426-45fc-8f70-1684989745cc.png)

### Accuracy against SotA classifiers
![UCR_accuracy](https://user-images.githubusercontent.com/7783034/214376249-51f49c4a-1691-4d12-97e0-3d6ade7de4e3.png)

### Runtime against SotA classifiers
![UCR_runtime](https://user-images.githubusercontent.com/7783034/214376264-7961db3b-2f24-488f-abbc-d53433ffacbc.png)


## Installation

### Dependencies
```
sktime >= 0.13,<=0.15
```

### Build from Source

First, download the repository.
```
git clone https://github.com/patrickzib/dictionary.git
```

Change into the directory and build the package from source.
```
pip install .
```


### Train a WEASEL 2.0 classifier

WEASEL v2 follows the sktime pipeline.

```python
from sktime.datasets import load_arrow_head
from weasel.classification.dictionary_based import WEASEL_V2

X_train, y_train = load_arrow_head(split="train", return_type="numpy3d")
X_test, y_test = load_arrow_head(split="test", return_type="numpy3d")
clf = WEASEL_V2(random_state=1379, n_jobs=4)
clf.fit(X_train,y_train)
clf.predict(X_test)
```

## Citing

If you use this algorithm or publication, please cite (ArXiv: [https://arxiv.org/abs/2109.13514](https://arxiv.org/abs/2301.10194)):

```bibtex
@article{schaefer2023weasel2,
  author = {Schäfer, Patrick and Leser, Ulf},
  title = {{WEASEL 2.0 -- A Random Dilated Dictionary Transform for Fast, Accurate and Memory Constrained Time Series Classification}},
  journal={arXiv preprint arXiv:2301.10194},
  year = {2023},
}
```
