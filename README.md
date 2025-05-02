# WEASEL 2.0 - A Random Dilated Dictionary Transform for Fast, Accurate and Memory Constrained Time Series Classification

WEASEL 2.0 combines a novel dilation mapping, small dictionaries and hyper-parameter ensembling to obtain a fast, accurate, and constrained memory TSC. WEASEL 2.0 is significantly more accurate than its predecessor dictionary methods (BOSS, TDE, WEASEL), and in the same group as SotA non-ensemble methods. 

ArXiv-Paper: https://arxiv.org/abs/2301.10194

The paper has been accepted within the journal track at ECML-PKDD 2023: https://link.springer.com/article/10.1007/s10994-023-06395-w
 
### Accuracy against dictionary classifiers
![UCR_accuracy_subset](https://user-images.githubusercontent.com/7783034/214376239-0115e87e-e426-45fc-8f70-1684989745cc.png)

### Accuracy against SotA classifiers
![UCR_accuracy](https://user-images.githubusercontent.com/7783034/214376249-51f49c4a-1691-4d12-97e0-3d6ade7de4e3.png)

### Runtime against SotA classifiers
![UCR_runtime](https://user-images.githubusercontent.com/7783034/214376264-7961db3b-2f24-488f-abbc-d53433ffacbc.png)


## Installation

### Dependencies
```
aeon >= 0.1.0
```

# Installation

The easiest is to use pip to install weasel-classifier.

## a) Install using pip
```
pip install weasel-classifier
```

You can also install  the project from source.

## b) Build from Source

First, download the repository.
```
git clone https://github.com/patrickzib/dictionary.git
```

Change into the directory and build the package from source.
```
pip install .
```


### Train a WEASEL 2.0 classifier

WEASEL v2 follows the aeon pipeline.

```python
from aeon.datasets import load_arrow_head
from weasel.classification.dictionary_based import WEASEL_V2

X_train, y_train = load_arrow_head(split="train", return_type="numpy3d")
X_test, y_test = load_arrow_head(split="test", return_type="numpy3d")
clf = WEASEL_V2(random_state=1379, n_jobs=4)
clf.fit(X_train,y_train)
clf.predict(X_test)
```


## AEON

WEASEL v2 is part of the `aeon` toolkit, too: https://github.com/aeon-toolkit/aeon


## Citing

If you use this algorithm or publication, please cite:

```bibtex
@article{schaefer2023weasel,
  title={WEASEL 2.0: a random dilated dictionary transform for fast, accurate and memory constrained time series classification},
  author={Sch{\"a}fer, Patrick and Leser, Ulf},
  journal={Machine Learning},
  volume={112},
  number={12},
  pages={4763--4788},
  year={2023},
  publisher={Springer}
}
```
