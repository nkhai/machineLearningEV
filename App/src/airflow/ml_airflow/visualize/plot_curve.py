import io
import numpy as np
import matplotlib.pyplot as plt

def plot_learning_curve(client, evals_result, model_name, hdfs_save_path):
    if not evals_result:
        return
    
    # Get metric (default for reg:squarederror is rmse)
    metric_name = list(evals_result['train'].keys())[0]
    
    epochs = len(evals_result['train'][metric_name])
    x_axis = range(0, epochs)
    
    plt.figure(figsize=(10, 6))
    plt.plot(x_axis, evals_result['train'][metric_name], label='Train Loss (RMSE)')
    
    if 'val' in evals_result:
        plt.plot(x_axis, evals_result['val'][metric_name], label='Val Loss (RMSE)')
        
    plt.legend()
    plt.ylabel('RMSE')
    plt.xlabel('Boosting Rounds (Iterations)')
    plt.title(f'XGBoost Learning Curve - {model_name}')
    plt.grid(True)
    
    # STEP 1: Save chart to RAM buffer instead of disk
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0) # Move read pointer to start of file
    plt.close()
    
    # STEP 2: Write this buffer directly to HDFS
    # overwrite=True parameter allows overwriting if file already exists
    client.write(hdfs_save_path, buf, overwrite=True)
    print(f"-> Uploaded {model_name} chart to {hdfs_save_path} successfully!")