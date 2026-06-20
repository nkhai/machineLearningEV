import io
import numpy as np
import matplotlib.pyplot as plt

def plot_learning_curve(client, evals_result, model_name, hdfs_save_path):
    if not evals_result:
        return
    
    # Lấy metric (mặc định của reg:squarederror là rmse)
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
    
    # BƯỚC 1: Lưu biểu đồ vào bộ nhớ đệm (RAM) thay vì ổ cứng
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0) # Đưa con trỏ đọc về đầu file
    plt.close()
    
    # BƯỚC 2: Ghi trực tiếp bộ nhớ đệm này lên HDFS
    # Tham số overwrite=True giúp ghi đè nếu file đã tồn tại
    client.write(hdfs_save_path, buf, overwrite=True)
    print(f"-> Uploaded {model_name} chart to {hdfs_save_path} successfully!")