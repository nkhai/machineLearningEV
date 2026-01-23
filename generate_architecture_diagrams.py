"""
Generate Architecture Diagrams for Battery Dataset Analysis Project
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import numpy as np

# Set style
plt.rcParams['font.size'] = 10
plt.rcParams['font.family'] = 'sans-serif'

def create_overall_architecture():
    """Create overall system architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(8, 9.5, 'Battery Health Monitoring System Architecture', 
            ha='center', fontsize=18, fontweight='bold')
    
    # Data Layer
    data_box = FancyBboxPatch((0.5, 7), 3, 1.5, 
                               boxstyle="round,pad=0.1", 
                               edgecolor='#2E86AB', facecolor='#A7C7E7', linewidth=2)
    ax.add_patch(data_box)
    ax.text(2, 7.75, 'Data Layer', ha='center', fontsize=12, fontweight='bold')
    ax.text(2, 7.35, '• Battery Dataset 1/2/3\n• Time Series Data\n• Metadata & Labels', 
            ha='center', fontsize=9, va='top')
    
    # Preprocessing Layer
    prep_box = FancyBboxPatch((4.5, 7), 3, 1.5,
                              boxstyle="round,pad=0.1",
                              edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(prep_box)
    ax.text(6, 7.75, 'Preprocessing', ha='center', fontsize=12, fontweight='bold')
    ax.text(6, 7.35, '• Five-Fold Split\n• Normalization\n• Feature Engineering', 
            ha='center', fontsize=9, va='top')
    
    # Model Layer - Anomaly Detection
    models_y = 4.5
    model_width = 2.2
    model_height = 1.8
    
    # DyAD
    dyad_box = FancyBboxPatch((0.3, models_y), model_width, model_height,
                              boxstyle="round,pad=0.1",
                              edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(dyad_box)
    ax.text(0.3 + model_width/2, models_y + model_height - 0.25, 'DyAD (Ours)', 
            ha='center', fontsize=11, fontweight='bold')
    ax.text(0.3 + model_width/2, models_y + 0.9, '• Dynamic VAE\n• Reconstruction\n• Forecasting', 
            ha='center', fontsize=8, va='center')
    
    # MTAD-GAT
    mtad_box = FancyBboxPatch((2.8, models_y), model_width, model_height,
                              boxstyle="round,pad=0.1",
                              edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(mtad_box)
    ax.text(2.8 + model_width/2, models_y + model_height - 0.25, 'MTAD-GAT', 
            ha='center', fontsize=11, fontweight='bold')
    ax.text(2.8 + model_width/2, models_y + 0.9, '• Graph Attention\n• Temporal Conv\n• Multi-head', 
            ha='center', fontsize=8, va='center')
    
    # GDN
    gdn_box = FancyBboxPatch((5.3, models_y), model_width, model_height,
                             boxstyle="round,pad=0.1",
                             edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(gdn_box)
    ax.text(5.3 + model_width/2, models_y + model_height - 0.25, 'GDN', 
            ha='center', fontsize=11, fontweight='bold')
    ax.text(5.3 + model_width/2, models_y + 0.9, '• Graph Neural Net\n• Attention Mech.\n• Deviation Scores', 
            ha='center', fontsize=8, va='center')
    
    # LSTM-AD
    lstm_box = FancyBboxPatch((7.8, models_y), model_width, model_height,
                              boxstyle="round,pad=0.1",
                              edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(lstm_box)
    ax.text(7.8 + model_width/2, models_y + model_height - 0.25, 'LSTM-AD', 
            ha='center', fontsize=11, fontweight='bold')
    ax.text(7.8 + model_width/2, models_y + 0.9, '• LSTM Encoder\n• LSTM Decoder\n• Autoencoder', 
            ha='center', fontsize=8, va='center')
    
    # Traditional Methods
    trad_box = FancyBboxPatch((10.3, models_y), model_width, model_height,
                              boxstyle="round,pad=0.1",
                              edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(trad_box)
    ax.text(10.3 + model_width/2, models_y + model_height - 0.25, 'Traditional', 
            ha='center', fontsize=11, fontweight='bold')
    ax.text(10.3 + model_width/2, models_y + 0.9, '• AutoEncoder\n• Deep SVDD\n• PyOD', 
            ha='center', fontsize=8, va='center')
    
    # Capacity Estimation
    cap_box = FancyBboxPatch((12.8, models_y), model_width, model_height,
                             boxstyle="round,pad=0.1",
                             edgecolor='#6A4C93', facecolor='#C9ADA7', linewidth=2)
    ax.add_patch(cap_box)
    ax.text(12.8 + model_width/2, models_y + model_height - 0.25, 'Capacity Est.', 
            ha='center', fontsize=11, fontweight='bold')
    ax.text(12.8 + model_width/2, models_y + 0.9, '• LSTM Net\n• MLP\n• Gated CNN', 
            ha='center', fontsize=8, va='center')
    
    # Evaluation Layer
    eval_box = FancyBboxPatch((1, 2.5), 6, 1.2,
                              boxstyle="round,pad=0.1",
                              edgecolor='#BC4749', facecolor='#FFD6BA', linewidth=2)
    ax.add_patch(eval_box)
    ax.text(4, 3.4, 'Anomaly Detection Evaluation', ha='center', fontsize=12, fontweight='bold')
    ax.text(4, 2.9, '• AUROC Score • Threshold Analysis • ROC Curves', 
            ha='center', fontsize=9)
    
    cap_eval_box = FancyBboxPatch((9, 2.5), 6, 1.2,
                                  boxstyle="round,pad=0.1",
                                  edgecolor='#6A4C93', facecolor='#DDA15E', linewidth=2)
    ax.add_patch(cap_eval_box)
    ax.text(12, 3.4, 'Capacity Estimation Evaluation', ha='center', fontsize=12, fontweight='bold')
    ax.text(12, 2.9, '• MSE • RMSE • R² Score', 
            ha='center', fontsize=9)
    
    # Results Layer
    result_box = FancyBboxPatch((2, 0.5), 12, 1.2,
                                boxstyle="round,pad=0.1",
                                edgecolor='#386641', facecolor='#A7C957', linewidth=2)
    ax.add_patch(result_box)
    ax.text(8, 1.35, 'Results & Visualization', ha='center', fontsize=12, fontweight='bold')
    ax.text(8, 0.85, '• Jupyter Notebooks • Performance Metrics • Comparison Tables • Visualizations', 
            ha='center', fontsize=9)
    
    # Arrows
    # Data to Preprocessing
    arrow1 = FancyArrowPatch((3.5, 7.75), (4.5, 7.75),
                            arrowstyle='->', mutation_scale=20, linewidth=2, color='black')
    ax.add_patch(arrow1)
    
    # Preprocessing to Models
    for x in [1.4, 3.9, 6.4, 8.9, 11.4, 13.9]:
        arrow = FancyArrowPatch((6, 7), (x, models_y + model_height),
                               arrowstyle='->', mutation_scale=15, linewidth=1.5, color='gray', alpha=0.6)
        ax.add_patch(arrow)
    
    # Models to Evaluation
    for x_model in [1.4, 3.9, 6.4, 8.9, 11.4]:
        arrow = FancyArrowPatch((x_model, models_y), (4, 3.7),
                               arrowstyle='->', mutation_scale=15, linewidth=1.5, color='gray', alpha=0.6)
        ax.add_patch(arrow)
    
    arrow = FancyArrowPatch((13.9, models_y), (12, 3.7),
                           arrowstyle='->', mutation_scale=15, linewidth=1.5, color='gray', alpha=0.6)
    ax.add_patch(arrow)
    
    # Evaluation to Results
    arrow_eval1 = FancyArrowPatch((4, 2.5), (6, 1.7),
                                  arrowstyle='->', mutation_scale=20, linewidth=2, color='black')
    ax.add_patch(arrow_eval1)
    arrow_eval2 = FancyArrowPatch((12, 2.5), (10, 1.7),
                                  arrowstyle='->', mutation_scale=20, linewidth=2, color='black')
    ax.add_patch(arrow_eval2)
    
    plt.tight_layout()
    plt.savefig('architecture_overall.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("✓ Generated: architecture_overall.png")
    plt.close()


def create_dyad_architecture():
    """Create DyAD model architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.5, 'DyAD: Dynamic Variational Autoencoder Architecture', 
            ha='center', fontsize=16, fontweight='bold')
    
    # Input
    input_box = FancyBboxPatch((1, 7.5), 2, 1,
                               boxstyle="round,pad=0.1",
                               edgecolor='#2E86AB', facecolor='#A7C7E7', linewidth=2)
    ax.add_patch(input_box)
    ax.text(2, 8.3, 'Input', ha='center', fontsize=11, fontweight='bold')
    ax.text(2, 7.85, 'Time Series\n(volt, current,\nsoc, temp)', 
            ha='center', fontsize=8)
    
    # Encoder Filter
    enc_filter_box = FancyBboxPatch((3.5, 7.5), 1.8, 1,
                                    boxstyle="round,pad=0.1",
                                    edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(enc_filter_box)
    ax.text(4.4, 8.2, 'Encoder\nFilter', ha='center', fontsize=10, fontweight='bold')
    
    # Encoder RNN
    encoder_box = FancyBboxPatch((5.8, 7.5), 2, 1,
                                 boxstyle="round,pad=0.1",
                                 edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(encoder_box)
    ax.text(6.8, 8.2, 'Encoder RNN', ha='center', fontsize=11, fontweight='bold')
    ax.text(6.8, 7.8, '(LSTM/GRU)', ha='center', fontsize=8)
    
    # Latent Space
    mean_box = FancyBboxPatch((8.3, 8), 1.5, 0.6,
                              boxstyle="round,pad=0.05",
                              edgecolor='#6A4C93', facecolor='#C9ADA7', linewidth=2)
    ax.add_patch(mean_box)
    ax.text(9.05, 8.3, 'μ (Mean)', ha='center', fontsize=9, fontweight='bold')
    
    logv_box = FancyBboxPatch((8.3, 7.2), 1.5, 0.6,
                              boxstyle="round,pad=0.05",
                              edgecolor='#6A4C93', facecolor='#C9ADA7', linewidth=2)
    ax.add_patch(logv_box)
    ax.text(9.05, 7.5, 'log σ²', ha='center', fontsize=9, fontweight='bold')
    
    # Reparameterization
    reparam_circle = Circle((10.5, 7.9), 0.5, edgecolor='#BC4749', 
                            facecolor='#FFD6BA', linewidth=2)
    ax.add_patch(reparam_circle)
    ax.text(10.5, 7.9, 'z = μ + σε', ha='center', va='center', fontsize=8)
    
    # Latent to Hidden
    lat2hid_box = FancyBboxPatch((11.5, 7.5), 1.8, 1,
                                 boxstyle="round,pad=0.1",
                                 edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(lat2hid_box)
    ax.text(12.4, 8.2, 'Latent to\nHidden', ha='center', fontsize=10, fontweight='bold')
    
    # Decoder
    dec_filter_box = FancyBboxPatch((3.5, 5.5), 1.8, 1,
                                    boxstyle="round,pad=0.1",
                                    edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(dec_filter_box)
    ax.text(4.4, 6.2, 'Decoder\nFilter', ha='center', fontsize=10, fontweight='bold')
    
    decoder_box = FancyBboxPatch((5.8, 5.5), 2, 1,
                                 boxstyle="round,pad=0.1",
                                 edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(decoder_box)
    ax.text(6.8, 6.2, 'Decoder RNN', ha='center', fontsize=11, fontweight='bold')
    ax.text(6.8, 5.8, '(LSTM/GRU)', ha='center', fontsize=8)
    
    # Output Projection
    output_proj_box = FancyBboxPatch((8.3, 5.5), 2, 1,
                                     boxstyle="round,pad=0.1",
                                     edgecolor='#386641', facecolor='#A7C957', linewidth=2)
    ax.add_patch(output_proj_box)
    ax.text(9.3, 6.2, 'Output\nProjection', ha='center', fontsize=10, fontweight='bold')
    
    # Reconstruction Output
    recon_box = FancyBboxPatch((10.8, 5.5), 2, 1,
                               boxstyle="round,pad=0.1",
                               edgecolor='#2E86AB', facecolor='#A7C7E7', linewidth=2)
    ax.add_patch(recon_box)
    ax.text(11.8, 6.2, 'Reconstructed', ha='center', fontsize=11, fontweight='bold')
    ax.text(11.8, 5.8, 'Output', ha='center', fontsize=9)
    
    # Forecasting Branch
    forecast_box = FancyBboxPatch((8.3, 3.5), 2, 0.8,
                                  boxstyle="round,pad=0.1",
                                  edgecolor='#6A4C93', facecolor='#DDA15E', linewidth=2)
    ax.add_patch(forecast_box)
    ax.text(9.3, 3.9, 'Forecasting\nBranch', ha='center', fontsize=10, fontweight='bold')
    
    # Loss Functions
    loss_y = 1.5
    recon_loss = FancyBboxPatch((1, loss_y), 3, 0.8,
                                boxstyle="round,pad=0.1",
                                edgecolor='#BC4749', facecolor='#FFE5EC', linewidth=2)
    ax.add_patch(recon_loss)
    ax.text(2.5, loss_y + 0.4, 'Reconstruction Loss', ha='center', fontsize=9, fontweight='bold')
    
    kl_loss = FancyBboxPatch((4.5, loss_y), 3, 0.8,
                             boxstyle="round,pad=0.1",
                             edgecolor='#BC4749', facecolor='#FFE5EC', linewidth=2)
    ax.add_patch(kl_loss)
    ax.text(6, loss_y + 0.4, 'KL Divergence', ha='center', fontsize=9, fontweight='bold')
    
    forecast_loss = FancyBboxPatch((8, loss_y), 3, 0.8,
                                   boxstyle="round,pad=0.1",
                                   edgecolor='#BC4749', facecolor='#FFE5EC', linewidth=2)
    ax.add_patch(forecast_loss)
    ax.text(9.5, loss_y + 0.4, 'Forecasting Loss', ha='center', fontsize=9, fontweight='bold')
    
    # Arrows - Forward Pass
    arrows_forward = [
        ((3, 8), (3.5, 8)),
        ((5.3, 8), (5.8, 8)),
        ((7.8, 8.3), (8.3, 8.3)),
        ((7.8, 7.5), (8.3, 7.5)),
        ((9.8, 8.3), (10, 8.2)),
        ((9.8, 7.5), (10, 7.6)),
        ((11, 7.9), (11.5, 7.9)),
        ((3, 6), (3.5, 6)),
        ((5.3, 6), (5.8, 6)),
        ((7.8, 6), (8.3, 6)),
        ((10.3, 6), (10.8, 6)),
    ]
    
    for start, end in arrows_forward:
        arrow = FancyArrowPatch(start, end,
                               arrowstyle='->', mutation_scale=15, linewidth=1.5, color='black')
        ax.add_patch(arrow)
    
    # Decoder input from latent
    arrow_dec = FancyArrowPatch((12.4, 7.5), (6.8, 6.5),
                                arrowstyle='->', mutation_scale=15, linewidth=1.5, 
                                color='#BC4749', linestyle='--')
    ax.add_patch(arrow_dec)
    
    # To forecast
    arrow_forecast = FancyArrowPatch((9.05, 7.2), (9.3, 4.3),
                                     arrowstyle='->', mutation_scale=15, linewidth=1.5, 
                                     color='#6A4C93', linestyle='--')
    ax.add_patch(arrow_forecast)
    
    # To losses
    arrow_loss1 = FancyArrowPatch((11.8, 5.5), (2.5, 2.3),
                                  arrowstyle='->', mutation_scale=15, linewidth=1.2, 
                                  color='gray', alpha=0.6)
    ax.add_patch(arrow_loss1)
    
    arrow_loss2 = FancyArrowPatch((9.05, 7.2), (6, 2.3),
                                  arrowstyle='->', mutation_scale=15, linewidth=1.2, 
                                  color='gray', alpha=0.6)
    ax.add_patch(arrow_loss2)
    
    arrow_loss3 = FancyArrowPatch((9.3, 3.5), (9.5, 2.3),
                                  arrowstyle='->', mutation_scale=15, linewidth=1.2, 
                                  color='gray', alpha=0.6)
    ax.add_patch(arrow_loss3)
    
    # Add annotations
    ax.text(7, 0.5, 'Training: VAE with reconstruction + KL divergence + forecasting loss\n' +
                    'Testing: Reconstruction error + Forecasting error for anomaly detection',
            ha='center', fontsize=9, style='italic', 
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig('architecture_dyad.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("✓ Generated: architecture_dyad.png")
    plt.close()


def create_data_flow_diagram():
    """Create data flow and processing pipeline"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(7, 7.5, 'Data Processing and Training Pipeline', 
            ha='center', fontsize=16, fontweight='bold')
    
    # Stage 1: Raw Data
    stage1_y = 6
    raw_data_box = FancyBboxPatch((0.5, stage1_y), 2.5, 1,
                                  boxstyle="round,pad=0.1",
                                  edgecolor='#2E86AB', facecolor='#A7C7E7', linewidth=2)
    ax.add_patch(raw_data_box)
    ax.text(1.75, stage1_y + 0.7, 'Raw Dataset', ha='center', fontsize=10, fontweight='bold')
    ax.text(1.75, stage1_y + 0.3, 'PKL Files\n(data + metadata)', ha='center', fontsize=8)
    
    # Stage 2: Split Generation
    split_box = FancyBboxPatch((3.5, stage1_y), 2.5, 1,
                               boxstyle="round,pad=0.1",
                               edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(split_box)
    ax.text(4.75, stage1_y + 0.7, 'Five-Fold Split', ha='center', fontsize=10, fontweight='bold')
    ax.text(4.75, stage1_y + 0.3, 'all_car_dict.npz\nind_odd_dict.npz', ha='center', fontsize=8)
    
    # Stage 3: Brand Selection
    brand_box = FancyBboxPatch((6.5, stage1_y), 2.5, 1,
                               boxstyle="round,pad=0.1",
                               edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(brand_box)
    ax.text(7.75, stage1_y + 0.7, 'Brand Selection', ha='center', fontsize=10, fontweight='bold')
    ax.text(7.75, stage1_y + 0.3, 'Brand 1/2/3/All', ha='center', fontsize=8)
    
    # Stage 4: Preprocessing
    preproc_box = FancyBboxPatch((9.5, stage1_y), 2.5, 1,
                                 boxstyle="round,pad=0.1",
                                 edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(preproc_box)
    ax.text(10.75, stage1_y + 0.7, 'Preprocessing', ha='center', fontsize=10, fontweight='bold')
    ax.text(10.75, stage1_y + 0.3, 'Normalize\nSliding Window', ha='center', fontsize=8)
    
    # Arrows for stage 1-4
    for i in range(3):
        x_start = 3 + i * 3.5
        arrow = FancyArrowPatch((x_start, stage1_y + 0.5), (x_start + 0.5, stage1_y + 0.5),
                               arrowstyle='->', mutation_scale=20, linewidth=2, color='black')
        ax.add_patch(arrow)
    
    # Stage 5: Model Training (Multiple Paths)
    train_y = 3.5
    models = [
        ('DyAD', 1, '#F2CC8F'),
        ('MTAD-GAT', 3.5, '#F2CC8F'),
        ('GDN', 6, '#F2CC8F'),
        ('LSTM-AD', 8.5, '#F2CC8F'),
        ('AE/SVDD', 11, '#F2CC8F')
    ]
    
    for name, x, color in models:
        model_box = FancyBboxPatch((x, train_y), 2, 1,
                                   boxstyle="round,pad=0.1",
                                   edgecolor='#BC4749', facecolor=color, linewidth=2)
        ax.add_patch(model_box)
        ax.text(x + 1, train_y + 0.7, 'Train', ha='center', fontsize=9, fontweight='bold')
        ax.text(x + 1, train_y + 0.3, name, ha='center', fontsize=8)
        
        # Arrow from preprocessing
        arrow = FancyArrowPatch((10.75, stage1_y), (x + 1, train_y + 1),
                               arrowstyle='->', mutation_scale=15, linewidth=1.5, 
                               color='gray', alpha=0.6)
        ax.add_patch(arrow)
    
    # Stage 6: Feature Extraction / Testing
    test_y = 1.8
    for i, (name, x, _) in enumerate(models):
        test_box = FancyBboxPatch((x, test_y), 2, 0.8,
                                  boxstyle="round,pad=0.1",
                                  edgecolor='#6A4C93', facecolor='#C9ADA7', linewidth=2)
        ax.add_patch(test_box)
        ax.text(x + 1, test_y + 0.4, 'Test/Extract', ha='center', fontsize=8)
        
        # Arrow from training to testing
        arrow = FancyArrowPatch((x + 1, train_y), (x + 1, test_y + 0.8),
                               arrowstyle='->', mutation_scale=15, linewidth=1.5, color='black')
        ax.add_patch(arrow)
    
    # Stage 7: Evaluation
    eval_box = FancyBboxPatch((4, 0.3), 6, 0.9,
                              boxstyle="round,pad=0.1",
                              edgecolor='#386641', facecolor='#A7C957', linewidth=2)
    ax.add_patch(eval_box)
    ax.text(7, 0.9, 'Evaluation & Comparison', ha='center', fontsize=11, fontweight='bold')
    ax.text(7, 0.5, 'AUROC, Threshold Analysis, Visualization', ha='center', fontsize=8)
    
    # Arrows to evaluation
    for _, x, _ in models:
        arrow = FancyArrowPatch((x + 1, test_y), (7, 1.2),
                               arrowstyle='->', mutation_scale=15, linewidth=1.2, 
                               color='gray', alpha=0.6)
        ax.add_patch(arrow)
    
    plt.tight_layout()
    plt.savefig('architecture_dataflow.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("✓ Generated: architecture_dataflow.png")
    plt.close()


def create_model_comparison_chart():
    """Create model comparison chart"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    models = ['DyAD\n(Ours)', 'MTAD-GAT', 'GDN', 'LSTM-AD', 'AutoEncoder', 'DeepSVDD']
    
    # Characteristics (hypothetical scores for visualization)
    complexity = [8, 7, 6, 5, 3, 4]
    performance = [9, 8, 7, 6, 5, 5]
    interpretability = [6, 5, 7, 6, 8, 7]
    training_time = [7, 8, 6, 5, 3, 4]
    
    x = np.arange(len(models))
    width = 0.2
    
    bars1 = ax.bar(x - 1.5*width, complexity, width, label='Model Complexity', color='#BC4749', alpha=0.8)
    bars2 = ax.bar(x - 0.5*width, performance, width, label='Performance', color='#6A994E', alpha=0.8)
    bars3 = ax.bar(x + 0.5*width, interpretability, width, label='Interpretability', color='#2E86AB', alpha=0.8)
    bars4 = ax.bar(x + 1.5*width, training_time, width, label='Training Time', color='#6A4C93', alpha=0.8)
    
    ax.set_xlabel('Models', fontsize=12, fontweight='bold')
    ax.set_ylabel('Score (1-10)', fontsize=12, fontweight='bold')
    ax.set_title('Anomaly Detection Models Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=10)
    ax.legend(fontsize=10, loc='upper right')
    ax.set_ylim(0, 10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig('model_comparison.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("✓ Generated: model_comparison.png")
    plt.close()


def create_feature_diagram():
    """Create battery features diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(5, 7.5, 'Battery Time Series Features', 
            ha='center', fontsize=16, fontweight='bold')
    
    # Center: Battery
    battery_circle = Circle((5, 4.5), 1.2, edgecolor='#BC4749', 
                           facecolor='#FFD6BA', linewidth=3)
    ax.add_patch(battery_circle)
    ax.text(5, 4.5, 'Battery\nSystem', ha='center', va='center', 
            fontsize=11, fontweight='bold')
    
    # Features around the battery
    features = [
        ('Voltage', 2, 6.5, '#2E86AB'),
        ('Current', 8, 6.5, '#6A994E'),
        ('SOC\n(State of Charge)', 1.5, 4.5, '#BC4749'),
        ('Temperature', 8.5, 4.5, '#FF6B6B'),
        ('Max Cell Voltage', 2, 2.5, '#6A4C93'),
        ('Min Cell Voltage', 8, 2.5, '#FFB627')
    ]
    
    for feature, x, y, color in features:
        feature_box = FancyBboxPatch((x - 0.7, y - 0.35), 1.4, 0.7,
                                     boxstyle="round,pad=0.1",
                                     edgecolor=color, facecolor=color, 
                                     linewidth=2, alpha=0.3)
        ax.add_patch(feature_box)
        ax.text(x, y, feature, ha='center', va='center', fontsize=9, fontweight='bold')
        
        # Arrow to battery
        arrow = FancyArrowPatch((x, y), (5, 4.5),
                               arrowstyle='<->', mutation_scale=15, linewidth=2, 
                               color=color, alpha=0.6)
        ax.add_patch(arrow)
    
    # Metadata box
    metadata_box = FancyBboxPatch((2, 0.5), 6, 1.2,
                                  boxstyle="round,pad=0.1",
                                  edgecolor='#386641', facecolor='#A7C957', 
                                  linewidth=2, alpha=0.5)
    ax.add_patch(metadata_box)
    ax.text(5, 1.4, 'Metadata', ha='center', fontsize=11, fontweight='bold')
    ax.text(5, 0.85, 'Car Number • Charge Segment • Mileage • Fault Label', 
            ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('battery_features.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("✓ Generated: battery_features.png")
    plt.close()


def create_workflow_diagram():
    """Create complete workflow from data to results"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.5, 'Complete Research Workflow', 
            ha='center', fontsize=16, fontweight='bold')
    
    y_positions = [8, 6.5, 5, 3.5, 2, 0.5]
    
    # Step 1: Data Collection
    step1 = FancyBboxPatch((1, y_positions[0]), 12, 1,
                           boxstyle="round,pad=0.1",
                           edgecolor='#2E86AB', facecolor='#A7C7E7', linewidth=2)
    ax.add_patch(step1)
    ax.text(1.5, y_positions[0] + 0.7, '1', ha='center', fontsize=14, fontweight='bold')
    ax.text(7, y_positions[0] + 0.7, 'Data Collection & Preparation', ha='center', 
            fontsize=12, fontweight='bold')
    ax.text(7, y_positions[0] + 0.25, 'Download datasets → Generate five-fold splits → ' +
                                       'Create brand-specific configurations',
            ha='center', fontsize=9)
    
    # Step 2: Model Selection
    step2 = FancyBboxPatch((1, y_positions[1]), 12, 1,
                           boxstyle="round,pad=0.1",
                           edgecolor='#6A994E', facecolor='#B7E4C7', linewidth=2)
    ax.add_patch(step2)
    ax.text(1.5, y_positions[1] + 0.7, '2', ha='center', fontsize=14, fontweight='bold')
    ax.text(7, y_positions[1] + 0.7, 'Model Configuration', ha='center', 
            fontsize=12, fontweight='bold')
    ax.text(7, y_positions[1] + 0.25, 'Select model(s) → Configure hyperparameters → ' +
                                       'Set brand and fold number',
            ha='center', fontsize=9)
    
    # Step 3: Training
    step3 = FancyBboxPatch((1, y_positions[2]), 12, 1,
                           boxstyle="round,pad=0.1",
                           edgecolor='#BC4749', facecolor='#F2CC8F', linewidth=2)
    ax.add_patch(step3)
    ax.text(1.5, y_positions[2] + 0.7, '3', ha='center', fontsize=14, fontweight='bold')
    ax.text(7, y_positions[2] + 0.7, 'Training Phase', ha='center', 
            fontsize=12, fontweight='bold')
    ax.text(7, y_positions[2] + 0.25, 'Train models on in-distribution data → ' +
                                       'Save checkpoints → Log training metrics',
            ha='center', fontsize=9)
    
    # Step 4: Evaluation
    step4 = FancyBboxPatch((1, y_positions[3]), 12, 1,
                           boxstyle="round,pad=0.1",
                           edgecolor='#6A4C93', facecolor='#C9ADA7', linewidth=2)
    ax.add_patch(step4)
    ax.text(1.5, y_positions[3] + 0.7, '4', ha='center', fontsize=14, fontweight='bold')
    ax.text(7, y_positions[3] + 0.7, 'Testing & Feature Extraction', ha='center', 
            fontsize=12, fontweight='bold')
    ax.text(7, y_positions[3] + 0.25, 'Test on out-of-distribution data → ' +
                                       'Extract features → Calculate reconstruction errors',
            ha='center', fontsize=9)
    
    # Step 5: Analysis
    step5 = FancyBboxPatch((1, y_positions[4]), 12, 1,
                           boxstyle="round,pad=0.1",
                           edgecolor='#FF6B6B', facecolor='#FFE5EC', linewidth=2)
    ax.add_patch(step5)
    ax.text(1.5, y_positions[4] + 0.7, '5', ha='center', fontsize=14, fontweight='bold')
    ax.text(7, y_positions[4] + 0.7, 'Anomaly Detection & Scoring', ha='center', 
            fontsize=12, fontweight='bold')
    ax.text(7, y_positions[4] + 0.25, 'Calculate AUROC → Threshold analysis → ' +
                                       'Generate ROC curves',
            ha='center', fontsize=9)
    
    # Step 6: Results
    step6 = FancyBboxPatch((1, y_positions[5]), 12, 1,
                           boxstyle="round,pad=0.1",
                           edgecolor='#386641', facecolor='#A7C957', linewidth=2)
    ax.add_patch(step6)
    ax.text(1.5, y_positions[5] + 0.7, '6', ha='center', fontsize=14, fontweight='bold')
    ax.text(7, y_positions[5] + 0.7, 'Visualization & Comparison', ha='center', 
            fontsize=12, fontweight='bold')
    ax.text(7, y_positions[5] + 0.25, 'Jupyter notebooks → Performance metrics → ' +
                                       'Cross-model comparison',
            ha='center', fontsize=9)
    
    # Arrows between steps
    for i in range(5):
        arrow = FancyArrowPatch((7, y_positions[i]), (7, y_positions[i+1] + 1),
                               arrowstyle='->', mutation_scale=25, linewidth=3, color='black')
        ax.add_patch(arrow)
    
    plt.tight_layout()
    plt.savefig('workflow_complete.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("✓ Generated: workflow_complete.png")
    plt.close()


if __name__ == '__main__':
    print("Generating architecture diagrams...")
    print("=" * 60)
    
    create_overall_architecture()
    create_dyad_architecture()
    create_data_flow_diagram()
    create_model_comparison_chart()
    create_feature_diagram()
    create_workflow_diagram()
    
    print("=" * 60)
    print("✓ All diagrams generated successfully!")
    print("\nGenerated files:")
    print("  - architecture_overall.png")
    print("  - architecture_dyad.png")
    print("  - architecture_dataflow.png")
    print("  - model_comparison.png")
    print("  - battery_features.png")
    print("  - workflow_complete.png")
