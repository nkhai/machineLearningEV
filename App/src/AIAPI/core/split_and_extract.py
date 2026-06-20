import numpy as np
from collections import defaultdict


def split_train_test_by_car(dataset, train_ratio=0.8, seed=168):
    rng = np.random.RandomState(seed)
    car_map = defaultdict(list)

    for sample in dataset:
        _, meta, _ = sample
        car_id = meta["car_id"]
        car_map[car_id].append(sample)

    cars = list(car_map.keys())
    rng.shuffle(cars)

    n_train = int(len(cars) * train_ratio)
    train_cars_set = set(cars[:n_train])

    train_set, test_set = [], []
    for car, samples in car_map.items():
        if car in train_cars_set:
            train_set.extend(samples)
        else:
            test_set.extend(samples)

    return train_set, test_set


def extract_features_3d(dataset):
    if not dataset:
        return np.array([]), np.array([])
    window_size, num_features = dataset[0][0].shape

    X = np.zeros((len(dataset), window_size, num_features), dtype=np.float32)
    y = np.zeros(len(dataset), dtype=np.float32)

    # Fixed: Added _ variable to hold the 3rd value
    for i, (x, meta, _) in enumerate(dataset):
        X[i] = x
        y[i] = meta["actual_max_capacity_Ah"]
    return X, y


def extract_features_2d(dataset):
    if not dataset:
        return np.array([]), np.array([])

    sample_shape = dataset[0][0].shape
    flattened_dim = sample_shape[0] * sample_shape[1]

    X = np.zeros((len(dataset), flattened_dim), dtype=np.float32)
    y = np.zeros(len(dataset), dtype=np.float32)

    # Fixed: Added _ variable to hold the 3rd value
    for i, (x, meta, _) in enumerate(dataset):
        X[i] = x.flatten()
        y[i] = meta["actual_max_capacity_Ah"]
    return X, y