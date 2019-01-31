import random
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import torch
from scipy.sparse import csr_matrix

# SCRIPT


def generate_dataset(
    k,
    m,
    n,
    L_kwargs={
        "min_r": 1,
        "max_r": 5,
        "min_acc": 0.5,
        "max_acc": 0.9,
        "min_prop": 0.5,
        "max_prop": 0.9,
    },
    X_kwargs={"random": False},
    Y_kwargs={"num_clusters": 4, "min_a": 1, "max_a": 3},
    Z_kwargs={"num_slices": 4, "min_a": 1, "max_a": 2},
    unipolar=False,
    slice_source="lfs",  # ['lfs', 'random', 'conflicts']
    point_size=1.0,
    plotting=True,
    seed=None,
):
    # Set random seed
    if seed:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    # Create canvas
    canvas = Rectangle(0, 10, 0, 10)
    # Create points
    X = create_points(canvas, n, **X_kwargs)
    # Create labels
    Y, label_regions = create_labels(X, k, **Y_kwargs)
    # Create lfs
    L, lf_regions = create_lfs(X, Y, m, unipolar, **L_kwargs)
    # Create slices
    Z, slice_regions = create_slices(
        X, Y, L, slice_source, lf_regions, **Z_kwargs
    )
    if plotting:
        plot_all(L, X, Y, Z)
        plt.show()

    # Restore expected datatypes
    L = csr_matrix(L)
    X = torch.Tensor(X)
    assert isinstance(Y, np.ndarray)
    assert isinstance(Z, np.ndarray)

    if slice_source == "lfs":
        lfs_targeting_regions = []
        for region in slice_regions:
            lf_targeting_region = [
                lf_region.center() == region.center()
                for lf_region in lf_regions
            ]
            lf_idx = lf_targeting_region.index(True)
            lfs_targeting_regions.append(lf_idx)
    else:
        lfs_targeting_regions = None
    return L, X, Y, Z, lfs_targeting_regions


# BUILDING BLOCKS


def flip(y):
    if y == 0:
        raise Exception("Cannot flip the label of an abstain vote")
    else:
        return 1 if y == 2 else 2


class Region(object):
    def contains(self, p):
        """Returns a boolean expressing whether p is in the region"""
        return NotImplementedError(
            "Abstract class: children must implement contains()"
        )

    def center(self):
        """Returns the center of the given region"""
        return NotImplementedError(
            "Abstract class: children must implement center()"
        )

    def __contains__(self, p):
        return self.contains(p)


class Rectangle(Region):
    """A rectangle defined by (t)op, (b)ottom, (l)eft, and (r)ight edges."""

    def __init__(self, b, t, l, r):
        assert b < t
        assert l < r
        self.b = b
        self.t = t
        self.l = l
        self.r = r

    def contains(self, p):
        x, y = p
        return x > self.b and x < self.t and y > self.l and y < self.r

    def center(self):
        x = (self.l + self.r) / 2
        y = (self.b + self.t) / 2
        return (x, y)


class Square(Rectangle):
    def __init__(self, *args):
        super().__init__(*args)
        assert self.t - self.b == self.r - self.l


class Ellipse(Region):
    """An ellipse defined by (h,k), a, and b

    (x - h)^2/a^2 + (y - k)^2/b^2 = 1
    """

    def __init__(self, h, k, a, b):
        self.h = h
        self.k = k
        self.a = a
        self.b = b

    def contains(self, p):
        x, y = p
        return (x - self.h) ** 2 / self.a ** 2 + (
            y - self.k
        ) ** 2 / self.b ** 2 < 1

    def center(self):
        return (self.h, self.k)


class Circle(Ellipse):
    """A circle defined by (h,k) and r"""

    def __init__(self, h, k, r):
        self.h = h
        self.k = k
        self.a = r
        self.b = r


def get_points(X, region):
    """Returns the members of a region and the corresponding indicator vector"""
    indices = [x in region for x in X]
    return X[indices, :], indices


def create_points(rect, n, random=True):
    """Creates n points randomly distributed throughout a canvas (rectangle)"""
    assert isinstance(rect, Rectangle)
    if random:
        x = np.random.uniform(rect.l, rect.r, size=(n, 1))
        y = np.random.uniform(rect.b, rect.t, size=(n, 1))
        X = np.hstack((x, y))
    else:
        X = []
        s = np.ceil(np.sqrt(n))
        for x in np.linspace(rect.l, rect.r, num=s):
            for y in np.linspace(rect.b, rect.t, num=s):
                X.append([x, y])
        X = np.array(X)[:n]
    return X


def create_labels(X, k, num_clusters=4, min_a=1, max_a=3):
    n, d = X.shape
    regions = []
    Y = np.full(n, k)
    for i in range(num_clusters):
        x, y = X[np.random.choice(range(n)), :]
        a = np.random.uniform(min_a, max_a)
        b = np.random.uniform(min_a, max_a)
        region = Ellipse(x, y, a, b)
        regions.append(region)
        Y = assign_y(X, Y, region, 1)
    return Y, regions


def create_lfs(
    X,
    Y,
    m,
    unipolar=False,
    min_r=1,
    max_r=5,
    min_acc=0.5,
    max_acc=0.9,
    min_prop=0.5,
    max_prop=0.9,
):
    n, d = X.shape

    L = []
    accs_hist = []
    props_hist = []
    regions_hist = []

    for j in range(m):
        x, y = X[np.random.choice(range(n)), :]
        r = np.random.uniform(min_r, max_r)
        region = Circle(x, y, r)
        props = np.random.uniform(min_acc, max_acc, d)
        accs = np.random.uniform(min_acc, max_acc, d)
        l = assign_l(X, Y, region, props, accs)
        if unipolar:
            k = 2  # Data generator currently only works with 2 classes
            polarity = np.random.randint(1, k + 1)
            l[l != polarity] = 0
        L.append(l)

        # bookkeeping
        regions_hist.append(region)
        accs_hist.append(accs)
        props_hist.append(props)

    regions_hist = np.array(regions_hist)
    accs_hist = np.array(accs_hist)
    props_hist = np.array(props_hist)
    L = np.array(L).transpose()
    assert L.shape[0] == n and L.shape[1] == m

    return L, regions_hist


def create_slices(
    X,
    Y,
    L,
    slice_source,
    lf_regions=None,
    num_slices=4,
    min_slice_size=20,
    min_a=1,
    max_a=2,
):
    n, d = X.shape
    regions = []
    Z = np.zeros(n)
    satisfied = False

    while not satisfied:
        if slice_source == "random":
            centers = X[np.random.choice(range(n), num_slices), :]
        elif slice_source == "lfs":
            assert lf_regions is not None
            centers = [
                reg.center()
                for reg in np.random.choice(
                    lf_regions, num_slices, replace=False
                )
            ]
        elif slice_source == "conflicts":
            min_dist = max_a * 1.25
            centers = select_conflicted_points(X, L, num_slices, min_dist)
        elif slice_source == "maxmin":
            centers = select_maxmin_points(X, L, num_slices)
        else:
            raise Exception(f"Unrecognized slice_source: {slice_source}")

        for i in range(num_slices):
            x, y = centers[i]
            a = np.random.uniform(min_a, max_a)
            b = np.random.uniform(min_a, max_a)
            region = Ellipse(x, y, a, b)
            regions.append(region)
            Z = assign_y(X, Z, region, i + 1)

        #  Make sure not slices were totally overwritten
        satisfied = (len(set(Z)) == num_slices + 1) and all(
            z > min_slice_size for z in Counter(Z).values()
        )
        if not satisfied:
            print("At least one slice was clobbered. Trying again.")
            Z = np.zeros(n)

    return Z, regions


def select_conflicted_points(X, L, num_slices, min_dist):
    def dist(x, y):
        return np.sqrt(sum((np.array(x) - np.array(y)) ** 2))

    ranked_examples = rank_by_conflict(X, L)
    # Pick centers in most conflicted areas while maintaining distance
    centers = []
    i = 0
    while len(centers) < num_slices:
        score, x = ranked_examples[i]
        if any(dist(x, c) < min_dist for c in centers):
            i += 1
            continue
        centers.append(x)
    return centers


def select_maxmin_points(X, L, num_slices):
    assert num_slices == 2
    ranked_examples = rank_by_conflict(X, L)
    centers = [ranked_examples[0][1], ranked_examples[-1][1]]
    return centers


def rank_by_conflict(X, L):
    def conflict_func(votes):
        assert 0 not in votes
        counter = Counter(votes)
        num_votes = len(votes)
        num_pairs = (num_votes - abs(counter[1] - counter[2])) / 2
        return num_pairs + 0.01 * num_votes

    votes_by_example = []
    for i, x in enumerate(X):
        votes = [int(l) for l in L[i, :] if l != 0]
        votes_by_example.append((x, votes))
    # Rank points by maximum conflicting labels
    ranked_examples = sorted(
        [(conflict_func(votes), x) for (x, votes) in votes_by_example],
        key=lambda x: x[0],
        reverse=True,
    )
    return ranked_examples


def assign_y(X, Y, region, label):
    """Sets y=label for every point in X that falls within the region"""
    for i, x in enumerate(X):
        if x in region:
            Y[i] = label
    return Y.astype(int)


def assign_l(X, Y, region, props, accs):
    """Returns a label vector for an lf in the given region, accs, and props

    prop[l] = P(lambda_i != 0 | y_i = l)
    acc[i]: P(lambda_i = y | y_i = y, lambda_i != 0)
    """
    L_j = np.zeros_like(Y)
    for i, (x, y) in enumerate(zip(X, Y)):
        if x in region:
            if random.random() < props[y - 1]:
                if random.random() < accs[y - 1]:
                    L_j[i] = int(y)
                else:
                    L_j[i] = int(flip(y))
    return L_j.astype(int)


# PLOTTING


def plot_all(L, X, Y, Z, fig_size=12):
    fig, axs = plt.subplots(1, 3, figsize=(fig_size, fig_size))
    plt.sca(axs[0])
    plot_labels(X, Y)
    plt.sca(axs[1])
    # plot_lfs(X, L)
    plot_coverage(X, L)
    plt.sca(axs[2])
    plot_slices(X, Z)


def plot_labels(X, Y, title="Classes", point_size=1.0):
    plt.scatter(X[:, 0], X[:, 1], color=color_map(Y), s=point_size)
    plt.title(title)
    plt.gca().set_aspect("equal", adjustable="box")


def plot_coverage(X, L, title="Coverage", point_size=1.0):
    n, d = X.shape
    num_votes = np.zeros(n)
    num_votes = np.asarray(L.sum(axis=1))
    plt.scatter(X[:, 0], X[:, 1], c=num_votes)
    plt.title(title)
    plt.gca().set_aspect("equal", adjustable="box")


def plot_lfs(X, L):
    # TODO: implement me
    plt.gca().set_aspect("equal", adjustable="box")
    pass


def plot_slices(X, Z, title="Slices", **kwargs):
    plot_labels(X, Z, title=title, **kwargs)


def color_map(Y):
    colors = ["k", "r", "b", "g", "y", "c", "m"]
    return [colors[int(y)] for y in Y]
