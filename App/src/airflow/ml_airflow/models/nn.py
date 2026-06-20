import torch
import torch.nn as nn

class EnsembleNN(nn.Module):
    """Ensemble NN (Meta-Learner) that takes 2 predictions (Charging and Driving) as input"""
    def __init__(self):
        super(EnsembleNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 32),   
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1)
        )

    def forward(self, p_chg, p_drv):
        # Concatenate 2 tensors into shape (batch_size, 2)
        x = torch.cat([p_chg, p_drv], dim=1) 
        return self.net(x)