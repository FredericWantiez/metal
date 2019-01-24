import numpy as np
import torch
from scipy.sparse import csr_matrix
from scipy.special import expit
from termcolor import colored
from torch.utils.data.sampler import WeightedRandomSampler
from tqdm import tqdm

from metal.metrics import accuracy_score, metric_score


def get_L_weights_from_targeting_lfs_idx(m, targeting_lfs_idx, multiplier):
    L_weights = np.ones(m)
    L_weights[targeting_lfs_idx] = multiplier
    L_weights = list(L_weights)
    return L_weights


def slice_mask_from_targeting_lfs_idx(L, targeting_lfs_idx):
    if isinstance(L, csr_matrix):
        L = np.array(L.todense())

    mask = np.sum(L[:, targeting_lfs_idx], axis=1) > 0
    return mask.squeeze()


def get_weighted_sampler_via_targeting_lfs(
    L_train, targeting_lfs_idx, upweight_multiplier
):
    """ Creates a weighted sampler that upweights values based on whether they are targeted
    by LFs. Intuitively, upweights examples that might be "contributing" to slice performance,
    as defined by label matrix.

    Args:
        L_train: label matrix
        targeting_lfs_idx: list of ints pointing to the columns of the L_matrix
            that are targeting the slice of interest.
        upweight_multiplier: multiplier to upweight samples covered by targeting_lfs_idx
    Returns:
        WeightedSampler to be pasesd into Dataloader

    """

    upweighting_mask = slice_mask_from_targeting_lfs_idx(
        L_train, targeting_lfs_idx
    )
    weights = np.ones(upweighting_mask.shape)
    weights[upweighting_mask] = upweight_multiplier
    num_samples = int(sum(weights))
    return WeightedRandomSampler(weights, num_samples)


def compute_lf_accuracies(L_dev, Y_dev):
    """ Returns len m list of accuracies corresponding to each lf"""
    accs = []
    m = L_dev.shape[1]
    for lf_idx in range(m):
        voted_idx = L_dev[:, lf_idx] != 0
        accs.append(accuracy_score(L_dev[voted_idx, lf_idx], Y_dev[voted_idx]))
    return accs


def generate_weak_labels(L_train, weights=None, verbose=False, seed=0):
    """ Combines L_train into weak labels either using accuracies of LFs or LabelModel."""
    L_train_np = L_train.copy()

    if weights is not None:
        if verbose:
            print("Using weights to combine L_train:", weights)

        weights = np.array(weights)
        if np.any(weights >= 1):
            weights = weights / np.max(
                weights + 1e-5
            )  # add epsilon to avoid 1.0 weight

        # Combine with weights computed from LF accuracies
        w = np.log(weights / (1 - weights))
        w[np.abs(w) == np.inf] = 0  # set weights from acc==0 to 0

        # L_train_pt = torch.from_numpy(L_train.astype(np.float32))
        # TODO: add multiclass support
        L_train_np[L_train_np == 2] = -1
        label_probs = expit(2 * L_train_np @ w).reshape(-1, 1)
        Y_weak = np.concatenate((label_probs, 1 - label_probs), axis=1)
    else:
        if verbose:
            print("Training Snorkel label model...")
        from metal.contrib.backends.snorkel_gm_wrapper import (
            SnorkelLabelModel as LabelModel,
        )

        label_model = LabelModel()
        label_model.train_model(L_train_np.astype(np.int8))
        Y_weak = label_model.predict_proba(L_train)

    return Y_weak


def compare_LF_slices(
    Yp_ours, Yp_base, Y, L_test, LFs, metric="accuracy", delta_threshold=0
):
    """Compares improvements between `ours` over `base` predictions."""

    improved = 0
    for LF_num, LF in enumerate(LFs):
        LF_covered_idx = np.where(L_test[:, LF_num] != 0)[0]
        ours_score = metric_score(
            Y[LF_covered_idx], Yp_ours[LF_covered_idx], metric
        )
        base_score = metric_score(
            Y[LF_covered_idx], Yp_base[LF_covered_idx], metric
        )

        delta = ours_score - base_score
        # filter out trivial differences
        if abs(delta) < delta_threshold:
            continue

        to_print = (
            f"[{LF.__name__}] delta: {delta:.4f}, "
            f"OURS: {ours_score:.4f}, BASE: {base_score:.4f}"
        )

        if ours_score > base_score:
            improved += 1
            print(colored(to_print, "green"))
        elif ours_score < base_score:
            print(colored(to_print, "red"))
        else:
            print(to_print)

    print(f"improved {improved}/{len(LFs)}")
