from functools import partial

import torch
import torch.nn as nn
import torch.nn.functional as F

from metal.mmtl.modules import (
    BertBinaryHead,
    BertEncoder,
    BertMulticlassHead,
    BertRegressionHead,
)
from metal.mmtl.scorer import Scorer
from metal.mmtl.task import Task
from metal.mmtl.utils.dataset_utils import get_all_dataloaders
from metal.mmtl.utils.metrics import matthews_corr, pearson_corr, spearman_corr


def create_task(
    task_name,
    bert_model="bert-base-uncased",
    split_prop=0.8,
    max_len=512,
    dl_kwargs={},
    bert_kwargs={},
    bert_output_dim=768,
    max_datapoints=-1,
):
    dataloaders = get_all_dataloaders(
        task_name,
        bert_model,
        max_len=max_len,
        dl_kwargs=dl_kwargs,
        split_prop=split_prop,
        max_datapoints=max_datapoints,
    )
    bert_encoder = BertEncoder(bert_model, **bert_kwargs)

    if task_name == "COLA":

        scorer = Scorer(
            standard_metrics=["accuracy"],
            custom_train_funcs=[matthews_corr],
            custom_valid_funcs=[matthews_corr],
        )
        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertBinaryHead(bert_output_dim),
            scorer,
        )

    if task_name == "SST2":

        return Task(
            task_name, dataloaders, bert_encoder, BertBinaryHead(bert_output_dim)
        )

    elif task_name == "MNLI":

        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertMulticlassHead(bert_output_dim, 3),
            Scorer(standard_metrics=["accuracy"]),
        )

    elif task_name == "RTE":

        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertBinaryHead(bert_output_dim),
            Scorer(standard_metrics=["accuracy"]),
        )

    elif task_name == "WNLI":

        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertBinaryHead(bert_output_dim),
            Scorer(standard_metrics=["accuracy"]),
        )

    elif task_name == "QQP":

        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertBinaryHead(bert_output_dim),
            Scorer(standard_metrics=["accuracy"]),
        )

    elif task_name == "MRPC":

        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertBinaryHead(bert_output_dim),
            Scorer(standard_metrics=["accuracy"]),
        )

    elif task_name == "STSB":
        scorer = Scorer(
            standard_metrics=[],
            custom_train_funcs=[pearson_corr, spearman_corr],
            custom_valid_funcs=[pearson_corr, spearman_corr],
        )

        # x -> sigmoid -> [0,1], and compute mse_loss (y \in [0,1])
        loss_hat_func = lambda x, y: F.mse_loss(torch.sigmoid(x), y)

        return Task(
            task_name,
            dataloaders,
            bert_encoder,
            BertRegressionHead(bert_output_dim),
            scorer,
            loss_hat_func=loss_hat_func,
            output_hat_func=torch.sigmoid,
        )

    elif task_name == "QNLI":
        qnli_head = nn.Linear(bert_output_dim, 2, bias=False)
        return Task(
            name="QNLI",
            data_loaders=dataloaders,
            input_module=bert_encoder,
            head_module=qnli_head,
            scorer=Scorer(standard_metrics=["accuracy"]),
            loss_hat_func=lambda Y_hat, Y: F.cross_entropy(Y_hat, Y - 1),
            output_hat_func=partial(F.softmax, dim=1),
        )

    elif task_name == "SNLI":
        raise NotImplementedError

    elif task_name == "SciTail":
        raise NotImplementedError

    else:
        raise ValueError(f"{task_name} does not exist.")