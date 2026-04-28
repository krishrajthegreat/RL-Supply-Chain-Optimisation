"""Quick smoke test — 5 HAPPO iterations to verify everything works."""
import sys, logging, time
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("smoke")

import torch
from nexus.environment.supply_chain_env import SupplyChainEnv
from nexus.training.happo_trainer import HAPPOTrainer

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info("Device: %s", device)

if device == "cuda":
    name = torch.cuda.get_device_name(0)
    logger.info("GPU: %s", name)

env = SupplyChainEnv(max_steps=20, seed=42, disruption_probability=0.02)
env.reset()
logger.info("Env created: %d agents", len(env.possible_agents))

trainer = HAPPOTrainer(
    env=env,
    rollout_steps=64,
    batch_size=32,
    update_epochs=2,
    device=device,
    checkpoint_dir="checkpoints_smoke",
)
logger.info("Trainer created")

if device == "cuda":
    alloc = torch.cuda.memory_allocated() / 1e6
    logger.info("VRAM allocated after init: %.1f MB", alloc)

t0 = time.time()
metrics = trainer.train(num_iterations=5, log_interval=1, save_interval=5)
dt = time.time() - t0

logger.info("=" * 50)
logger.info("SMOKE TEST PASSED — 5 iterations in %.1f seconds", dt)
logger.info("Final mean episode reward: %.4f", metrics[-1]["mean_ep_reward"])
logger.info("Total steps collected: %d", trainer.total_steps)

if device == "cuda":
    peak = torch.cuda.max_memory_allocated() / 1e6
    logger.info("Peak VRAM usage: %.1f MB", peak)

logger.info("=" * 50)
