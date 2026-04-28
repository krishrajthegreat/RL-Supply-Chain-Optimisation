import torch
print(torch.cuda.is_available())  # Returns True if CUDA is ready
print(torch.version.cuda)         # Shows version PyTorch was built with
