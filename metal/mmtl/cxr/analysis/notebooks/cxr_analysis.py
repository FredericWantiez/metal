import os
import json

def load_log_json(log_json):
    """
    Loads MMTL json-formatted log file
    """
    with open(log_json, encoding='utf-8') as data_file:
        data = json.loads(data_file.read())
    return data

def load_results_from_log(log_dir):
    """
    Load all json logs from MMTL log dict
    """
    results = {}
    json_files = [a for a in os.listdir(log_dir) if a.endswith('json')]
    for fl in json_files:
        path = os.path.join(log_dir,fl)
        fl_str = fl.split('.')[0]
        results[fl_str] = load_log_json(path)
    return results

def get_task_name(nm):
    return '_'.join(nm.split('_')[1:])

def get_cxr14_rocs_from_log(chexnet_results, metrics_dict, col_name = 'experiment'):
    output_dict = {}
    for ky, val in metrics_dict.items():
        # Current format: task, split, labelset, metric
        task, split, labelset, metric = ky.split('/')

        # Current task format: DATASET_TASKNAME
        task_name = get_task_name(task)
        labelset_name = get_task_name(labelset)
        
        # Checking if this is a valid result for comparison
        if (task_name == labelset_name) and (task_name.upper() in chexnet_results.index) and (metric == 'roc-auc'):
            output_dict[task_name] = val
            
        # Adding to chexnet results
        chexnet_results[col_name] = chexnet_results.index.map(output_dict)
            
    return chexnet_results 