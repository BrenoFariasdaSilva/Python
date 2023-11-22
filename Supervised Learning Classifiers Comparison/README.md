<div align="center">
  
# [Digits Recognizer.](https://github.com/BrenoFariasdaSilva/Python/tree/main/Supervised%20Learning%20Classifiers%20Comparison) <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">

</div>

<div align="center">
  
---

This project focuses on using the K-Nearest Neighbors (K-NN), Decision Trees (DT), Support Vector Machines (SVM), MultiLayer Perceptrons (MLP), Random Forest, Naive Bayes and Combining Supervised Learning Algorithms to recognize Digits from 0 to 9. The dataset used for this project can be downloaded from [here](https://drive.google.com/file/d/1fEK7BI02r85NuJM0HD7Hkr_MRmcELaFH/view?usp=sharing) url.

---

</div>

<div align="center">

![GitHub Code Size in Bytes](https://img.shields.io/github/languages/code-size/BrenoFariasdaSilva/Python)
![GitHub Last Commit](https://img.shields.io/github/last-commit/BrenoFariasdaSilva/Python)
![GitHub](https://img.shields.io/github/license/BrenoFariasdaSilva/Python)
![wakatime](https://wakatime.com/badge/github/BrenoFariasdaSilva/Python.svg)

</div>

<div align="center">
  
![RepoBeats Statistics](https://repobeats.axiom.co/api/embed/5907a919937c0e8c81a9c3f0c4ca39c044ba14b0.svg "Repobeats analytics image")

</div>

## Table of Contents
- [Digits Recognizer. ](#digits-recognizer-)
	- [Table of Contents](#table-of-contents)
	- [Introduction](#introduction)
		- [Machine Learning Supervised Classifiers](#machine-learning-supervised-classifiers)
		- [K-Nearest Neighbors (K-NN)](#k-nearest-neighbors-k-nn)
		- [Decision Trees (DT)](#decision-trees-dt)
		- [Support Vector Machines (SVM)](#support-vector-machines-svm)
		- [Multi-Layer Perceptron (MLP)](#multi-layer-perceptron-mlp)
		- [Random Forest](#random-forest)
		- [Naive Bayes](#naive-bayes)
		- [Dataset](#dataset)
		- [Feature Extraction](#feature-extraction)
		- [Data Description](#data-description)
	- [Requirements](#requirements)
	- [Setup](#setup)
		- [Clone the repository](#clone-the-repository)
		- [Install Dependencies](#install-dependencies)
		- [Get Dataset](#get-dataset)
	- [Usage](#usage)
	- [Results](#results)
	- [Contributing](#contributing)
	- [License](#license)

## Introduction

Classification problems in AI involve assigning predefined labels or categories to input data based on its features. The goal is to train models that can generalize patterns from labeled examples to accurately predict the class of new, unseen instances.  
In this project, we use the K-Nearest Neighbors (K-NN), Decision Trees (DT), Support Vector Machines (SVM), MultiLayer Perceptrons (MLP), Random Forest and Combining Supervised Learning Algorithms to recognize Digits from 0 to 9. So, in order to use all of the previously mentioned algorithms to train them to recognize them from the features we extract with the labels we provide, which digit corresponds to which image.
The system will try to predict digit corresponds to which image and will produce as output the accuracy and F1-Score [0 to 100%] and a confusion matrix (N × N) indicating the percentage of system hits and errors among the N classes.

### Machine Learning Supervised Classifiers

This project employs various machine learning supervised classifiers to recognize Digits from 0 to 9. Each classifier has unique characteristics and applications. Below are brief descriptions of the classifiers used in this project.

### K-Nearest Neighbors (K-NN)

K-Nearest Neighbors (K-NN) is a simple and widely used machine learning algorithm that falls under the category of supervised learning. It is a non-parametric and instance-based method used for classification and regression tasks. The fundamental idea behind K-NN is to make predictions based on the majority class or average value of the `k` nearest data points in the feature space. In other words, the algorithm classifies or predicts the output of an instance by considering the labels of its nearest neighbors that are the data points closest to that instance in a Cartesian plane. The K-NN doesn't have an explicit training and classification progress, so its classification time could be very slow, depending on the size of the dataset.  
The impleted K-NN is using the Grid Search to find the best parameters for the model and the parameters used are:
- `metric`: The distance metric to use for the tree. The selected metrics are `"euclidean", "manhattan" and "minkowski"`.
- `n_neighbors`: Number of neighbors to use by default for kneighbors queries -> `1, 3, 5 and 7`.

### Decision Trees (DT)

Decision Trees are a versatile machine learning algorithm used for both classification and regression tasks. They make decisions based on a set of rules learned from the training data.  
Decision Trees recursively split the data into subsets based on the most significant features, creating a tree-like structure. They are interpretable and can capture complex relationships in the data.  
The implemented Decision Tree is using the Grid Search to find the best parameters for the model and the parameters used are:
- `criterion`: The function to measure the quality of a split. The selected criterion are `"gini" and "entropy"`.
- `max_depth`: The maximum depth of the tree. The selected max_depth are `None, 10, 20, 30`.
- `splitter`: The strategy used to choose the split at each node. The selected splitter are `"best" and "random"`.

### Support Vector Machines (SVM)

Support Vector Machines (SVM) is a powerful supervised learning algorithm used for classification and regression tasks. SVM aims to find a hyperplane that best separates data into different classes. It works by maximizing the margin between classes, and it is effective in high-dimensional spaces.  
SVM can handle non-linear relationships through the use of kernel functions.  
The implemented SVM is using the Grid Search to find the best parameters for the model and the parameters used are:
- `C`: Regularization parameter: It test the values from `0.01, 0.1, 1, 10, 100`
- `gamma`: Kernel coefficient. The selected gamma define the influence of input vectors on the margins. The values are from `0.001, 0.01, 0.1, 1, 10`.
- `kernel`: Specifies the kernel type to be used in the algorithm. The selected kernel are `"linear", "poly", "rbf" and "sigmoid"`.

### Multi-Layer Perceptron (MLP)

Multi-Layer Perceptron (MLP) is a type of artificial neural network commonly used for classification and regression tasks. It consists of multiple layers of interconnected nodes (neurons) with each layer having a set of weights. MLPs can capture complex relationships in data and are known for their ability to model non-linear functions.  
The implemented MLP is using the Grid Search to find the best parameters for the model and the parameters used are:
- `alpha`: L2 penalty (regularization term) parameter. The selected alpha are `1e-5, 1e-4 and 1e-3`.
- `hidden_layer_sizes`: The number of neurons in the hidden layers. The selected hidden_layer_sizes are `(100,), (100, 100), (500, 500, 500, 500)`.
- `solver`: The solver for weight optimization. The selected solver are `"adam" and "lbfgs"`.

### Random Forest

Random Forest is an ensemble learning algorithm that combines multiple decision trees to improve predictive accuracy and control overfitting. Each tree in the forest is trained on a random subset of the data, and the final prediction is based on the majority vote or average of the individual tree predictions. Random Forest is robust and effective for both classification and regression tasks.  
The implemented Random Forest is using the Grid Search to find the best parameters for the model and the parameters used are:
- `max_depth`: The maximum depth of the tree. The selected max_depth are `None, 10, 20, 30`.
- `n_estimators`: The number of trees in the forest. The selected n_estimators are `100, 500 and 1000`.

### Naive Bayes

Naive Bayes is a simple yet powerful machine learning algorithm commonly used for classification tasks. It is a probabilistic classifier that makes use of Bayes' Theorem, which states that the probability of A given B is equal to the probability of B given A times the probability of A divided by the probability of B. The algorithm it self is simple and easy to implement, and it is effective in high-dimensional spaces. It is also fast and can be used for both binary and multi-class classification tasks. It has a few drawbacks, such as the assumption of independent features and the zero-frequency problem. Also, it requires a parameter called "var_smoothing" to be set, which is a smoothing parameter that accounts for features not present in the learning samples and prevents zero probabilities in the prediction. "prior" is another parameter that can be set to specify the prior probabilities of the classes, and be aware that the sum of the priors must be 1.
The implemented Naive Bayes is using the Grid Search to find the best parameters for the model and the parameters used are:
- `priors`: Prior probabilities of the classes. The selected priors are `None and [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]`.
- `var_smoothing`: Portion of the largest variance of all features that is added to variances for calculation stability. The selected var_smoothing are `1e-9, 1e-8, 1e-7, 1e-6, 1e-5`.

### Dataset

The dataset used for this project can be found [here](https://drive.google.com/file/d/1fEK7BI02r85NuJM0HD7Hkr_MRmcELaFH/view?usp=sharing).

### Feature Extraction

The read training and test datasets already have the features processed, splitting the images in different grid sizes (1x1, 2x2, 3x3, and 5x5), that already calculated the number of black and white pixels in each region of the split image.

### Data Description

The dataset contains two folders, one named "Train" and another named "Test". Each of this directories have .csv and .txt files. The .csv and .txt have the same content, but in different formats. Each of them have the features extracted from the images. In the used .txt files, each line represents a image and each column represents a region of the image. The last column is the label of the image. The .csv files have the same content, but in a different format, but open them and read it's header, as it is self-explanatory.

## Requirements

- Python 3.x
- Colorama
- Collection
- NumPy
- Scikit-learn
- TQDM

## Setup

### Clone the repository

1. Clone the repository with the following command:

```bash
git clone https://github.com/BrenoFariasdaSilva/Python.git
cd Python/Supervised\ Learning\ Classifiers\ Comparison/
```

### Install Dependencies

1. Install the project dependencies with the following command:

```bash
make dependencies
```

### Get Dataset

1. Download the dataset from [here](https://drive.google.com/file/d/1fEK7BI02r85NuJM0HD7Hkr_MRmcELaFH/view?usp=sharing) and place it in this project directory `(/Python)` and run the following command:

```bash
make dataset
```

This command will give execution permission to the `Setup-Dataset.sh` ShellScript and execute it. The `Setup-Dataset.sh` ShellScript will verify if the dataset compressed file is already in the project directory, if it is, it will just unzip it and delete the compressed file, if it isn't, it will echo a message saying that the dataset compressed file is not in the project directory and will exit.

## Usage

In order to run the project, run the following command:

```bash
make run
```

## Results

The results of the K-Nearest Neighbors (K-NN), Decision Tree (DT), Support Vector Machine (SVM), Multilayer Perceptron (MLP), Random Forest, Naive Bayes and Combining those algorithms models will produce as output the accuracy, F1-Score [0 to 100%], it's Best Params found by the Grid Search, the execution time and a confusion matrix (N × N) indicating the percentage of system hits and errors among the N classes. That results will be shown in the terminal and saved in the `Results` directory.

## Contributing

Code improvement recommendations are very welcome. In order to contribute, submit a Pull Request describing your code improvements.

## License

This project is licensed under the [Apache License 2.0](LICENSE), which allows you to use, modify, distribute, and sublicense this code, even for commercial purposes, as long as you include the original copyright notice and attribute you as the original author for the repository. See the [LICENSE](LICENSE) file for more details.
